#!/usr/bin/env python3
"""Replay real type-parser acceptance through declared written syntax."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
reference=ROOT/'evidence/type-reference.json'
cases=json.loads(reference.read_text())['cases']
q=lambda s:json.dumps(s,ensure_ascii=False)
driver='''(module fixture.main)
(import "rewrite.typesyntax" :use *)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena]) (import "coil.debug-allocator" :use [DebugAllocator])
(defn main [] (-> i64)
(let [debug (DebugAllocator::new (malloc-allocator)) a (DebugAllocator::view debug)]
'''
for i,c in enumerate(cases):
    driver+=f'''(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a) sa (allocator (mut scratch))
(mut store) (store-new a)
input (match (read-all sa {q(c['type'])} 1) (Ok [v] v) (Err [_] (panic "reader")))
accepted (match (surface-3 (mut store) (elem input 0)) (Ok [_] true) (Err [_] false))]
(defer (close! (mut scratch))) (defer (store-free! (mut store)))
(println "case|{i}|{{}}" accepted))\n'''
driver+='''(unless (= (DebugAllocator::deinit! debug) 0) (panic "type syntax leak"))) 0)'''
inputs=[ROOT/f'seed/{n}.coil' for n in ['types','scope','resolution','source','sequence','equality_runtime','lexical','text_runtime']]+[ROOT/'seed/generated/type_syntax.coil']
with tempfile.TemporaryDirectory(prefix='rewrite-type-syntax-') as directory:
    work=Path(directory);(work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for p in inputs:shutil.copyfile(p,work/p.name)
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:
        r=subprocess.run(['coil','run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        actual=r.stdout.splitlines()
        expected=[f'case|{i}|'+('true' if c['exit_code']==0 else 'false') for i,c in enumerate(cases)]
        if actual!=expected:
            raise RuntimeError([(cases[i]['type'],a,b) for i,(a,b) in enumerate(zip(actual,expected)) if a!=b]+[('counts',len(actual),len(expected))])
digest=lambda value:hashlib.sha256(value).hexdigest()
host=Path(shutil.which('coil')).resolve(strict=True)
evidence=dict(scope='Written type grammar acceptance only against real parser capture. Classified graph comparison has separate evidence; this result does not establish source-site effects or exact diagnostic equivalence.',cases=len(cases),configurations=['default','debug-checks','release'],allocator_leaks=0,host_version=subprocess.check_output([str(host),'--version'],text=True).strip(),host_sha256=digest(host.read_bytes()),reference_sha256=digest(reference.read_bytes()),driver_sha256=digest(driver.encode()),inputs={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs+[Path(__file__),ROOT/'languages/type_syntax.schema']})
(ROOT/'evidence/type-syntax-replay.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(f'Written type syntax: {len(cases)} acceptance results match real parser capture in three configurations; no allocator leaks')
