#!/usr/bin/env python3
"""Hash and classify the rewrite's current source, including its retained backend."""
import collections
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def category(path):
    if path.startswith(('seed/', 'runtime/')):
        return 'authored-seed-and-runtime'
    if path.startswith('tests/'):
        return 'rewrite-tests-and-fixtures'
    if path.startswith('tools/'):
        return 'rewrite-build-and-validation-tools'
    if path.startswith('vendor/coil/'):
        local = path.removeprefix('vendor/coil/')
        if '/generated/' in local and path.endswith('.coil'):
            return 'retained-generated'
        if local.startswith('src/declarative/tests/'):
            return 'retained-tests'
        if path.endswith(('.md', '.txt', '.json', '.toml')) or Path(path).name in ('LICENSE', 'NOTICE'):
            return 'retained-metadata'
        return 'retained-authored-machinery-and-specifications'
    return None


paths = subprocess.check_output(
    ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT
).decode().split('\0')
deleted = set(subprocess.check_output(
    ['git', 'ls-files', '-z', '--deleted'], cwd=ROOT
).decode().split('\0'))
files = []
totals = collections.defaultdict(lambda: dict(files=0, bytes=0, physical_lines=0))
for path in sorted(set(paths) - deleted - {''}):
    group = category(path)
    if group is None:
        continue
    data = (ROOT/path).read_bytes()
    row = dict(path=path, category=group, sha256=hashlib.sha256(data).hexdigest(),
               bytes=len(data), physical_lines=len(data.splitlines()))
    files.append(row)
    totals[group]['files'] += 1
    totals[group]['bytes'] += row['bytes']
    totals[group]['physical_lines'] += row['physical_lines']
result = dict(
    scope='Working-tree seed, runtime, tests, tools and complete pinned backend; per-file hashes identify inputs.',
    caveats='Physical lines include comments and blanks. Templates count as authored source. '
            'This is not a code-only LOC count or a complete toolchain reduction claim. '
            'Host Coil/stdlib bootstrap dependencies are not vendored or included. '
            'Generated seed output is ephemeral and not included; retained generated backend is separate.',
    totals=dict(sorted(totals.items())), files=files)
output = ROOT/'evidence/rewrite-source-inventory.json'
output.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result['totals'], indent=2))
