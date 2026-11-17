#!/usr/bin/env python3
"""Check schema-derived canonical rows, sequence equality and occurrence provenance."""
from pathlib import Path
import subprocess, shutil, tempfile, hashlib, json
ROOT = Path(__file__).resolve().parents[1]
schema = b'''(sum Tree
(Item (left Text) (right Text) (number Int) (flag Bool))
(Pair (first Tree) (second Tree)) (Many (children (many Tree))))
(intern Tree)
(transform Tree Tree :occurrences
(Item (Item left right number flag)) (Pair (Pair first second)) (Many (Many children)))'''
driver = '''(module fixture.main)
(import "rewrite.generated" :use *) (import "rewrite.sequence" :as sequence)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *) (import "coil.reader" :use *)
(import "coil.result" :use *) (import "coil.str" :use [StrBuf])
(import "coil.scratch" :use [ScratchArena]) (import "coil.debug-allocator" :use [DebugAllocator])
(defn check [(a (dyn Allocator))] (-> void)
(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a) sa (allocator (mut scratch))
(mut input) (store-new a) (mut target) (store-new a)
text "(Many [(Item \\"ab\\" \\"c\\" 1 true) (Item \\"ab\\" \\"c\\" 1 true)]) (Many [(Item \\"ab\\" \\"c\\" 1 true) (Item \\"ab\\" \\"c\\" 1 true)])"
roots (match (read-all sa text 1) (Ok [v] v) (_ (panic "reader")))
one (match (parse-0 (mut input) (elem roots 0)) (Ok [v] v) (_ (panic "first")))
two (match (parse-0 (mut input) (elem roots 1)) (Ok [v] v) (_ (panic "second")))
origin (origin-of (elem roots 0))]
(defer (store-free! (mut target)))
(match (store-source! (mut input) 1 "intern.coil" text) (Ok [_]) (_ (panic "source")))
(let [(mut state) (transform-state-new a (mut input) (mut target))]
(match (transform-0-0 (mut state) one) (Ok [v] (unless (= (.index v) 1) (panic "first canonical root"))) (_ (panic "first map")))
(transform-state-free! (mut state)))
(let [(mut state) (transform-state-new a (mut input) (mut target))]
(match (transform-0-0 (mut state) two) (Ok [v] (unless (= (.index v) 1) (panic "second canonical root"))) (_ (panic "second map")))
(transform-state-free! (mut state)))
(unless (and (= (len (.rows0 target)) 2) (= (len (.origins0 target)) 2) (= (len (.traces target)) 6)) (panic "canonical counts"))
(let [first (.origin (get (.traces target) 2)) second (.origin (get (.traces target) 5))]
(unless (and (= (.source first) 1) (= (.source second) 1) (!= (.lo first) (.lo second))) (panic "collapsed occurrence sites")))
(for value (.strings (.source-data input)) (for [i 0 (len value)] (set! value i 88)))
(store-free! (mut input)) (close! (mut scratch))
; Key framing separates text boundaries, variant tags, bool and signed integer fields.
(let [different (match (intern-0! (mut target) (N0V0 "a" "bc" 1 true) origin) (Ok [v] v) (_ (panic "framed text")))
negative (match (intern-0! (mut target) (N0V0 "ab" "c" -1 true) origin) (Ok [v] v) (_ (panic "signed field")))
flag (match (intern-0! (mut target) (N0V0 "ab" "c" 1 false) origin) (Ok [v] v) (_ (panic "bool field")))]
(unless (and (= (.index different) 2) (= (.index negative) 3) (= (.index flag) 4)) (panic "key collision")))
; Equivalent sequence segmentation and an empty join use the same logical key.
(let [leaf (sequence/singleton! (mut (.sequences0 target)) (N0Id :index 0))
(mut parts) (ArrayList::new [i64] a)]
(defer (free! (mut parts))) (push! (mut parts) leaf) (push! (mut parts) leaf)
(let [joined (match (sequence/join! (mut (.sequences0 target)) (mut parts)) (Ok [v] v) (_ (panic "join")))]
(match (intern-0! (mut target) (N0V2 (N0Seq :index joined)) origin)
(Ok [v] (unless (= (.index v) 1) (panic "segmentation key"))) (_ (panic "joined intern")))))
(let [before (len (.rows0 target))]
(match (intern-0! (mut target) (N0V1 (N0Id :index 99999) (N0Id :index 0)) origin)
(Err [e] (match e (InternReference [_ _]) (_ (panic "reference error kind")))) (_ (panic "invalid child accepted")))
(match (intern-0! (mut target) (N0V2 (N0Seq :index 99999)) origin)
(Err [e] (match e (InternSequence [_]) (_ (panic "sequence error kind")))) (_ (panic "invalid sequence accepted")))
(unless (= before (len (.rows0 target))) (panic "failed construction mutated rows")))
; Source text for newly interned values is copied, and equal rows do not grow the pool.
(let [(mut buffer) (StrBuf::new a)]
(defer (free! (mut buffer)))
(for [i 0 2000]
(set! (.len (.bytes buffer)) 0) (push-i64! (mut buffer) i)
(let [one (match (intern-0! (mut target) (N0V0 (str buffer) "growth" i true) origin) (Ok [v] v) (_ (panic "growth")))
two (match (intern-0! (mut target) (N0V0 (str buffer) "growth" i true) origin) (Ok [v] v) (_ (panic "growth repeat")))]
(unless (= (.index one) (.index two)) (panic "growth duplicate")))))
(unless (= (len (.rows0 target)) 2005) (panic "nonlinear row growth"))
; Bypassing canonical construction is detected before a parent can depend on it.
(let [(mut bad) (store-new a) raw (append-0 (mut (.rows0 bad)) (N0V0 "raw" "" 0 false))]
(defer (store-free! (mut bad)))
(match (intern-0! (mut bad) (N0V1 raw raw) origin)
(Err [e] (match e (InternUntracked [_]) (_ (panic "untracked error kind")))) (_ (panic "untracked row accepted"))))))
(defn main [] (-> i64)
(let [debug (DebugAllocator::new (malloc-allocator))] (check (DebugAllocator::view debug))
(unless (= (DebugAllocator::deinit! debug) 0) (panic "intern leak"))) 0)
'''
with tempfile.TemporaryDirectory(prefix='rewrite-interning-') as directory:
    work = Path(directory)
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for name in ['types','scope','resolution','source','sequence']:
        shutil.copyfile(ROOT/f'seed/{name}.coil', work/f'{name}.coil')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')],input=schema))
    (work/'main.coil').write_text(driver)
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil','run','main.coil',*flags],cwd=work,check=True)
for source, message in [(schema+b'(intern Tree)', 'duplicate intern root'),(schema+b'(intern Missing)', 'unknown intern schema'),(schema+b'(intern Tree Tree)', 'expected (intern Schema)')]:
    result = subprocess.run([str(ROOT/'build/schema-seed')],input=source,capture_output=True)
    assert result.returncode and not result.stdout and message.encode() in result.stderr, result
digest = lambda data: hashlib.sha256(data).hexdigest()
inputs = [ROOT/'seed/interning.coil', ROOT/'seed/readers.coil', ROOT/'seed/transform.coil', ROOT/'seed/source.coil', ROOT/'seed/sequence.coil', Path(__file__)]
evidence = dict(scope='Schema-derived canonical row construction; exact content keys, canonical child identities and per-transform occurrence origins. Sequence storage itself is not interned, and exact identifier-site publication is not established.', configurations=['default','debug-checks','release'], unique_growth_rows=2000, final_rows=2005, repeated_root_rows=2, repeated_root_traces=6, schema_sha256=digest(schema), driver_sha256=digest(driver.encode()), inputs={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs})
(ROOT/'evidence/interning.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('Interning: exact framed keys, cross-state reuse, independent occurrence origins, segmented sequences, rejected invalid/untracked children, 2000 unique rows and ownership passed')
