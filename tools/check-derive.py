#!/usr/bin/env python3
"""Replay captured derive registration and settlement through production components."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
q=lambda value:json.dumps(value,ensure_ascii=False)
reference=json.loads((ROOT/'evidence/derive-reference.json').read_text())
HEADER='''(module fixture.main)
(import "rewrite.deriveregistry" :as registry)
(import "rewrite.deriveregistration" :as admission)
(import "rewrite.deriveprotocol" :as policy)
(import "rewrite.codeforms" :as forms)
(import "coil.alloc" :use *)
(import "coil.arraylist" :use *)
(import "coil.reader" :use *)
(import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena])
(import "coil.debug-allocator" :use [DebugAllocator])
(import "coil.primitive" :as primitive)
(import "coil.cc" :as cc)
(defstruct Fact [(name (slice u8)) (target (slice u8))])
(defstruct Context [(facts (ArrayList Fact))])
(defn macro-head :cc (cc/C) [(c (ptr Context)) (node Sexp) (module (Option (slice u8)))]
  (-> (Result (Option (slice u8)) (slice u8)))
  (let [name (sx-sval node)]
    (println "macro|{}|{}" name (match module (None [] "<none>") (Some [m] m)))
    (Ok (cond (= name "good") (Some "impl.good") (= name "other") (Some "impl.other") :else (None)))))
(defn trait :cc (cc/C) [(c (ptr Context)) (name (slice u8)) (module (Option (slice u8)))]
  (-> (Result (Option (slice u8)) (slice u8)))
  (println "trait|{}|{}" name (match module (None [] "<none>") (Some [m] m)))
  (let [(mut found) (None [(slice u8)])]
    (for fact (.facts c) (when (= (.name fact) name) (set! found (Some (.target fact)))))
    (match found
      (None [] (Ok (None)))
      (Some [target] (if (= target "!ambiguous") (Err "fixture trait ambiguity") (Ok (Some target)))))))
(defn failure [(error (registry/Failure (slice u8)))] (-> void)
  (match error
    (registry/Unresolved [row]
      (println "result|register-derive: '{}' in module '{}' does not name a trait" (.f4 row) (.f3 row)))
    (registry/Transition [error]
      (match error
        (policy/HandlerError [_ reason]
          (match reason
            (registry/Resolution [message] (println "result|{}" message))
            (registry/Duplicate [previous]
              (println "result|register-derive: trait '{}' already has a deriver, registered in '{}'" (.f0 previous) (.f3 previous)))))
        (_ (panic "invalid registration protocol"))))))
(defn print-admission [(result (Result i64 (admission/Error (slice u8))))] (-> void)
  (match result
    (Ok [_] (println "result|ok"))
    (Err [e] (match e
      (admission/InvalidTrait [] (println "result|register-derive: expected (register-derive Trait :struct FN :sum FN)"))
      (admission/MissingArm [] (println "result|register-derive: each arm must name a [(T Code)] -> Code function in scope"))
      (admission/NoArms [] (println "result|register-derive: needs at least one of :struct FN / :sum FN"))
      (admission/Macro [message] (println "result|{}" message))
      (admission/Registry [e] (failure e))))))
(defn print-result [(result (Result bool (registry/Failure (slice u8))))] (-> void)
  (match result (Ok [_] (println "result|ok")) (Err [e] (failure e))))
(defn print-state [(r (ptr registry/Registry))] (-> void)
  (for row (.entries r)
    (println "row|{}|{}|{}|{}|{}" (.f0 row) (.f1 row) (.f2 row) (.f3 row) (.f4 row))))
'''
body=['(defn main [] (-> i64) (let [debug (DebugAllocator::new (malloc-allocator)) owned (DebugAllocator::view debug)]']
for i,case in enumerate(reference['cases']):
    module='(None [(slice u8)])' if case['module'] is None else f'(Some {q(case["module"])})'
    body += ['(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) (malloc-allocator)) a (allocator (mut scratch))',
             '(mut r) (registry/create owned) (mut c) (Context :facts (ArrayList::new [Fact] a))',
             '(mut traits) (registry/Resolver [Context (slice u8)] :context (primitive/cast (ptr Context) (mut c)) :lookup (primitive/fnptr-of trait))',
             '(mut macros) (admission/Macros [Context (slice u8)] :context (primitive/cast (ptr Context) (mut c)) :resolve (primitive/fnptr-of macro-head))]',
             '(defer (close! (mut scratch))) (defer (registry/release! (mut r)))',f'(println "case|{i}")']
    for step,action in enumerate(case['actions']):
        body.append(f'(println "step|{step}|{action[0]}")')
        if action[0]=='register':
            body.append(f'''(let [input (match (read-all a {q(action[1])} 1) (Ok [v] v) (Err [_] (panic "fixture parse"))) form (elem input 0)]
              (if (admission/recognizes? form)
                (do
                  (println "arm|struct|{{}}" (match (forms/select-pair-derive-arms form "struct") (None [] "<none>") (Some [node] (sx-sval node))))
                  (println "arm|sum|{{}}" (match (forms/select-pair-derive-arms form "sum") (None [] "<none>") (Some [node] (sx-sval node))))
                  (print-admission (admission/register! a (mut r) (mut traits) (mut macros) form {module})))
                (do (println "unrecognized") (println "result|ok"))))''')
        elif action[0]=='expose':
            body.append(f'(push! (mut (.facts c)) (Fact :name {q(action[1])} :target {q(action[2])})) (println "result|ok")')
        elif action[0]=='reset':
            body.append('(registry/reset! (mut r)) (println "result|ok")')
        else:
            body.append(f'(print-result (registry/{action[0]}! (mut r) (mut traits)))')
        body.append('(print-state (mut r))')
    body.append(')')
body.append('(unless (= (DebugAllocator::deinit! debug) 0) (panic "derive registry leak"))) 0)')
driver=HEADER+'\n'.join(body)+'\n'
expected=''.join(f'case|{i}\n'+'\n'.join(c['trace'])+'\n' for i,c in enumerate(reference['cases']))
runtime=['derive_registry','derive_registration','types','scope','resolution','source','sequence','equality_runtime']
generated=['derive_forms','derive_protocol','code_forms']
with tempfile.TemporaryDirectory(prefix='rewrite-derive-') as directory:
    work=Path(directory)
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for name in runtime:shutil.copyfile(ROOT/f'seed/{name}.coil',work/f'{name}.coil')
    for name in generated:shutil.copyfile(ROOT/f'seed/generated/{name}.coil',work/f'{name}.coil')
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:
        result=subprocess.run(['coil','run','main.coil',*flags],cwd=work,capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        if result.stdout!=expected:
            import difflib
            raise RuntimeError(''.join(difflib.unified_diff(expected.splitlines(True),result.stdout.splitlines(True),fromfile='reference',tofile='rewrite')))
host=Path(shutil.which('coil')).resolve(strict=True)
paths=['tools/check-derive.py','compiler/expansion/derive.schema','compiler/expansion/derive_registration.protocol','compiler/syntax/code.schema']+[f'seed/{n}.coil' for n in runtime]+[f'seed/generated/{n}.coil' for n in generated]
digest=lambda data:hashlib.sha256(data).hexdigest()
evidence=dict(scope='Production derive surface registration and registry transitions against captured helper traces, with explicit macro/trait resolver fixtures. Not real module loading, source diagnostics or complete generated-form admission.',
              scenarios=len(reference['cases']),actions=sum(len(c['actions']) for c in reference['cases']),
              configurations=['default','debug-checks','release'],allocator_leaks=0,
              host_version=subprocess.check_output([str(host),'--version'],text=True).strip(),host_sha256=digest(host.read_bytes()),
              reference_sha256=digest((ROOT/'evidence/derive-reference.json').read_bytes()),driver_sha256=digest(driver.encode()),
              inputs={path:digest((ROOT/path).read_bytes()) for path in paths})
(ROOT/'evidence/derive-replay.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(f'Derive replay: {evidence["scenarios"]} scenarios, {evidence["actions"]} actions; full traces match in three configurations; no registry allocator leaks')
