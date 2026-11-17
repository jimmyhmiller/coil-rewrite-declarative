#!/usr/bin/env python3
"""Execute exact resolver/head helpers with explicit table and session adapters."""
import argparse
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
E=runpy.run_path(str(ROOT/'tools/capture-export-reference.py'))
F=runpy.run_path(str(ROOT/'tools/route-fixtures.py'))
q,digest,definition=(E[n] for n in ['q','digest','definition'])


def use(e):
    lines=['(let [selected (boxed a (ArrayList::new [(slice u8)] a)) excluded (boxed a (ArrayList::new [(slice u8)] a)) renamed (boxed a (ArrayList::new [Rename] a))]']
    for key in ['selected','excluded']:
        for name in e[key]: lines.append(f'(push! {key} {q(name)})')
    for old,new in e['renames']: lines.append(f'(push! renamed (Rename :from {q(old)} :to {q(new)}))')
    lines.append(f'(Use :target {q(e["target"])} :spec {"(UAll)" if e["all"] else "(UNames selected)"} :exclude excluded :renames renamed))')
    return '\n'.join(lines)


EXTRA='''
(import "fixture.toolchain" :as sm)
(import "coil.slice" :use [subslice])
(defstruct Diag [(msg (slice u8))])
(defn derr [(text (slice u8))] (-> Diag) (Diag :msg text))
(defn use-ambig-msg [(a (dyn Allocator)) (module (slice u8)) (name (slice u8)) (first (slice u8)) (next (slice u8))] (-> (slice u8)) (sconcat3 a first "|" next))
(defn declared-list [] (-> (ptr (ArrayList (slice u8)))) (primitive/alloc-static (ArrayList (slice u8))))
(defn declared-name? [(name (slice u8))] (-> bool) (set-contains (declared-list) name))
(defn prelude-cell [] (-> (ptr (slice u8))) (primitive/alloc-static (slice u8)))
(defn implicit-prelude-name [(a (dyn Allocator))] (-> (slice u8)) (load (prelude-cell)))
(defn core-prov-box [] (-> (ptr CoreProvBox)) (primitive/alloc-static CoreProvBox))
(defn core-prov-init! [] (-> i64) 0)
(defn macro-mode [] (-> (ptr bool)) (primitive/alloc-static bool))
(defn macro-space? [(space (ptr NameSpace))] (-> bool) (load (macro-mode)))
(defstruct Route [(asking (slice u8)) (head (slice u8)) (kind i64) (owner (slice u8)) (exported (slice u8)) (target (slice u8)) (count i64)])
(defn route [] (-> (ptr Route)) (primitive/alloc-static Route))
(defn source-route-record! [(asking (slice u8)) (head (slice u8)) (kind i64) (owner (slice u8)) (exported (slice u8)) (target (slice u8))] (-> i64)
  (unless (= kind 6) (panic "route kind"))
  (store! (route) (Route :asking asking :head head :kind kind :owner owner :exported exported :target target :count (+ (.count (route)) 1))) 0)
(defn print-result [(result (Result (Option (slice u8)) Diag))] (-> void)
  (when (> (.count (route)) 1) (panic "multiple selected routes"))
  (match result
    (Err [e] (unless (= (.count (route)) 0) (panic "ambiguity route")) (println "ambiguous|{}" (.msg e)))
    (Ok [value] (match value
      (None [] (unless (= (.count (route)) 0) (panic "missing route")) (println "none"))
      (Some [target]
        (if (= (.count (route)) 0) (println "hit|{}" target)
          (do (unless (and (load (macro-mode)) (= target (.target (route)))) (panic "wrong recorded target"))
              (println "hit|{}|{}|{}|{}|{}|{}" target (.asking (route)) (.head (route)) (.owner (route)) (.exported (route)) (.target (route))))))))))
; Memoization is bypassed; the exact resolver determines every answer.
(defn resolve-macro [(head (slice u8)) (module (Option (slice u8))) (macros (ptr (ArrayList (slice u8))))
                     (impb (ptr (AVec ImpEntry))) (expb (ptr (AVec ExpEntry))) (a (dyn Allocator))] (-> (Option (slice u8)))
  (let [(mut space) (NameSpace :names macros)]
    (match (resolve-in-space head module (mut space) impb expb a) (Ok [r] r) (Err [_] (None)))))
'''
TOOLCHAIN='''(module fixture.toolchain)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *) (import "coil.primitive" :as primitive)
(defn names [] (-> (ptr (ArrayList (slice u8)))) (primitive/alloc-static (ArrayList (slice u8))))
(defn toolchain-namespace? [(name (slice u8))] (-> bool)
  (block :done (for value (load (names)) (when (= value name) (break :done true))) false))
'''


