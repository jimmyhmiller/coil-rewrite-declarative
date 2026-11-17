#!/usr/bin/env python3
"""Check generated traversal policy using heads unrelated to Coil declarations."""
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
compiler = ROOT/'build/schema-seed'
base = '(node Atom (value Int)) '
policy = '(walk probe (opaque-list "data") (prefix "function" 2 (keyword 1 "mode" 3)))'
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
    0))
''')
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
for policy, message in [
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
print('Walk policies: independent heads, keyword pairs, list opacity, vector prefixes and invalid declarations passed')
