#!/usr/bin/env python3
"""Regenerate the schema parser, using the checked-in parser to bootstrap the seed."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'languages/schema.schema'
OUTPUT = ROOT / 'seed/generated/schema_forms.coil'
HEADER = b';;; Generated from languages/schema.schema by tools/gen-schema.py. Do not edit.\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def generate(compiler):
    result = subprocess.run([str(compiler)], input=SPEC.read_bytes(), capture_output=True, check=True)
    if not result.stdout.startswith(b'(module rewrite.schemaforms)\n'):
        raise RuntimeError('schema grammar did not emit its declared module')
    return HEADER + result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='reject a stale checked-in parser')
    parser.add_argument('--bootstrap-check', action='store_true',
                        help='rebuild with regenerated parser in isolation, then compare generation')
    args = parser.parse_args()
    if not OUTPUT.is_file():
        raise RuntimeError('the reviewed generated parser snapshot is required to bootstrap')
    (ROOT / 'build').mkdir(exist_ok=True)
    compiler = ROOT / 'build/schema-seed'
    subprocess.run(['coil', 'build', 'seed/main.coil', '-o', str(compiler)], cwd=ROOT, check=True)
    generated = generate(compiler)
    if args.check:
        if OUTPUT.read_bytes() != generated:
            raise RuntimeError('schema parser is stale; run python3 tools/gen-schema.py')
    else:
        OUTPUT.write_bytes(generated)
    if args.bootstrap_check:
        with tempfile.TemporaryDirectory(prefix='rewrite-schema-bootstrap-') as directory:
            stage = Path(directory)
            shutil.copytree(ROOT / 'seed', stage / 'seed')
            (stage / 'seed/generated/schema_forms.coil').write_bytes(generated)
            (stage / 'Coil.toml').write_text(
                '[package]\nname = "rewrite"\nentry = "seed/main.coil"\nsource-roots = ["seed"]\n')
            second = stage / 'schema-seed'
            subprocess.run(['coil', 'build', 'seed/main.coil', '-o', str(second)], cwd=stage, check=True)
            regenerated = generate(second)
            if regenerated != generated:
                raise RuntimeError('regenerated schema parser did not reach a fixed point')
        host = Path(shutil.which('coil')).resolve()
        version = subprocess.check_output(['coil', '--version'], text=True).strip()
        evidence = {
            'scope': 'Schema grammar/parser regeneration only; host Coil builds both stages.',
            'host_version': version,
            'host_executable_sha256': digest(host.read_bytes()),
            'specification_sha256': digest(SPEC.read_bytes()),
            'generated_sha256': digest(generated),
            'isolated_rebuild_regeneration_equal': True,
            'seed_inputs': {str(path.relative_to(ROOT)): digest(path.read_bytes())
                            for path in sorted((ROOT / 'seed').rglob('*.coil'))},
            'limitations': 'Not full compiler self-hosting or a machine-code bootstrap comparison. '
                           'Installed host stdlib/tool dependencies are not pinned by this check.',
        }
        (ROOT / 'evidence/schema-bootstrap.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print('Schema parser: current' + ('; isolated regeneration fixed point passed' if args.bootstrap_check else ''))


if __name__ == '__main__':
    main()
