#!/usr/bin/env python3
"""Verify the retained backend's provenance, regeneration, and direct CIR behavior."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'vendor/coil'
manifest = json.loads((VENDOR / 'snapshot.json').read_text())
for path, expected in manifest['sha256'].items():
    if hashlib.sha256((VENDOR / path).read_bytes()).hexdigest() != expected:
        raise SystemExit(f'backend snapshot modified: {path}')
actual = {str(p.relative_to(VENDOR)) for p in VENDOR.rglob('*') if p.is_file()}
if actual != set(manifest['sha256']) | {'snapshot.json'}:
    raise SystemExit('backend snapshot has unexpected files')
compiler = str(Path(shutil.which('coil')).resolve())
commands = [
    ([sys.executable, '-B', str(VENDOR / 'scripts/compiler/gen-declarative.py'), '--check', '--compiler', compiler], ROOT),
    ([compiler, 'run'], ROOT / 'tests/backend'),
]
report = {'revision': manifest['revision'], 'compiler_sha256': hashlib.sha256(Path(compiler).read_bytes()).hexdigest(), 'checks': []}
for command, cwd in commands:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    report['checks'].append({'command': command, 'cwd': str(cwd), 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    (ROOT / 'evidence/backend-baseline.json').write_text(json.dumps(report, indent=2) + '\n')
    print(result.stdout, end='')
    print(result.stderr, end='', file=sys.stderr)
    if result.returncode:
        raise SystemExit(result.returncode)
print('Retained backend: snapshot, regeneration and direct CIR execution passed')
