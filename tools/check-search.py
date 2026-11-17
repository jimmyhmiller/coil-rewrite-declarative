#!/usr/bin/env python3
"""Exercise the search algebra independently of the namespace adapter."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / 'build/schema-seed'
for limit, follow_first in [(4, False), (4, True), (0, True)]:
    alternatives = ['(prefer direct)', '(follow edges)']
    if follow_first:
        alternatives.reverse()
    source = f'(module fixture.policy) (search pick (depth {limit}) (guard visible) {" ".join(alternatives)})'
    generated = subprocess.check_output([str(SEED)], input=source.encode())
    with tempfile.TemporaryDirectory(prefix='rewrite-search-') as directory:
        work = Path(directory)
        (work / 'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
        shutil.copyfile(ROOT / 'seed/search_runtime.coil', work / 'runtime.coil')
        (work / 'policy.coil').write_bytes(generated)
        client = (ROOT / 'tests/search.coil.in').read_text()
        client = client.replace('FOLLOW_FIRST', str(follow_first).lower()).replace('EXPECTED', str(2 if follow_first else 1)).replace('LIMIT', str(limit))
        (work / 'main.coil').write_text(client)
        for flags in [[], ['--debug-checks'], ['--release']]:
            subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)

for body, diagnostic in [
    ('(search pick (prefer x))', 'search needs a depth bound'),
    ('(search pick (depth -1) (prefer x))', 'search depth must be nonnegative'),
    ('(search pick (depth 1) (depth 2) (prefer x))', 'duplicate search depth'),
    ('(search pick (depth 1) (guard x))', 'search needs an alternative'),
    ('(search pick (depth 1) (prefer x) (guard y))', 'search guards must precede alternatives'),
    ('(search pick (depth 1) (prefer x) (prefer x))', 'duplicate search handler'),
    ('(search pick (depth 1) (follow x) (follow x))', 'duplicate search handler'),
    ('(search pick (depth 1) (guard x) (guard x) (prefer y))', 'duplicate search handler'),
]:
    result = subprocess.run([str(SEED)], input=body.encode(), capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic.encode() in result.stderr, result
print('Independent generated search policies and invalid declarations passed')
