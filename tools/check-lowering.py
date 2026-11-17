#!/usr/bin/env python3
"""Compile schema-driven source to CIR and execute the retained native backend's code."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import json
ROOT = Path(__file__).resolve().parents[1]
(ROOT / 'build').mkdir(exist_ok=True)
subprocess.run(['coil', 'build', 'seed/main.coil', '-o', 'build/schema-seed'], cwd=ROOT, check=True)
with tempfile.TemporaryDirectory(prefix='rewrite-lowering-') as directory:
    work = Path(directory)
    roots = ['.', *[str(ROOT / 'vendor/coil' / p) for p in ['src/compiler/declarative', 'src/compiler/native', 'src/declarative/tests']]]
    (work/'Coil.toml').write_text('[package]\nname = "fixture"\nentry = "main.coil"\nsource-roots = '+json.dumps(roots)+'\n')
    shutil.copyfile(ROOT/'seed/types.coil', work/'types.coil')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=(ROOT/'tests/schemas/lowering.schema').read_bytes()))
    (work/'main.coil').write_text((ROOT/'tests/lowering.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
print('Source -> generated checking/lowering -> CIR -> native execution passed')

source = (ROOT/'tests/schemas/lowering.schema').read_bytes()
for invalid in [source + b'(lower Expr)', source.replace(b'(const value)', b'(const missing)'), source.replace(b'(add left right)', b'(unknown left right)'), source.replace(b'(Boolean (bool value))', b'')]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout, result
print('Invalid lowering definitions rejected before output')
