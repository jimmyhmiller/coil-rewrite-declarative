#!/usr/bin/env python3
"""Compile generated schema output and exercise references across table growth."""
from pathlib import Path
import subprocess
import tempfile
import shutil

ROOT = Path(__file__).resolve().parents[1]
(ROOT / 'build').mkdir(exist_ok=True)
subprocess.run(['python3', 'tools/gen-schema.py', '--check', '--bootstrap-check'], cwd=ROOT, check=True)
for flags in [[], ['--debug-checks'], ['--release']]:
    subprocess.run(['coil', 'run', 'tests/schema.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/classification.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/schema-scale.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/phases.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/protocol.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/types.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/type-syntax.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/type-elaboration.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/type-lexical.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/type-classified.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/code.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/equality.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/revision.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/admission.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/refer.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/namespace.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/use-lookup.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/routing.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/macro-head.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/source-routes.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/derive-registry.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/derive-routing.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/rounds.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/promotion.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/stage-datum.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/stage-split.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/requests.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/request-execution.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/produced.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/staged-requests.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/invocation.coil', *flags], cwd=ROOT, check=True)
    subprocess.run(['coil', 'run', 'tests/sequences.coil', *flags], cwd=ROOT, check=True)
source = (ROOT / 'tests/schemas/expressions.schema').read_bytes()
generated = subprocess.check_output([str(ROOT / 'build/schema-seed')], input=source)
assert generated == subprocess.check_output([str(ROOT / 'build/schema-seed')], input=source)
with tempfile.TemporaryDirectory(prefix='rewrite-schema-') as directory:
    work = Path(directory)
    shutil.copyfile(ROOT / "seed/types.coil", work / "types.coil")
    shutil.copyfile(ROOT / "seed/scope.coil", work / "scope.coil")
    shutil.copyfile(ROOT / "seed/resolution.coil", work / "resolution.coil")
    shutil.copyfile(ROOT / "seed/source.coil", work / "source.coil")
    shutil.copyfile(ROOT / "seed/sequence.coil", work / "sequence.coil")
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
    shutil.copyfile(ROOT / "seed/resolution.coil", work / "resolution.coil")
    shutil.copyfile(ROOT / "seed/source.coil", work / "source.coil")
    shutil.copyfile(ROOT / "seed/sequence.coil", work / "sequence.coil")
    (work / 'generated.coil').write_bytes(subprocess.check_output([str(ROOT / 'build/schema-seed')], input=recursive))
    subprocess.run(['coil', 'check', str(work / 'generated.coil')], check=True)
invalid = subprocess.run([str(ROOT / 'build/schema-seed')], input=b'(node X (x Missing))', capture_output=True)
assert invalid.returncode != 0 and not invalid.stdout and b'unknown field type' in invalid.stderr
print('Recursive schema and generator error-channel checks passed')

with tempfile.TemporaryDirectory(prefix='rewrite-variants-') as directory:
    work = Path(directory)
    shutil.copyfile(ROOT / "seed/types.coil", work / "types.coil")
    shutil.copyfile(ROOT / "seed/scope.coil", work / "scope.coil")
    shutil.copyfile(ROOT / "seed/resolution.coil", work / "resolution.coil")
    shutil.copyfile(ROOT / "seed/source.coil", work / "source.coil")
    shutil.copyfile(ROOT / "seed/sequence.coil", work / "sequence.coil")
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
    shutil.copyfile(ROOT / "seed/resolution.coil", work / "resolution.coil")
    shutil.copyfile(ROOT / "seed/source.coil", work / "source.coil")
    shutil.copyfile(ROOT / "seed/sequence.coil", work / "sequence.coil")
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
        (typing.replace(b'(in [address] ?type)', b'(in [] ?type)'), b'expected (in'),
        (typing.replace(b'(in [address] ?type)', b'(in [address address] ?type)'), b'duplicate accepted category'),
        (typing.replace(b'(in [address] ?type)', b'(in [7] ?type)'), b'category must be a symbol'),
        (typing.replace(b'(as address ?type)', b'(as address)'), b'expected (as'),
        (typing.replace(b'(as address ?type)', b'(as 7 ?type)'), b'expected (as'),
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
        (typing.replace(b'(reference name)', b'(reference missing)'), b'unknown binding field'),
        (typing.replace(b'(scope body name)', b'(scope body value)'), b'binding requires'),
        (typing.replace(b'(with ?value)', b'(with ?body)'), b'known before'),
    ]:
        result = subprocess.run([str(ROOT / 'build/schema-seed')], input=invalid, capture_output=True)
        assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Generated judgments: valid/invalid typing, malformed rules, bounds and cycles passed')

