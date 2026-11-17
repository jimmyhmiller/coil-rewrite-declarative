#!/usr/bin/env python3
"""Replay captured use-tier results through production declared selection."""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
EXPORT = runpy.run_path(str(ROOT/'tools/check-export.py'))
q, names, graph_data = (EXPORT[n] for n in ['q', 'names', 'data'])


def imports_data(edges):
    rows = []
    for e in edges:
        renames = '[' + ' '.join(f'(Rename {q(k)} {q(v)})' for k,v in e['renames']) + ']'
        rows.append(f'(Reexport {q(e["target"])} (Refer {str(e["all"]).lower()} {names(e["selected"])} {names(e["excluded"])} {renames}))')
    return f'(Imports [{" ".join(rows)}])'


def fixture(graphs):
    body = ['''(module fixture.main)
(import "rewrite.namespace" :as namespace)
(import "rewrite.nameforms" :as forms)
(import "coil.alloc" :use *)
(import "coil.arraylist" :use *)
(import "coil.reader" :use *)
(import "coil.scratch" :use [ScratchArena])
(import "coil.debug-allocator" :use [DebugAllocator])
(import "coil.result" :use *)
(defn query [(a (dyn Allocator)) (view (ptr namespace/View)) (uses (ptr (ArrayList namespace/Edge))) (name (slice u8)) (macro? bool)] (-> void)
  (match (namespace/used a view uses name macro?)
    (Err [error] (match error (namespace/Ambiguous [first next] (println "ambiguous|{}|{}" (.f0 first) (.f0 next))) (_ (panic "export failure"))))
    (Ok [answer] (match answer (None [] (println "none"))
      (Some [candidate] (if macro?
        (println "hit|{}|{}|{}|{}" (.f2 candidate) (.f0 candidate) (.f1 candidate) (.f2 candidate))
        (println "hit|{}" (.f2 candidate))))))))
(defn parse-imports [(a (dyn Allocator)) (store (ptr forms/Store)) (text (slice u8))] (-> forms/N9Id)
  (let [input (match (read-all a text 0) (Ok [forms] forms) (Err [_] (panic "uses read")))]
    (match (forms/parse-9 store (elem input 0)) (Ok [id] id) (Err [_] (panic "uses parse")))))
(defn check [(a (dyn Allocator))] (-> void)
''']
    for graph in graphs:
        body.append(f'''(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a)
            sa (allocator (mut scratch)) (mut store) (forms/store-new a)
            (mut roots) (ArrayList::new [forms/N9Id] a)
            input (match (read-all sa {q(graph_data(graph))} 0) (Ok [forms] forms) (Err [_] (panic "graph read")))
            root (match (forms/parse-7 (mut store) (elem input 0)) (Ok [id] id) (Err [_] (panic "graph parse")))]
            (defer (close! (mut scratch))) (defer (forms/store-free! (mut store))) (defer (free! (mut roots)))''')
        # Complete the store before constructing an immutable borrowing view.
        for use in graph['uses']:
            body.append(f'(push! (mut roots) (parse-imports sa (mut store) {q(imports_data(use["edges"]))}))')
        body.append('''(let [(mut view) (match (namespace/compile a (mut store) root) (Ok [v] v) (Err [_] (panic "view")))]
           (defer (namespace/release! (mut view)))''')
        for i,use in enumerate(graph['uses']):
            body.append(f'''(let [(mut uses) (match (namespace/compile-uses a (mut store) (get roots {i})) (Ok [uses] uses) (Err [_] (panic "use build")))]
              (defer (namespace/release-edges! (mut uses)))''')
            for name in use['queries']:
                for macro in [False, True]:
                    body.append(f'(query a (mut view) (mut uses) {q(name)} {str(macro).lower()})')
            body.append(')')
        body.append('))')
    body.append(''')
(defn main [] (-> i64)
  (let [debug (DebugAllocator::new (malloc-allocator))]
    (check (DebugAllocator::view debug))
    (unless (= (DebugAllocator::deinit! debug) 0) (panic "use replay leak"))) 0)
''')
    return '\n'.join(body)


def main():
    reference = ROOT/'evidence/use-reference.json'
    graphs = json.loads(reference.read_text())['cases']
    assert graphs and all(len(u['answers']) == 2*len(u['queries']) for g in graphs for u in g['uses'])
    expected = [a for g in graphs for u in g['uses'] for a in u['answers']]
    driver = fixture(graphs)
    inputs = [ROOT/f'seed/{name}.coil' for name in ['types','scope','resolution','source','sequence','refer_runtime','selection_runtime','namespace','search_runtime']]
    inputs += [ROOT/'seed/generated/name_forms.coil', ROOT/'seed/generated/export_search.coil']
    with tempfile.TemporaryDirectory(prefix='rewrite-use-') as directory:
        work = Path(directory)
        (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
        for path in inputs:
            shutil.copyfile(path, work/path.name)
        (work/'main.coil').write_text(driver)
        for flags in [[], ['--debug-checks'], ['--release']]:
            result = subprocess.run(['coil','run','main.coil',*flags], cwd=work, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            actual = result.stdout.splitlines()
            assert len(actual) == len(expected), (flags,len(actual),len(expected))
            for i,(a,b) in enumerate(zip(actual,expected)):
                assert a == b, (flags,i,a,b)
    report = dict(scope='Use-tier selected target, macro provenance and ambiguity-owner replay. No full source resolver, diagnostic text or route publication claim.',
                  graphs=len(graphs), results=len(expected), reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
                  driver_sha256=hashlib.sha256(driver.encode()).hexdigest(),
                  implementation_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                  configurations_passed=['default','debug-checks','release'])
    (ROOT/'evidence/use-replay.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Use replay: {len(graphs)} graphs, {len(expected)} matching outcomes/provenance records; three configurations; no allocator leaks')


if __name__ == '__main__':
    main()
