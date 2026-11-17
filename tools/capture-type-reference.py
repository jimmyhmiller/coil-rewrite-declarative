#!/usr/bin/env python3
"""Capture real parse-program acceptance and AST output for written type forms."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
ROOT = Path(__file__).resolve().parents[1]

def cases():
    values = ['i64','i1','i65535','i65536','u0','i999999999999999999999999','f32','f64','bool','void','never','externref','usize','isize','Code','CodeBuilder','T','T...','lib.T','alias/T','λ','true','false','0','-1',':meters','"bad"','[]','()','(1 i64)']
    for head in ['const','mask','mut','ref','ptr','array','slice','vec','struct','dyn','fnptr','Box']:
        values += [f'({head}{tail})' for tail in ['', ' i64', ' i64 3', ' i64 3 "ignored"']]
    values += ['(const true)','(const false)','(const :m)','(const 42)','(const N)','(const [])','(const 1 2)',
               '(mask 0)','(mask 1)','(mask -1)','(mask W)','(mask 8 "ignored")',
               '(array i64 0)','(array i64 -1)','(array i64 N)','(array [] 1)',
               '(vec i32 0)','(vec i32 -1)','(vec i32 W)','(vec i32 :width)',
               '(ptr i64 "ignored")','(ptr [] i64)','(ref i64 "ignored")','(slice i64 [])',
               '(dyn Show [])','(struct Foo [])','(fnptr cc [] void)','(fnptr (cc/C) [i64 (ptr)] i64)',
               '(fnptr (cc/C) [] void "ignored")','(fnptr (cc/C bad) [] void)',
               '(fnptr [] [] void)','(fnptr cc () void)','(fnptr cc [] [])',
               '(Box (array (ptr T) N) (const :meters))','(Box [])']
    return list(dict.fromkeys(values))

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reference',required=True,type=Path);args=parser.parse_args()
    host=Path(shutil.which('coil')).resolve(strict=True)
    version=subprocess.check_output([str(host),'--version'],text=True).strip()
    revision=re.search(r'commit ([0-9a-f]+)',version).group(1)
    revision=subprocess.check_output(['git','rev-parse',revision],cwd=args.reference,text=True).strip()
    paths=['src/compiler/driver.coil','src/compiler/frontend/parser.coil','src/compiler/frontend/astdump.coil']
    digest=lambda b:hashlib.sha256(b).hexdigest()
    sources={p:digest(subprocess.check_output(['git','show',f'{revision}:{p}'],cwd=args.reference)) for p in paths}
    work=ROOT/'build/type-reference';work.mkdir(parents=True,exist_ok=True)
    rows=[]
    for i,t in enumerate(cases()):
        source=f'(defstruct TypeProbe [(value {t})])\n'
        path=work/f'case-{i}.coil';path.write_text(source)
        r=subprocess.run([str(host),'dump-ast',str(path)],cwd=ROOT,capture_output=True,text=True)
        if r.returncode not in [0,1] or r.stderr:raise RuntimeError((t,r.returncode,r.stdout,r.stderr))
        if not r.stdout.startswith('(conventions ' if r.returncode==0 else '(error@'):raise RuntimeError((t,r.stdout))
        rows.append(dict(type=t,source=source,exit_code=r.returncode,output=r.stdout))
    evidence=dict(scope='Real installed parse-program through dump-ast, type in a struct field; one installed executable/profile. Written grammar replay covers acceptance only, not canonical type AST, hygiene, source-site effects or exact diagnostics.',compiler_version=version,compiler_sha256=digest(host.read_bytes()),reference_revision=revision,source_sha256=sources,capture_script_sha256=digest(Path(__file__).read_bytes()),cases=rows)
    (ROOT/'evidence/type-reference.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    print(f'Type parser reference: {len(rows)} forms, {sum(c["exit_code"]==0 for c in rows)} accepted')
if __name__=='__main__':main()
