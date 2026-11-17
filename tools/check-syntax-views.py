#!/usr/bin/env python3
"""Check borrowed syntax captures independently of the stage declaration schema."""
from pathlib import Path
import subprocess
import tempfile
import shutil
ROOT = Path(__file__).resolve().parents[1]
schema = b'''(node Pair (left Int) (right Int))
(syntax Pair (Pair (list "pair" (int right) (int left))))
(node Nest (inner Pair)) (syntax Nest (Nest (list "nest" (ref inner))))
(node Many (items (many Pair))) (syntax Many (Many (list "pairs" (rest items))))
(sum Choice (A (value Int)) (B (value Text)))
(syntax Choice (A (list "a" (int value))) (B (list "b" (text value))))'''
with tempfile.TemporaryDirectory(prefix='rewrite-view-') as directory:
    work = Path(directory)
    for name in ['types', 'scope', 'resolution', 'source', 'sequence']:
        shutil.copyfile(ROOT/f'seed/{name}.coil', work/f'{name}.coil')
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=schema))
    (work/'main.coil').write_text('''(module fixture.main)
(import "rewrite.generated" :use *)
(import "coil.reader" :use *)
(import "coil.scratch" :use [ScratchArena])
(import "coil.alloc" :use *)
(import "coil.arraylist" :use *)
(import "coil.result" :use *)
(defn main [] (-> i64)
  (let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) (malloc-allocator))
        a (allocator (mut scratch)) (mut store) (store-new a)
        input (match (read-all a "(pair 10 20) (other) (pair 10) (pair 10 bad) (nest bad) (pairs) (b \\"text\\")" 1)
                (Ok [input] input) (Err [_] (panic "source")))]
    (defer (close! (mut scratch)))
    (let [view (match (view-0 a (elem input 0)) (Ok [v] (match v (Some [v] v) (None [] (panic "match")))) (Err [_] (panic "view")))
          left (get (.captures view) 0) right (get (.captures view) 1)
          row (match (surface-0 (mut store) (elem input 0)) (Ok [id] (get (.rows0 store) (.index id))) (Err [_] (panic "parse")))]
      (unless (and (= (.variant view) 0) (= (sexp-int (.source left)) 20) (= (sexp-int (.source right)) 10)
                   (= (.f0 row) 20) (= (.f1 row) 10) (not (.rest? left))) (panic "field order")))
    (match (view-0 a (elem input 1)) (Ok [v] (match v (None []) (_ (panic "unexpected match")))) (_ (panic "no-match became error")))
    (for [i 2 4] (match (view-0 a (elem input i)) (Err [_]) (_ (panic "committed malformed view"))))
    (match (view-1 a (elem input 4)) (Ok [v] (match v (Some [_]) (_ (panic "shallow ref")))) (_ (panic "shallow inspection")))
    (match (surface-1 (mut store) (elem input 4)) (Err [_]) (_ (panic "recursive parse accepted invalid child")))
    (let [view (match (view-2 a (elem input 5)) (Ok [v] (match v (Some [v] v) (_ (panic "rest")))) (_ (panic "rest view")))
          capture (get (.captures view) 0)]
      (unless (and (.rest? capture) (= (.start capture) 1) (= (sexp-count (.source capture)) 1)) (panic "empty tail")))
    (let [view (match (view-3 a (elem input 6)) (Ok [v] (match v (Some [v] v) (_ (panic "sum")))) (_ (panic "sum view")))]
      (unless (= (.variant view) 1) (panic "sum variant")))
    0))
''')
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
print('Syntax views: field order, variants, shallow references, empty tails and committed diagnostics passed')
