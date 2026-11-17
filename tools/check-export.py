#!/usr/bin/env python3
"""Replay reference export graphs through the declared production search."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def q(value):
    return json.dumps(value, ensure_ascii=False)


def names(values):
    return '[' + ' '.join(f'(Name {q(v)})' for v in values) + ']'


def data(graph):
    declarations = '[' + ' '.join(f'(Declaration {q(v)})' for v in graph['declarations']) + ']'
    aliases = '[' + ' '.join(f'(Alias {q(k)} {q(v)})' for k, v in graph['aliases']) + ']'
    modules = []
    for mod in graph['modules']:
        edges = []
        for e in mod['edges']:
            renames = '[' + ' '.join(f'(Rename {q(k)} {q(v)})' for k, v in e['renames']) + ']'
            edges.append(f'(Reexport {q(e["target"])} (Refer {str(e["all"]).lower()} {names(e["selected"])} {names(e["excluded"])} {renames}))')
        modules.append(f'(ExportModule {q(mod["name"])} {str(mod["exports"] is not None).lower()} {names(mod["exports"] or [])} [{" ".join(edges)}])')
    return f'(Namespace {declarations} {aliases} [{" ".join(modules)}])'


def fixture(graphs):
    body = ['''(module fixture.main)
(import "rewrite.namespace" :as namespace)
(import "rewrite.nameforms" :as forms)
(import "rewrite.searchruntime" :as search)
(import "coil.alloc" :use *)
(import "coil.arraylist" :use *)
(import "coil.reader" :use *)
(import "coil.scratch" :use [ScratchArena])
(import "coil.debug-allocator" :use [DebugAllocator])
(import "coil.result" :use *)
(defn query [(a (dyn Allocator)) (view (ptr namespace/View)) (owner (slice u8)) (name (slice u8)) (depth i64)] (-> void)
  (let [(mut stats) (search/Stats :expanded 0 :cached 0)]
    (match (namespace/exported a view owner name depth (mut stats))
      (Err [_] (panic "query failure"))
      (Ok [answer] (println "{}" (match answer (Some [value] value) (None [] "-")))))))
(defn check [(a (dyn Allocator))] (-> void)
''']
    for graph in graphs:
        body.append(f'''(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a)
            sa (allocator (mut scratch)) (mut store) (forms/store-new a)
            input (match (read-all sa {q(data(graph))} 0) (Ok [forms] forms) (Err [_] (panic "read")))
            root (match (forms/parse-7 (mut store) (elem input 0)) (Ok [id] id) (Err [_] (panic "parse")))]
            (defer (close! (mut scratch))) (defer (forms/store-free! (mut store)))
            (let [(mut view) (match (namespace/compile a (mut store) root) (Ok [view] view) (Err [_] (panic "view")))]
                (defer (namespace/release! (mut view)))''')
        for owner, name, depth in graph['queries']:
            body.append(f'(query a (mut view) {q(owner)} {q(name)} {depth})')
        body.append('))')
    body.append(''')
(defn main [] (-> i64)
  (let [debug (DebugAllocator::new (malloc-allocator))]
    (check (DebugAllocator::view debug))
    (unless (= (DebugAllocator::deinit! debug) 0) (panic "export replay leak"))) 0)
''')
    return '\n'.join(body)


def main():
    reference = ROOT/'evidence/export-reference.json'
    evidence = json.loads(reference.read_text())
    graphs = evidence['cases']
    assert graphs and all(len(g['queries']) == len(g['answers']) for g in graphs)
    expected = ''.join(f'{v if v is not None else "-"}\n' for g in graphs for v in g['answers'])
    driver = fixture(graphs)
    runtimes = ['types', 'scope', 'resolution', 'source', 'sequence', 'refer_runtime', 'namespace', 'search_runtime']
    inputs = [ROOT/f'seed/{name}.coil' for name in runtimes] + [ROOT/'seed/generated/name_forms.coil', ROOT/'seed/generated/export_search.coil']
    with tempfile.TemporaryDirectory(prefix='rewrite-export-') as directory:
        work = Path(directory)
        (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
        for path in inputs:
            shutil.copyfile(path, work/path.name)
        (work/'main.coil').write_text(driver)
        for flags in [[], ['--debug-checks'], ['--release']]:
            result = subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            actual = result.stdout.splitlines()
            wanted = expected.splitlines()
            assert len(actual) == len(wanted), (flags, len(actual), len(wanted))
            for i, (a, b) in enumerate(zip(actual, wanted)):
                assert a == b, (flags, i, a, b)
    report = dict(scope='Export helper graph replay, not full source resolver parity.', graphs=len(graphs), queries=len(expected.splitlines()),
                  reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
                  driver_sha256=hashlib.sha256(driver.encode()).hexdigest(),
                  implementation_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                  configurations_passed=['default', 'debug-checks', 'release'])
    (ROOT/'evidence/export-replay.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Export replay: {report["graphs"]} graphs, {report["queries"]} matching queries in three configurations; no allocator leaks')


if __name__ == '__main__':
    main()
