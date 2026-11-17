#!/usr/bin/env python3
"""Bootstrap the DSL-authored compiler command; never invoke Coil on guest input."""
from pathlib import Path
import json, subprocess
ROOT=Path(__file__).resolve().parents[1]
subprocess.run(['python3','tools/gen-schema.py'],cwd=ROOT,check=True)
work=ROOT/'build/compiler';work.mkdir(parents=True,exist_ok=True)
roots=[str(ROOT/'seed'),str(ROOT/'runtime'),*[str(ROOT/'vendor/coil'/p) for p in ['src/compiler/declarative','src/compiler/native','src/declarative/tests']]]
(work/'Coil.toml').write_text('[package]\nname="rewrite"\nsource-roots='+json.dumps(roots)+'\n')
subprocess.run(['coil','build',str(ROOT/'seed/generated/core_compiler.coil'),'-o',str(ROOT/'build/coil-rewrite')],cwd=work,check=True)
print(ROOT/'build/coil-rewrite')
