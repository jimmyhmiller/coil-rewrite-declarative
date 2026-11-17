#!/usr/bin/env python3
"""Compare classified type graphs with the captured real parser's AST fields."""
import ast, hashlib, json, re, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
reference = ROOT/'evidence/type-reference.json'
class Text(str): pass

def read(text):
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|[()\[\]]|[^\s()\[\]]+', text)
    position = 0
    def item():
        nonlocal position
        token = tokens[position]; position += 1
        if token in ('(', '['):
            end = ')' if token == '(' else ']'
            result = []
            while tokens[position] != end: result.append(item())
            position += 1
            return result
        if token.startswith('"'):
            # The dump writes non-ASCII UTF-8 bytes as \xNN escapes.
            return Text(ast.literal_eval(token).encode('latin1').decode('utf8'))
        if re.fullmatch(r'-?\d+', token): return int(token)
        assert token not in (')', ']'), token
        return token
    result = item()
    assert position == len(tokens), (position, tokens)
    return result

q = lambda x: json.dumps(x, ensure_ascii=False)
def ctor(name, *args): return '(' + ' '.join([name, *args]) + ')'
def lexical(name): return ctor('LexicalName', q(name))
def extent(value): return ctor('Fixed', str(value)) if isinstance(value, int) else ctor('Parameter', lexical(value))
def convert(value):
    if isinstance(value, str):
        return ctor({'bool':'Boolean','void':'Void','never':'Never','externref':'ExternRef','code':'Code','codebuilder':'CodeBuilder'}[value])
    tag, *args = value
    if tag == 'int': return ctor('Integer', str(args[0]), 'true' if args[1] else 'false')
    if tag == 'float': return ctor('Float', str(args[0]))
    if tag == 'primitive/struct?': return ctor('Nominal', q(args[0]))
    if tag == 'ptr': return ctor('Pointer', convert(args[0]))
    if tag == 'ref': return ctor('Reference', 'true' if args[0] else 'false', convert(args[1]))
    if tag == 'array': return ctor('Array', convert(args[0]), extent(args[1]))
    if tag == 'slice': return ctor('Slice', convert(args[0]))
    if tag == 'vec': return ctor('Vector', convert(args[0]), extent(args[1]))
    if tag == 'const':
        v = args[0]
        if isinstance(v, int): inner = ctor('Integer', str(v))
        elif v in ('true','false'): inner = ctor('Boolean', v)
        elif v.startswith(':'): inner = ctor('Keyword', q(v[1:]))
        else: inner = ctor('Reference', lexical(v))
        return ctor('Constant', inner)
    if tag == 'app':
        if args[0] == '$pack-var':
            assert len(args[1]) == 1 and args[1][0][0] == 'primitive/struct?'
            return ctor('Pack', q(args[1][0][1]))
        return ctor('Application', lexical(args[0]), '['+' '.join(map(convert, args[1]))+']')
    if tag == 'fn':
        cc = args[0]
        convention = ctor('Value', lexical(cc[1:-1])) if cc.startswith('(') and cc.endswith(')') else ctor('Named', lexical(cc))
        return ctor('Function', convention, '['+' '.join(map(convert, args[1]))+']', convert(args[2]))
    raise AssertionError(value)

cases = []
for case in json.loads(reference.read_text())['cases']:
    if case['exit_code'] != 0: continue
    structs = read(next(line for line in case['output'].splitlines() if line.startswith('(structs ')))
    assert structs[0] == 'structs' and structs[1][1] == 'TypeProbe'
    field = structs[1][4][0]
    assert field[0] == 'fld' and field[1] == 'value'
    cases.append((case['type'], convert(field[2])))
helper = ROOT/'tests/type-classified.coil'
driver = helper.read_text().split('(defn main', 1)[0].replace('rewrite.testtypeclassified', 'rewrite.typereplay')
driver += '(defn main [] (-> i64) (let [debug (DebugAllocator::new (malloc-allocator)) a (DebugAllocator::view debug)]\n'
driver += ''.join(f'(expect a {q(source)} {q(expected)} 0 64)\n' for source, expected in cases)
driver += '(unless (= (DebugAllocator::deinit! debug) 0) (panic "type replay leak"))) 0)\n'
path = ROOT/'build/type-elaboration-replay.coil'; path.write_text(driver)
for flags in [[], ['--debug-checks'], ['--release']]:
    subprocess.run(['coil','run',str(path),*flags],cwd=ROOT,check=True)
digest = lambda data: hashlib.sha256(data).hexdigest()
inputs = [helper, Path(__file__), ROOT/'languages/type_syntax.schema', ROOT/'seed/generated/type_syntax.coil', ROOT/'seed/transform.coil', ROOT/'seed/lexical.coil', ROOT/'seed/text_runtime.coil']
evidence = dict(scope='Classified type graph equality for accepted captured struct-field types, scope zero and reference 64-bit target. Pack application encoding is normalized to Pack, and convention dump spelling to Named/Value. Excludes source-site effects, exact errors, canonical interning, nonzero-scope reference parity and full declaration admission.',cases=len(cases),configurations=['default','debug-checks','release'],reference_sha256=digest(reference.read_bytes()),driver_sha256=digest(driver.encode()),inputs={str(p.relative_to(ROOT)):digest(p.read_bytes()) for p in inputs})
(ROOT/'evidence/type-elaboration-replay.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(f'Classified type graphs: {len(cases)} accepted real-parser ASTs match in three configurations with independent ownership')
