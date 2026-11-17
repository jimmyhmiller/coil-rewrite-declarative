#!/usr/bin/env python3
"""Replay primitive-name observations with owned text surviving reader teardown."""
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
helpers = runpy.run_path(str(ROOT/'tools/capture-function-reference.py'))
q, normalize = helpers['q'], helpers['normalize']
reference = ROOT/'evidence/function-reference.json'
cases = json.loads(reference.read_text())['cases']
driver = '''(module fixture.main)
(import "rewrite.functionnames" :as functions)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena]) (import "coil.debug-allocator" :use [DebugAllocator])
(defn main [] (-> i64)
(let [debug (DebugAllocator::new (malloc-allocator)) a (DebugAllocator::view debug)]
'''
for i,c in enumerate(cases):
    module = '(None [(slice u8)])' if c['module'] is None else f'(Some {q(c["module"])})'
    driver += f'''(let [(mut names) (functions/create a)]
(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a) sa (allocator (mut scratch))
input (match (read-all sa {q(c['source'])} 1) (Ok [v] v) (Err [_] (panic "source")))]
(defer (close! (mut scratch)))
(for [j 0 (len input)] (functions/observe! sa (mut names) (elem input j) {module})))
(println "case|{i}") (for [j 0 (len (.items names))] (println "name|{{}}" (get (.items names) j)))
(functions/release! (mut names)))\n'''
driver += '(unless (= (DebugAllocator::deinit! debug) 0) (panic "function names leak"))) 0)'
runtime = ['types','scope','resolution','source','sequence','equality_runtime','function_names']
inputs = [ROOT/f'seed/{n}.coil' for n in runtime]+[ROOT/'seed/generated/code_forms.coil']
with tempfile.TemporaryDirectory(prefix='rewrite-functions-') as directory:
    work = Path(directory)
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for path in inputs: shutil.copyfile(path,work/path.name)
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:
        r = subprocess.run(['coil','run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if r.returncode: raise RuntimeError(r.stdout+r.stderr)
        observed = normalize(r.stdout,len(cases))
        for i,(actual,c) in enumerate(zip(observed,cases)):
            if actual != c['names']: raise RuntimeError((flags,i,actual,c))
digest = lambda value: hashlib.sha256(value).hexdigest()
host = Path(shutil.which('coil')).resolve(strict=True)
evidence = dict(scope='Generated primitive-name view and ordered owned collection against exact helper capture; not full declaration validation.',
                cases=len(cases),configurations=['default','debug-checks','release'],allocator_leaks=0,
                host_version=subprocess.check_output([str(host),'--version'],text=True).strip(),host_sha256=digest(host.read_bytes()),
                reference_sha256=digest(reference.read_bytes()),driver_sha256=digest(driver.encode()),
                inputs={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs+[Path(__file__),ROOT/'compiler/syntax/code.schema']})
(ROOT/'evidence/function-replay.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(f'Function-name replay: {len(cases)} cases, three configurations, ordered owned names and no allocator leaks')
