#!/usr/bin/env python3
"""Check identifier context capture, owned transforms and deferred lexical identity."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
schema=b'''(node Name (owner Text) (spelling Text) (stamp Int))
(syntax Name (Name (identifier spelling stamp owner)))
(node Lowered (name Text) (scope Int) (module Text))
(transform Name Lowered (Name (Lowered spelling stamp owner)))'''
driver='''(module fixture.main)
(import "rewrite.generated" :use *) (import "rewrite.lexical" :as lexical)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *) (import "coil.str" :use [StrBuf])
(import "coil.scratch" :use [ScratchArena]) (import "coil.debug-allocator" :use [DebugAllocator])
(import "coil.primitive" :as primitive)
(defn build [(a (dyn Allocator)) (target (ptr Store)) (scope i64)] (-> N1Id)
(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a) sa (allocator (mut scratch))
(mut input) (store-new a) (mut text) (StrBuf::new sa)
forms (match (read-all sa "name :not-a-name" 5) (Ok [v] v) (_ (panic "reader")))
form (elem forms 0)]
(defer (close! (mut scratch))) (defer (store-free! (mut input)))
(match (store-source! (mut input) 5 "identifiers.coil" "name :not-a-name") (Ok [_]) (_ (panic "source registration")))
(push-str! (mut text) "owner.λ")
(let [(mut module) (HygModule :name (str text))]
(set! (.hmod form) (primitive/cast (ptr HygModule) (mut module))) (set! (.hyg form) scope)
(let [before (next-node-id)
view (match (view-0 sa form) (Ok [v] (match v (Some [v] v) (_ (panic "view absent")))) (_ (panic "view")))
id (match (surface-0 (mut input) form) (Ok [v] v) (_ (panic "capture")))
(mut state) (transform-state-new a (mut input) target)]
(defer (transform-state-free! (mut state)))
(unless (and (= (next-node-id) (+ before 1)) (= (len (.captures view)) 3)) (panic "capture allocated identity"))
(for capture (.captures view)
(unless (and (= (.hyg (.source capture)) scope) (= (.count capture) 1) (not (.rest? capture))) (panic "capture occurrence")))
(match (view-0 sa (elem forms 1)) (Ok [v] (match v (None []) (_ (panic "keyword identifier")))) (_ (panic "no-match")))
(match (surface-0 (mut input) (elem forms 1)) (Err [_]) (_ (panic "keyword parsed")))
(let [out (match (transform-0-1 (mut state) id) (Ok [v] v) (_ (panic "transform")))]
; Poison both source pools before release: the target owns both name and module.
(for value (.strings (.source-data input)) (for [i 0 (len value)] (set! value i 88)))
(for [i 0 (len (str text))] (set! (str text) i 88))
out)))))
(defn check [(a (dyn Allocator)) (scope i64)] (-> void)
(let [(mut target) (store-new a) id (build a (mut target) scope)
row (get (.rows1 target) (.index id))
(mut first) (StrBuf::new a) (mut second) (StrBuf::new a) (mut expected) (StrBuf::new a)
before (next-node-id)]
(defer (store-free! (mut target))) (defer (free! (mut first))) (defer (free! (mut second))) (defer (free! (mut expected)))
(unless (and (= (.f0 row) "name") (= (.f1 row) scope) (= (.f2 row) "owner.λ")) (panic "owned context"))
(lexical/write! (mut first) (.f0 row) (.f1 row) (.f2 row))
(lexical/write! (mut second) (.f0 row) (.f1 row) (.f2 row))
(cond (< scope 0)
(do (push-str! (mut expected) "$datum") (push-i64! (mut expected) (+ before 1)) (push-str! (mut expected) "$name")
(unless (and (= (str first) (str expected)) (!= (str first) (str second)) (= (next-node-id) (+ before 3))) (panic "fresh occurrence")))
(= scope 0)
(unless (and (= (str first) "name") (= (str second) "name") (= (next-node-id) (+ before 1))) (panic "raw name"))
:else (do (push-str! (mut expected) "$scope") (push-i64! (mut expected) scope) (push-str! (mut expected) "@owner.λ$name")
(unless (and (= (str first) (str expected)) (= (str first) (str second)) (= (next-node-id) (+ before 1))) (panic "stable scoped name"))))))
(defn main [] (-> i64)
(let [debug (DebugAllocator::new (malloc-allocator)) a (DebugAllocator::view debug)]
(check a (- 0 7)) (check a 0) (check a 99)
(unless (= (DebugAllocator::deinit! debug) 0) (panic "identifier leak"))) 0)
'''
with tempfile.TemporaryDirectory(prefix='rewrite-identifiers-') as directory:
    work=Path(directory);(work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for n in ['types','scope','resolution','source','sequence','lexical']:shutil.copyfile(ROOT/f'seed/{n}.coil',work/f'{n}.coil')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')],input=schema))
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:subprocess.run(['coil','run','main.coil',*flags],cwd=work,check=True)
for invalid in [
    schema.replace(b'identifier spelling stamp owner',b'identifier spelling stamp'),
    schema.replace(b'identifier spelling stamp owner',b'identifier spelling stamp missing'),
    schema.replace(b'identifier spelling stamp owner',b'identifier spelling stamp spelling'),
    schema.replace(b'identifier spelling stamp owner',b'identifier stamp spelling owner'),
    schema.replace(b'(stamp Int)',b'(stamp Text)'),
    schema.replace(b'(owner Text)',b'(owner (many Name))'),
    b'(sum X (A (s Text) (h Int) (m Text)) (B (b Bool))) (syntax X (A (identifier s h m)) (B (bool b)))',
    b'(sum X (A (s Text)) (B (s Text) (h Int) (m Text))) (syntax X (A (symbol s)) (B (identifier s h m)))',
]:
    r=subprocess.run([str(ROOT/'build/schema-seed')],input=invalid,capture_output=True)
    assert r.returncode!=0 and not r.stdout,(invalid,r)
print('Identifier captures: reordered fields, owned context through transformation, borrowed views, deferred fresh identities and declaration errors passed')
