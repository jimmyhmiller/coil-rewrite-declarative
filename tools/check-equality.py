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
for source, message in [
    ('(node X (v Int)) (equality)', 'expected (equality Schema)'),
    ('(node X (v Int)) (equality Missing)', 'unknown equality schema'),
    ('(node X (v Int)) (equality X) (equality X)', 'duplicate equality declaration'),
]:
    result = subprocess.run([str(compiler)], input=source.encode(), capture_output=True)
    assert result.returncode != 0 and not result.stdout and message.encode() in result.stderr, result
print('Independent equality generation and declaration diagnostics passed')
