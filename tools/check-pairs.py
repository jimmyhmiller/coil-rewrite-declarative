#!/usr/bin/env python3
"""Exercise independent pair policies and replay captured derive arm selection."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
compiler = ROOT/'build/schema-seed'
q = lambda x: json.dumps(x, ensure_ascii=False)
base = '(node Atom (value Int))\n'
policies = '''
(pair-selection first-int (start 1) (key symbol) (value int) (choose first))
(pair-selection last-text (start 0) (key keyword) (value text) (choose last))
(pair-selection any-value (start 0) (key keyword) (value any) (choose last))
(pair-selection huge-offset (start 9223372036854775807) (key keyword) (value keyword) (choose last))
'''
reference = json.loads((ROOT/'evidence/derive-reference.json').read_text())
replay = []
for case in reference['cases']:
    step = None
    for line in case['trace']:
        parts = line.split('|')
        if parts[0] == 'step':
            step = int(parts[1])
        if parts[0] == 'arm':
            replay.append((case['actions'][step][1], parts[1], None if parts[2]=='<none>' else parts[2]))
if not replay:
    raise RuntimeError('reference capture has no arm observations')
with tempfile.TemporaryDirectory(prefix='rewrite-pairs-') as directory:
    work = Path(directory)
    for name in ['types','scope','resolution','source','sequence','equality_runtime']:
        shutil.copyfile(ROOT/f'seed/{name}.coil',work/f'{name}.coil')
    shutil.copyfile(ROOT/'seed/generated/code_forms.coil',work/'code_forms.coil')
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    independent_source = subprocess.check_output([str(compiler)],input=(base+policies).encode())
    (work/'generated.coil').write_bytes(independent_source)
    header = '''(module fixture.main)
(import "rewrite.generated" :as independent)
(import "rewrite.codeforms" :as code)
(import "coil.alloc" :use *)
(import "coil.arraylist" :use *)
(import "coil.reader" :use *)
(import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena])
(defn main [] (-> i64)
  (let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) (malloc-allocator)) a (allocator (mut scratch))
        inputs (match (read-all a "(prefix n 5 n 8 n bad) (:k \\"first\\" :k 3 :k \\"last\\") (:k 9 :k [x]) () atom [:k x] (:struct first :struct last)" 1)
                 (Ok [v] v) (Err [_] (panic "parse")))]
    (defer (close! (mut scratch)))
    (match (independent/select-pair-first-int (elem inputs 0) "n")
      (Some [v] (unless (= (sx-tag v) 0) (panic "integer kind"))
                (let [(mut item) v] (unless (= (sexp-int (mut item)) 5) (panic "first integer"))))
      (None [] (panic "missing integer")))
    (match (independent/select-pair-last-text (elem inputs 1) "k")
      (Some [v] (unless (= (sx-sval v) "last") (panic "last text")))
      (None [] (panic "missing text")))
    (match (independent/select-pair-any-value (elem inputs 2) "k")
      (Some [v] (unless (= (sx-tag v) 7) (panic "any value")))
      (None [] (panic "missing any")))
    (for [i 0 (len inputs)]
      (match (independent/select-pair-huge-offset (elem inputs i) "k") (None []) (_ (panic "offset overflow"))))
    (for [i 3 6]
      (match (independent/select-pair-any-value (elem inputs i) "k") (None []) (_ (panic "container boundary"))))
'''
    body=[]
    for index,(source,key,expected) in enumerate(replay):
        check='(None []) (_ (panic "expected absent arm"))' if expected is None else f'(Some [v] (unless (= (sx-sval v) {q(expected)}) (panic "wrong captured arm"))) (_ (panic "missing captured arm"))'
        body.append(f'''(let [input (match (read-all a {q(source)} 1) (Ok [v] v) (Err [_] (panic "capture parse")))]
          (match (code/select-pair-derive-arms (elem input 0) {q(key)}) {check}))''')
    # Preserve the complete selected occurrence, not a reconstructed symbol.
    body.append('''(let [input (match (read-all a "(register-derive T :struct first :struct last)" 1) (Ok [v] v) (Err [_] (panic "metadata parse")))
                        chosen (sexp-nth (elem input 0) 5)]
      (set! (.hyg chosen) 17) (set! (.ctxt chosen) 29) (set! (.horigin chosen) 4) (set! (.hflags chosen) 11)
      (set! (.hmod chosen) (box! a HygModule (HygModule :name "definition")))
      (match (code/select-pair-derive-arms (elem input 0) "struct")
        (None [] (panic "missing metadata arm"))
        (Some [v] (unless (and (= (.hyg v) 17) (= (.ctxt v) 29) (= (.horigin v) 4) (= (.hflags v) 11)
                             (= (.hmod v) (.hmod chosen)) (= (.node-id v) (.node-id chosen))
                             (= (.source v) (.source chosen)) (= (.lo v) (.lo chosen)) (= (.hi v) (.hi chosen)))
                    (panic "selected syntax metadata changed")))))
    (println "pair selection: independent policies, captured derive arms and occurrence metadata passed") 0))''')
    driver=header+'\n'.join(body)
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:
        subprocess.run(['coil','run','main.coil',*flags],cwd=work,check=True)
for policy,message in [
    ('(pair-selection bad (start -1) (key keyword) (value symbol) (choose last))','pair start must be nonnegative'),
    ('(pair-selection bad (start 0) (key int) (value symbol) (choose last))','pair key must be keyword or symbol'),
    ('(pair-selection bad (start 0) (key keyword) (value missing) (choose last))','unknown pair value kind'),
    ('(pair-selection bad (start 0) (key keyword) (value symbol) (choose middle))','pair choice must be first or last'),
    ('(pair-selection bad/name (start 0) (key keyword) (value symbol) (choose last))','invalid pair selection name'),
    ('(pair-selection bad (start 0) (key keyword))','wrong syntax arity'),
    (policies+policies,'duplicate pair selection'),
]:
    result=subprocess.run([str(compiler)],input=(base+policy).encode(),capture_output=True)
    if result.returncode==0 or message not in (result.stdout+result.stderr).decode():
        raise RuntimeError(f'expected rejection {message}: {result.stdout!r} {result.stderr!r}')
host = Path(shutil.which('coil')).resolve(strict=True)
evidence=dict(host_version=subprocess.check_output([str(host),'--version'],text=True).strip(),
              host_sha256=hashlib.sha256(host.read_bytes()).hexdigest(),
              seed_sha256=hashlib.sha256(compiler.read_bytes()).hexdigest(),
              driver_sha256=hashlib.sha256(driver.encode()).hexdigest(),
              independent_generated_sha256=hashlib.sha256(independent_source).hexdigest(),
              scope='Generated pair selection and selected syntax occurrence preservation; derive registry and full admission are not replayed.',
              observations=len(replay),configurations=['default','debug-checks','release'],
              reference_sha256=hashlib.sha256((ROOT/'evidence/derive-reference.json').read_bytes()).hexdigest(),
              inputs={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                      ['tools/check-pairs.py','seed/pair_selection.coil','languages/pair_selection.schema','seed/generated/pair_forms.coil','languages/code.schema','seed/generated/code_forms.coil']})
(ROOT/'evidence/pair-selection-replay.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(f'Pair selection: {len(replay)} captured arm observations and invalid policies passed')
