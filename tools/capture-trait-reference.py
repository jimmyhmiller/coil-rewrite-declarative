#!/usr/bin/env python3
"""Capture exact trait-availability observation helpers; not full trait parsing."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
definition=runpy.run_path(str(ROOT/'tools/capture-refer-reference.py'))['definition']
q=lambda x:json.dumps(x,ensure_ascii=False)
digest=lambda x:hashlib.sha256(x).hexdigest()

def cases():
    sources=['x','()', '(deftrait)', '(deftrait T)', '(deftrait T invalid body)',
             '(deftrait "T")', '(deftrait :T)', '(deftrait 3)', '[deftrait T]',
             '(quote (deftrait T))', '(other (deftrait T))', '(:do (deftrait T))',
             '(do)', '(do (deftrait A) (do (deftrait B) (deftrait A)) (deftrait C))',
             '(do [deftrait A] (deftrait B) (deftrait) (deftrait C))',
             '(deftrait lib.T)', '(deftrait alias/T)', '(deftrait λ)',
             '(do (do (do (deftrait T))) (other (do (deftrait Hidden))))']
    return [dict(source=s,module=m) for m in [None,'','app'] for s in sources]

HEADER='''(module reference.main)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *)
(import "coil.hashmap" :use *) (import "coil.str" :use [keyops])
(import "coil.scratch" :use [ScratchArena])
(import "coil.text" :use [sconcat3]) (import "coil.primitive" :as primitive)
(defstruct Traits [(names (HashMap (slice u8) bool))])
(defn declared-traits [] (-> (ptr Traits)) (primitive/alloc-static Traits))
'''

def normalize(output,count):
    rows=[None for _ in range(count)];current=None
    for line in output.splitlines():
        if line.startswith('case|'):
            current=int(line.split('|')[1])
            if not 0<=current<count or rows[current] is not None:raise RuntimeError('bad case output')
            rows[current]=[]
        elif line.startswith('name|') and current is not None:
            rows[current].append(line[5:])
        else:raise RuntimeError(f'unexpected output: {line}')
    if any(r is None for r in rows):raise RuntimeError('missing case output')
    return [sorted(r) for r in rows]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reference',required=True,type=Path);parser.add_argument('--compiler',default='coil');args=parser.parse_args()
    host=Path(shutil.which(args.compiler) or args.compiler).resolve(strict=True)
    version=subprocess.check_output([str(host),'--version'],text=True).strip()
    revision=re.search(r'commit ([0-9a-f]+)',version).group(1)
    revision=subprocess.check_output(['git','rev-parse',revision],cwd=args.reference,text=True).strip()
    sources={n:subprocess.check_output(['git','show',f'{revision}:src/compiler/frontend/{n}.coil'],cwd=args.reference,text=True) for n in ['expander','parser']}
    helpers={n:definition(sources['expander'],n) for n in ['qualify-name','sx-head-name','declared-trait-add!','trait-names-into!']}
    helpers.update({n:definition(sources['parser'],n) for n in ['sx-len','sx-at']})
    fixtures=cases();body=['(defn main [] (-> i64)']
    for i,c in enumerate(fixtures):
        module='(None [(slice u8)])' if c['module'] is None else f'(Some {q(c["module"])})'
        body.append(f'''(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) (malloc-allocator)) a (allocator (mut scratch))
          input (match (read-all a {q(c['source'])} 1) (Ok [v] v) (Err [_] (panic "source")))]
          (defer (close! (mut scratch)))
          (store! (declared-traits) (Traits :names (HashMap::new [(slice u8) bool] a (keyops))))
          (trait-names-into! (elem input 0) {module} a)
          (println "case|{i}")
          (for name (.names (declared-traits)) (println "name|{{}}" name)))''')
    body.append('0)');driver=HEADER+'\n'.join(helpers.values())+'\n'+'\n'.join(body)
    work=ROOT/'build/trait-reference';work.mkdir(parents=True,exist_ok=True)
    (work/'Coil.toml').write_text('[package]\nname="reference"\nentry="main.coil"\nsource-roots=["."]\n');(work/'main.coil').write_text(driver)
    outputs=[]
    for flags in [[],['--debug-checks'],['--release']]:
        r=subprocess.run([str(host),'run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        outputs.append(normalize(r.stdout,len(fixtures)))
    if any(x!=outputs[0] for x in outputs):raise RuntimeError('reference configurations differ')
    for c,names in zip(fixtures,outputs[0]):c['names']=names
    evidence=dict(scope='Exact trait-names-into!, qualification and membership insertion helpers with a fixture state accessor. Availability only; not full trait syntax/type validation or session-parent integration.',
                  compiler_version=version,compiler_sha256=digest(host.read_bytes()),reference_revision=revision,
                  source_sha256={k:digest(v.encode()) for k,v in sources.items()},helper_sha256={k:digest(v.encode()) for k,v in helpers.items()},
                  capture_script_sha256=digest(Path(__file__).read_bytes()),driver_sha256=digest(driver.encode()),
                  configurations=['default','debug-checks','release'],cases=fixtures)
    (ROOT/'evidence/trait-reference.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    print(f'Trait availability reference: {len(fixtures)} cases, three matching configurations')

if __name__=='__main__':main()
