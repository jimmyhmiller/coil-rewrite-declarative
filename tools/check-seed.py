#!/usr/bin/env python3
"""Compile generated schema output and exercise references across table growth."""
from pathlib import Path
import subprocess
import tempfile
import shutil

ROOT = Path(__file__).resolve().parents[1]
(ROOT / 'build').mkdir(exist_ok=True)
for flags in [[], ['--debug-checks'], ['--release']]:
    subprocess.run(['coil', 'run', 'tests/phases.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/types.coil', *flags], cwd=ROOT, check=True)
subprocess.run(['coil', 'build', 'seed/main.coil', '-o', 'build/schema-seed'], cwd=ROOT, check=True)
source = (ROOT / 'tests/schemas/expressions.schema').read_bytes()
generated = subprocess.check_output([str(ROOT / 'build/schema-seed')], input=source)
assert generated == subprocess.check_output([str(ROOT / 'build/schema-seed')], input=source)
with tempfile.TemporaryDirectory(prefix='rewrite-schema-') as directory:
    work = Path(directory)
    shutil.copyfile(ROOT / "seed/types.coil", work / "types.coil")
    shutil.copyfile(ROOT / "seed/scope.coil", work / "scope.coil")
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
    shutil.copyfile(ROOT / "seed/types.coil", work / "types.coil")
    shutil.copyfile(ROOT / "seed/scope.coil", work / "scope.coil")
    (work / 'generated.coil').write_bytes(subprocess.check_output([str(ROOT / 'build/schema-seed')], input=recursive))
    subprocess.run(['coil', 'check', str(work / 'generated.coil')], check=True)
invalid = subprocess.run([str(ROOT / 'build/schema-seed')], input=b'(node X (x Missing))', capture_output=True)
assert invalid.returncode != 0 and not invalid.stdout and b'unknown field type' in invalid.stderr
print('Recursive schema and generator error-channel checks passed')

with tempfile.TemporaryDirectory(prefix='rewrite-variants-') as directory:
    work = Path(directory)
    shutil.copyfile(ROOT / "seed/types.coil", work / "types.coil")
    shutil.copyfile(ROOT / "seed/scope.coil", work / "scope.coil")
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
    shutil.copyfile(ROOT / "seed/types.coil", work / "types.coil")
    shutil.copyfile(ROOT / "seed/scope.coil", work / "scope.coil")
    (work / 'Coil.toml').write_text('[package]\nname = "fixture"\nentry = "main.coil"\nsource-roots = ["."]\n')
    typing = (ROOT / 'tests/schemas/typing.schema').read_bytes()
    output = subprocess.check_output([str(ROOT / 'build/schema-seed')], input=typing)
    renamed = subprocess.check_output([str(ROOT / 'build/schema-seed')], input=typing.replace(b'?result', b'?branch'))
    assert output == renamed, 'same-length variable renaming changed generated code'
    (work / 'generated.coil').write_bytes(output)
    premise = b'(right Int)'
    offset = typing.index(premise)
    (work / 'main.coil').write_text((ROOT / 'tests/judgment.coil.in').read_text()
        .replace('RULE_LO', str(offset)).replace('RULE_HI', str(offset + len(premise))))
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
    for invalid, diagnostic in [
        (typing.replace(b'(Boolean Bool)', b''), b'exactly one rule'),
        (typing + b'(judgment Expr)', b'duplicate judgment'),
        (typing.replace(b'(left Int)', b'(missing Int)'), b'unknown premise field'),
        (typing.replace(b'(Integer Int)', b'(Integer Int (value Int))'), b'premise field'),
        (typing.replace(b'(Integer Int)', b'(Integer Mystery)'), b'judgment result'),
        (typing.replace(b'(Integer Int)', b'(Integer ?unbound)'), b'unbound result'),
        (typing.replace(b'(Fn Int ?body)', b'(Fn Int ?missing)'), b'unbound result'),
        (typing.replace(b'(Fn Int ?body)', b'(Fn Int)'), b'expected (Fn'),
        (typing.replace(b'(Fn ?argument ?result)', b'(Fn ?argument)'), b'expected (Fn'),
        (typing.replace(b'(Fn ?same ?same)', b'(Fn Unknown ?same)'), b'unknown judgment'),
        (typing.replace(b'(lookup name)', b'(lookup missing)'), b'lookup requires'),
        (typing.replace(b'(bind name ?value)', b'(bind value ?value)'), b'binding requires'),
        (typing.replace(b'(bind name ?value)', b'(bind name ?body)'), b'known before'),
    ]:
        result = subprocess.run([str(ROOT / 'build/schema-seed')], input=invalid, capture_output=True)
        assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Generated judgments: valid/invalid typing, malformed rules, bounds and cycles passed')

