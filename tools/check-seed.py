#!/usr/bin/env python3
"""Compile generated schema output and exercise references across table growth."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
(ROOT / 'build').mkdir(exist_ok=True)
subprocess.run(['coil', 'build', 'seed/main.coil', '-o', 'build/schema-seed'], cwd=ROOT, check=True)
source = (ROOT / 'tests/schemas/expressions.schema').read_bytes()
generated = subprocess.check_output([str(ROOT / 'build/schema-seed')], input=source)
assert generated == subprocess.check_output([str(ROOT / 'build/schema-seed')], input=source)
with tempfile.TemporaryDirectory(prefix='rewrite-schema-') as directory:
    work = Path(directory)
    (work / 'Coil.toml').write_text('[package]\nname = "fixture"\nentry = "main.coil"\nsource-roots = ["."]\n')
    (work / 'generated.coil').write_bytes(generated)
    client = (ROOT / 'tests/generated.coil.in').read_text()
    (work / 'main.coil').write_text(client)
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
    # A wrong nominal reference must fail before native code is produced.
    (work / 'main.coil').write_text(client.replace(':f0 left :f1 right', ':f0 (N1Id :index 0) :f1 right'))
    rejected = subprocess.run(['coil', 'check', 'main.coil'], cwd=work, capture_output=True, text=True)
    assert rejected.returncode != 0, 'cross-node ID was accepted'
    assert 'N0Id' in rejected.stdout + rejected.stderr and 'N1Id' in rejected.stdout + rejected.stderr, rejected
print('Generated schemas: deterministic; runtime, growth, bounds and nominal-reference checks passed')

# A second representation exercises recursive fields and the other scalar layouts.
recursive = b'(node Link (next Link) (label Text) (live Bool))'
with tempfile.TemporaryDirectory(prefix='rewrite-recursive-') as directory:
    work = Path(directory)
    (work / 'generated.coil').write_bytes(subprocess.check_output([str(ROOT / 'build/schema-seed')], input=recursive))
    subprocess.run(['coil', 'check', str(work / 'generated.coil')], check=True)
invalid = subprocess.run([str(ROOT / 'build/schema-seed')], input=b'(node X (x Missing))', capture_output=True)
assert invalid.returncode != 0 and not invalid.stdout and b'unknown field type' in invalid.stderr
print('Recursive schema and generator error-channel checks passed')

with tempfile.TemporaryDirectory(prefix='rewrite-variants-') as directory:
    work = Path(directory)
    (work / 'Coil.toml').write_text('[package]\nname = "fixture"\nentry = "main.coil"\nsource-roots = ["."]\n')
    (work / 'generated.coil').write_bytes(subprocess.check_output(
        [str(ROOT / 'build/schema-seed')], input=(ROOT / 'tests/schemas/recursive.schema').read_bytes()))
    (work / 'main.coil').write_text((ROOT / 'tests/variants.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
for source, diagnostic in [
    (b'(sum Expr)', b'at least one variant'),
    (b'(sum Expr (A) (A))', b'duplicate variant'),
    (b'(sum Expr (A (x Unknown)))', b'unknown field type'),
    (b'(sum Expr (A (x Int) (x Bool)))', b'duplicate field'),
    (b'(sum Expr 12)', b'expected named variant'),
]:
    result = subprocess.run([str(ROOT / 'build/schema-seed')], input=source, capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Recursive variants: execution, growth, and invalid-declaration checks passed')

with tempfile.TemporaryDirectory(prefix='rewrite-judgment-') as directory:
    work = Path(directory)
    (work / 'Coil.toml').write_text('[package]\nname = "fixture"\nentry = "main.coil"\nsource-roots = ["."]\n')
    typing = (ROOT / 'tests/schemas/typing.schema').read_bytes()
    output = subprocess.check_output([str(ROOT / 'build/schema-seed')], input=typing)
    (work / 'generated.coil').write_bytes(output)
    (work / 'main.coil').write_text((ROOT / 'tests/judgment.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
    for invalid, diagnostic in [
        (typing.replace(b'(Boolean Bool)', b''), b'exactly one rule'),
        (typing.replace(b'(left Int)', b'(missing Int)'), b'unknown premise field'),
        (typing.replace(b'(Integer Int)', b'(Integer Int (value Int))'), b'premise field'),
        (typing.replace(b'(Integer Int)', b'(Integer Mystery)'), b'judgment result'),
    ]:
        result = subprocess.run([str(ROOT / 'build/schema-seed')], input=invalid, capture_output=True)
        assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Generated judgments: valid/invalid typing, malformed rules, bounds and cycles passed')
