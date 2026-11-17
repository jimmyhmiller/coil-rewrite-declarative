#!/usr/bin/env python3
"""Capture primitive function-name observation, independently of declaration validation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess
ROOT = Path(__file__).resolve().parents[1]
definition = runpy.run_path(str(ROOT/'tools/capture-refer-reference.py'))['definition']
q = lambda value: json.dumps(value, ensure_ascii=False)
digest = lambda value: hashlib.sha256(value).hexdigest()

def normalize(output, count):
    rows = []; current = None
    for line in output.splitlines():
        if line.startswith('case|'):
            if int(line[5:]) != len(rows): raise RuntimeError('case order')
            current = []; rows.append(current)
        elif line.startswith('name|') and current is not None: current.append(line[5:])
        else: raise RuntimeError(f'unexpected output: {line}')
    if len(rows) != count: raise RuntimeError('missing cases')
    return rows

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    args = parser.parse_args()
    host = Path(shutil.which('coil')).resolve(strict=True)
    version = subprocess.check_output([str(host), '--version'], text=True).strip()
    revision = re.search(r'commit ([0-9a-f]+)', version).group(1)
    revision = subprocess.check_output(['git','rev-parse',revision], cwd=args.reference,text=True).strip()
    sources = {n: subprocess.check_output(['git','show',f'{revision}:src/compiler/frontend/{n}.coil'],cwd=args.reference,text=True) for n in ['expander','parser']}
    helpers = {n: definition(sources['expander'], n) for n in ['defn-name-of','qualify-name']}
    helpers.update({n: definition(sources['parser'], n) for n in ['sx-len','sx-at']})
    inputs = ['x','()','(defn*)','(defn* f)','(defn* f invalid body)','(defn f [] 1)',
              '(defn* "f")','(defn* :f)','(defn* 1)','[defn* f]','(:defn* f)',
              '(quote (defn* f))','(do (defn* f))','(defn* lib.f)','(defn* alias/f)',
              '(defn* λ)','(defn* a) (defn* b) (defn* a)']
    cases = [dict(source=s,module=m) for m in [None,'','app'] for s in inputs]
    driver = '''(module reference.main)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena]) (import "coil.text" :use [sconcat3])
'''+ '\n'.join(helpers.values()) + '\n(defn main [] (-> i64)\n'
    for i,c in enumerate(cases):
        module = '(None [(slice u8)])' if c['module'] is None else f'(Some {q(c["module"])})'
        driver += f'''(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) (malloc-allocator)) a (allocator (mut scratch))
input (match (read-all a {q(c['source'])} 1) (Ok [v] v) (Err [_] (panic "source")))]
(defer (close! (mut scratch))) (println "case|{i}")
(for [j 0 (len input)] (match (defn-name-of (elem input j)) (None []) (Some [n] (println "name|{{}}" (qualify-name a n {module})))) ))\n'''
    driver += '0)'
    work = ROOT/'build/function-reference'; work.mkdir(parents=True,exist_ok=True)
    (work/'Coil.toml').write_text('[package]\nname="reference"\nentry="main.coil"\nsource-roots=["."]\n')
    (work/'main.coil').write_text(driver)
    outputs = []
    for flags in [[],['--debug-checks'],['--release']]:
        r = subprocess.run([str(host),'run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if r.returncode: raise RuntimeError(r.stdout+r.stderr)
        outputs.append(normalize(r.stdout,len(cases)))
    if any(x != outputs[0] for x in outputs): raise RuntimeError('configuration mismatch')
    for c,names in zip(cases,outputs[0]): c['names'] = names
    evidence = dict(scope='Exact defn-name-of and qualify-name helpers on reader forms. Ordered observation only; not function syntax validation or full admission.',
                    compiler_version=version,compiler_sha256=digest(host.read_bytes()),reference_revision=revision,
                    source_sha256={k:digest(v.encode()) for k,v in sources.items()},helper_sha256={k:digest(v.encode()) for k,v in helpers.items()},
                    capture_script_sha256=digest(Path(__file__).read_bytes()),driver_sha256=digest(driver.encode()),
                    configurations=['default','debug-checks','release'],cases=cases)
    (ROOT/'evidence/function-reference.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    print(f'Function-name reference: {len(cases)} cases, three configurations')
if __name__ == '__main__': main()
