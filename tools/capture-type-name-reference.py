#!/usr/bin/env python3
"""Capture exact pack/builtin/primitive helpers with explicit target-width facts."""
import argparse, hashlib, json, re, runpy, shutil, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
definition=runpy.run_path(str(ROOT/'tools/capture-refer-reference.py'))['definition']
q=lambda s:json.dumps(s,ensure_ascii=False)
HEADER='''(module reference.main)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *)
(import "coil.slice" :use [subslice]) (import "coil.text" :use [sconcat sconcat3])
(import "coil.scratch" :use [ScratchArena]) (import "coil.primitive" :as primitive)
(defsum Type (TInt [(bits i64) (signed bool)]) (TFloat [(bits i64)])
(TBool) (TVoid) (TNever) (TExternRef) (TCode) (TCodeBuilder))
(defn width [] (-> (ptr i64)) (primitive/alloc-static i64))
(defn target-word-bits [] (-> i64) (load (width)))
(defn observe [(a (dyn Allocator)) (name (slice u8))] (-> void)
(if (pack-name? name) (println "Pack")
(let [result (match (builtin-code-type name) (Some [t] (Ok [Type Diag] t)) (None [] (prim-type a name)))]
(match result (Err [_] (println "Nominal")) (Ok [t]
(match t (TInt [bits signed] (println "Integer|{}|{}" bits signed))
(TFloat [bits] (println "Float|{}" bits)) (TBool [] (println "Boolean"))
(TVoid [] (println "Void")) (TNever [] (println "Never")) (TExternRef [] (println "ExternRef"))
(TCode [] (println "Code")) (TCodeBuilder [] (println "CodeBuilder"))))))))
'''
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--reference',required=True,type=Path);args=parser.parse_args()
    host=Path(shutil.which('coil')).resolve(strict=True);version=subprocess.check_output([str(host),'--version'],text=True).strip()
    rev=re.search(r'commit ([0-9a-f]+)',version).group(1);rev=subprocess.check_output(['git','rev-parse',rev],cwd=args.reference,text=True).strip()
    source=subprocess.check_output(['git','show',f'{rev}:src/compiler/frontend/parser.coil'],cwd=args.reference,text=True)
    helpers={n:definition(source,n) for n in ['pack-name?','builtin-code-type','prim-type','int-type','not-int-diag','derr']}
    names=['','i','u','i0','u0','i1','u1','i64','u64','i65535','u65535','i65536','u65536','i00064','i00000','i4294967295','i4294967296','i9223372036854775807','u18446744073709551615','i'+'9'*100,'i'+'0'*100+'64','i+64','i-1','i6x','i６４','I64','f16','f32','f64','F32','bool','void','never','externref','usize','isize','Code','CodeBuilder','code','lib.Code','alias/T','λ','T','T...','...','..','Code...','i64...','true','false']
    rows=[dict(name=n,word_bits=w) for w in [32,64] for n in names]
    driver=HEADER+'\n'.join(helpers.values())+'\n(defn main [] (-> i64)\n'
    for c in rows:driver+=f'''(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) (malloc-allocator)) a (allocator (mut scratch))] (defer (close! (mut scratch))) (store! (width) {c['word_bits']}) (observe a {q(c['name'])}))\n'''
    driver+='0)';work=ROOT/'build/type-name-reference';work.mkdir(parents=True,exist_ok=True)
    (work/'Coil.toml').write_text('[package]\nname="reference"\nentry="main.coil"\nsource-roots=["."]\n');(work/'main.coil').write_text(driver)
    outputs=[]
    for flags in [[],['--debug-checks'],['--release']]:
        r=subprocess.run([str(host),'run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        lines=r.stdout.splitlines()
        if len(lines)!=len(rows):raise RuntimeError('missing classification output')
        outputs.append(lines)
    if any(x!=outputs[0] for x in outputs):raise RuntimeError('configurations differ')
    for c,result in zip(rows,outputs[0]):c['result']=result
    digest=lambda b:hashlib.sha256(b).hexdigest()
    evidence=dict(scope='Exact pack-name?, builtin-code-type and prim-type/int-type helpers, composed in inspected order with a target-width fixture and primitive Type subset. Classification of written Name nodes only: source true/false become constant nodes earlier. Not complete parse-type, lexical resolution or diagnostic parity.',compiler_version=version,compiler_sha256=digest(host.read_bytes()),reference_revision=rev,source_sha256=digest(source.encode()),helper_sha256={n:digest(s.encode()) for n,s in helpers.items()},capture_script_sha256=digest(Path(__file__).read_bytes()),driver_sha256=digest(driver.encode()),configurations=['default','debug-checks','release'],cases=rows)
    (ROOT/'evidence/type-name-reference.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    print(f'Type name reference: {len(rows)} outcomes, two target widths, three configurations')
if __name__=='__main__':main()
