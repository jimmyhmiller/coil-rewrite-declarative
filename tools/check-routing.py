#!/usr/bin/env python3
"""Replay captured route and scoped-head answers and selected provenance."""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
E=runpy.run_path(str(ROOT/'tools/check-export.py'))
U=runpy.run_path(str(ROOT/'tools/check-use.py'))
q,names=E['q'],E['names']


def refer(e):
    renamed='['+' '.join(f'(Rename {q(k)} {q(v)})' for k,v in e['renames'])+']'
    return f'(Refer {str(e["all"]).lower()} {names(e["selected"])} {names(e["excluded"])} {renamed})'


def world_data(g):
    modules=[]
    for m in g['imports']:
        aliases='['+' '.join(f'(ImportAlias {q(k)} {q(v)})' for k,v in m['aliases'])+']'
        modules.append(f'(ModuleImports {q(m["name"])} {aliases} {U["imports_data"](m["uses"])} {refer(m["core"])})')
    providers='['+' '.join(f'(Provider {q(n)} {q(o)} {str(r).lower()})' for n,o,r in g['providers'])+']'
    return f'(Routing [{" ".join(modules)}] {providers} {names(g["declared"])} {names(g["toolchain"])} {q(g["prelude"])})'


HEADER='''(module fixture.main)
(import "rewrite.routing" :as routing)
(import "rewrite.sourceroutes" :as records)
(import "rewrite.observedresolution" :as observed)
(import "coil.hashmap" :use *)
(import "coil.primitive" :as primitive)
(import "rewrite.resolveprotocol" :as protocol)
(import "rewrite.routingfacts" :as facts)
(import "rewrite.namespace" :as namespace)
(import "rewrite.nameforms" :as forms)
(import "rewrite.macrohead" :as head)
(import "rewrite.code" :as code)
(import "rewrite.codeforms" :as syntax)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena]) (import "coil.debug-allocator" :use [DebugAllocator])
(defn print-answer [(answer routing/Answer) (spelling (slice u8)) (module (Option (slice u8)))] (-> void)
  (match (.target answer)
    (None [] (match (.route answer) (None []) (_ (panic "missing route"))) (println "none"))
    (Some [target] (match (.route answer)
      (None [] (println "hit|{}" target))
      (Some [r] (println "hit|{}|{}|{}|{}|{}|{}" target (match module (Some [m] m) (None [] "")) spelling (.f0 r) (.f1 r) (.f2 r)))))))
(defn check-record [(table (ptr records/Table)) (spelling (slice u8)) (module (Option (slice u8))) (answer routing/Answer)] (-> void)
  (match (.route answer)
    (None [] (unless (= (len (.routes table)) 0) (panic "unexpected published route")))
    (Some [candidate]
      (unless (= (len (.routes table)) 1) (panic "wrong route count"))
      (match (records/lookup table (match module (Some [m] m) (None [] "")) spelling 6)
        (None [] (panic "missing published route"))
        (Some [value] (unless (and (= (.f0 value) (.f0 candidate)) (= (.f1 value) (.f1 candidate)) (= (.f2 value) (.f2 candidate))) (panic "wrong published provenance")))))))
(defn query [(a (dyn Allocator)) (view (ptr namespace/View)) (world (ptr facts/World))
             (spelling (slice u8)) (module (Option (slice u8))) (macro? bool)] (-> void)
  (let [(mut table) (records/create a)]
    (defer (records/release! (mut table))) (records/start! (mut table))
    (match (observed/resolve! a (mut table) view world spelling module macro?)
      (Ok [answer] (check-record (mut table) spelling module answer) (print-answer answer spelling module))
      (Err [e]
        (unless (= (len (.routes table)) 0) (panic "error published a route"))
        (match e
          (protocol/HandlerError [_ error] (match error
            (routing/Use [error] (match error
              (namespace/Ambiguous [first next] (println "ambiguous|{}|{}" (.f0 first) (.f0 next)))
              (_ (panic "wrong use error"))))
            (_ (panic "wrong route error"))))
          (_ (panic "protocol failure")))))))
(defn query-head [(a (dyn Allocator)) (view (ptr namespace/View)) (world (ptr facts/World))
                  (name (slice u8)) (scope i64) (definition (slice u8)) (fallback (Option (slice u8)))] (-> void)
  (let [(mut table) (records/create a) (mut input) (code/create a)
        id (syntax/append-0 (mut (.rows0 (.store input))) (syntax/N0V2 (syntax/store-text! (mut (.store input)) name)))]
    (defer (code/release! (mut input)))
    (defer (records/release! (mut table))) (records/start! (mut table))
    (push! (mut (.contexts input)) (syntax/N1Row :f0 scope :f1 (syntax/store-text! (mut (.store input)) definition) :f2 0 :f3 0 :f4 0 :f5 0))
    (let [(mut output) (observed/macro-head! a (mut table) view world (mut input) id fallback)]
      (defer (head/release! (mut output)))
      (match (.result output) (Err [_] (panic "head error"))
        (Ok [answer] (check-record (mut table) (.spelling output) (.module output) answer) (print-answer answer (.spelling output) (.module output)))))))
(defn query-reader-head [(a (dyn Allocator)) (view (ptr namespace/View)) (world (ptr facts/World))
                         (name (slice u8)) (scope i64) (definition (slice u8)) (fallback (Option (slice u8)))] (-> void)
  (let [(mut table) (records/create a) (mut module) (HygModule :name definition)
        (mut form) (mk-sexp (KSym name) 0 0)]
    (defer (records/release! (mut table))) (records/start! (mut table))
    (set! (.hyg form) scope)
    (set! (.hmod form) (primitive/cast (ptr HygModule) (mut module)))
    (let [(mut output) (observed/reader-head! a (mut table) view world form fallback)]
      (defer (head/release! (mut output)))
      (match (.result output) (Err [_] (panic "reader head error"))
        (Ok [answer] (check-record (mut table) (.spelling output) (.module output) answer) (print-answer answer (.spelling output) (.module output)))))))
(defn check [(a (dyn Allocator))] (-> void)
'''


