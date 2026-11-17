#!/usr/bin/env python3
"""Generate context edits for an independent schema and reject malformed policies."""
from pathlib import Path
import subprocess
import shutil
import tempfile
ROOT = Path(__file__).resolve().parents[1]
compiler = ROOT/'build/schema-seed'
base = '(sum Value (Leaf (value Int)) (Branch (child Value))) (node Context (flag Bool) (name Text) (serial Int)) '
policy = '(context-policy demo Value Context (Leaf (flag true) (name "literal") (serial fresh)))'
with tempfile.TemporaryDirectory(prefix='rewrite-context-') as directory:
    work = Path(directory)
    for name in ['types', 'scope', 'resolution', 'source', 'sequence']:
        shutil.copyfile(ROOT/f'seed/{name}.coil', work/f'{name}.coil')
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(compiler)], input=(base+policy).encode()))
    (work/'main.coil').write_text('''(module fixture.main)
(import "rewrite.generated" :use *)
(defn main [] (-> i64)
  (let [input (N1Row :f0 false :f1 "original" :f2 7)
        leaf (N0V0 42) branch (N0V1 (N0Id :index 0))
        changed (context-demo leaf input 99) preserved (context-demo branch input 99)]
    (unless (and (.f0 changed) (= (.f1 changed) "literal") (= (.f2 changed) 99)
                 (not (.f0 preserved)) (= (.f1 preserved) "original") (= (.f2 preserved) 7)
                 (context-demo-fresh? leaf) (not (context-demo-fresh? branch)))
      (panic "context policy"))
    0))
''')
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
for policy, message in [
    ('(context-policy demo)', 'expected (context-policy'),
    ('(context-policy bad/name Value Context)', 'invalid context policy name'),
    ('(context-policy demo Missing Context)', 'unknown context policy schema'),
    ('(context-policy demo Context Value)', 'context policy needs a sum and a record'),
    ('(context-policy demo Value Context (Missing))', 'unknown context variant'),
    ('(context-policy demo Value Context (Leaf) (Leaf))', 'duplicate context variant'),
    ('(context-policy demo Value Context (Leaf (unknown 1)))', 'unknown context field'),
    ('(context-policy demo Value Context (Leaf (serial 1) (serial 2)))', 'duplicate context field'),
    ('(context-policy demo Value Context (Leaf (flag fresh)))', 'context value disagrees'),
    ('(context-policy demo Value Context (Leaf (serial "text")))', 'context value disagrees'),
    ('(context-policy demo Value Context) (context-policy demo Value Context)', 'duplicate context policy'),
]:
    result = subprocess.run([str(compiler)], input=(base+policy).encode(), capture_output=True)
    assert result.returncode != 0 and not result.stdout and message.encode() in result.stderr, result
print('Context policies: independent Bool/Text/Int edits, preservation, freshness and declaration diagnostics passed')
