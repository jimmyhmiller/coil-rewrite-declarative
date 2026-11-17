#!/usr/bin/env python3
"""Compile real Coil source through compiler/ and execute its native image."""
from pathlib import Path
import json, shutil, subprocess, tempfile, os, hashlib
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tests/compiler/integer-functions.coil').read_text()
q=lambda value:json.dumps(value,ensure_ascii=False)
executions=[('entry',41,84),('factorial',12,479001600),('factorial',0,1),
            ('fibonacci',10,55),('even',24,1),('even',23,0),
            ('comparisons',-9223372036854775808,14),('comparisons',-1,14),
            ('comparisons',0,41),('comparisons',1,50),
            ('comparisons',9223372036854775807,50)]
with tempfile.TemporaryDirectory(prefix='coil-replacement-') as directory:
    work=Path(directory)
    roots=['.',*[str(ROOT/'vendor/coil'/p) for p in ['src/compiler/declarative','src/compiler/native','src/declarative/tests']]]
    (work/'Coil.toml').write_text('[package]\nname="driver"\nentry="main.coil"\nsource-roots='+json.dumps(roots)+'\n')
    for name in ['types','scope','resolution','source','sequence']:
        shutil.copyfile(ROOT/f'seed/{name}.coil',work/f'{name}.coil')
    shutil.copyfile(ROOT/'runtime/native.coil',work/'native.coil')
    shutil.copyfile(ROOT/'seed/generated/core_compiler.coil',work/'core_compiler.coil')
    driver='''(module driver.main)
(import "rewrite.corecompiler" :use [compile-source store-new store-free!]) (import "rewrite.native" :as native)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *) (import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena]) (import "coil.primitive" :as primitive) (import "coil.cc" :as cc)
(import "declarative.rt.jit" :as jit)
(defn main [] (-> i64)
(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) (malloc-allocator)) a (allocator (mut scratch))
(mut store) (store-new a)]
(defer (close! (mut scratch))) (defer (store-free! (mut store)))
'''
    driver+=f'''(match (compile-source a (mut store) "integer-functions.coil" {q(source)} 1)
(Err [_] (panic "compiler rejected source"))
(Ok [image]
(let [loaded (native/load-image a image)] (defer (jit/unload! loaded))
'''
    for entry,argument,expected in executions:
        driver+=f'''(let [(mut symbol) -1]
(for [i 0 (len (.names image))] (when (= (get (.names image) i) {q(entry)}) (set! symbol i)))
(when (< symbol 0) (panic "entry missing"))
(let [run (primitive/cast (fnptr (cc/C) [i64] i64) (jit/address-of loaded symbol))]
(unless (= (run {argument}) {expected}) (panic {q(f'{entry}({argument}) != {expected}')}))))
'''
    for entry,arguments,expected in [('forty-two',[],42),('weighted',[1,2,3],123)]:
        params=' '.join('i64' for _ in arguments)
        values=' '.join(map(str,arguments))
        driver+=f'''(let [(mut symbol) -1]
(for [i 0 (len (.names image))] (when (= (get (.names image) i) {q(entry)}) (set! symbol i)))
(when (< symbol 0) (panic "missing native function"))
(let [run (primitive/cast (fnptr (cc/C) [{params}] i64) (jit/address-of loaded symbol))]
(unless (= (run {values}) {expected}) (panic "incorrect native parameter binding"))))\n'''
    driver+=')))\n'
    for i,bad in enumerate(['(defn bad [(x i64)] (-> i64) (+ x true))','(defn bad [(x i64)] (-> i64) missing)','(unknown-form 1)','(defn bad [(x i64)] (-> i64) (if true 1 false))', '(defn bad [(x i64)] (-> i64) (* x true))', '(defn bad [(x i64)] (-> i64) (if (< x true) 1 0))', '(defn bad [(x i64)] (-> i64) (+ (< x 0) 1))'],2):
        driver+=f'''(let [(mut rejected) (store-new a)] (defer (store-free! (mut rejected)))
(match (compile-source a (mut rejected) "invalid.coil" {q(bad)} {i})
(Err [_]) (Ok [_] (panic "compiler accepted invalid source"))))\n'''
    driver+=') (println "compiler/frontend/core.schema: source -> declared parsing/checking/lowering -> native arithmetic, comparisons and recursion passed; invalid programs rejected") 0)'
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:subprocess.run(['coil','run','main.coil',*flags],cwd=work,check=True)

    binary=work/'coil-rewrite'
    subprocess.run(['coil','build','core_compiler.coil','-o',str(binary)],cwd=work,check=True)
    cli_cases=[]
    for name,text,entry,argument,status,output in [
        *[(f'valid-{i}.coil',source,entry,str(argument),0,str(expected)) for i,(entry,argument,expected) in enumerate(executions)],
        ('invalid.coil','(defn bad [(x i64)] (-> i64) (+ x true))','bad','1',1,'type checking failed in bad'),
        ('stack.coil',source,'stack-arguments','2 3 4 5 6 7 8 9 10 11 12 13',0,'28'),
        ('duplicate-parameter.coil','(defn bad [(x i64) (x i64)] (-> i64) x)','bad','1 2',1,'duplicate parameter: x'),
        ('zero.coil',source,'forty-two','',0,'42'),
        ('three.coil',source,'weighted','1 2 3',0,'123'),
        ('wrong-entry-arity.coil',source,'weighted','1',1,'entry argument count mismatch'),
        ('missing.coil','(defn present [(x i64)] (-> i64) x)','absent','0',1,'entry not found: absent'),
    ]:
        path=work/name;path.write_text(text)
        result=subprocess.run([str(binary),'run',str(path),entry,*argument.split()],cwd=work,env={**os.environ,'PATH':''},capture_output=True,text=True)
        assert (result.returncode,result.stdout.strip())==(status,output),(name,result)
        cli_cases.append(dict(source_file="tests/compiler/integer-functions.coil" if text==source else None,source=None if text==source else text,entry=entry,argument=argument,status=status,output=output))
    reference='(module driver.reference)\n'+source+'\n(defn main [] (-> i64)\n'
    for entry,argument,expected in executions:
        reference+=f'(println "{{}}" ({entry} {argument}))\n'
    reference+='0)\n'
    (work/'reference.coil').write_text(reference)
    baseline=subprocess.run(['coil','run','reference.coil'],cwd=work,check=True,capture_output=True,text=True)
    reference_results=[int(line) for line in baseline.stdout.splitlines()]
    assert reference_results==[expected for _,_,expected in executions],baseline
    digest=lambda data:hashlib.sha256(data).hexdigest()
    inputs=[ROOT/'compiler/frontend/core.schema',ROOT/'seed/program.coil',ROOT/'seed/lower.coil',ROOT/'tests/compiler/integer-functions.coil',ROOT/'seed/command.coil',ROOT/'seed/generated/core_compiler.coil',Path(__file__)]
    evidence=dict(scope='Executable DSL-authored compiler integration for integer functions with ordered parameter lists; not complete Coil compatibility. CLI runs with empty PATH and does not invoke the bootstrap compiler on guest source.',library_configurations=['default','debug-checks','release'],reference_results=reference_results,cli_cases=cli_cases,binary_sha256=digest(binary.read_bytes()),inputs={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs})
    (ROOT/'evidence/compiler-command.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('Compiler command: file input, native execution, invalid programs and missing entry; empty PATH passed; arithmetic and recursive execution agrees with installed Coil')