def fixture(graphs):
    b=[HEADER]
    for g in graphs:
        source=E['data'](g)+'\n'+world_data(g)
        b.append(f'''(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a) sa (allocator (mut scratch))
          (mut store) (forms/store-new a) input (match (read-all sa {q(source)} 0) (Ok [forms] forms) (Err [_] (panic "read")))
          root (match (forms/parse-7 (mut store) (elem input 0)) (Ok [id] id) (Err [_] (panic "graph")))
          route-root (match (forms/parse-13 (mut store) (elem input 1)) (Ok [id] id) (Err [_] (panic "facts")))]
          (defer (close! (mut scratch))) (defer (forms/store-free! (mut store)))
          (let [(mut view) (match (namespace/compile a (mut store) root) (Ok [v] v) (Err [_] (panic "view")))
                (mut world) (match (facts/compile a (mut store) route-root) (Ok [v] v) (Err [_] (panic "world")))]
            (defer (namespace/release! (mut view))) (defer (facts/release! (mut world)))''')
        for name,module,macro in g['route_queries']:
            md='(None [(slice u8)])' if module is None else f'(Some {q(module)})'
            b.append(f'(query a (mut view) (mut world) {q(name)} {md} {str(macro).lower()})')
        for name,scope,definition,fallback in g['head_queries']:
            md='(None [(slice u8)])' if fallback is None else f'(Some {q(fallback)})'
            b.append(f'(query-head a (mut view) (mut world) {q(name)} {scope} {q(definition)} {md})')
            b.append(f'(query-reader-head a (mut view) (mut world) {q(name)} {scope} {q(definition)} {md})')
        b.append('))')
    b.append(''')
(defn main [] (-> i64) (let [debug (DebugAllocator::new (malloc-allocator))]
  (check (DebugAllocator::view debug)) (unless (= (DebugAllocator::deinit! debug) 0) (panic "routing replay leak"))) 0)
''')
    return '\n'.join(b)


def main():
    reference=ROOT/'evidence/routing-reference.json';graphs=json.loads(reference.read_text())['cases']
    assert graphs and all(len(g['answers'])==len(g['route_queries'])+len(g['head_queries']) for g in graphs)
    expected=[]
    for g in graphs:
        count=len(g['route_queries'])
        expected.extend(g['answers'][:count])
        expected.extend(v for answer in g['answers'][count:] for v in [answer,answer])
    driver=fixture(graphs)
    runtime=['types','scope','resolution','source','sequence','refer_runtime','selection_runtime','namespace','search_runtime','routing','routing_facts','lexical','macro_head','code','equality_runtime','source_routes','observed_resolution']
    generated=['name_forms','export_search','resolve_protocol','head_protocol','code_forms']
    inputs=[ROOT/f'seed/{n}.coil' for n in runtime]+[ROOT/f'seed/generated/{n}.coil' for n in generated]
    with tempfile.TemporaryDirectory(prefix='rewrite-routing-') as directory:
        work=Path(directory);(work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
        for path in inputs: shutil.copyfile(path,work/path.name)
        (work/'main.coil').write_text(driver)
        for flags in [[],['--debug-checks'],['--release']]:
            r=subprocess.run(['coil','run','main.coil',*flags],cwd=work,capture_output=True,text=True)
            assert r.returncode==0,r.stdout+r.stderr
            actual=r.stdout.splitlines();assert len(actual)==len(expected),(flags,len(actual),len(expected))
            for i,(a,b) in enumerate(zip(actual,expected)): assert a==b,(flags,i,a,b)
    report=dict(scope='Resolver/head helper replay including selected route metadata; all captured scoped heads run through both owned-row and reader-symbol entry points. Published route contents checked per query. Source parsing, diagnostic text, memo invalidation and complete source-facts lifecycle parity remain outside scope.',graphs=len(graphs),outcomes=len(expected),reference_outcomes=sum(len(g['answers']) for g in graphs),additional_reader_head_replays=sum(len(g['head_queries']) for g in graphs),reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),driver_sha256=hashlib.sha256(driver.encode()).hexdigest(),implementation_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},configurations_passed=['default','debug-checks','release'])
    (ROOT/'evidence/routing-replay.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Routing/head replay: {len(graphs)} graphs, {len(expected)} matching outcomes/provenance records; three configurations; no allocator leaks')


if __name__=='__main__':main()
