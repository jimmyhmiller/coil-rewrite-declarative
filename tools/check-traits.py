#!/usr/bin/env python3
"""Replay trait-availability capture through generated views and incremental indexes."""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
helpers=runpy.run_path(str(ROOT/'tools/capture-trait-reference.py'))
q,normalize=helpers['q'],helpers['normalize']
reference=ROOT/'evidence/trait-reference.json';cases=json.loads(reference.read_text())['cases']
HEADER='''(module fixture.main)
(import "rewrite.traitdeclarations" :as traits)
(import "rewrite.namespace" :as namespace)
(import "rewrite.nameforms" :as forms)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *) (import "coil.hashmap" :use *)
(import "coil.scratch" :use [ScratchArena]) (import "coil.debug-allocator" :use [DebugAllocator])
'''
body=['(defn main [] (-> i64) (let [debug (DebugAllocator::new (malloc-allocator)) a (DebugAllocator::view debug)]']
for i,c in enumerate(cases):
    module='(None [(slice u8)])' if c['module'] is None else f'(Some {q(c["module"])})'
    body.append(f'''(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a) sa (allocator (mut scratch))
      (mut store) (forms/store-new a)
      input (match (read-all sa {q(c['source'])} 1) (Ok [v] v) (Err [_] (panic "source")))
      graph (match (read-all sa "(Namespace [] [] [])" 0) (Ok [v] v) (Err [_] (panic "graph")))
      root (match (forms/parse-7 (mut store) (elem graph 0)) (Ok [v] v) (Err [_] (panic "root")))
      (mut view) (match (namespace/compile a (mut store) root) (Ok [v] v) (Err [_] (panic "view")))]
      (defer (close! (mut scratch))) (defer (forms/store-free! (mut store))) (defer (namespace/release! (mut view)))
      (unless (= (traits/observe! sa (mut view) (elem input 0) {module}) {len(c['names'])}) (panic "wrong new membership count"))
      (unless (= (traits/observe! sa (mut view) (elem input 0) {module}) 0) (panic "repeated observation changed membership"))
      (println "case|{i}")
      (for name (.introduced-index view)
        (match (namespace/declaration (mut view) name) (None [] (panic "introduced name absent")) (Some [canonical] (unless (= name canonical) (panic "wrong canonical name"))))
        (println "name|{{}}" name)))''')
body.append('(unless (= (DebugAllocator::deinit! debug) 0) (panic "trait publication leak"))) 0)')
driver=HEADER+'\n'.join(body)
runtime=['types','scope','resolution','source','sequence','refer_runtime','selection_runtime','namespace','search_runtime','equality_runtime','trait_declarations']
generated=['name_forms','export_search','code_forms']
inputs=[ROOT/f'seed/{n}.coil' for n in runtime]+[ROOT/f'seed/generated/{n}.coil' for n in generated]
with tempfile.TemporaryDirectory(prefix='rewrite-traits-') as directory:
    work=Path(directory);(work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for path in inputs:shutil.copyfile(path,work/path.name)
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:
        r=subprocess.run(['coil','run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        actual=normalize(r.stdout,len(cases))
        for i,(observed,case) in enumerate(zip(actual,cases)):
            if observed!=case['names']:raise RuntimeError((flags,i,observed,case))
digest=lambda value:hashlib.sha256(value).hexdigest()
host=Path(shutil.which('coil')).resolve(strict=True)
evidence=dict(scope='Trait availability membership, idempotent introduction and direct declaration lookup against exact helper capture; not full declaration validation, parent-session integration or generated-form admission.',
              cases=len(cases),configurations=['default','debug-checks','release'],allocator_leaks=0,
              host_version=subprocess.check_output([str(host),'--version'],text=True).strip(),host_sha256=digest(host.read_bytes()),
              reference_sha256=digest(reference.read_bytes()),driver_sha256=digest(driver.encode()),
              inputs={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs+[Path(__file__),ROOT/'compiler/syntax/code.schema']})
(ROOT/'evidence/trait-replay.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(f'Trait availability replay: {len(cases)} cases, three configurations, idempotent publication and no allocator leaks')
