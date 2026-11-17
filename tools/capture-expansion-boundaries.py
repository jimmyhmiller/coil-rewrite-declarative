#!/usr/bin/env python3
"""Measure reference expansion boundary calls, including mixed stage progress.

Runs the installed reference compiler only. Does not assert rewrite parity.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT/'tests/reference/expansion-boundary.coil.in'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--compiler', default='coil')
    parser.add_argument('--output', type=Path, default=ROOT/'evidence/expansion-boundaries.json')
    args = parser.parse_args()
    reference = args.reference.resolve()
    compiler = Path(shutil.which(args.compiler) or args.compiler).resolve(strict=True)
    identity = compiler.read_bytes()
    version = subprocess.check_output([str(compiler), '--version'], text=True).strip()
    match = re.search(r'commit ([0-9a-f]+)', version)
    if not match:
        raise RuntimeError('compiler does not identify its source revision')
    source_revision = subprocess.check_output(['git', 'rev-parse', match[1]], cwd=reference, text=True).strip()
    source = subprocess.check_output(['git', 'show', f'{source_revision}:src/compiler/frontend/expander.coil'], cwd=reference)
    # The guard source belongs to the reported compiler revision, not necessarily HEAD.
    for required in [b'(>= (load iters) 16)', b'(>= (load iters) 64)', b'(forms-equal (load cur) (load round))']:
        if required not in source:
            raise RuntimeError(f'reference guard source needs review: {required!r}')
    evidence = dict(scope='Executed reference boundary observations only; not rewritten expansion parity.',
                    compiler=str(compiler), compiler_version=version, compiler_sha256=digest(identity),
                    compiler_reported_source_revision=source_revision, expander_source_sha256=digest(source),
                    reference_checkout_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=reference, text=True).strip(),
                    reference_checkout_status=subprocess.check_output(['git', 'status', '--porcelain'], cwd=reference, text=True),
                    template_sha256=digest(TEMPLATE.read_bytes()), capture_script_sha256=digest(Path(__file__).read_bytes()), cases=[],
                    limitations='Compiler-reported revision and object hashes identify evidence, not a hermetic rebuild. '
                    'OwnModules probes use scalar global rewrites and fresh Code-to-Code stage identities; '
                    'they do not exercise arbitrary request routing, macro towers, or semantic-model partiality.')
    env = os.environ.copy()
    for key in ('COIL_TRACE', 'COIL_LIBRARY_STATE', 'COIL_META_INTERP', 'COIL_MTRACE', 'COIL_TRACE_MACROS', 'COIL_TRACE_PHASES', 'COIL_MACRO_EXPANSION_LIMIT'):
        env.pop(key, None)
    # name, phase, target, progress predicate, stage-only, expected calls, expected exit, runtime count, diagnostic
    cases = [
        ('before-stable-0', 'before', 0, 'false', False, [0, 0], 0, 0, None),
        ('before-stable-16', 'before', 16, 'false', False, 17, 0, 16, None),
        ('before-change-17', 'before', 17, 'false', False, 17, 1, None, 'before-expand transform: did not reach a fixpoint after 16 rounds'),
        ('staged-stable-64', 'before', 64, 'true', False, 65, 0, 64, None),
        ('staged-change-65', 'before', 65, 'true', False, 65, 1, None, 'before-expand staging: did not reach a fixpoint after 64 rounds'),
        ('early-stage-stable-16', 'before', 16, '(< n 16)', False, 17, 0, 16, None),
        ('early-stage-plain-change-17', 'before', 17, '(< n 16)', False, 17, 1, None, 'before-expand transform: did not reach a fixpoint after 16 rounds'),
        ('late-stage-stable-17', 'before', 17, '(= n 16)', False, 18, 0, 17, None),
        ('late-stage-plain-change-18', 'before', 18, '(= n 16)', False, 18, 1, None, 'before-expand transform: did not reach a fixpoint after 16 rounds'),
        ('stage-only-stable', 'before', 0, 'false', True, [0, 0], 0, 0, None),
        ('semantic-stable-16', 'semantic', 16, 'false', False, 17, 0, 16, None),
        ('semantic-change-17', 'semantic', 17, 'false', False, 17, 1, None, 'transform: did not reach a fixpoint after 16 rounds'),
        ('after-single-pass', 'after', 16, 'false', False, 1, 0, 1, None),
    ]
    log_root = ROOT/'build/expansion-boundaries'
    log_root.mkdir(parents=True, exist_ok=True)
    for name, phase, target, progress, stage_only, calls, exit_code, count, diagnostic in cases:
        work = log_root/name
        work.mkdir(exist_ok=True)
        text = TEMPLATE.read_text().replace('@@TARGET@@', str(target)).replace('@@PROGRESS@@', progress)
        text = text.replace('@@STAGE_ONLY@@', str(stage_only).lower()).replace('@@PHASE@@',
            {'before': ':phase (phase/BeforeExpand)', 'after': ':phase (phase/AfterExpand)', 'semantic': ''}[phase])
        if '@@' in text:
            raise RuntimeError('unsubstituted fixture parameter')
        (work/'transform.coil').write_text(text)
        (work/'main.coil').write_text('(module boundary.main)\n(import "boundary.transform")\n(def boundary-count 0)\n(defn main [] (-> i64) (+ boundary-count 42))\n')
        (work/'Coil.toml').write_text('[package]\nname="boundary"\nentry="main.coil"\nsource-roots=["."]\n')
        inputs = {p.name: digest(p.read_bytes()) for p in (work/'transform.coil', work/'main.coil', work/'Coil.toml')}
        binary = work/'program'
        binary.unlink(missing_ok=True)
        argv = [str(compiler), 'build', '.', '-o', str(binary)]
        result = subprocess.run(argv, cwd=work, env=env, capture_output=True, text=True)
        observed = [int(n) for n in re.findall(r'^boundary-call (\d+)$', result.stdout, re.MULTILINE)]
        expected_calls = list(range(calls)) if isinstance(calls, int) else calls
        module_equal = re.findall(r'^boundary-module-equal (true|false)$', result.stdout, re.MULTILINE)
        expected_equal = ['false' if stage_only or n < target else 'true' for n in expected_calls]
        passed = result.returncode == exit_code and observed == expected_calls and module_equal == expected_equal
        if diagnostic:
            passed &= diagnostic in result.stdout + result.stderr
        row = dict(name=name, phase=phase, target=target, progress_predicate=progress, stage_only=stage_only,
                   command=argv, cwd=str(work), inputs=inputs, expected_exit=exit_code, actual_exit=result.returncode,
                   expected_calls=expected_calls, observed_calls=observed, expected_module_equality=expected_equal,
                   observed_module_equality=module_equal, required_diagnostic=diagnostic)
        for stream in ('stdout', 'stderr'):
            raw = getattr(result, stream)
            path = work/f'compile.{stream}.txt'
            path.write_text(raw)
            row[stream+'_log'] = str(path.relative_to(ROOT))
            row[stream+'_sha256'] = digest(raw.encode())
            row[stream+'_excerpt'] = raw[:2048]
        if exit_code == 0:
            if not binary.is_file():
                passed = False
            else:
                run = subprocess.run([str(binary)], capture_output=True, text=True)
                row['runtime'] = dict(expected_exit=count + 42, actual_exit=run.returncode,
                                      stdout=run.stdout, stderr=run.stderr, binary_sha256=digest(binary.read_bytes()))
                passed &= run.returncode == count + 42 and not run.stdout and not run.stderr
        else:
            row['artifact_present'] = binary.exists()
            passed &= not binary.exists()
        after = {p.name: digest(p.read_bytes()) for p in (work/'transform.coil', work/'main.coil', work/'Coil.toml')}
        passed &= after == inputs
        row['passed'] = bool(passed)
        evidence['cases'].append(row)
        print(f'{name}: {"PASS" if passed else "FAIL"} ({len(observed)} calls)', flush=True)
    work = log_root/'before-stable-0'
    traced_binary = work/'traced-program'
    traced_binary.unlink(missing_ok=True)
    trace = subprocess.run([str(compiler), 'build', '.', '-o', str(traced_binary)],
                           cwd=work, env=env | {'COIL_MTRACE': 'rounds'}, capture_output=True, text=True)
    changed = re.findall(r'leave boundary.transform.transform  changed=(yes|no)', trace.stderr)
    trace_calls = [int(n) for n in re.findall(r'^boundary-call (\d+)$', trace.stdout, re.MULTILINE)]
    trace_equal = re.findall(r'^boundary-module-equal (true|false)$', trace.stdout, re.MULTILINE)
    trace_passed = trace.returncode == 0 and changed == ['yes', 'no'] and trace_calls == [0, 0] and trace_equal == ['true', 'true']
    trace_runtime = None
    if trace.returncode == 0 and traced_binary.is_file():
        executed = subprocess.run([str(traced_binary)], capture_output=True, text=True)
        trace_runtime = dict(expected_exit=42, actual_exit=executed.returncode,
                             stdout=executed.stdout, stderr=executed.stderr)
        trace_passed &= executed.returncode == 42 and not executed.stdout and not executed.stderr
    else:
        trace_passed = False
    trace_record = dict(environment_overrides={'COIL_MTRACE': 'rounds'}, actual_exit=trace.returncode,
                        transform_changed=changed, observed_calls=trace_calls, module_equality=trace_equal, runtime=trace_runtime, passed=trace_passed,
                        interpretation='The module projection compares equal on both calls, but the reference '
                        'whole-form comparison reports a changed first round. Do not equate these predicates '
                        'or interpret mtrace round 0 as an iteration count; it is the transformer index.')
    for stream in ('stdout', 'stderr'):
        raw = getattr(trace, stream)
        path = work/f'trace.{stream}.txt'
        path.write_text(raw)
        trace_record[stream] = raw
        trace_record[stream+'_log'] = str(path.relative_to(ROOT))
        trace_record[stream+'_sha256'] = digest(raw.encode())
    evidence['initial_comparison_probe'] = trace_record
    evidence['compiler_unchanged'] = digest(compiler.read_bytes()) == evidence['compiler_sha256']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2)+'\n')
    if not trace_passed or not evidence['compiler_unchanged'] or not all(c['passed'] for c in evidence['cases']):
        raise SystemExit('Expansion boundary evidence failed; inspect JSON and raw logs')


if __name__ == '__main__':
    main()
