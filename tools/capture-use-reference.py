#!/usr/bin/env python3
"""Capture exact use selection, ambiguity owners and selected macro provenance."""
import argparse
import json
from pathlib import Path
import random
import re
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPORT = runpy.run_path(str(ROOT/'tools/capture-export-reference.py'))
q, digest, definition, edge = (EXPORT[n] for n in ['q', 'digest', 'definition', 'edge'])


def cases():
    graphs = EXPORT['cases']()
    rng = random.Random(749331)
    for graph in graphs:
        graph['queries'] = []
        owners = [m['name'] for m in graph['modules']]
        graph['uses'] = []
        for _ in range(10):
            edges = [edge(rng.choice(owners), bool(rng.randrange(2)), rng.sample(['a', 'b', 'x'], rng.randrange(4)),
                          rng.sample(['a', 'b', 'x'], rng.randrange(3)),
                          [(rng.choice(['a', 'b', 'λ']), rng.choice(['a', 'x', 'λ'])) for _ in range(rng.randrange(3))])
                     for _ in range(rng.randrange(6))]
            graph['uses'].append(dict(edges=edges, queries=['a', 'b', 'x', 'λ', 'missing']))
    graphs[0]['modules'].append(EXPORT['module']('pass', edges=[edge('base')]))
    rename = lambda owner, old: edge(owner, False, renames=[(old, 'x')])
    targeted = [[], [edge('base'), edge('other')], [edge('pass'), edge('base')],
                [rename('base', 'a'), rename('base', 'b')],
                [rename('base', 'a'), rename('base', 'b'), rename('other', 'a')],
                [rename('base', 'a'), rename('pass', 'a'), rename('pass', 'b')],
                [edge('base', False), edge('other')], [edge('base', excluded=['a']), edge('other')]]
    graphs[0]['uses'][:0] = [dict(edges=edges, queries=['a', 'b', 'x', 'missing']) for edges in targeted]
    return graphs


EXTRA = '''
; Fixture diagnostic transport retains only ambiguity owners, not rendered text.
(defstruct Diag [(msg (slice u8))])
(defn derr [(text (slice u8))] (-> Diag) (Diag :msg text))
(defn use-ambig-msg [(a (dyn Allocator)) (module (slice u8)) (name (slice u8)) (first (slice u8)) (next (slice u8))] (-> (slice u8))
  (sconcat3 a first "|" next))
(defstruct Route [(owner (slice u8)) (exported (slice u8)) (target (slice u8)) (count i64)])
(defn route [] (-> (ptr Route)) (primitive/alloc-static Route))
(defn macro-mode [] (-> (ptr bool)) (primitive/alloc-static bool))
(defn expected-head [] (-> (ptr (slice u8))) (primitive/alloc-static (slice u8)))
(defn macro-space? [(space (ptr NameSpace))] (-> bool) (load (macro-mode)))
(defn source-route-record! [(module (slice u8)) (head (slice u8)) (kind i64) (owner (slice u8)) (exported (slice u8)) (target (slice u8))] (-> i64)
  (unless (and (= module "asking") (= head (load (expected-head))) (= kind 6)) (panic "unexpected route identity"))
  (store! (route) (Route :owner owner :exported exported :target target :count (+ (.count (route)) 1))) 0)
(defn print-use [(result (Result (Option (slice u8)) Diag))] (-> void)
  (match result
    (Err [error] (unless (= (.count (route)) 0) (panic "ambiguous route published")) (println "ambiguous|{}" (.msg error)))
    (Ok [value]
      (match value
        (None [] (unless (= (.count (route)) 0) (panic "missing route published")) (println "none"))
        (Some [target]
          (if (load (macro-mode))
            (do (unless (= (.count (route)) 1) (panic "macro route count"))
                (println "hit|{}|{}|{}|{}" target (.owner (route)) (.exported (route)) (.target (route))))
            (do (unless (= (.count (route)) 0) (panic "nominal route published")) (println "hit|{}" target))))))))
'''


