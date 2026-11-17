#!/usr/bin/env python3
"""Check lazy typed sequence selection independently of type elaboration."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
schema=b'''(node Atom (value Int))
(node Choice (children (many Atom)) (fallback Atom))
(node Output (value Int))
(transform Atom Output (Atom (Output value)))
(transform Choice Output (Choice (first-or children fallback)))'''
driver='''(module fixture.main)
(import "rewrite.generated" :use *) (import "rewrite.sequence" :as sequence)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.result" :use *) (import "coil.reader" :use *)
(import "coil.scratch" :use [ScratchArena]) (import "coil.debug-allocator" :use [DebugAllocator])
(defn check [(a (dyn Allocator))] (-> void)
(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a) sa (allocator (mut scratch))
(mut input) (store-new a) (mut target) (store-new a)
roots (match (read-all sa "(Choice [(Atom 7) (Atom 8)] (Atom 99)) (Choice [] (Atom 42))" 1) (Ok [v] v) (_ (panic "reader")))
present (match (parse-1 (mut input) (elem roots 0)) (Ok [v] v) (_ (panic "present")))
empty (match (parse-1 (mut input) (elem roots 1)) (Ok [v] v) (_ (panic "empty")))
nonempty (.f0 (get (.rows1 input) (.index present)))
empty-sequence (.f0 (get (.rows1 input) (.index empty)))
original-first (get (.values (.sequences0 input)) 0)
(mut parts) (ArrayList::new [i64] a) (mut deep) (.index nonempty)]
(defer (close! (mut scratch))) (defer (store-free! (mut input))) (defer (store-free! (mut target))) (defer (free! (mut parts)))
(match (store-source! (mut input) 1 "selection.coil" "(Choice [(Atom 7) (Atom 8)] (Atom 99)) (Choice [] (Atom 42))") (Ok [_]) (_ (panic "source")))
; Neither the ignored second child nor the unused fallback is valid.
(set! (mut (.values (.sequences0 input))) 1 (N0Id :index 9999))
(set! (.f1 (elem (mut (.rows1 input)) (.index present))) (N0Id :index 9999))
(push! (mut parts) deep) (push! (mut parts) (sequence/singleton! (mut (.sequences0 input)) original-first))
(for [i 0 25000]
(set! (mut parts) 0 deep)
(set! deep (match (sequence/join! (mut (.sequences0 input)) (mut parts)) (Ok [v] v) (_ (panic "join")))))
(set! (.f0 (elem (mut (.rows1 input)) (.index present))) (N0Seq :index deep))
(let [(mut state) (transform-state-new a (mut input) (mut target))]
(defer (transform-state-free! (mut state))) (set! (.sharing? state) false)
(let [id (match (transform-1-2 (mut state) present) (Ok [v] v) (_ (panic "lazy present")))]
(unless (and (= (.f0 (get (.rows2 target) (.index id))) 7) (= (len (.rows2 target)) 1)) (panic "visited tail or fallback")))
(let [id (match (transform-1-2 (mut state) empty) (Ok [v] v) (_ (panic "fallback")))]
(unless (= (.f0 (get (.rows2 target) (.index id))) 42) (panic "fallback value")))
(set! (mut (.values (.sequences0 input))) 0 (N0Id :index 9999))
(match (transform-1-2 (mut state) present) (Err [e] (match e (TransformReference [_ _]) (_ (panic "wrong child error")))) (_ (panic "invalid child became default")))
(set! (mut (.values (.sequences0 input))) 0 original-first)
(set! (.f0 (elem (mut (.rows1 input)) (.index present))) (N0Seq :index (- 0 1)))
(match (transform-1-2 (mut state) present) (Err [e] (match e (TransformSequence [_]) (_ (panic "wrong sequence error")))) (_ (panic "invalid sequence became default")))
(set! (.f0 (elem (mut (.rows1 input)) (.index present))) (N0Seq :index deep))
(let [edge (.start (get (.segments (.sequences0 input)) deep))
previous (get (.edges (.sequences0 input)) edge)]
(set! (mut (.edges (.sequences0 input))) edge deep)
(match (transform-1-2 (mut state) present) (Err [e] (match e (TransformSequence [e] (match e (sequence/SequenceCycle [_]) (_ (panic "wrong cycle error")))) (_ (panic "wrong cycle wrapper")))) (_ (panic "cycle accepted")))
(set! (mut (.edges (.sequences0 input))) edge previous))
; Failure unwinds transform memo state, so retry works.
(match (transform-1-2 (mut state) present) (Ok [_]) (_ (panic "retry"))))))
(defn main [] (-> i64)
(let [debug (DebugAllocator::new (malloc-allocator))]
(check (DebugAllocator::view debug))
(unless (= (DebugAllocator::deinit! debug) 0) (panic "selection leak"))) 0)
'''
with tempfile.TemporaryDirectory(prefix='rewrite-first-or-') as directory:
    work=Path(directory);(work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for n in ['types','scope','resolution','source','sequence']:shutil.copyfile(ROOT/f'seed/{n}.coil',work/f'{n}.coil')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')],input=schema))
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:subprocess.run(['coil','run','main.coil',*flags],cwd=work,check=True)
for invalid in [
    schema.replace(b'first-or children fallback',b'first-or children'),
    schema.replace(b'first-or children fallback',b'first-or missing fallback'),
    schema.replace(b'first-or children fallback',b'first-or fallback fallback'),
    schema.replace(b'first-or children fallback',b'first-or children (Unknown 0)'),
    schema.replace(b'(first-or children fallback)',b'(Output (first-or children 0))'),
    schema.replace(b'(transform Atom Output (Atom (Output value)))',b''),
]:
    r=subprocess.run([str(ROOT/'build/schema-seed')],input=invalid,capture_output=True)
    assert r.returncode!=0 and not r.stdout,(invalid,r)
print('First-or transforms: lazy default/tail, 25000-deep joins, invalid references, cycles, retry and declaration validation passed')
