#!/usr/bin/env python3
"""Replay captured refer helpers through schema-derived owned indexes."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
compiler = ROOT/'build/schema-seed'
evidence_path = ROOT/'evidence/refer-reference.json'
evidence = json.loads(evidence_path.read_text())


def q(text):
    return json.dumps(text, ensure_ascii=False)


def names(values, alternate):
    return '[' + ' '.join(f'(Word false {q(value)})' if alternate else f'(Name {q(value)})' for value in values) + ']'


def fixture(alternate):
    body = ['''(module fixture.main)
(import "fixture.refer" :use *)
(import "rewrite.refer" :as refer)
(import "coil.alloc" :use *)
(import "coil.arraylist" :use *)
(import "coil.reader" :use *)
(import "coil.scratch" :use [ScratchArena])
(import "coil.result" :use *)
(defn answer [(value (Option (slice u8)))] (-> (slice u8))
  (match value (Some [text] text) (None [] "-")))
(defn build [(a (dyn Allocator)) (text (slice u8))] (-> refer/Policy)
  (let [(mut store) (store-new a) (mut scratch) (zeroed ScratchArena)
        initialized (init (mut scratch) a) sa (allocator (mut scratch))
        forms (match (read-all sa text 0) (Ok [forms] forms) (Err [_] (panic "read")))
        root (match (parse-2 (mut store) (elem forms 0)) (Ok [root] root) (Err [_] (panic "schema parse")))]
    (defer (store-free! (mut store))) (defer (close! (mut scratch)))
    (match (REFER (mut store) root) (Ok [policy] policy) (Err [_] (panic "policy build")))))
(defn main [] (-> i64) (let [a (malloc-allocator)]
'''.replace('(REFER (mut store)', f'({"refer-access" if alternate else "refer-imports"} a (mut store)')]
    for i, case in enumerate(evidence['cases']):
        selected = names(case['selected'], alternate)
        excluded = names(case['excluded'], alternate)
        renames = '[' + ' '.join(f'(Rename {q(local)} 17 {q(exported)})' if alternate else f'(Rename {q(exported)} {q(local)})'
                                 for exported, local in case['renames']) + ']'
        flag = str(case['all']).lower()
        data = f'(Use {renames} {flag} {excluded} {selected})' if alternate else f'(Refer {flag} {selected} {excluded} {renames})'
        body.append(f'(let [(mut policy) (build a {q(data)})] (defer (refer/release! (mut policy)))')
        for answer in case['answers']:
            query = q(answer['query'])
            body.append(f'(println "{i} {{}} {{}} {{}} {{}}" {query} (answer (refer/referred (mut policy) {query})) (answer (refer/local-name (mut policy) {query})) (refer/drops? (mut policy) {query}))')
        body.append(')')
    body.append('0))')
    return '\n'.join(body)


expected = ''.join(f"{i} {a['query']} {a['referred'] if a['referred'] is not None else '-'} {a['local'] if a['local'] is not None else '-'} {str(a['drops']).lower()}\n"
                   for i, case in enumerate(evidence['cases']) for a in case['answers'])
base = (ROOT/'languages/names.schema').read_text().replace('rewrite.nameforms', 'fixture.refer')
other = '''(module fixture.refer)
(node Rename (local Text) (ignored Int) (exported Text))
(node Word (ignored Bool) (name Text))
(node Use (renamed (many Rename)) (all Bool) (excluded (many Word)) (selected (many Word)))
(refer-policy access Use (selection all selected name) (exclude excluded name) (rename renamed exported local))
'''
records = []
with tempfile.TemporaryDirectory(prefix='rewrite-refer-') as directory:
    work = Path(directory)
    for name in ['types', 'scope', 'resolution', 'source', 'sequence', 'refer_runtime', 'selection_runtime']:
        shutil.copyfile(ROOT/f'seed/{name}.coil', work/f'{name}.coil')
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for alternate, schema in [(False, base), (True, other)]:
        generated = subprocess.check_output([str(compiler)], input=schema.encode())
        driver = fixture(alternate)
        (work/'generated.coil').write_bytes(generated)
        (work/'main.coil').write_text(driver)
        for flags in [[], ['--debug-checks'], ['--release']]:
            result = subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            assert result.stdout == expected, (alternate, flags, result.stdout[:4000], expected[:4000])
        records.append(dict(alternate_layout=alternate, schema_sha256=hashlib.sha256(schema.encode()).hexdigest(),
                            driver_sha256=hashlib.sha256(driver.encode()).hexdigest(),
                            generated_sha256=hashlib.sha256(generated).hexdigest(), configurations_passed=3))
for source, message in [
    (base.replace('imports Refer', 'bad/name Refer'), 'expected (refer-policy'),
    (base.replace('imports Refer', 'imports Missing'), 'unknown refer record'),
    (base + '(refer-policy imports Refer (selection all selected text) (exclude excluded text) (rename renames exported local))', 'duplicate refer policy'),
    (base.replace('(selection all selected text)', '(selection all selected)'), 'expected selection, exclude and rename'),
    (base.replace('(selection all selected text)', '(selection missing selected text)'), 'unknown refer field'),
    (base.replace('(all Bool)', '(all Int)'), 'refer field has wrong scalar type'),
    (base.replace('(selected (many Name))', '(selected Name)'), 'refer collections must contain records'),
    (base.replace('(text Text)', '(text Int)'), 'refer field has wrong scalar type'),
    (base.replace('(node Name (text Text))', '(sum Name (Named (text Text)))'), 'refer policy fields need records'),
    (base.replace('(rename renames exported local)', '(rename renames exported missing)'), 'unknown refer field'),
]:
    result = subprocess.run([str(compiler)], input=source.encode(), capture_output=True)
    assert result.returncode != 0 and not result.stdout and message.encode() in result.stderr, result
replay = dict(scope='Owned generated refer indexes versus extracted reference helpers; not full import parser or namespace resolver parity.',
              reference_sha256=hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
              replay_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              expected_output_sha256=hashlib.sha256(expected.encode()).hexdigest(),
              policies=len(evidence['cases']), queries=len(expected.splitlines()), layouts=records)
(ROOT/'evidence/refer-replay.json').write_text(json.dumps(replay, indent=2)+'\n')
print(f'Refer policies: {len(evidence["cases"])} captured policies, {len(expected.splitlines())} queries, two layouts and three configurations passed')
