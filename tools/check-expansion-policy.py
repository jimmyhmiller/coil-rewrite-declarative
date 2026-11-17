#!/usr/bin/env python3
"""Replay reference changing-round traces through the declared before-expand guard.

This isolates round accounting from request discovery, normalization and code execution.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
reference_path = ROOT/'evidence/expansion-boundaries.json'
reference = json.loads(reference_path.read_text())
assert reference['compiler_unchanged'] and reference['initial_comparison_probe']['passed']
assert all(case['passed'] for case in reference['cases'])
names = {'before-stable-16', 'before-change-17', 'staged-stable-64', 'staged-change-65',
         'early-stage-stable-16', 'early-stage-plain-change-17', 'late-stage-stable-17', 'late-stage-plain-change-18'}
cases = [case for case in reference['cases'] if case['name'] in names]
assert {case['name'] for case in cases} == names
modes = {'false': 0, 'true': 1, '(< n 16)': 2, '(= n 16)': 3}
checks = []
for case in cases:
    assert case['phase'] == 'before' and case['observed_calls'] == list(range(len(case['observed_calls'])))
    limit = 0 if case['actual_exit'] == 0 else (64 if '64 rounds' in case['required_diagnostic'] else 16)
    checks.append(f"(check {case['target']} {modes[case['progress_predicate']]} {len(case['observed_calls'])} {case['observed_calls'][-1]} {limit})")
client = (ROOT/'tests/expansion-policy.coil.in').read_text()
client += '(defn main [] (-> i64) (let [ok (and (check 0 0 1 0 0) ' + ' '.join(checks) + ')] (println "before-expand guard: shared counter and equality precedence: {}" ok) (if ok 0 1)))\n'
results = []
with tempfile.TemporaryDirectory(prefix='rewrite-expansion-policy-') as directory:
    work = Path(directory)
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    shutil.copyfile(ROOT/'seed/generated/before_protocol.coil', work/'protocol.coil')
    (work/'main.coil').write_text(client)
    for flags in [[], ['--debug-checks'], ['--release']]:
        result = subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, capture_output=True, text=True)
        print(result.stdout, end='')
        assert result.returncode == 0 and 'shared counter and equality precedence: true' in result.stdout, result
        results.append(dict(flags=flags, exit=result.returncode, stdout=result.stdout, stderr=result.stderr))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
evidence = dict(scope='Before-expand guard accounting only; replays eight captured reference changing-round traces. '
                      'Does not execute reference source through the rewritten frontend or model initial form normalization.',
                reference_evidence_sha256=sha(reference_path), model_sha256=sha(ROOT/'compiler/expansion/before_expand.protocol'),
                generated_sha256=sha(ROOT/'seed/generated/before_protocol.coil'),
                fixture_sha256=sha(ROOT/'tests/expansion-policy.coil.in'), replay_script_sha256=sha(Path(__file__)),
                host_compiler_sha256=sha(Path(shutil.which('coil')).resolve()),
                reference_cases=sorted(names), generated_client_sha256=hashlib.sha256(client.encode()).hexdigest(),
                results=results)
(ROOT/'evidence/before-policy-replay.json').write_text(json.dumps(evidence, indent=2)+'\n')
