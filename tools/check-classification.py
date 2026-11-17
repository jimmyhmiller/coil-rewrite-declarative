#!/usr/bin/env python3
"""Check generated text classifiers and replay the type-name helper oracle."""
import hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
q=lambda x:json.dumps(x,ensure_ascii=False)
reference=ROOT/'evidence/type-name-reference.json';cases=json.loads(reference.read_text())['cases']
HEADER='''(module fixture.main)
(import "rewrite.typenameforms" :use *)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *) (import "coil.result" :use *)
(defn observe [(name (slice u8)) (bits i64)] (-> void)
(match (classify-type-name name bits)
(N0V0 [width signed] (println "Integer|{}|{}" width signed))
(N0V1 [width] (println "Float|{}" width)) (N0V2 [] (println "Boolean"))
(N0V3 [] (println "Void")) (N0V4 [] (println "Never")) (N0V5 [] (println "ExternRef"))
(N0V6 [] (println "Code")) (N0V7 [] (println "CodeBuilder"))
(N0V8 [] (println "Pack")) (N0V9 [] (println "Nominal"))))
'''
driver=HEADER+'(defn main [] (-> i64)\n'+''.join(f'(observe {q(c["name"])} {c["word_bits"]})\n' for c in cases)+'0)'
inputs=[ROOT/f'seed/{n}.coil' for n in ['types','scope','resolution','source','sequence','text_runtime']]+[ROOT/'seed/generated/type_names.coil']
with tempfile.TemporaryDirectory(prefix='rewrite-classification-') as directory:
    work=Path(directory);(work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for p in inputs:shutil.copyfile(p,work/p.name)
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:
        r=subprocess.run(['coil','run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        if r.stdout.splitlines()!=[c['result'] for c in cases]:raise RuntimeError((flags,r.stdout))
    (work/'type_names.coil').unlink()
    schema=b'''(node Out (text Text) (number Int) (flag Bool))
(text-classifier policy Out
(exact "winner!" (Out "exact" $parameter true))
(suffix "!" (Out $input 7 false))
(decimal "n" 1 99 (Out $input $number true))
(default (Out "none" 0 false)))
(text-classifier wide Out
(decimal "" 0 9223372036854775807 (Out $input $number true))
(default (Out "none" 0 false)))'''
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')],input=schema))
    independent='''(module fixture.main)
(import "rewrite.generated" :use *)
(defn check [(text (slice u8)) (value i64) (valid bool)] (-> void)
(let [row (classify-wide text 0)]
(unless (and (= (.f1 row) value) (= (.f2 row) valid)) (panic "decimal range"))))
(defn main [] (-> i64)
(let [row (classify-policy "winner!" 31)] (unless (and (= (.f0 row) "exact") (= (.f1 row) 31) (.f2 row)) (panic "exact precedence")))
(let [row (classify-policy "other!" 31)] (unless (and (= (.f0 row) "other!") (= (.f1 row) 7) (not (.f2 row))) (panic "suffix")))
(let [row (classify-policy "n0099" 31)] (unless (and (= (.f0 row) "n0099") (= (.f1 row) 99) (.f2 row)) (panic "numeric capture")))
(let [row (classify-policy "n100" 31)] (unless (= (.f0 row) "none") (panic "bound fallback")))
(check "0" 0 true) (check "000" 0 true)
(check "9223372036854775807" 9223372036854775807 true)
(check "9223372036854775808" 0 false)
(check "9999999999999999999999999999999999999999999999999" 0 false)
(check "" 0 false) (check "-1" 0 false) (check "+1" 0 false) (check "１" 0 false)
0)'''
    (work/'main.coil').write_text(independent)
    for flags in [[],['--debug-checks'],['--release']]:subprocess.run(['coil','run','main.coil',*flags],cwd=work,check=True)
    for invalid in [
        schema.replace(b' 1 99 ',b' 99 1 '),schema.replace(b' 1 99 ',b' -1 99 '),
        schema.replace(b'(Out "exact" $parameter true)',b'(Out "exact" $number true)'),
        schema.replace(b'(Out "exact" $parameter true)',b'(Out 3 $parameter true)'),
        schema.replace(b'(Out "exact" $parameter true)',b'(Missing "exact" $parameter true)'),
        schema.replace(b'(Out "exact" $parameter true)',b'(Out "exact")'),
        schema.replace(b'text-classifier wide Out',b'text-classifier policy Out'),
        schema.replace(b'text-classifier wide Out',b'text-classifier wide Missing'),
        schema.replace(b'(exact "winner!"',b'(default'),
        schema.replace(b'(default (Out "none" 0 false))',b'(exact "none" (Out "none" 0 false))'),
        b'(node X (child X)) (text-classifier p X (default (X $input)))',
    ]:
        r=subprocess.run([str(ROOT/'build/schema-seed')],input=invalid,capture_output=True)
        assert r.returncode!=0 and not r.stdout,(invalid,r)
digest=lambda b:hashlib.sha256(b).hexdigest();host=Path(shutil.which('coil')).resolve(strict=True)
evidence=dict(scope='Declared type-name classification against exact helper capture; excludes full canonical type conversion, lexical naming and diagnostic parity. Independent policies check typed scalar results, ordered matching and overflow boundaries.',cases=len(cases),configurations=['default','debug-checks','release'],target_word_bits=[32,64],host_version=subprocess.check_output([str(host),'--version'],text=True).strip(),host_sha256=digest(host.read_bytes()),reference_sha256=digest(reference.read_bytes()),driver_sha256=digest(driver.encode()),independent_schema_sha256=digest(schema),independent_driver_sha256=digest(independent.encode()),inputs={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs+[Path(__file__),ROOT/'languages/type_names.schema',ROOT/'languages/classification.schema',ROOT/'seed/classification.coil']})
(ROOT/'evidence/type-name-replay.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(f'Text classifiers: {len(cases)} reference outcomes match in three configurations; independent typed policies and overflow checks passed')
