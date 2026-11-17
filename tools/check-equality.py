#!/usr/bin/env python3
"""Exercise schema-derived comparison independently of the syntax schema."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
compiler = ROOT / 'build/schema-seed'
with tempfile.TemporaryDirectory(prefix='rewrite-equality-') as directory:
    work = Path(directory)
    for runtime in ['types', 'scope', 'resolution', 'source', 'sequence', 'equality_runtime']:
        shutil.copyfile(ROOT / f'seed/{runtime}.coil', work / f'{runtime}.coil')
    (work / 'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    (work / 'generated.coil').write_bytes(subprocess.check_output(
        [str(compiler)], input=(ROOT / 'tests/schemas/equality.schema').read_bytes()))
    (work / 'main.coil').write_bytes((ROOT / 'tests/equality-record.coil.in').read_bytes())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
# Field-projection equivalence also works without any structural equality root.
with tempfile.TemporaryDirectory(prefix='rewrite-equivalence-') as directory:
    work = Path(directory)
    for runtime in ['types', 'scope', 'resolution', 'source', 'sequence']:
        shutil.copyfile(ROOT / f'seed/{runtime}.coil', work / f'{runtime}.coil')
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    specification = '(node Item (count Int) (label Text) (enabled Bool)) (equivalence relevant Item enabled label) (equivalence number Item count) (equivalence empty Item)'
    (work/'generated.coil').write_bytes(subprocess.check_output([str(compiler)], input=specification.encode()))
    (work/'main.coil').write_text('''(module fixture.main)
(import "rewrite.generated" :use *)
(defn main [] (-> i64)
  (let [(mut left) (N0Row :f0 1 :f1 "same" :f2 true)
        (mut right) (N0Row :f0 2 :f1 "same" :f2 true)]
    (unless (equivalent-relevant (mut left) (mut right)) (panic "unselected field"))
    (when (equivalent-number (mut left) (mut right)) (panic "integer field"))
    (set! (.f2 right) false)
    (when (equivalent-relevant (mut left) (mut right)) (panic "boolean field"))
    (set! (.f2 right) true)
    (set! (.f1 right) "different")
    (when (equivalent-relevant (mut left) (mut right)) (panic "text field"))
    (unless (equivalent-empty (mut left) (mut right)) (panic "empty projection"))
    0))
''')
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
for source, message in [
    ('(node X (v Int)) (equivalence)', 'expected (equivalence'),
    ('(node X (v Int)) (equivalence bad/name X v)', 'expected (equivalence'),
    ('(node X (v Int)) (equivalence same Missing v)', 'unknown equivalence record'),
    ('(sum X (A)) (equivalence same X)', 'equivalence needs a record'),
    ('(node X (v Int)) (equivalence same X v) (equivalence same X)', 'duplicate equivalence policy'),
    ('(node X (v Int)) (equivalence same X missing)', 'unknown equivalence field'),
    ('(node X (v Int)) (equivalence same X (v))', 'expected equivalence field name'),
    ('(node X (v Int)) (equivalence same X v v)', 'duplicate equivalence field'),
    ('(node X (v X)) (equivalence same X v)', 'equivalence fields must be scalar'),
    ('(node X (v (many X))) (equivalence same X v)', 'equivalence fields must be scalar'),
    ('(node X (v Int)) (equality)',  'expected (equality Schema)'),
    ('(node X (v Int)) (equality Missing)', 'unknown equality schema'),
    ('(node X (v Int)) (equality X) (equality X)', 'duplicate equality declaration'),
]:
    result = subprocess.run([str(compiler)], input=source.encode(), capture_output=True)
    assert result.returncode != 0 and not result.stdout and message.encode() in result.stderr, result
print('Independent structural equality, field equivalence and declaration diagnostics passed')
