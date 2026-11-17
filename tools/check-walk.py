#!/usr/bin/env python3
"""Check generated traversal policy using heads unrelated to Coil declarations."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
compiler = ROOT/'build/schema-seed'
base = '(node Atom (value Int)) '
policy = '(walk probe (default children) (opaque-list "data") (prefix "function" 2 (keyword 1 "mode" 3))) (walk bundles (prefix-list "bundle" 1) (default keep))'
with tempfile.TemporaryDirectory(prefix='rewrite-walk-') as directory:
    work = Path(directory)
    for runtime in ['types', 'scope', 'resolution', 'source', 'sequence']:
        shutil.copyfile(ROOT/f'seed/{runtime}.coil', work/f'{runtime}.coil')
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(compiler)], input=(base+policy).encode()))
    (work/'main.coil').write_text('''(module fixture.main)
(import "rewrite.generated" :use *)
(import "coil.alloc" :use *)
(import "coil.scratch" :use [ScratchArena])
(import "coil.reader" :use *)
(import "coil.arraylist" :use *)
(import "coil.result" :use *)
(defn main [] (-> i64)
  (let [(mut scratch) (zeroed ScratchArena) initialized (init (mut scratch) (malloc-allocator))
        a (allocator (mut scratch))
        input (match (read-all a "7 (data x) [data x] (function x y) (function :mode fast x) (function :mode) (other x)" 1)
                (Ok [input] input) (Err [_] (panic "source")))]
    (defer (close! (mut scratch)))
    (for [i 0 7]
      (match (walk-probe (elem input i))
        (KeepSyntax [] (unless (< i 2) (panic "opaque")))
        (VisitChildren [start]
          (unless (and (>= i 2) (= start (cond (= i 3) 2 (= i 4) 3 (= i 5) 2 :else 0))) (panic "prefix")))))
    (let [input (match (read-all a "(bundle 1 (bundle) (bundle 2 [bundle 3]) (keep (bundle 4)))" 2)
                  (Ok [forms] forms) (Err [_] (panic "bundles")))
          leaves (leaves-bundles a (elem input 0))]
      (unless (= (len leaves) 4) (panic "leaf count"))
      (unless (and (= (sexp-int (get leaves 0)) 1) (= (sexp-int (get leaves 1)) 2)
                   (sexp-vec? (get leaves 2)) (sexp-sym-is (sexp-nth (get leaves 3) 0) "keep"))
        (panic "leaf boundaries"))
      ; This scale check exercises the generated walk, not recursive owned projection.
      (let [(mut root) (get leaves 0)]
        (for [i 0 25000]
          (let [items (box! a (ArrayList Sexp) (ArrayList::new [Sexp] a))]
            (push! items (mk-sexp (KSym "bundle") 0 0))
            (push! items (load (load root)))
            (set! root (box! a Sexp (mk-sexp (KList items) 0 0)))))
        (let [deep (leaves-bundles a root)]
          (unless (and (= (len deep) 1) (= (sexp-int (get deep 0)) 1)) (panic "deep walk")))))
    0))
''')
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
for policy, message in [
    ('(walk probe (default other))', 'expected (default'),
    ('(walk probe (default keep extra))', 'expected (default'),
    ('(walk probe (default keep) (default children))', 'duplicate walk default'),
    ('(walk probe (prefix-list "x" -1))', 'invalid walk rule arity'),
    ('(walk probe (prefix-list "x" 1) (prefix "x" 2))', 'duplicate walk head'),
    ('(walk bad/name)', 'expected (walk'),
    ('(walk probe) (walk probe)', 'duplicate walk policy'),
    ('(walk probe (unknown "x"))', 'expected opaque-list or prefix'),
    ('(walk probe (opaque-list "x" 1))', 'invalid walk rule arity'),
    ('(walk probe (prefix "x" -1))', 'invalid walk rule arity'),
    ('(walk probe (prefix "x" 1) (opaque-list "x"))', 'duplicate walk head'),
    ('(walk probe (prefix "x" 1 (keyword 2 "cc" 2)))', 'expected (keyword'),
    ('(walk probe (prefix "x" 1 (keyword -1 "cc" 3)))', 'expected (keyword'),
    ('(walk probe (prefix "x" 1 (keyword 9223372036854775807 "cc" 3)))', 'expected (keyword'),
]:
    result = subprocess.run([str(compiler)], input=(base+policy).encode(), capture_output=True)
    assert result.returncode != 0 and not result.stdout and message.encode() in result.stderr, result
print('Walk policies: independent heads, keyword pairs, list opacity, vector prefixes, default policies, iterative leaves and invalid declarations passed')
