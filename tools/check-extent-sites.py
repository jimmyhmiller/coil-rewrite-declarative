#!/usr/bin/env python3
"""Replay first-site and alias effects against the exact parser helper capture."""
from pathlib import Path
import hashlib, json, shutil, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
reference=ROOT/'evidence/type-sites-reference.json'
cases=json.loads(reference.read_text())['extent_cases']
q=lambda value:json.dumps(value,ensure_ascii=False)
driver='''(module fixture.main)
(import "rewrite.extentsites" :as sites) (import "rewrite.source" :use [Origin])
(import "coil.alloc" :use *) (import "coil.arraylist" :use *) (import "coil.result" :use *)
(import "coil.str" :use [StrBuf]) (import "coil.debug-allocator" :use [DebugAllocator])
(defn query [(table (ptr sites/Table)) (name (slice u8))] (-> void)
(match (sites/lookup table name)
(None [] (println "missing|{}" name))
(Some [v] (println "extent|{}|{}|{}|{}" name (.source v) (.lo v) (.hi v)))))
(defn main [] (-> i64)
(let [debug (DebugAllocator::new (malloc-allocator)) a (DebugAllocator::view debug)]
'''
expected=[]
for case in cases:
    driver+='(let [(mut table) (sites/create a)] (defer (sites/release! (mut table)))\n'
    for action,observed in zip(case['actions'],case['observed']):
        if action[0]=='record':
            driver+=f'(sites/record! (mut table) {q(action[1])} (Origin :source {action[2]} :lo {action[3]} :hi {action[4]}))\n'
        else:driver+=f'(sites/alias! (mut table) {q(action[1])} {q(action[2])})\n'
        driver+=''.join(f'(query (mut table) {q(name)})\n' for name in case['queries'])
        expected+=observed
    driver+=')\n'
driver+='''(let [(mut table) (sites/create a) (mut other) (sites/create a) (mut name) (StrBuf::new a)]
(defer (sites/release! (mut table))) (defer (sites/release! (mut other)))
(for [i 0 2000]
(clear! (mut (.bytes name))) (push-i64! (mut name) i)
(unless (sites/record! (mut table) (str name) (Origin :source i :lo i :hi (+ i 1))) (panic "first write"))
(when (sites/record! (mut table) (str name) (Origin :source 99 :lo 0 :hi 1)) (panic "duplicate write")))
(free! (mut name))
(unless (sites/alias! (mut table) "1999" "last") (panic "new alias"))
(when (sites/alias! (mut table) "0" "last") (panic "alias replaced existing"))
(match (sites/lookup (mut table) "last")
(Some [v] (unless (and (= (.source v) 1999) (= (.lo v) 1999) (= (.hi v) 2000)) (panic "owned keys")))
(_ (panic "missing alias")))
(match (sites/lookup (mut other) "last") (None []) (_ (panic "table lifetime isolation"))))
(unless (= (DebugAllocator::deinit! debug) 0) (panic "extent site leak"))) 0)
'''
inputs=[ROOT/'seed/extent_sites.coil',ROOT/'seed/source.coil']
with tempfile.TemporaryDirectory(prefix='rewrite-extent-sites-') as directory:
    work=Path(directory);(work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for p in inputs:shutil.copyfile(p,work/p.name)
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:
        result=subprocess.run(['coil','run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        assert result.stdout.splitlines()==expected,(flags,result.stdout,expected)
digest=lambda data:hashlib.sha256(data).hexdigest()
evidence=dict(scope='Owned explicit-lifetime extent-site table against exact record/alias/lookup helpers. Does not establish parser publication timing, exact identifier capture or full SourceFacts behavior.',scenarios=len(cases),actions=sum(len(c['actions']) for c in cases),observations=len(expected),growth_rows=2000,configurations=['default','debug-checks','release'],reference_sha256=digest(reference.read_bytes()),driver_sha256=digest(driver.encode()),inputs={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs+[Path(__file__)]})
(ROOT/'evidence/extent-sites-replay.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(f'Extent sites: {len(cases)} scenarios/{evidence["actions"]} actions match in three configurations; owned keys, alias precedence, isolation and 2000-row growth passed')