def queries(graph):
    body = []
    for use in graph['uses']:
        body.append('(let [(mut edges) (ArrayList::new [Use] a)]')
        for e in use['edges']:
            body.append('''(let [selected (boxed a (ArrayList::new [(slice u8)] a)) excluded (boxed a (ArrayList::new [(slice u8)] a)) renamed (boxed a (ArrayList::new [Rename] a))]''')
            for key, variable in [('selected', 'selected'), ('excluded', 'excluded')]:
                for name in e[key]:
                    body.append(f'(push! {variable} {q(name)})')
            for old, new in e['renames']:
                body.append(f'(push! renamed (Rename :from {q(old)} :to {q(new)}))')
            body.append(f'(push! (mut edges) (Use :target {q(e["target"])} :spec {"(UAll)" if e["all"] else "(UNames selected)"} :exclude excluded :renames renamed)))')
        body.append('(let [(mut asking) (ImpEntry :name "asking" :imp (ModImports :reexports (ArrayList::new [Use] a) :uses edges) :edit 0)]')
        for name in use['queries']:
            for macro in [False, True]:
                body.append(f'(store! (route) (zeroed Route)) (store! (macro-mode) {str(macro).lower()}) (store! (expected-head) {q(name)})')
                body.append(f'(print-use (space-use-match (mut imports) (mut asking) (mut space) (mut exports) {q(name)} a))')
        body.append('))')
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--compiler', default='coil')
    args = parser.parse_args()
    compiler = Path(shutil.which(args.compiler) or args.compiler).resolve(strict=True)
    version = subprocess.check_output([str(compiler), '--version'], text=True).strip()
    revision = re.search(r'commit ([0-9a-f]+)', version).group(1)
    revision = subprocess.check_output(['git', 'rev-parse', revision], cwd=args.reference, text=True).strip()
    sources = {name: subprocess.check_output(['git', 'show', f'{revision}:src/compiler/frontend/{name}.coil'], cwd=args.reference).decode()
               for name in ['loader', 'resolve', 'expander', 'ast']}
    helpers = {name: definition(sources[source], name) for source, names in [
        ('loader', ['UseSpec', 'Rename', 'Use', 'ImpEntry', 'ExpEntry', 'use-refers']),
        ('resolve', ['set-contains', 'imports-find', 'exports-check']),
        ('ast', ['DeclAliasEntry', 'decl-alias-target']),
        ('expander', ['space-exported', 'space-none', 'space-some', 'space-use-match'])] for name in names}
    graphs = cases()
    header = EXPORT['HEADER'].replace('(defstruct ModImports [(reexports (ArrayList Use))])', '(defstruct ModImports [(reexports (ArrayList Use)) (uses (ArrayList Use))])') + EXTRA
    driver = EXPORT['fixture'](graphs, helpers, header=header, after_graph=queries,
                               import_value='(ModImports :reexports edges :uses (ArrayList::new [Use] a))')
    work = ROOT/'build/use-reference'
    work.mkdir(parents=True, exist_ok=True)
    (work/'Coil.toml').write_text('[package]\nname="reference"\nentry="main.coil"\nsource-roots=["."]\n')
    (work/'main.coil').write_text(driver)
    outputs = []
    for flags in [[], ['--debug-checks'], ['--release']]:
        result = subprocess.run([str(compiler), 'run', 'main.coil', *flags], cwd=work, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        outputs.append(result.stdout)
    assert len(set(outputs)) == 1, 'reference configurations disagree'
    answers = outputs[0].splitlines()
    assert len(answers) == sum(2*len(u['queries']) for g in graphs for u in g['uses'])
    cursor = 0
    for graph in graphs:
        for use in graph['uses']:
            count = 2*len(use['queries'])
            use['answers'] = answers[cursor:cursor+count]
            cursor += count
    report = dict(scope='Exact space-use-match/export helpers, ambiguity owners and selected macro provenance. Fixture membership, namespace mode, diagnostic transport and route recorder; not full source import/resolver or diagnostic text parity.',
                  compiler_version=version, compiler_sha256=digest(compiler.read_bytes()), reference_revision=revision,
                  source_sha256={n: digest(s.encode()) for n,s in sources.items()}, helper_sha256={n: digest(s.encode()) for n,s in helpers.items()},
                  driver_sha256=digest(driver.encode()), capture_script_sha256=digest(Path(__file__).read_bytes()),
                  shared_fixture_sha256=digest((ROOT/'tools/capture-export-reference.py').read_bytes()),
                  configurations=['default', 'debug-checks', 'release'], cases=graphs)
    (ROOT/'evidence/use-reference.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(f'Reference use lookup: {len(graphs)} graphs, {len(answers)} results and macro-route checks, three matching configurations')


if __name__ == '__main__':
    main()
