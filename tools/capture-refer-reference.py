#!/usr/bin/env python3
"""Execute exact reference refer helpers in isolation; not full import parsing."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def definition(source, name):
    match = re.search(r'^\(def(?:n|struct|sum) ' + re.escape(name) + r'(?=[\s\[])', source, re.M)
    if not match:
        raise ValueError(f'missing reference definition {name}')
    depth, quoted, escaped, comment = 0, False, False, False
    for i in range(match.start(), len(source)):
        char = source[i]
        if comment:
            comment = char != '\n'
        elif quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
        elif char == ';':
            comment = True
        elif char == '"':
            quoted = True
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return source[match.start():i+1]
    raise ValueError(f'unclosed reference definition {name}')


def quoted(text):
    return json.dumps(text, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--compiler', default='coil')
    args = parser.parse_args()
    compiler = Path(shutil.which(args.compiler) or args.compiler).resolve(strict=True)
    version = subprocess.check_output([str(compiler), '--version'], text=True).strip()
    revision = re.search(r'commit ([0-9a-f]+)', version).group(1)
    revision = subprocess.check_output(['git', 'rev-parse', revision], cwd=args.reference, text=True).strip()
    sources = {name: subprocess.check_output(['git', 'show', f'{revision}:src/compiler/frontend/{name}.coil'],
                                            cwd=args.reference).decode() for name in ['loader', 'resolve']}
    helpers = {name: definition(sources['loader'], name) for name in
               ['UseSpec', 'Rename', 'Use', 'use-refers', 'use-local-of', 'use-drops?']}
    helpers['set-contains'] = definition(sources['resolve'], 'set-contains')
    cases = [
        (True, [], [], []), (False, [], [], []), (False, ['a', 'c'], [], []),
        (True, [], ['a'], []), (False, [], ['a', 'b'], [('a', 'b')]),
        (True, [], ['a'], [('a', 'a')]), (True, [], [], [('a', 'b'), ('b', 'c')]),
        (True, [], [], [('a', 'c'), ('b', 'c')]), (True, [], [], [('a', 'b'), ('b', 'a')]),
        (False, ['a'], [], [('a', 'b'), ('a', 'c')]), (False, [], [], [('α', 'λ')]),
    ]
    rng = random.Random(84615)
    names = ['a', 'b', 'c', 'd', 'α', 'λ', 'p/q', 'm.x']
    for _ in range(32):
        cases.append((bool(rng.randrange(2)), rng.sample(names, rng.randrange(5)),
                      rng.sample(names, rng.randrange(5)),
                      [(rng.choice(names), rng.choice(names)) for _ in range(rng.randrange(6))]))
    queries = names + ['missing']
    header = '''(module reference.main)
(import "coil.alloc" :use *)
(import "coil.arraylist" :use *)
(import "coil.result" :use *)
(import "coil.primitive" :as primitive)
(defn answer [(value (Option (slice u8)))] (-> (slice u8))
  (match value (Some [text] text) (None [] "-")))
'''
    body = ['(defn main [] (-> i64) (let [a (malloc-allocator)]']
    for i, (all_names, selected, excluded, renames) in enumerate(cases):
        body.append('(let [(mut selected) (ArrayList::new [(slice u8)] a) (mut excluded) (ArrayList::new [(slice u8)] a) (mut renames) (ArrayList::new [Rename] a)]')
        body.append('(defer (free! (mut selected))) (defer (free! (mut excluded))) (defer (free! (mut renames)))')
        for name in selected:
            body.append(f'(push! (mut selected) {quoted(name)})')
        for name in excluded:
            body.append(f'(push! (mut excluded) {quoted(name)})')
        for exported, local in renames:
            body.append(f'(push! (mut renames) (Rename :from {quoted(exported)} :to {quoted(local)}))')
        body.append(f'(let [(mut u) (Use :target "target" :spec {"(UAll)" if all_names else "(UNames (primitive/cast (ptr (ArrayList (slice u8))) (mut selected)))"} :exclude (primitive/cast (ptr (ArrayList (slice u8))) (mut excluded)) :renames (primitive/cast (ptr (ArrayList Rename)) (mut renames)))]')
        for query in queries:
            q = quoted(query)
            body.append(f'(println "{i} {{}} {{}} {{}} {{}}" {q} (answer (use-refers (mut u) {q})) (answer (use-local-of (mut u) {q})) (use-drops? (mut u) {q}))')
        body.append('))')
    body.append('0))')
    driver = header + '\n'.join(helpers.values()) + '\n' + '\n'.join(body) + '\n'
    work = ROOT/'build/refer-reference'
    work.mkdir(parents=True, exist_ok=True)
    (work/'Coil.toml').write_text('[package]\nname="reference"\nentry="main.coil"\nsource-roots=["."]\n')
    (work/'main.coil').write_text(driver)
    outputs = []
    for flags in [[], ['--debug-checks'], ['--release']]:
        result = subprocess.run([str(compiler), 'run', 'main.coil', *flags], cwd=work, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        outputs.append(result.stdout)
    if len(set(outputs)) != 1:
        raise RuntimeError('reference helpers disagree across configurations')
    rows = [dict(all=all_names, selected=selected, excluded=excluded, renames=renames, answers=[])
            for all_names, selected, excluded, renames in cases]
    for line in outputs[0].splitlines():
        i, query, forward, reverse, drops = line.split()
        rows[int(i)]['answers'].append(dict(query=query, referred=None if forward == '-' else forward,
                                           local=None if reverse == '-' else reverse, drops=drops == 'true'))
    assert all([a['query'] for a in row['answers']] == queries for row in rows)
    evidence = dict(scope='Exact extracted reference refer helpers executed in isolation; not full source import or namespace resolution parity.',
                    compiler_version=version, compiler_sha256=digest(compiler.read_bytes()), reference_revision=revision,
                    source_sha256={name: digest(text.encode()) for name, text in sources.items()},
                    helper_sha256={name: digest(text.encode()) for name, text in helpers.items()},
                    driver_sha256=digest(driver.encode()), capture_script_sha256=digest(Path(__file__).read_bytes()),
                    configurations=['default', 'debug-checks', 'release'], equal_across_configurations=True, cases=rows)
    (work/'stdout.txt').write_text(outputs[0])
    (ROOT/'evidence/refer-reference.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False)+'\n')
    print(f'Reference refer helpers: {len(rows)} policies, {len(outputs[0].splitlines())} queries, three matching configurations')


if __name__ == '__main__':
    main()
