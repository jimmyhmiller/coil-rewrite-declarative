#!/usr/bin/env python3
"""Capture exact type-wrapper effects and extent-site table semantics."""
import argparse, hashlib, json, re, runpy, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
definition = runpy.run_path(str(ROOT/'tools/capture-refer-reference.py'))['definition']
q = lambda value: json.dumps(value, ensure_ascii=False)
digest = lambda data: hashlib.sha256(data).hexdigest()
HEADER = '''(module reference.main)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *)
(import "coil.hashmap" :use [HashMap]) (import "coil.str" :use [keyops])
(import "coil.primitive" :as primitive) (import "coil.scratch" :use [ScratchArena])
(defsum Type (TStruct [(name (slice u8))]) (TApp [(name (slice u8)) (arguments i64)]) (TInt))
(defn fixture-mode [] (-> (ptr i64)) (primitive/alloc-static i64))
(defn parse-type-inner [(a (dyn Allocator)) (s Sexp)] (-> (Result Type Diag))
(cond (= (load (fixture-mode)) 0) (Ok (TStruct "fixture"))
      (= (load (fixture-mode)) 1) (Ok (TApp "fixture" 0))
      (= (load (fixture-mode)) 2) (Ok (TInt))
      (= (load (fixture-mode)) 3) (Err (Diag :source -1 :lo -1 :hi -1 :ctxt 0 :msg "fixture"))
      :else (Err (Diag :source -1 :lo 2 :hi 3 :ctxt 9 :msg "fixture"))))
(defn source-site-record! [(origin Sexp) (node Sexp) (role (slice u8))] (-> i64)
(println "site|{}|{}|{}|{}|{}|{}|{}|{}" role (.source origin) (.lo origin) (.hi origin) (.source node) (.lo node) (.hi node) (sx-sval node)) 0)
(defn fixture-reset! [] (-> void)
(let [sites (extent-sites)]
(when (.ready sites) (free! (mut (.map sites))) (set! (.ready sites) false))))
(defn query [(name (slice u8))] (-> void)
(match (extent-site name)
(None [] (println "missing|{}" name))
(Some [v] (println "extent|{}|{}|{}|{}" name (.source v) (.lo v) (.hi v)))))
'''
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    args = parser.parse_args()
    host = Path(shutil.which('coil')).resolve(strict=True)
    version = subprocess.check_output([str(host),'--version'],text=True).strip()
    revision = re.search(r'commit ([0-9a-f]+)',version).group(1)
    revision = subprocess.check_output(['git','rev-parse',revision],cwd=args.reference,text=True).strip()
    source = subprocess.check_output(['git','show',f'{revision}:src/compiler/frontend/parser.coil'],cwd=args.reference,text=True)
    names = ['ExtentSite','ExtentSites','extent-sites','extent-site-record!','extent-site-alias!','extent-site','parse-type','sx-source','sx-ctxt','sx-len','sx-at','dwspan']
    helpers = {name:definition(source,name) for name in names}
    wrapper = [dict(form=form,mode=mode) for form in ['T','i64','T...','(struct T)','(dyn T)','(dyn 4)','(dyn)','(Box T)','[]','()'] for mode in range(5)]
    scenarios = [
        [['alias','N','app.N'],['record','N',1,-1,5],['record','N',2,4,6],['record','N',3,8,9],['alias','N','app.N'],['record','app.N',9,2,3]],
        [['record','N',1,0,1],['record','M',2,3,4],['alias','N','M'],['alias','M','Q'],['alias','Q','N']],
        [['record','N',-1,0,-2],['alias','N',''],['record','',8,8,9],['alias','','copy']],
        [['record','',1,0,0],['alias','',''],['alias','','N'],['alias','N','Q']],
        [['record','a/b',1,2,3],['alias','a/b','a.b'],['record','a.b',4,5,6],['alias','missing','a.b']],
        [['record','N',1,-2,0],['alias','N','M'],['record','N',2,0,0],['alias','N','M']],
    ]
    driver = HEADER+'\n'.join(helpers.values())+'\n(defn main [] (-> i64)\n'
    for i,case in enumerate(wrapper):
        driver += f'''(println "wrapper|{i}")
(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) (malloc-allocator)) a (allocator (mut scratch))
roots (match (read-all a {q(case['form'])} 11) (Ok [v] v) (_ (panic "reader"))) root (elem roots 0)]
(defer (close! (mut scratch))) (set! (.ctxt root) 77) (store! (fixture-mode) {case['mode']})
(match (parse-type a (load root)) (Ok [_] (println "ok"))
(Err [d] (println "error|{{}}|{{}}|{{}}|{{}}" (.source d) (.lo d) (.hi d) (.ctxt d)))))\n'''
    extent=[]
    for i,actions in enumerate(scenarios):
        queries = list(dict.fromkeys(name for action in actions for name in (action[1:3] if action[0]=='alias' else action[1:2])))
        extent.append(dict(actions=actions,queries=queries))
        driver += f'(fixture-reset!) (println "scenario|{i}")\n'
        for j,action in enumerate(actions):
            driver += f'(println "step|{j}")\n'
            if action[0]=='record':
                driver += f'(extent-site-record! {q(action[1])} {action[2]} {action[3]} {action[4]})\n'
            else: driver += f'(extent-site-alias! {q(action[1])} {q(action[2])})\n'
            driver += ''.join(f'(query {q(name)})\n' for name in queries)
    driver += '(fixture-reset!) 0)'
    work=ROOT/'build/type-sites-reference';work.mkdir(parents=True,exist_ok=True)
    (work/'Coil.toml').write_text('[package]\nname="reference"\nentry="main.coil"\nsource-roots=["."]\n')
    (work/'main.coil').write_text(driver)
    outputs=[]
    for flags in [[],['--debug-checks'],['--release']]:
        result=subprocess.run([str(host),'run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)
        outputs.append(result.stdout.splitlines())
    assert all(lines==outputs[0] for lines in outputs), 'configurations disagree'
    current=None
    for line in outputs[0]:
        if line.startswith('wrapper|'):
            current=wrapper[int(line.split('|')[1])].setdefault('observed',[])
        elif line.startswith('scenario|'):
            scenario=extent[int(line.split('|')[1])]; scenario['observed']=[]; current=None
        elif line.startswith('step|'):
            assert int(line.split('|')[1])==len(scenario['observed'])
            current=[];scenario['observed'].append(current)
        else:
            assert current is not None
            current.append(line)
    assert all('observed' in c for c in wrapper)
    assert all(len(c['observed'])==len(c['actions']) and all(len(row)==len(c['queries']) for row in c['observed']) for c in extent)
    evidence=dict(scope='Exact parse-type wrapper with explicit inner-result fixture and source-site call spy; this isolates call order and diagnostic span stamping, not full parsing or SourceFacts publication/filtering. Exact extent-site helpers use their actual map and allocator, with fixture resets between independent scenarios.',compiler_version=version,compiler_sha256=digest(host.read_bytes()),reference_revision=revision,source_sha256=digest(source.encode()),helper_sha256={n:digest(t.encode()) for n,t in helpers.items()},capture_script_sha256=digest(Path(__file__).read_bytes()),driver_sha256=digest(driver.encode()),configurations=['default','debug-checks','release'],wrapper_cases=wrapper,extent_cases=extent)
    (ROOT/'evidence/type-sites-reference.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    print(f'Type site reference: {len(wrapper)} wrapper outcomes and {sum(len(c["actions"]) for c in extent)} extent actions, three configurations')
if __name__=='__main__': main()
