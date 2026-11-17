#!/usr/bin/env python3
"""Capture the installed reference's real primitive declaration parser via dump-ast."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
ROOT=Path(__file__).resolve().parents[1]
def digest(value):return hashlib.sha256(value).hexdigest()

def cases():
    rows=[]
    def add(name,source):rows.append(dict(name=name,source=source+'\n'))
    for name,source in [
        ('empty-struct','(defstruct Empty [])'),('struct-fields','(defstruct Pair [(x i64) (next (ptr Pair))])'),
        ('generic-struct','(defstruct Box [T] [(value T)])'),('bounded-struct','(defstruct Box [(T Ord)] [(value T)])'),
        ('empty-two-vectors','(defstruct Empty [] [])'),('missing-fields','(defstruct Empty)'),
        ('symbol-fields','(defstruct Bad fields)'),('bad-field','(defstruct Bad [x])'),
        ('short-field','(defstruct Bad [(x)])'),('default-field','(defstruct Defaults [(x i64 :default 42)])'),
        ('field-offset','(defstruct Offset [(x i64 :at 0)])'),('old-layout','(defstruct Old :layout packed [(x i64)])'),
        ('written-layout','(defstruct Packed :layout (layout/Packed) [(x i64)])'),
        ('align-only','(defstruct Align :align 16 [(x i64)])'),('bad-align','(defstruct Align :align 3 [])'),
        ('size-only','(defstruct Size :size 16 [])'),('negative-size','(defstruct Size :size -1 [])'),
        ('backing-only','(defstruct Back :backing u32 [])'),('bad-backing','(defstruct Back :backing f64 [])'),
        ('bits-field','(defstruct Bits [(x :bits 3) (y :bits 5 :signed true)])'),
        ('hidden-fields','(defstruct Hidden :hidden [(counter i64 0)] [])'),
        ('duplicate-hidden','(defstruct Hidden :hidden [(counter i64 0) (counter i64 1)] [])'),
        ('bad-hidden-arity','(defstruct Hidden :hidden [(counter i64)] [])'),
        ('annotation','(defstruct Annotated :doc "note" [])'),('unknown-annotation','(defstruct Annotated :custom/key (+ 1 2) [])'),
        ('missing-option','(defstruct Missing :size)'),('duplicate-option','(defstruct Sized :align 8 :align 16 [])'),
        ('trailing-struct','(defstruct Trailing [] extra)'),('duplicate-field','(defstruct Duplicated [(x i64) (x i32)])'),
        ('empty-sum','(defsum Empty)'),('sum-variants','(defsum Choice (A) (B [(value i64)]))'),
        ('generic-sum','(defsum Maybe [T] (None) (Some [(value T)]))'),
        ('bounded-sum','(defsum Maybe [(T Ord)] (None) (Some [(value T)]))'),
        ('sum-annotation','(defsum Choice :doc "note" (A))'),('bad-variant','(defsum Choice A)'),
        ('missing-variant-name','(defsum Choice ())'),('bad-variant-fields','(defsum Choice (A (x i64)))'),
        ('extra-variant-items','(defsum Choice (A [] ignored))'),('duplicate-variant','(defsum Choice (A) (A))'),
        ('bad-struct-name','(defstruct 3 [])'),('bad-sum-name','(defsum :Bad (A))'),
        ('missing-struct-name','(defstruct)'),('missing-sum-name','(defsum)'),
    ]:add(name,source)
    types=['i8','u64','f32','bool','void','Code','true',':unit','42','(const N)','(ptr)','(ptr i32 ignored)',
           '(ref i64)','(mut i64)','(slice u8)','(array i64 0)','(array i64 -1)','(array i64 N)',
           '(vec i32 4)','(mask 8)','(dyn Show)','(Box i64)','(fnptr (cc/C) [i64] i64)',
           '(array i64)','()','[i64]','"i64"']
    for i,t in enumerate(types):add(f'field-type-{i}',f'(defstruct Typed [(value {t})])')
    return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reference',required=True,type=Path);parser.add_argument('--compiler',default='coil');args=parser.parse_args()
    host=Path(shutil.which(args.compiler) or args.compiler).resolve(strict=True)
    version=subprocess.check_output([str(host),'--version'],text=True).strip()
    revision=re.search(r'commit ([0-9a-f]+)',version).group(1)
    revision=subprocess.check_output(['git','rev-parse',revision],cwd=args.reference,text=True).strip()
    paths=['src/compiler/driver.coil','src/compiler/frontend/parser.coil','src/compiler/frontend/ast.coil','src/compiler/frontend/astdump.coil']
    sources={p:subprocess.check_output(['git','show',f'{revision}:{p}'],cwd=args.reference) for p in paths}
    work=ROOT/'build/declaration-reference';work.mkdir(parents=True,exist_ok=True)
    rows=cases()
    for case in rows:
        path=work/(case['name']+'.coil');path.write_text(case['source'])
        r=subprocess.run([str(host),'dump-ast',str(path)],cwd=ROOT,capture_output=True,text=True)
        if r.returncode not in [0,1]:raise RuntimeError(f'parser process failed: {case["name"]}: {r.returncode}: {r.stdout}{r.stderr}')
        if r.stderr:raise RuntimeError(f'unexpected stderr: {case["name"]}: {r.stderr}')
        if r.returncode==0 and not r.stdout.startswith('(conventions '):raise RuntimeError('missing successful AST output')
        if r.returncode==1 and not r.stdout.startswith('(error@'):raise RuntimeError(f'missing parser diagnostic: {r.stdout}')
        case.update(exit_code=r.returncode,output=r.stdout)
    evidence=dict(scope='Real installed primitive reader/parse-program via dump-ast, without module loading or macro expansion. AST dumps omit struct/sum bounds, annotations and hidden initializer payloads; success does not prove those fields equal. One installed executable/profile, not three separately built configurations.',
                  compiler_version=version,compiler_sha256=digest(host.read_bytes()),reference_revision=revision,
                  source_sha256={p:digest(v) for p,v in sources.items()},capture_script_sha256=digest(Path(__file__).read_bytes()),cases=rows)
    (ROOT/'evidence/declaration-reference.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    print(f'Declaration parser reference: {len(rows)} inputs, {sum(c["exit_code"]==0 for c in rows)} accepted, {sum(c["exit_code"]!=0 for c in rows)} rejected')
if __name__=='__main__':main()
