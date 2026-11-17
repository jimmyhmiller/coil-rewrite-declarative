#!/usr/bin/env python3
"""Exercise bounded captures, ignored suffixes and integer guards independently."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
schema=b'''(node Item (value Int)) (syntax Item (Item (int value :min -2)))
(node Window (items (many Item))) (syntax Window (Window (vector "take" (rest items :limit 2))))
(node Ignore (value Item)) (syntax Ignore (Ignore (list "first" (ref value) (skip-rest))))
(node Empty (items (many Item))) (syntax Empty (Empty (list "zero" (rest items :limit 0))))
(node Huge (items (many Item))) (syntax Huge (Huge (list "huge" (rest items :limit 9223372036854775807))))
(node Nested (value Int)) (syntax Nested (Nested (list "outer" (vector (int value :min 1) (skip-rest)))))'''
driver='''(module fixture.main)
(import "rewrite.generated" :use *)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena]) (import "coil.debug-allocator" :use [DebugAllocator])
(defn size [(store (ptr Store)) (items N0Seq)] (-> i64)
(match (sequence-size-0 store items) (Some [n] n) (_ (panic "invalid sequence"))))
(defn check [(a (dyn Allocator))] (-> void)
(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a) sa (allocator (mut scratch))
(mut store) (store-new a)
input (match (read-all sa "[take -2 3 bad] [take] [take -3] (first 8 bad []) (first) (zero bad []) (huge 1 2) (outer [9 bad]) (outer [0])" 1) (Ok [v] v) (Err [_] (panic "reader")))]
(defer (close! (mut scratch))) (defer (store-free! (mut store)))
(let [view (match (view-1 sa (elem input 0)) (Ok [v] (match v (Some [v] v) (_ (panic "missing view")))) (_ (panic "view")))
capture (get (.captures view) 0)
id (match (surface-1 (mut store) (elem input 0)) (Ok [id] id) (_ (panic "window")))
row (get (.rows1 store) (.index id))]
(unless (and (.rest? capture) (= (.start capture) 1) (= (.count capture) 2)
             (= (size (mut store) (.f0 row)) 2) (= (len (.rows0 store)) 2)) (panic "bounded capture")))
(let [id (match (surface-1 (mut store) (elem input 1)) (Ok [id] id) (_ (panic "empty window"))) row (get (.rows1 store) (.index id))]
(unless (= (size (mut store) (.f0 row)) 0) (panic "empty sequence")))
(match (surface-1 (mut store) (elem input 2)) (Err [_]) (_ (panic "minimum ignored")))
(match (surface-2 (mut store) (elem input 3)) (Ok [_]) (_ (panic "ignored suffix parsed")))
(match (surface-2 (mut store) (elem input 4)) (Err [_]) (_ (panic "required prefix absent")))
(let [before (len (.rows0 store)) id (match (surface-3 (mut store) (elem input 5)) (Ok [id] id) (_ (panic "zero limit"))) row (get (.rows3 store) (.index id))]
(unless (and (= before (len (.rows0 store))) (= (size (mut store) (.f0 row)) 0)) (panic "zero limit parsed children")))
(let [id (match (surface-4 (mut store) (elem input 6)) (Ok [id] id) (_ (panic "large limit"))) row (get (.rows4 store) (.index id))]
(unless (= (size (mut store) (.f0 row)) 2) (panic "large limit overflow")))
(match (surface-5 (mut store) (elem input 7)) (Ok [_]) (_ (panic "nested suffix")))
(match (surface-5 (mut store) (elem input 8)) (Err [_]) (_ (panic "nested guard")))))
(defn main [] (-> i64)
(let [debug (DebugAllocator::new (malloc-allocator))]
(check (DebugAllocator::view debug))
(unless (= (DebugAllocator::deinit! debug) 0) (panic "syntax tails leak"))) 0)
'''
with tempfile.TemporaryDirectory(prefix='rewrite-syntax-tails-') as directory:
    work=Path(directory);(work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for n in ['types','scope','resolution','source','sequence']:shutil.copyfile(ROOT/f'seed/{n}.coil',work/f'{n}.coil')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')],input=schema))
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:subprocess.run(['coil','run','main.coil',*flags],cwd=work,check=True)
for invalid in [
    schema.replace(b':limit 2',b':limit -1'),
    schema.replace(b':limit 2',b':limit two'),
    schema.replace(b':limit 2',b':min 2'),
    schema.replace(b':min -2',b':limit 2'),
    schema.replace(b':min -2',b':min false'),
    schema.replace(b'(skip-rest)',b'(skip-rest ignored)',1),
    schema.replace(b'(ref value) (skip-rest)',b'(skip-rest) (ref value)'),
    schema.replace(b'(rest items :limit 2)',b'(rest items :limit 2) "last"'),
]:
    r=subprocess.run([str(ROOT/'build/schema-seed')],input=invalid,capture_output=True)
    assert r.returncode!=0 and not r.stdout,(invalid,r)
print('Syntax tails: independent bounds, zero/large limits, ignored invalid suffixes, nested guards and declaration errors passed')
