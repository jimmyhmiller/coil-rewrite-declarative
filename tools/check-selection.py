#!/usr/bin/env python3
"""Exercise schema-directed candidate selection independently of namespace names."""
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT/'build/schema-seed'
schema = b'''(module fixture.generated)
(node Candidate (text Text) (number Int) (flag Bool))
(selection first-hit Candidate first)
(selection agreeing Candidate (agree-any number flag))
'''
client = '''(module fixture.main)
(import "fixture.generated" :use *)
(import "rewrite.selection" :as selection)
(import "coil.result" :use *)
(defn main [] (-> i64)
  (let [first (N0Row :f0 "first" :f1 11 :f2 true)
        same-number (N0Row :f0 "next" :f1 11 :f2 false)
        same-flag (N0Row :f0 "later" :f1 22 :f2 true)
        conflict (N0Row :f0 "last" :f1 22 :f2 false)]
    (match (select-first-hit (None) first) (selection/Stop [x] (unless (= (.f0 x) "first") (panic "first"))) (_ (panic "stop")))
    (match (select-first-hit (Some first) conflict) (selection/Stop [x] (unless (= (.f0 x) "first") (panic "preserve first"))) (_ (panic "stop prior")))
    (match (select-agreeing (None) first) (selection/Continue [x] (unless (= (.f0 x) "first") (panic "initial"))) (_ (panic "continue initial")))
    (match (select-agreeing (Some first) same-number) (selection/Continue [x] (unless (= (.f0 x) "first") (panic "number"))) (_ (panic "number agreement")))
    (match (select-agreeing (Some first) same-flag) (selection/Continue [x] (unless (= (.f0 x) "first") (panic "flag"))) (_ (panic "flag agreement")))
    (match (select-agreeing (Some first) conflict)
      (selection/Conflict [a b] (unless (and (= (.f0 a) "first") (= (.f0 b) "last")) (panic "witnesses")))
      (_ (panic "conflict lost"))))
  (println "selection: independent Int/Bool projections, early stop and retained witnesses passed") 0)
'''
with tempfile.TemporaryDirectory(prefix='rewrite-selection-') as directory:
    work = Path(directory)
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for name in ['types', 'scope', 'resolution', 'source', 'sequence', 'selection_runtime']:
        shutil.copyfile(ROOT/f'seed/{name}.coil', work/f'{name}.coil')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(SEED)], input=schema))
    (work/'main.coil').write_text(client)
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
for declaration, diagnostic in [
    ('(selection x Candidate)', 'expected (selection'),
    ('(selection x Missing first)', 'unknown selection record'),
    ('(selection x Choice first)', 'selection needs a record'),
    ('(selection x Candidate unknown)', 'selection needs first or nonempty agree-any'),
    ('(selection x Candidate (agree-any))', 'selection needs first or nonempty agree-any'),
    ('(selection x Candidate (agree-any absent))', 'unknown selection field'),
    ('(selection x Candidate (agree-any number number))', 'duplicate selection field'),
    ('(selection x Candidate (agree-any 12))', 'expected selection field name'),
    ('(selection x Candidate (agree-any child))', 'selection fields must be scalar'),
    ('(selection x Candidate first) (selection x Candidate first)', 'duplicate selection policy'),
]:
    source = '(node Child) (sum Choice (One)) (node Candidate (number Int) (child Child)) ' + declaration
    result = subprocess.run([str(SEED)], input=source.encode(), capture_output=True)
    assert result.returncode != 0 and not result.stdout and diagnostic.encode() in result.stderr, result
print('Independent selection generation and invalid declarations passed')
