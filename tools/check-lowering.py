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
    shutil.copyfile(ROOT/'seed/scope.coil', work/'scope.coil')
    shutil.copyfile(ROOT/'runtime/native.coil', work/'native.coil')
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
    (work/'main.coil').write_text((ROOT/'tests/calls.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
    program_schema = (ROOT/'tests/schemas/lowering.schema').read_bytes() + b'\n(node Function (name Text :key) (parameter Text) (body Expr))\n(program Expr Function name parameter body Int Int)\n'
    program_schema += (ROOT/'tests/schemas/surface.syntax').read_bytes()
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=program_schema))
    client = (ROOT/'tests/program.coil.in').read_text().replace('(defn main []', '(defn hand-tests []')
    surface_program = (ROOT/'tests/surface-program.coil.in').read_text()
    invalid_function_value = (ROOT/'tests/surface-function-value-invalid.coil.in').read_text()
    (work/'reference-invalid.coil').write_text('(module fixture.referenceinvalid)\n' + invalid_function_value)
    rejected = subprocess.run(['coil', 'check', 'reference-invalid.coil'], cwd=work, capture_output=True)
    assert rejected.returncode != 0 and b'is a function, not a value' in rejected.stdout + rejected.stderr, rejected
    (work/'reference.coil').write_text('(module fixture.reference)\n(import \"coil.primitive\" :use [fnptr-of])\n' + surface_program + '\n(defn main [] (-> i64) (if (= (entry 41) 42) 0 1))\n')
    # The first function calls the last declaration, across unused global names.
    many = '(Function "main" "x" (Call (Variable "f127") (Variable "x"))) '
    many += ' '.join(f'(Function "f{i}" "x" (Add (Variable "x") (Integer 1)))' for i in range(128))
    client += '\n(defn main [] (-> i64) (if (and (= (hand-tests) 0) (check ' + json.dumps(many) + ' 42) (check-with ' + json.dumps(surface_program) + ' 42 true) (check-with ' + json.dumps(invalid_function_value) + ' 4 true)) 0 1))\n'
    (work/'main.coil').write_text(client)
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
        subprocess.run(['coil', 'run', 'reference.coil', *flags], cwd=work, check=True)
    transform_schema = (ROOT/'tests/schemas/lowering.schema').read_bytes() + b'\n(node Function (name Text :key) (parameter Text) (body Expr))\n(program Expr Function name parameter body Int Int)\n' + (ROOT/'tests/schemas/transform.schema').read_bytes()
    (work/'generated.coil').write_bytes(subprocess.check_output([str(ROOT/'build/schema-seed')], input=transform_schema))
    (work/'main.coil').write_text((ROOT/'tests/transform.coil.in').read_text())
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
    invalid_client = (ROOT/'tests/transform.coil.in').read_text().replace(
        '(compile-program a (mut store) (mut target-ids))',
        '(compile-program a (mut store) (mut source-ids))')
    (work/'main.coil').write_text(invalid_client)
    rejected = subprocess.run(['coil', 'check', 'main.coil'], cwd=work, capture_output=True)
    assert rejected.returncode != 0 and all(name in rejected.stdout + rejected.stderr for name in [b'N1Id', b'N3Id']), rejected
print('Source -> generated checking/lowering -> CIR -> native execution passed')
print('Function designators rejected as values; explicit function pointers agree with installed Coil')

source = (ROOT/'tests/schemas/lowering.schema').read_bytes()
for invalid in [source + b'(lower Expr)', source.replace(b'(const value)', b'(const missing)'), source.replace(b'(add left right)', b'(unknown left right)'), source.replace(b'(Boolean (bool value))', b'')]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout, result
print('Invalid lowering definitions rejected before output')

program = b'(program Expr Function name parameter body Int Int)'
record = b'\n(node Function (name Text :key) (parameter Text) (body Expr))\n'
valid_program = source + record + program
for invalid, message in [
    (valid_program.replace(b'name Text :key', b'name Text'), b'program name field requires :key'),
    (valid_program + program, b'duplicate program declaration'),
    (source + record + program.replace(b'program Expr', b'program Missing'), b'program requires'),
    (valid_program.replace(b'(program Expr Function name parameter body Int Int)', b'(program Expr Function name name body Int Int)'), b'invalid program fields'),
    (valid_program.replace(b'body Int Int)', b'body Bool Int)'), b'unary Int -> Int'),
    (source.split(b'(lower Expr')[0] + record + program, b'program requires'),
    (source.split(b'(judgment Expr')[0] + b'(lower Expr' + source.split(b'(lower Expr')[1] + record + program, b'program requires'),
]:
    result = subprocess.run([str(ROOT/'build/schema-seed')], input=invalid, capture_output=True)
    assert result.returncode != 0 and not result.stdout, result
    assert message in result.stderr, result
print('Invalid program declarations rejected before output')
