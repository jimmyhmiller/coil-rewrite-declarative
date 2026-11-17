#!/usr/bin/env python3
"""Compile schema-driven source to CIR and execute the retained native backend's code."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import json
import random
ROOT = Path(__file__).resolve().parents[1]
(ROOT / 'build').mkdir(exist_ok=True)
subprocess.run(['coil', 'build', 'seed/main.coil', '-o', 'build/schema-seed'], cwd=ROOT, check=True)
with tempfile.TemporaryDirectory(prefix='rewrite-lowering-') as directory:
    work = Path(directory)
    roots = ['.', *[str(ROOT / 'vendor/coil' / p) for p in ['src/compiler/declarative', 'src/compiler/native', 'src/declarative/tests']]]
    (work/'Coil.toml').write_text('[package]\nname = "fixture"\nentry = "main.coil"\nsource-roots = '+json.dumps(roots)+'\n')
    shutil.copyfile(ROOT/'seed/types.coil', work/'types.coil')
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=(ROOT/'tests/schemas/lowering.schema').read_bytes()))
    rng = random.Random(90210)
    def expression(depth, env):
        choice = rng.randrange(5) if depth else 0
        if choice == 0:
            if env and rng.randrange(2):
                name = rng.choice(list(env))
                return '(Variable ' + json.dumps(name) + ')', env[name]
            value = rng.randrange(43)
            return f'(Integer {value})', value
        if choice == 1:
            left, a = expression(depth - 1, env)
            right, b = expression(depth - 1, env)
            return f'(Add {left} {right})', a + b
        if choice == 2:
            condition = bool(rng.randrange(2))
            yes, a = expression(depth - 1, env)
            no, b = expression(depth - 1, env)
            return f'(Choose (Boolean {str(condition).lower()}) {yes} {no})', a if condition else b
        name = rng.choice(['x', 'y'])
        initializer, value = expression(depth - 1, env)
        body, result = expression(depth - 1, dict(env, **{name: value}))
        return f'(Let {json.dumps(name)} {initializer} {body})', result
    client = (ROOT/'tests/lowering.coil.in').read_text().replace('(defn main []', '(defn hand-tests []')
    client += '\n(defn main [] (-> i64) (let [(mut failures) (hand-tests)]\n'
    for index in range(40):
        source, expected = expression(4, {})
        client += f'(unless (check {json.dumps(source)} {expected}) (println "generated case {index} failed") (set! failures (+ failures 1)))\n'
    client += 'failures))\n'
    (work/'main.coil').write_text(client)
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
print('Source -> generated checking/lowering -> CIR -> native execution passed')

source = (ROOT/'tests/schemas/lowering.schema').read_bytes()
for invalid in [source + b'(lower Expr)', source.replace(b'(const value)', b'(const missing)'), source.replace(b'(add left right)', b'(unknown left right)'), source.replace(b'(Boolean (bool value))', b'')]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout, result
print('Invalid lowering definitions rejected before output')