with tempfile.TemporaryDirectory(prefix='rewrite-reader-') as directory:
    work = Path(directory)
    shutil.copyfile(ROOT / "seed/types.coil", work / "types.coil")
    shutil.copyfile(ROOT / "seed/scope.coil", work / "scope.coil")
    shutil.copyfile(ROOT / "seed/resolution.coil", work / "resolution.coil")
    shutil.copyfile(ROOT / "seed/source.coil", work / "source.coil")
    shutil.copyfile(ROOT / "seed/sequence.coil", work / "sequence.coil")
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
    shutil.copyfile(ROOT/'seed/resolution.coil', work/'resolution.coil')
    shutil.copyfile(ROOT/'seed/source.coil', work/'source.coil')
    shutil.copyfile(ROOT/'seed/sequence.coil', work/'sequence.coil')
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    keyed = b'(node Entry (label Text :key) (serial Int :key) (flag Bool :key))'
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=keyed))
    (work/'main.coil').write_text((ROOT/'tests/index.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
for source, diagnostic in [
    (b'(sum Entry (Named (name Text :key)) (Unnamed))', b'sum key must have the same name'),
    (b'(node Entry (parent Entry :key))', b'key requires a scalar field'),
    (b'(node Entry (name Text :unknown))', b'optional :key'),
]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=source, capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Schema keys: content lookup, growth, subset identity, duplicate provenance and rejection passed')

sum_keys = b"""
(sum Symbol
  (Local (name Text :key) (serial Int :key) (value Int))
  (External (serial Int :key) (library Text) (name Text :key))
  (Alias (target Int) (name Text :key) (serial Int :key)))
"""
with tempfile.TemporaryDirectory(prefix='rewrite-sum-keys-') as directory:
    work = Path(directory)
    for name in ['types', 'scope', 'source', 'sequence']:
        shutil.copyfile(ROOT/'seed'/f'{name}.coil', work/f'{name}.coil')
    (work/'Coil.toml').write_text("""[package]
name = "fixture"
entry = "main.coil"
source-roots = ["."]
""")
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=sum_keys))
    (work/'main.coil').write_text((ROOT/'tests/sum-index.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
for invalid in [
    b'(sum A (X (key Text :key)) (Y))',
    b'(sum A (X) (Y (key Text :key)))',
    b'(sum A (X (key Text :key)) (Y (key Int :key)))',
    b'(sum A (X (key Text :key)) (Y (other Text :key)))',
    b'(sum A (X (key Text :key)) (Y (key Text)))',
]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout and b'sum key must have the same name' in result.stderr, result
print('Common sum keys and incremental indexes passed')


with tempfile.TemporaryDirectory(prefix='rewrite-syntax-') as directory:
    work = Path(directory)
    for name in ['types', 'scope', 'source', 'sequence']:
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


source = ((ROOT/'tests/schemas/lowering.schema').read_bytes()
          + b'\n(node Function (name Text :key) (parameter Text) (body Expr))\n'
          + (ROOT/'tests/schemas/transform.schema').read_bytes())
for invalid, diagnostic in [
    (source + b'(transform Surface Expr (Integer (Integer value)))', b'duplicate schema transformation'),
    (source.replace(b'(Bump (Add value (Integer 1)))', b'(Bump (Unknown value))'), b'unknown target constructor'),
    (source.replace(b'(Bump (Add value (Integer 1)))', b'(Bump (Add value))'), b'wrong target constructor arity'),
    (source.replace(b'(Integer (Integer value))', b'(Integer (Integer true))'), b'transform scalar must be'),
    (source.replace(b'(Bump (Add value (Integer 1)))', b''), b'exactly one transformation rule'),
    (source.replace(b'(Bump (Add value (Integer 1)))', b'(Bogus (Integer 0))'), b'unknown transformation source constructor'),
    (source[:source.index(b'(transform Surface Expr')] + source[source.index(b'(transform SurfaceFunction Function'):], b'field type needs a matching schema map'),
    (b'(node Child (value Int)) (node S (child Child)) (node T (child Child)) (transform S T (S (T child)))', b'field type needs a matching schema map'),
]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Typed transformations: schema and rule contract rejections passed')

# Same-schema transformations must copy reference graphs into independent stores.
identity_schema = b'(sum Tree (Leaf (text Text)) (Pair (left Tree) (right Tree))) (transform Tree Tree (Leaf (Leaf text)) (Pair (Pair left right)))'
with tempfile.TemporaryDirectory(prefix='rewrite-owned-transform-') as directory:
    work = Path(directory)
    for name in ['types', 'scope', 'source', 'sequence']:
        shutil.copyfile(ROOT/'seed'/f'{name}.coil', work/f'{name}.coil')
    (work/'Coil.toml').write_text('[package]\nname = "fixture"\nentry = "main.coil"\nsource-roots = ["."]\n')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=identity_schema))
    (work/'main.coil').write_text((ROOT/'tests/transform-owned.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)

# Cardinality is part of a map's signature. Invalid sequence terms publish no output.
for invalid, diagnostic in [
    (b'(node A) (node B) (transform A (many B) (A (B)))', b'sequence result requires'),
    (b'(node A) (node B) (transform A (many Missing) (A (items)))', b'unknown transformation schema'),
    (b'(node A) (node B) (transform A (many B Int) (A (items)))', b'expected (transform'),
    (b'(node A (x Int)) (node B) (transform A (many B) (A (items (spread x))))', b'spread field needs'),
    (b'(node A) (node B) (transform A (many B) (A (items (spread))))', b'spread requires'),
    (b'(node A (x A)) (node B) (transform A B (A (B))) (transform A (many B) (A (items (spread missing))))', b'spread field needs'),
    (b'(node A (x A)) (node B (x B)) (transform A (many B) (A (items (B x))))', b'field type needs a matching schema map'),
    (b'(node A) (node B) (transform A (many B) (A (items))) (transform A (many B) (A (items)))', b'duplicate schema transformation'),
]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Sequence map cardinality and splice contract rejections passed')

sequence_schema = b"""
(sum S (Leaf (value Int)) (Empty) (Fork (left S) (right S)))
(node T (value Int))
(transform S T (Leaf (T value)) (Empty (T 0)) (Fork (T 0)))
(transform S (many T)
  (Leaf (items (T value) (T 99)))
  (Empty (items))
  (Fork (items (spread left) (spread right))))
"""
with tempfile.TemporaryDirectory(prefix='rewrite-sequence-map-') as directory:
    work = Path(directory)
    for name in ['types', 'scope', 'source', 'sequence']:
        shutil.copyfile(ROOT/'seed'/f'{name}.coil', work/f'{name}.coil')
    (work/'Coil.toml').write_text('''[package]
name = "fixture"
entry = "main.coil"
source-roots = ["."]
''')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=sequence_schema))
    (work/'main.coil').write_text((ROOT/'tests/sequence-map.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)

field_schema = b"""
(node Entry (label Text))
(node SourceBox (children (many Entry)))
(node TargetEntry (label Text))
(node TargetBox (children (many TargetEntry)))
(transform Entry TargetEntry (Entry (TargetEntry label)))
(transform SourceBox TargetBox (SourceBox (TargetBox children)))
(syntax Entry (Entry (symbol label)))
(syntax SourceBox (SourceBox (list "box" (vector (rest children)))))
"""
with tempfile.TemporaryDirectory(prefix='rewrite-sequence-fields-') as directory:
    work = Path(directory)
    for name in ['types', 'scope', 'source', 'sequence']:
        shutil.copyfile(ROOT/'seed'/f'{name}.coil', work/f'{name}.coil')
    (work/'Coil.toml').write_text('''[package]
name = "fixture"
entry = "main.coil"
source-roots = ["."]
''')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=field_schema))
    (work/'main.coil').write_text((ROOT/'tests/sequence-fields.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
for invalid, diagnostic in [
    (b'(node A (xs (many Int)))', b'sequence fields require node elements'),
    (b'(node A (xs (many Missing)))', b'unknown field type'),
    (b'(node A (xs (many A) :key))', b'key requires a scalar field'),
    (field_schema.replace(b'(rest children)', b'(ref children)'), b'syntax capture type disagrees'),
    (field_schema.replace(b'(vector (rest children))', b'(vector (rest children) "tail")'), b'rest capture must be last'),
    (field_schema.replace(b'(TargetBox children)', b'(TargetBox (items children))'), b'field type needs a matching schema map'),
    (b'(sum E (Group (children (many E)))) (judgment E (Group Int (children Int)))', b'premise field must reference'),
]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Sequence field and rest-capture contracts passed')


binding_source = (ROOT/'tests/schemas/parallel-bindings.schema').read_bytes()
for invalid, diagnostic in [
    (b'(node A) (bindings Missing)', b'unknown binding schema'),
    (b'(node A) (bindings A) (bindings A)', b'duplicate binding declaration'),
    (binding_source.replace(b'(Read (reference label))', b'(Read (reference label) (reference label))'), b'already has a reference'),
    (binding_source.replace(b'(Read (reference label))', b'(Unknown (reference label))'), b'unknown binding constructor'),
    (binding_source.replace(b'(Read (reference label))', b'(Read (reference label)) (Read (reference label))'), b'duplicate constructor binding rule'),
    (binding_source.replace(b'(Read (reference label))', b'(Read (reference missing))'), b'unknown binding field'),
    (binding_source.replace(b'(scope body label)', b'(scope label label)'), b'scope child must be a node reference'),
    (binding_source.replace(b'(scope body label)', b'(scope body value)'), b'scope binding requires a Text field'),
    (binding_source.replace(b'(scope body label)', b'(scope body label) (scope body label)'), b'duplicate child scope'),
    (binding_source.replace(b'(scope body left-name right-name)', b'(scope body left-name left-name)'), b'duplicate scope binding field'),
    (binding_source.replace(b'(reference label)', b'(lookup label)'), b'expected (reference name)'),
    (binding_source.replace(b'(body ?body (with ?value))', b'(body ?body)'), b'scope payloads must match'),
    (binding_source.replace(b'(with ?left ?right)', b'(with ?left)'), b'scope payloads must match'),
    (binding_source.replace(b'(body ?body (with ?left ?right))', b'(left ?body)'), b'check each declared scoped child once'),
    (binding_source.replace(b'(Read (lookup))', b'(Read Int)'), b'lookup must match the declared reference'),
    (binding_source.replace(b'(let left right body)', b'(let body right left)'), b'let body must be the declared scoped child'),
    (binding_source.replace(b'(let left right body)', b'(let left body)'), b'let values must match declared binding names'),
    (binding_source.replace(b'(Outer (let value body))', b'(Outer (identity body))'), b'consume declared references and scopes'),
    (binding_source.replace(b'(with ?value)', b'(with ?body)'), b'known before'),
]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Shared binding declaration and semantic-client contracts passed')


for invalid, diagnostic in [
    (b'(node A) (module rewrite.a) (module rewrite.b)', b'duplicate output module'),
    (b'(node A) (module single)', b'at least two nonempty segments'),
    (b'(node A) (module rewrite..a)', b'invalid output module name'),
    (b'(node A) (module rewrite/a)', b'invalid output module name'),
    (b'(node A) (module "rewrite.a")', b'expected (module qualified.name)'),
    (b'(node A) (syntax A :expect 1 (A (list)))', b'expected :expect string'),
    (b'(node A) (syntax A :unknown "expected A" (A (list)))', b'expected :expect string'),
]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic in result.stderr, result
print('Named output modules and syntax expectation contracts passed')

# Binding topology derives reference identities independently of typing/lowering.
with tempfile.TemporaryDirectory(prefix='rewrite-resolution-') as directory:
    work = Path(directory)
    for runtime in ('types', 'scope', 'resolution', 'source', 'sequence'):
        shutil.copyfile(ROOT / f'seed/{runtime}.coil', work / f'{runtime}.coil')
    (work / 'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    (work / 'generated.coil').write_bytes(subprocess.check_output(
        [str(ROOT / 'build/schema-seed')], input=(ROOT / 'tests/schemas/resolution.schema').read_bytes()))
    (work / 'main.coil').write_bytes((ROOT / 'tests/resolution.coil.in').read_bytes())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
print('Generated lexical resolution: identity and invalid-graph checks passed')

with tempfile.TemporaryDirectory(prefix='rewrite-alpha-') as directory:
    work = Path(directory)
    for runtime in ('types', 'scope', 'resolution', 'source', 'sequence'):
        shutil.copyfile(ROOT / f'seed/{runtime}.coil', work / f'{runtime}.coil')
    (work / 'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    (work / 'generated.coil').write_bytes(subprocess.check_output(
        [str(ROOT / 'build/schema-seed')], input=(ROOT / 'tests/schemas/resolution.schema').read_bytes()))
    (work / 'main.coil').write_bytes((ROOT / 'tests/alpha.coil.in').read_bytes())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
print('Identity-directed alpha copying passed')

for invalid in [b'(node X (value Text)) (syntax X (X (float-bits value)))',
                b'(node X (value Int)) (syntax X (X (cstring value)))']:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout and b'capture type disagrees' in result.stderr, result
print('Raw float-bit and C-string syntax capture type checks passed')

subprocess.run(['python3', 'tools/check-protocol.py', '--compiler', 'build/schema-seed'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-expansion-policy.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-equality.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-context-policy.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-syntax-views.py'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/check-syntax-tails.py'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/check-identifiers.py'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/check-first-or.py'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/check-type-syntax.py'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/check-classification.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-walk.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-refer.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-search.py'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/check-export.py'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/check-selection.py'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/check-use.py'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/check-routing.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-pairs.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-derive.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-traits.py'], cwd=ROOT, check=True)
subprocess.run(['python3', 'tools/check-functions.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-occurrences.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-classified-maps.py'], cwd=ROOT, check=True)

subprocess.run(['python3', 'tools/check-type-elaboration.py'], cwd=ROOT, check=True)
