#!/usr/bin/env python3
"""Copy an immutable Coil backend snapshot, retaining authored sources and provenance."""
import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

REVISION = 'b7a54594b42820c24c4b4cce0d9348f160bdd38e'
PATHS = ['src/declarative', 'src/compiler/declarative', 'src/compiler/native',
         'scripts/compiler/gen-declarative.py', 'scripts/compiler/project_config.py']
ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('coil', type=Path)
ap.add_argument('--check', action='store_true')
args = ap.parse_args()
archive = subprocess.check_output(['git', '-C', str(args.coil), 'archive', REVISION, *PATHS])
destination = ROOT / 'vendor/coil'
manifest = {}
with tarfile.open(fileobj=io.BytesIO(archive)) as files:
    for item in files:
        if not item.isfile():
            continue
        relative = Path(item.name)
        if relative.is_absolute() or '..' in relative.parts:
            raise SystemExit('unsafe archive path')
        content = files.extractfile(item).read()
        manifest[item.name] = hashlib.sha256(content).hexdigest()
        output = destination / relative
        if args.check:
            if not output.is_file() or output.read_bytes() != content:
                raise SystemExit(f'snapshot differs: {item.name}')
        else:
            if output.exists() and output.read_bytes() != content:
                raise SystemExit(f'refusing to overwrite modified snapshot: {item.name}')
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)
record = {'repository': 'https://github.com/jimmyhmiller/coil', 'revision': REVISION,
          'paths': PATHS, 'sha256': manifest}
lock = destination / 'snapshot.json'
expected = json.dumps(record, indent=2) + '\n'
if args.check:
    if lock.read_text() != expected:
        raise SystemExit('snapshot manifest differs')
    actual = {str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()}
    if actual != set(manifest) | {'snapshot.json'}:
        raise SystemExit('unexpected snapshot files')
else:
    lock.write_text(expected)
print(f'{len(manifest)} files {"verified" if args.check else "imported"} at {REVISION}')
