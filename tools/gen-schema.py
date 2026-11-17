#!/usr/bin/env python3
"""Regenerate bootstrap grammars and protocol programs using the checked-in language seed."""
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
LANGUAGE_ARTIFACTS = [(SPEC, OUTPUT, 'rewrite.schemaforms'),
            (ROOT/'languages/classification.schema', ROOT/'seed/generated/classification_forms.coil', 'rewrite.classificationforms'),
            (ROOT/'languages/type_syntax.schema', ROOT/'seed/generated/type_syntax.coil', 'rewrite.typesyntax'),
            (ROOT/'languages/admission.protocol', ROOT/'seed/generated/admission_protocol.coil', 'rewrite.admissionprotocol'),
            (ROOT/'languages/derive.schema', ROOT/'seed/generated/derive_forms.coil', 'rewrite.deriveforms'),
            (ROOT/'languages/derive_registration.protocol', ROOT/'seed/generated/derive_protocol.coil', 'rewrite.deriveprotocol'),
            (ROOT/'languages/pair_selection.schema', ROOT/'seed/generated/pair_forms.coil', 'rewrite.pairforms'),
            (ROOT/'languages/macro_head.protocol', ROOT/'seed/generated/head_protocol.coil', 'rewrite.headprotocol'),
            (ROOT/'languages/resolution.protocol', ROOT/'seed/generated/resolve_protocol.coil', 'rewrite.resolveprotocol'),
            (ROOT/'languages/exports.search', ROOT/'seed/generated/export_search.coil', 'rewrite.exportsearch'),
            (ROOT/'languages/search.schema', ROOT/'seed/generated/search_forms.coil', 'rewrite.searchforms'),
            (ROOT/'languages/names.schema', ROOT/'seed/generated/name_forms.coil', 'rewrite.nameforms'),
            (ROOT/'languages/code.schema', ROOT/'seed/generated/code_forms.coil', 'rewrite.codeforms'),
            (ROOT/'languages/protocol.schema', ROOT/'seed/generated/protocol_forms.coil', 'rewrite.protocolforms'),
            (ROOT/'languages/staging.protocol', ROOT/'seed/generated/stage_protocol.coil', 'rewrite.stageprotocol'),
            (ROOT/'languages/before_expand.protocol', ROOT/'seed/generated/before_protocol.coil', 'rewrite.beforeprotocol'),
            (ROOT/'languages/request_expansion.protocol', ROOT/'seed/generated/request_protocol.coil', 'rewrite.requestprotocol')]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def generate(compiler, spec, module):
    result = subprocess.run([str(compiler)], input=spec.read_bytes(), capture_output=True, check=True)
    if not result.stdout.startswith(f'(module {module})\n'.encode()):
        raise RuntimeError('schema grammar did not emit its declared module')
    header = f';;; Generated from {spec.relative_to(ROOT)} by tools/gen-schema.py. Do not edit.\n'.encode()
    return header + result.stdout


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
    generated = {}
    for spec, output, module in LANGUAGE_ARTIFACTS:
        generated[output] = generate(compiler, spec, module)
        if args.check:
            if not output.is_file() or output.read_bytes() != generated[output]:
                raise RuntimeError(f'{output.relative_to(ROOT)} is stale; run python3 tools/gen-schema.py')
        else:
            output.write_bytes(generated[output])
    if args.bootstrap_check:
        with tempfile.TemporaryDirectory(prefix='rewrite-schema-bootstrap-') as directory:
            stage = Path(directory)
            shutil.copytree(ROOT / 'seed', stage / 'seed')
            for output, data in generated.items():
                (stage/output.relative_to(ROOT)).write_bytes(data)
            (stage / 'Coil.toml').write_text(
                '[package]\nname = "rewrite"\nentry = "seed/main.coil"\nsource-roots = ["seed"]\n')
            second = stage / 'schema-seed'
            subprocess.run(['coil', 'build', 'seed/main.coil', '-o', str(second)], cwd=stage, check=True)
            for spec, output, module in LANGUAGE_ARTIFACTS:
                if generate(second, spec, module) != generated[output]:
                    raise RuntimeError(f'{output.relative_to(ROOT)} did not reach a fixed point')
        host = Path(shutil.which('coil')).resolve()
        version = subprocess.check_output(['coil', '--version'], text=True).strip()
        evidence = {
            'scope': 'Schema, syntax-value and protocol language regeneration only; host Coil builds both stages.',
            'host_version': version,
            'host_executable_sha256': digest(host.read_bytes()),
            'specification_sha256': digest(SPEC.read_bytes()),
            'generated_sha256': digest(generated[OUTPUT]),
            'language_artifacts': {str(spec.relative_to(ROOT)): dict(
                specification_sha256=digest(spec.read_bytes()), output=str(output.relative_to(ROOT)),
                generated_sha256=digest(generated[output])) for spec, output, module in LANGUAGE_ARTIFACTS},
            'isolated_rebuild_regeneration_equal': True,
            'seed_inputs': {str(path.relative_to(ROOT)): digest(path.read_bytes())
                            for path in sorted((ROOT / 'seed').rglob('*.coil'))},
            'limitations': 'Not full compiler self-hosting or a machine-code bootstrap comparison. '
                           'Installed host stdlib/tool dependencies are not pinned by this check.',
        }
        (ROOT / 'evidence/schema-bootstrap.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print('Schema, syntax-value and protocol artifacts: current' + ('; isolated regeneration fixed point passed' if args.bootstrap_check else ''))


if __name__ == '__main__':
    main()
