#!/usr/bin/env python3
"""Check declared occurrence effects across node and sequence transformation paths."""
from pathlib import Path
import subprocess,shutil,tempfile
ROOT=Path(__file__).resolve().parents[1]
schema=b'''(node Name (name Text) (scope Int) (module Text))
(node Group (items (many Name))) (node Wrapper (group Group))
(node Out (name Text)) (node OutGroup (items (many Out))) (node OutWrapper (group OutGroup))
(node Choice (items (many Name)) (fallback Name)) (node Raw (name Text))
(transform Name Out :occurrences (Name (Out (lexical name scope module))))
(transform Group OutGroup :occurrences (Group (OutGroup items)))
(transform Wrapper OutWrapper :occurrences (Wrapper (OutWrapper group)))
(transform Choice Out :occurrences (Choice (first-or items fallback)))
(transform Name (many Out) :occurrences (Name (items (Out (lexical name scope module)) (Out (lexical name scope module)))))
(transform Group (many Out) :occurrences (Group (items (spread items))))
(transform Name Raw (Name (Raw name)))'''
driver='''(module fixture.main)
(import "rewrite.generated" :use *) (import "rewrite.sequence" :as sequence)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena]) (import "coil.debug-allocator" :use [DebugAllocator])
(defn check [(a (dyn Allocator))] (-> void)
(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a) sa (allocator (mut scratch))
(mut input) (store-new a) (mut target) (store-new a)
text "(Name \\"x\\" -1 \\"definition\\")"
forms (match (read-all sa text 1) (Ok [v] v) (_ (panic "reader")))
name (match (parse-0 (mut input) (elem forms 0)) (Ok [v] v) (_ (panic "name")))
origin (origin-of (elem forms 0)) (mut ids) (ArrayList::new [N0Id] a)
(mut parts) (ArrayList::new [i64] a)]
(defer (close! (mut scratch))) (defer (store-free! (mut input))) (defer (store-free! (mut target)))
(defer (free! (mut ids))) (defer (free! (mut parts)))
(match (store-source! (mut input) 1 "names.coil" text) (Ok [_]) (_ (panic "source")))
(push! (mut ids) name) (push! (mut ids) name)
(let [xs (sequence-0 (mut input) (mut ids))
group (append-1 (mut (.rows1 input)) (N1Row :f0 xs))
wrapper (append-2 (mut (.rows2 input)) (N2Row :f0 group))
choice (append-6 (mut (.rows6 input)) (N6Row :f0 xs :f1 (N0Id :index 9999)))]
(push! (mut (.origins1 input)) origin) (push! (mut (.origins2 input)) origin) (push! (mut (.origins6 input)) origin)
(push! (mut parts) (.index xs)) (push! (mut parts) (.index xs))
(let [joined (match (sequence/join! (mut (.sequences0 input)) (mut parts)) (Ok [v] v) (_ (panic "join")))
(mut state) (transform-state-new a (mut input) (mut target))
before (next-node-id)]
(defer (transform-state-free! (mut state)))
(let [one (match (transform-0-3 (mut state) name) (Ok [v] v) (_ (panic "first")))
two (match (transform-0-3 (mut state) name) (Ok [v] v) (_ (panic "second")))]
(unless (and (!= (.index one) (.index two)) (!= (.f0 (get (.rows3 target) (.index one))) (.f0 (get (.rows3 target) (.index two))))) (panic "memoized lexical identity")))
(match (transform-1-4 (mut state) group) (Ok [_]) (_ (panic "sequence map")))
(match (transform-2-5 (mut state) wrapper) (Ok [_]) (_ (panic "parent map")))
(set! (.sharing? state) true)
(match (transform-1-4 (mut state) group) (Ok [_]) (_ (panic "repeat sequence")))
(match (transform-many-1-3 (mut state) group)
(Ok [xs] (unless (= (match (sequence-size-3 (mut target) xs) (Some [n] n) (_ 0)) 4) (panic "spread cardinality"))) (_ (panic "spread")))
(match (transform-6-3 (mut state) choice) (Ok [_]) (_ (panic "lazy choice")))
(unless (= (next-node-id) (+ before 14)) (panic "incorrect occurrence count"))
(let [one (match (transform-0-7 (mut state) name) (Ok [v] v) (_ (panic "pure first")))
two (match (transform-0-7 (mut state) name) (Ok [v] v) (_ (panic "pure second")))]
(unless (= (.index one) (.index two)) (panic "pure sharing disabled")))
; Cycles remain errors even though successful occurrence results are never cached.
(set! (.f0 (elem (mut (.rows1 input)) (.index group))) (N0Seq :index joined))
(let [edge (.start (get (.segments (.sequences0 input)) joined))
previous (get (.edges (.sequences0 input)) edge)]
(set! (mut (.edges (.sequences0 input))) edge joined)
(match (transform-1-4 (mut state) group)
(Err [e] (match e (TransformSequence [e] (match e (sequence/SequenceCycle [_]) (_ (panic "cycle kind")))) (_ (panic "cycle wrapper")))) (_ (panic "cycle accepted")))
(set! (mut (.edges (.sequences0 input))) edge previous))
(match (transform-1-4 (mut state) group) (Ok [_]) (_ (panic "retry")))))))
(defn main [] (-> i64)
(let [debug (DebugAllocator::new (malloc-allocator))]
(check (DebugAllocator::view debug))
(unless (= (DebugAllocator::deinit! debug) 0) (panic "occurrence leak"))) 0)
'''
with tempfile.TemporaryDirectory(prefix='rewrite-occurrences-') as directory:
    work=Path(directory);(work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for n in ['types','scope','resolution','source','sequence','lexical']:shutil.copyfile(ROOT/f'seed/{n}.coil',work/f'{n}.coil')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')],input=schema))
    (work/'main.coil').write_text(driver)
    for flags in [[],['--debug-checks'],['--release']]:subprocess.run(['coil','run','main.coil',*flags],cwd=work,check=True)
for invalid in [
    schema.replace(b'transform Name Out :occurrences',b'transform Name Out'),
    schema.replace(b'transform Group OutGroup :occurrences',b'transform Group OutGroup'),
    schema.replace(b'transform Wrapper OutWrapper :occurrences',b'transform Wrapper OutWrapper'),
    schema.replace(b'transform Choice Out :occurrences',b'transform Choice Out'),
    schema.replace(b'transform Group (many Out) :occurrences',b'transform Group (many Out)'),
    schema.replace(b':occurrences',b':memoize',1),
    schema.replace(b'(lexical name scope module)',b'(lexical name module scope)'),
    schema.replace(b'(lexical name scope module)',b'(lexical name scope)'),
]:
    r=subprocess.run([str(ROOT/'build/schema-seed')],input=invalid,capture_output=True)
    assert r.returncode!=0 and not r.stdout,(invalid,r)
print('Occurrence maps: fresh node/sequence/spread/selection identities, transitive effect checks, pure sharing, cycles and retry passed')