with tempfile.TemporaryDirectory(prefix='rewrite-reader-') as directory:
    work = Path(directory)
    shutil.copyfile(ROOT / "seed/types.coil", work / "types.coil")
    shutil.copyfile(ROOT / "seed/scope.coil", work / "scope.coil")
    (work / 'Coil.toml').write_text('[package]\nname = "fixture"\nentry = "main.coil"\nsource-roots = ["."]\n')
    (work / 'generated.coil').write_bytes(subprocess.check_output(
        [str(ROOT / 'build/schema-seed')], input=(ROOT / 'tests/schemas/typing.schema').read_bytes()))
    (work / 'main.coil').write_text((ROOT / 'tests/reader.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
print('Schema-derived source readers and typing pipeline passed')

with tempfile.TemporaryDirectory(prefix='rewrite-index-') as directory:
    work = Path(directory)
    shutil.copyfile(ROOT/'seed/types.coil', work/'types.coil')
    shutil.copyfile(ROOT/'seed/scope.coil', work/'scope.coil')
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    keyed = b'(node Entry (label Text :key) (serial Int :key) (flag Bool :key))'
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=keyed))
    (work/'main.coil').write_text((ROOT/'tests/index.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
for source, diagnostic in [
    (b'(sum Entry (Named (name Text :key)))', b'key requires a scalar field on a record'),
    (b'(node Entry (parent Entry :key))', b'key requires a scalar field on a record'),
    (b'(node Entry (name Text :unknown))', b'optional :key'),
]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=source, capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Schema keys: content lookup, growth, subset identity, duplicate provenance and rejection passed')

with tempfile.TemporaryDirectory(prefix='rewrite-syntax-') as directory:
    work = Path(directory)
    for name in ['types', 'scope']:
        shutil.copyfile(ROOT/'seed'/f'{name}.coil', work/f'{name}.coil')
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    source = b'(node Pair (first Text) (second Int)) (syntax Pair (Pair (vector (int second) (text first))))'
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=source))
    (work/'main.coil').write_text((ROOT/'tests/syntax.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
source = ((ROOT/'tests/schemas/lowering.schema').read_bytes()
          + b'\n(node Function (name Text :key) (parameter Text) (body Expr))\n'
          + (ROOT/'tests/schemas/surface.syntax').read_bytes())
for invalid, diagnostic in [
    (source + b'(syntax Expr (Integer (int value)))', b'duplicate syntax declaration'),
    (source.replace(b'(int value)', b'(int missing)'), b'unknown syntax field'),
    (source.replace(b'(int value)', b'(text value)'), b'capture type disagrees'),
    (source.replace(b'(ref left)', b'(ref right)'), b'captured more than once'),
    (source.replace(b'(ref right)', b''), b'capture every schema field'),
    (source.replace(b'(int value)', b'(ref value)'), b'root must consume'),
    (source.replace(b'(list "+"', b'(list'), b'shadowed by an earlier root'),
    (source.replace(b'(list "if"', b'(list "+"'), b'shadowed by an earlier root'),
    (source.replace(b'  (Boolean (bool value))', b''), b'exactly one syntax rule'),
    (source[:source.index(b'(syntax Expr')] + source[source.index(b'(syntax Function'):], b'referenced schema needs a syntax declaration'),
]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Typed syntax: record construction, reordered captures and malformed/ambiguous definitions passed')
