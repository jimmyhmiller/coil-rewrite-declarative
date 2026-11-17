#!/usr/bin/env python3
"""Capture exact derive admission/registry helpers with explicit resolver adapters."""
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

def digest(data):
    return hashlib.sha256(data).hexdigest()

def q(value):
    return json.dumps(value, ensure_ascii=False)

def cases():
    result = []
    forms = [
        'x', '()', '(register-derive)', '[register-derive T :struct good]',
        '(register-derive 12 :struct good)', '(register-derive T)',
        '(register-derive T :struct good)', '(register-derive T :sum other)',
        '(register-derive T :struct good :sum other)',
        '(register-derive T :struct missing :sum other)',
        '(register-derive T :struct good :sum missing)',
        '(register-derive T :struct missing :sum missing)',
        '(register-derive T :struct missing :struct good)',
        '(register-derive T :struct good :struct missing)',
        '(register-derive T :struct good :struct 12)',
        '(register-derive T :struct 12 :struct good)',
        '(register-derive T :struct good :sum)',
        '(register-derive T :unknown good :sum other)',
        '(register-derive T junk :struct good)',
        '(register-derive T :struct "good")',
        '(register-derive T :struct [good])',
        '(register-derive T :sum other :struct good :sum good)',
        '(register-derive λ :struct good)',
    ]
    for form in forms:
        result.append(dict(name=f'form-{len(result)}', module='app', actions=[['register', form], ['finish']]))
    result += [
        dict(name='settled-duplicate', module='app', actions=[['expose','T','lib.T'], ['register', forms[6]], ['register',forms[7]], ['finish']]),
        dict(name='pending-settles', module='app', actions=[['register', forms[6]], ['settle'], ['expose','T','lib.T'], ['settle'], ['finish']]),
        dict(name='pending-alias-duplicate', module='app', actions=[['register',forms[6]], ['register','(register-derive Alias :sum other)'], ['expose','T','lib.T'], ['expose','Alias','lib.T'], ['settle'], ['finish']]),
        dict(name='partial-settlement', module='app', actions=[['register',forms[6]], ['register','(register-derive U :sum other)'], ['expose','T','lib.T'], ['expose','U','!ambiguous'], ['settle'], ['expose','U','lib.U'], ['finish']]),
        dict(name='registration-ambiguity', module='app', actions=[['expose','T','!ambiguous'], ['register',forms[6]], ['finish']]),
        dict(name='reset', module='app', actions=[['expose','T','lib.T'], ['register',forms[6]], ['reset'], ['register',forms[7]], ['finish']]),
        dict(name='anonymous-owner', module=None, actions=[['register',forms[6]], ['expose','T','lib.T'], ['finish']]),
        dict(name='empty-owner', module='', actions=[['register',forms[6]], ['expose','T','lib.T'], ['finish']]),
    ]
    return result

