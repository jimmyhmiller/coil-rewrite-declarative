#!/usr/bin/env python3
"""Exercise typed classifier elimination and explicit transform context independently."""
from pathlib import Path
import shutil, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[1]
schema = b'''(node Input (name Text) (scope Int) (module Text))
(sum Tag (Number (value Int)) (Other))
(node Record (label Text) (flag Bool))
(node Output (text Text) (number Int) (flag Bool))
(text-classifier tag Tag (decimal "n" 1 9 (Number $number)) (default (Other)))
(text-classifier record Record (default (Record $input true)))
(transform-context (bits Int) (suffix Text) (enabled Bool))
(transform Input Output :occurrences
 (Input (classify tag name (context bits)
   (Number [value] (Output (concat name (context suffix)) value (context enabled)))
   (Other [] (classify record name 0
     (Record [label flag] (Output (lexical label scope module) (context bits) flag)))))))
(transform Input (many Output) :occurrences
 (Input (classify tag name 0
   (Number [value] (items (Output name value true) (Output name value false)))
   (Other [] (items)))))'''
driver = '''(module fixture.main)
(import "rewrite.generated" :use *)
(import "coil.alloc" :use *) (import "coil.arraylist" :use *)
(import "coil.reader" :use *) (import "coil.result" :use *) (import "coil.str" :use [StrBuf])
(import "coil.scratch" :use [ScratchArena]) (import "coil.debug-allocator" :use [DebugAllocator])
(defn check [(a (dyn Allocator))] (-> void)
(let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) a) sa (allocator (mut scratch))
(mut input) (store-new a) (mut target) (store-new a) (mut suffix) (StrBuf::new a)
text "(Input \\"n2\\" -1 \\"def\\") (Input \\"unknown\\" -1 \\"def\\")"
roots (match (read-all sa text 1) (Ok [v] v) (_ (panic "reader")))
one (match (parse-0 (mut input) (elem roots 0)) (Ok [v] v) (_ (panic "first input")))
two (match (parse-0 (mut input) (elem roots 1)) (Ok [v] v) (_ (panic "second input")))]
(defer (close! (mut scratch))) (defer (store-free! (mut input))) (defer (store-free! (mut target)))
(match (store-source! (mut input) 1 "input.coil" text) (Ok [_]) (_ (panic "source")))
(push-str! (mut suffix) "!")
(let [(mut state) (transform-state-new a (mut input) (mut target) 32 (str suffix) false)]
(defer (transform-state-free! (mut state)))
(free! (mut suffix))
(let [before (next-node-id)
first (match (transform-0-3 (mut state) one) (Ok [v] v) (_ (panic "numeric branch")))
second (match (transform-0-3 (mut state) two) (Ok [v] v) (_ (panic "record branch")))
x (get (.rows3 target) (.index first)) y (get (.rows3 target) (.index second))]
(unless (= (next-node-id) (+ before 2)) (panic "unselected lexical effect"))
(unless (and (= (.f0 x) "n2!") (= (.f1 x) 2) (not (.f2 x)) (= (.f1 y) 32) (.f2 y)) (panic "classified values")))
(match (transform-many-0-3 (mut state) one)
 (Ok [xs] (unless (= (match (sequence-size-3 (mut target) xs) (Some [n] n) (_ -1)) 2) (panic "many numeric"))) (_ (panic "many map")))
(match (transform-many-0-3 (mut state) two)
 (Ok [xs] (unless (= (match (sequence-size-3 (mut target) xs) (Some [n] n) (_ -1)) 0) (panic "many default"))) (_ (panic "many map"))))))
(defn main [] (-> i64)
(let [debug (DebugAllocator::new (malloc-allocator))]
(check (DebugAllocator::view debug)) (unless (= (DebugAllocator::deinit! debug) 0) (panic "map leak"))) 0)
'''
with tempfile.TemporaryDirectory(prefix='rewrite-classified-maps-') as directory:
    work = Path(directory)
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for name in ['types','scope','resolution','source','sequence','lexical','text_runtime']:
        shutil.copyfile(ROOT/f'seed/{name}.coil', work/f'{name}.coil')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=schema))
    (work/'main.coil').write_text(driver)
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
invalid = [
    (schema.replace(b'(context bits)', b'(context absent)'), 'unknown transform context'),
    (schema.replace(b'(context bits)', b'(context enabled)'), 'context type mismatch'),
    (schema.replace(b'(suffix Text)', b'(suffix Input)'), 'context requires'),
    (schema + b' (transform-context (another Int))', 'duplicate transform context'),
    (schema.replace(b'(suffix Text)', b'(bits Text)'), 'duplicate context field'),
    (schema.replace(b'classify tag name', b'classify missing name'), 'unknown classifier'),
    (schema.replace(b'(Number [value]', b'(Absent [value]', 1), 'unknown classifier constructor'),
    (schema.replace(b'(Number [value]', b'(Number []', 1), 'classifier binding arity'),
    (schema.replace(b'(Number [value]', b'(Number [name]', 1), 'shadows existing field'),
    (schema.replace(b'(Other [] (items))', b'(Number [extra] (items))'), 'duplicate classifier arm'),
    (schema.replace(b'(Other [] (items))', b''), 'classifier arms must be exhaustive'),
    (schema.replace(b'(concat name (context suffix))', b'(concat name 7)'), 'transform scalar'),
    (schema.replace(b'(Output name value true)', b'(Output name (concat name) true)'), 'concat requires'),
    (schema.replace(b'transform Input Output :occurrences', b'transform Input Output'), 'lexical requires'),
]
for source, message in invalid:
    r = subprocess.run([str(ROOT/'build/schema-seed')], input=source, capture_output=True)
    assert r.returncode != 0 and not r.stdout and message.encode() in r.stderr, (message, r.stdout, r.stderr)
print('Classified maps: exhaustive sum/record elimination, nested/many results, typed context, owned text, lazy effects and declaration diagnostics passed')