def queries(g):
    b=['(store! (declared-list) (ArrayList::new [(slice u8)] a)) (store! (sm/names) (ArrayList::new [(slice u8)] a))',
       f'(store! (prelude-cell) {q(g["prelude"])})',
       '(store! (core-prov-box) (CoreProvBox :init 1 :names (boxed a (ArrayList::new [(slice u8)] a)) :modules (boxed a (ArrayList::new [(slice u8)] a)) :roots (boxed a (ArrayList::new [i64] a))))']
    for name in g['declared']: b.append(f'(push! (declared-list) {q(name)})')
    for name in g['toolchain']: b.append(f'(push! (sm/names) {q(name)})')
    for name,owner,root in g['providers']:
        b.append(f'(push! (.names (core-prov-box)) {q(name)}) (push! (.modules (core-prov-box)) {q(owner)}) (push! (.roots (core-prov-box)) {int(root)})')
    for m in g['imports']:
        b.append('(let [(mut aliases) (ArrayList::new [Alias] a) (mut uses) (ArrayList::new [Use] a)]')
        for alias,target in m['aliases']: b.append(f'(push! (mut aliases) (Alias :alias {q(alias)} :target {q(target)}))')
        for e in m['uses']: b.append(f'(push! (mut uses) {use(e)})')
        b.append(f'''(let [prior (imports-find (mut imports) {q(m['name'])}) core {use(m['core'])}]
          (if (= (primitive/cast i64 prior) 0)
            (push! (mut imports) (ImpEntry :name {q(m['name'])} :edit 0 :imp (ModImports :aliases aliases :uses uses :core core :reexports (ArrayList::new [Use] a))))
            (do (set! (.aliases (.imp prior)) aliases) (set! (.uses (.imp prior)) uses) (set! (.core (.imp prior)) core) 0))))''')
    for head,module,macro in g['route_queries']:
        md='(None [(slice u8)])' if module is None else f'(Some {q(module)})'
        b.append(f'(store! (route) (zeroed Route)) (store! (macro-mode) {str(macro).lower()}) (print-result (resolve-in-space {q(head)} {md} (mut space) (mut imports) (mut exports) a))')
    for name,scope,definition_module,fallback in g['head_queries']:
        md='(None [(slice u8)])' if fallback is None else f'(Some {q(fallback)})'
        b.append(f'''(store! (route) (zeroed Route)) (store! (macro-mode) true)
          (let [(mut head) (mk-sexp (KSym {q(name)}) -1 -1)]
            (set! (.hyg head) {scope}) (set! (.hmod head) (hmod-intern {q(definition_module)}))
            (print-result (Ok [(Option (slice u8)) Diag] (resolve-macro-head head {md} names (mut imports) (mut exports) a))))''')
    return b


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference',type=Path,required=True);p.add_argument('--compiler',default='coil');args=p.parse_args()
    compiler=Path(shutil.which(args.compiler) or args.compiler).resolve(strict=True)
    version=subprocess.check_output([str(compiler),'--version'],text=True).strip()
    revision=re.search(r'commit ([0-9a-f]+)',version).group(1)
    revision=subprocess.check_output(['git','rev-parse',revision],cwd=args.reference,text=True).strip()
    sources={n:subprocess.check_output(['git','show',f'{revision}:src/compiler/frontend/{n}.coil'],cwd=args.reference,text=True) for n in ['loader','resolve','expander','ast','parser']}
    groups=[('loader',['UseSpec','Rename','Use','Alias','ImpEntry','ExpEntry','use-refers','core-refers']),
            ('resolve',['set-contains','imports-find','exports-check','alias-target','imported-module','has-dot','find-slash']),
            ('ast',['DeclAliasEntry','decl-alias-target','CoreProvBox','core-contribution-owner']),
            ('parser',['sx-hyg','sx-hmod','lexical-name']),
            ('expander',['qualify-name','space-exported','space-none','space-some','space-use-match','space-core-ordered','resolve-in-space','macro-module-of','resolve-macro-head'])]
    helpers={name:definition(sources[source],name) for source,names in groups for name in names}
    header=E['HEADER'].replace(':use [Sexp]',':use [Sexp KSym mk-sexp hmod-intern hmod-name sx-sval next-node-id]').replace(':use [sconcat3]',':use [sconcat sconcat3 i64->str]')
    header=header.replace('(defstruct ModImports [(reexports (ArrayList Use))])','(defstruct ModImports [(reexports (ArrayList Use)) (aliases (ArrayList Alias)) (uses (ArrayList Use)) (core Use)])')+EXTRA
    empty='(Use :target "core" :spec (UAll) :exclude (primitive/cast (ptr (ArrayList (slice u8))) 0) :renames (primitive/cast (ptr (ArrayList Rename)) 0))'
    graphs=F['cases']()
    driver=E['fixture'](graphs,helpers,header=header,after_graph=queries,import_value=f'(ModImports :reexports edges :aliases (ArrayList::new [Alias] a) :uses (ArrayList::new [Use] a) :core {empty})')
    work=ROOT/'build/routing-reference';work.mkdir(parents=True,exist_ok=True)
    (work/'Coil.toml').write_text('[package]\nname="reference"\nentry="main.coil"\nsource-roots=["."]\n');(work/'main.coil').write_text(driver);(work/'toolchain.coil').write_text(TOOLCHAIN)
    outputs=[]
    for flags in [[],['--debug-checks'],['--release']]:
        r=subprocess.run([str(compiler),'run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if r.returncode: raise RuntimeError(r.stdout+r.stderr)
        outputs.append(r.stdout)
    assert len(set(outputs))==1,'reference configurations disagree'
    answers=outputs[0].splitlines();assert len(answers)==sum(len(g['route_queries'])+len(g['head_queries']) for g in graphs)
    offset=0
    for g in graphs:
        n=len(g['route_queries'])+len(g['head_queries']);g['answers']=answers[offset:offset+n];offset+=n
    report=dict(scope='Exact route, core-owner and macro-head helpers with explicit declaration/import/toolchain/session adapters. Diagnostic text and source parsing are outside scope.',compiler_version=version,reference_revision=revision,compiler_sha256=digest(compiler.read_bytes()),source_sha256={n:digest(s.encode()) for n,s in sources.items()},helper_sha256={n:digest(s.encode()) for n,s in helpers.items()},driver_sha256=digest(driver.encode()),toolchain_adapter_sha256=digest(TOOLCHAIN.encode()),capture_script_sha256=digest(Path(__file__).read_bytes()),fixture_sha256=digest((ROOT/'tools/route-fixtures.py').read_bytes()),shared_export_fixture_sha256=digest((ROOT/'tools/capture-export-reference.py').read_bytes()),configurations=['default','debug-checks','release'],cases=graphs)
    (ROOT/'evidence/routing-reference.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(f'Reference routes/heads: {len(graphs)} graphs, {len(answers)} outcomes with route records; three matching configurations')


if __name__=='__main__':main()