HEADER = '''(module reference.main)
(import "coil.alloc" :use *)
(import "coil.arraylist" :use *)
(import "coil.avec" :use [AVec])
(import "coil.reader" :use *)
(import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena])
(import "coil.text" :use [sconcat3])
(import "coil.primitive" :as primitive)
(defstruct Diag [(msg (slice u8))])
(defstruct ImpEntry [(unused i64)])
(defstruct ExpEntry [(unused i64)])
(defstruct CtCtx [(unused i64)])
(defstruct Fact [(name (slice u8)) (target (slice u8))])
(defn facts [] (-> (ptr (ArrayList Fact))) (primitive/alloc-static (ArrayList Fact)))
(defn owner [] (-> (ptr (dyn Allocator))) (primitive/alloc-static (dyn Allocator)))
(defn unit-allocator [] (-> (dyn Allocator)) (load (owner)))
(defn ct-own-str [(s (slice u8))] (-> (slice u8)) (sconcat3 (unit-allocator) s "" ""))
(defn derr [(s (slice u8))] (-> Diag) (Diag :msg s))
(defn derive-reg [] (-> (ptr DeriveReg)) (primitive/alloc-static DeriveReg))
; Explicit fixture resolvers: no namespace, signature, import or hygiene claims.
(defn resolve-macro-head [(node Sexp) (module (Option (slice u8)))
                         (macros (ptr (ArrayList (slice u8)))) (impb (ptr (AVec ImpEntry)))
                         (expb (ptr (AVec ExpEntry))) (a (dyn Allocator))] (-> (Option (slice u8)))
  (let [name (sx-sval node)]
    (println "macro|{}|{}" name (match module (None [] "<none>") (Some [m] m)))
    (cond (= name "good") (Some "impl.good") (= name "other") (Some "impl.other") :else (None))))
(defn resolve-trait-ref [(name (slice u8)) (module (Option (slice u8))) (ctx (ptr CtCtx))
                        (impb (ptr (AVec ImpEntry))) (expb (ptr (AVec ExpEntry))) (a (dyn Allocator))]
  (-> (Result (Option (slice u8)) Diag))
  (println "trait|{}|{}" name (match module (None [] "<none>") (Some [m] m)))
  (block :done
    (let [(mut found) (None [(slice u8)])]
      (for fact (load (facts)) (when (= (.name fact) name) (set! found (Some (.target fact)))))
      (match found
        (None [] (Ok (None)))
        (Some [target] (if (= target "!ambiguous") (Err (derr "fixture trait ambiguity")) (Ok (Some target))))))))
(defn print-state [(diagnostic (Option Diag))] (-> void)
  (println "result|{}" (match diagnostic (None [] "ok") (Some [d] (.msg d))))
  (for row (.items (derive-reg-ready))
    (println "row|{}|{}|{}|{}|{}" (.trait row) (.arm_struct row) (.arm_sum row) (.owner row) (.spelled row))))
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--compiler', default='coil')
    args=parser.parse_args()
    compiler=Path(shutil.which(args.compiler) or args.compiler).resolve(strict=True)
    version=subprocess.check_output([str(compiler),'--version'],text=True).strip()
    revision=re.search(r'commit ([0-9a-f]+)', version).group(1)
    revision=subprocess.check_output(['git','rev-parse',revision],cwd=args.reference,text=True).strip()
    paths={'expander':'frontend/expander', 'parser':'frontend/parser', 'metastate':'meta/metastate'}
    sources={name:subprocess.check_output(['git','show',f'{revision}:src/compiler/{path}.coil'],cwd=args.reference,text=True) for name,path in paths.items()}
    names={
        'parser':['sx-len','sx-at'],
        'expander':['is-register-derive-form','regd-arm','regd-resolve','register-derive-form!'],
        'metastate':['DeriveEnt','DeriveReg','derive-reg-reset!','derive-reg-ready','derive-owner-module','derive-reg-settled','derive-reg-duplicate','derive-reg-put!','derive-reg-settle!','derive-reg-finish!'],
    }
    helpers={name:definition(sources[source],name) for source, entries in names.items() for name in entries}
    fixtures=cases()
    body=['(defn main [] (-> i64)']
    for index,case in enumerate(fixtures):
        module='(None [(slice u8)])' if case['module'] is None else f'(Some {q(case["module"])})'
        body += ['(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) (malloc-allocator)) a (allocator (mut scratch))',
                 'impb (primitive/cast (ptr (AVec ImpEntry)) 0) expb (primitive/cast (ptr (AVec ExpEntry)) 0)',
                 'macros (primitive/cast (ptr (ArrayList (slice u8))) 0)]',
                 '(defer (close! (mut scratch))) (store! (owner) a)',
                 '(store! (facts) (ArrayList::new [Fact] a))',
                 '(store! (derive-reg) (DeriveReg :items (ArrayList::new [DeriveEnt] a) :init 1))',
                 f'(println "case|{index}")']
        for step,action in enumerate(case['actions']):
            body.append(f'(println "step|{step}|{action[0]}")')
            if action[0]=='register':
                body.append(f'''(let [forms (match (read-all a {q(action[1])} 1) (Ok [v] v) (Err [_] (panic "fixture parse"))) form (elem forms 0)]
                  (if (is-register-derive-form form)
                    (do
                      (println "arm|struct|{{}}" (match (regd-arm (sx-items (load form)) "struct") (None [] "<none>") (Some [node] (sx-sval node))))
                      (println "arm|sum|{{}}" (match (regd-arm (sx-items (load form)) "sum") (None [] "<none>") (Some [node] (sx-sval node))))
                      (print-state (register-derive-form! form {module} macros impb expb a)))
                    (do (println "unrecognized") (print-state (None)))))''')
            elif action[0]=='expose':
                body.append(f'(push! (facts) (Fact :name {q(action[1])} :target {q(action[2])})) (print-state (None))')
            elif action[0]=='reset':
                body.append('(derive-reg-reset!) (print-state (None))')
            else:
                body.append(f'(print-state (derive-reg-{action[0]}! impb expb a))')
        body.append(')')
    body.append('0)')
    driver=HEADER+'\n'+'\n'.join(helpers.values())+'\n'+'\n'.join(body)+'\n'
    work=ROOT/'build/derive-reference'; work.mkdir(parents=True,exist_ok=True)
    (work/'Coil.toml').write_text('[package]\nname="reference"\nentry="main.coil"\nsource-roots=["."]\n')
    (work/'main.coil').write_text(driver)
    outputs=[]
    for flags in [[],['--debug-checks'],['--release']]:
        result=subprocess.run([str(compiler),'run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)
        outputs.append(result.stdout)
    if len(set(outputs))!=1: raise RuntimeError('reference derive behavior differs across configurations')
    current=None
    for line in outputs[0].splitlines():
        if line.startswith('case|'):
            current=fixtures[int(line.split('|')[1])]; current['trace']=[]
        else:
            if current is None: raise RuntimeError(f'unexpected output: {line}')
            current['trace'].append(line)
    if any('trace' not in c or sum(t.startswith('step|') for t in c['trace'])!=len(c['actions']) for c in fixtures):
        raise RuntimeError('incomplete reference trace')
    evidence=dict(scope='Exact derive recognition, arm selection, registration, pending settlement, duplicates and finish helpers. Macro/trait resolution and allocation state use explicit fixture adapters; not full admission or resolver parity.',
                  compiler_version=version, compiler_sha256=digest(compiler.read_bytes()), reference_revision=revision,
                  source_sha256={name:digest(text.encode()) for name,text in sources.items()},
                  helper_sha256={name:digest(text.encode()) for name,text in helpers.items()},
                  capture_script_sha256=digest(Path(__file__).read_bytes()),driver_sha256=digest(driver.encode()),
                  configurations=['default','debug-checks','release'],equal_across_configurations=True,cases=fixtures)
    (ROOT/'evidence/derive-reference.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    (work/'stdout.txt').write_text(outputs[0])
    print(f'Derive admission reference: {len(fixtures)} scenarios, {sum(len(c["actions"]) for c in fixtures)} actions, matching in three configurations')

if __name__=='__main__': main()
