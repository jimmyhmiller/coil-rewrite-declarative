#!/usr/bin/env python3
"""Capture selected existing Coil expansion/reader contracts; not a rewrite parity gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()



def retain_logs(evidence, directory):
    """Keep full raw output locally and hash it in the reviewable JSON report."""
    directory.mkdir(parents=True, exist_ok=True)
    for i, case in enumerate(evidence['cases']):
        for stream in ('stdout', 'stderr'):
            if stream not in case:
                continue
            raw = case[stream]
            path = directory/f'{i:02d}.{stream}.txt'
            path.write_text(raw)
            case[stream + '_log'] = str(path.resolve())
            case[stream + '_sha256'] = sha(path)
            case[stream + '_bytes'] = path.stat().st_size
            case[stream + '_truncated'] = len(raw) > 2048
            if len(raw) > 2048:
                case[stream] = raw[:1024] + '\n[excerpt omitted; see raw log]\n' + raw[-1024:]
        case['required_output_observed'] = [text for text in case.get('required_output', [])
            if any(text in (directory/f'{i:02d}.{stream}.txt').read_text()
                   for stream in ('stdout', 'stderr'))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--compiler', required=True)
    parser.add_argument('--output', type=Path, default=ROOT/'evidence/expansion-reference.json')
    args = parser.parse_args()
    reference = args.reference.resolve()
    compiler = Path(shutil.which(args.compiler) or args.compiler).resolve(strict=True)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=reference, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=reference, text=True)
    inputs = sorted(set(
        list((reference/'tests/meta').rglob('*')) +
        list((reference/'tests/readers').rglob('*')) +
        [reference/'Coil.toml', reference/'src/compiler/frontend/expander.coil',
         reference/'src/compiler/frontend/loader.coil', reference/'src/compiler/pipeline.coil',
         reference/'src/stdlib/phase.coil', reference/'src/compiler/meta/metastate.coil',
         reference/'docs/design/STAGED_METACOMPILATION.md']))
    before = {str(p.relative_to(reference)): sha(p) for p in inputs if p.is_file()}
    evidence = dict(scope='Selected reference behaviors only. No rewritten compiler executes these cases.',
                    reference_revision=revision, reference_dirty=dirty,
                    compiler=str(compiler), compiler_sha256=sha(compiler),
                    compiler_version=subprocess.check_output([str(compiler), '--version'], text=True).strip(),
                    inputs=before, cases=[])
    env = os.environ.copy()
    # Do not inherit optional trace/interpreter/library-state switches into the baseline.
    for key in ('COIL_TRACE', 'COIL_LIBRARY_STATE', 'COIL_META_INTERP'):
        env.pop(key, None)

    def run(name, argv, *, cwd=reference, exit_code=0, stdout=None, contains=(), extra_env=None):
        started = time.monotonic()
        result = subprocess.run([str(x) for x in argv], cwd=cwd,
                                env=env | (extra_env or {}), capture_output=True, text=True)
        passed = result.returncode == exit_code
        if stdout is not None:
            passed = passed and result.stdout == stdout
        passed = passed and all(text in result.stdout + result.stderr for text in contains)
        row = dict(name=name, command=[str(x) for x in argv], cwd=str(cwd),
                   environment_overrides=extra_env or {}, expected_exit=exit_code,
                   expected_stdout=stdout, required_output=list(contains),
                   actual_exit=result.returncode, stdout=result.stdout, stderr=result.stderr,
                   elapsed_seconds=round(time.monotonic()-started, 6), passed=passed)
        evidence['cases'].append(row)
        print(f'{name}: {"PASS" if passed else "FAIL"}', flush=True)
        return result

    with tempfile.TemporaryDirectory(prefix='coil-expansion-reference-') as tmp:
        binary = Path(tmp)/'staged-chain'
        build = run('cumulative stages and language resumption: build',
                    [compiler, 'build', 'tests/meta/staged_chain_test.coil', '-o', binary])
        if build.returncode == 0 and binary.is_file():
            run('cumulative stages and language resumption: execution', [binary], exit_code=42, stdout='')
            nm = run('staged binary symbol inventory', ['nm', binary])
            strings = run('staged binary strings inventory', ['strings', '-a', binary])
            inventory = nm.stdout + strings.stdout
            forbidden = ['chain-a-entry', 'chain-b-entry', 'chain-second']
            evidence['cases'].append(dict(
                name='staged helpers absent from runtime binary',
                required_symbol='_main', forbidden_strings=forbidden,
                passed=nm.returncode == 0 and strings.returncode == 0 and '_main' in nm.stdout
                       and all(name not in inventory for name in forbidden)))
            evidence['staged_binary_sha256'] = sha(binary)
        else:
            evidence['cases'].append(dict(name='staged runtime artifact exists', passed=False))
        run('macro introduces definitions needed by later macro',
            [compiler, 'run', 'tests/meta/early_macro.coil'], stdout='9\n')
        run('macro dependency behavior without library state',
            [compiler, 'run', 'tests/meta/early_macro.coil'], stdout='9\n',
            extra_env={'COIL_LIBRARY_STATE': '0'})
        run('before-expand introduction of definition and import',
            [compiler, 'run', 'tests/meta/transforms_test.coil'], exit_code=42, stdout='')
        run('project readers and imported guest modules', [compiler, 'run'],
            cwd=reference/'tests/readers/json_project', exit_code=48,
            contains=['coil-trace count reader.unit.released 1'], extra_env={'COIL_TRACE': '1'})
        run('guest readers execute for host during wasm check',
            [compiler, 'check', '--target', 'wasm32-unknown-unknown'],
            cwd=reference/'tests/readers/json_project')
        run('reflective reader retains compilation context', [compiler, 'run'],
            cwd=reference/'tests/readers/reflect_project', exit_code=7,
            contains=['coil-trace count reader.unit.kept 1'], extra_env={'COIL_TRACE': '1'})
    evidence['inputs_unchanged'] = all((reference/p).is_file() and sha(reference/p) == digest
                                       for p, digest in before.items())
    evidence['passed'] = evidence['inputs_unchanged'] and all(case['passed'] for case in evidence['cases'])
    retain_logs(evidence, ROOT/'build/expansion-reference')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2)+'\n')
    print(f'Evidence: {args.output}', flush=True)
    return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
