#!/usr/bin/env python3
"""Capture exact export traversal helpers with explicit fixture table adapters."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
definition = runpy.run_path(str(ROOT/'tools/capture-refer-reference.py'))['definition']
def q(value):
    return json.dumps(value, ensure_ascii=False)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def edge(target, all=True, selected=(), excluded=(), renames=()):
    return dict(target=target, all=all, selected=list(selected), excluded=list(excluded), renames=list(renames))


def module(name, exports=None, edges=()):
    return dict(name=name, exports=exports, edges=list(edges))


def cases():
    modules = [
        module('base', ['a', 'b', 'own']),
        module('other'),
        module('facade', ['a', 'local', 'own', 'alias', 'chain'], [edge('base', False, renames=[('b', 'local')]), edge('base'), edge('other')]),
        module('hidden', [], [edge('base')]),
        module('variants', edges=[edge('base', False, renames=[('ghost', 'x')]), edge('base', False, renames=[('a', 'x')])]),
        module('cycle', edges=[edge('cycle'), edge('base')]),
        module('dead', edges=[edge('dead')]),
        module('excluded', edges=[edge('base', excluded=['a']), edge('other')]),
        module('selected', edges=[edge('base', False, selected=['b'])]),
    ]
    first = dict(declarations=['base.a', 'base.b', 'base.own', 'other.a', 'facade.own', 'facade.alias', 'hidden.a', 'unrecorded.x'],
                 aliases=[['facade.alias', 'base.a'], ['facade.chain', 'facade.alias']], modules=modules)
    first['queries'] = [[owner, name, depth] for owner in ['facade', 'hidden', 'variants', 'cycle', 'dead', 'excluded', 'selected', 'unrecorded', 'base']
                        for name in ['a', 'b', 'local', 'own', 'alias', 'chain', 'x', 'missing'] for depth in [0, 62, 63, 64]]
    result = [first]
    # Acyclic generated graphs bound the un-memoized reference's path count.
    # The targeted graph above separately exercises cycles and exact depth.
    rng = random.Random(197243)
    names = ['a', 'b', 'c', 'λ']
    for _ in range(24):
        owners = [f'm{i}' for i in range(5)]
        declarations = [f'{owner}.{name}' for owner in owners for name in names if rng.randrange(3) == 0]
        graph = []
        for i, owner in enumerate(owners):
            edges = [edge(target, bool(rng.randrange(2)), rng.sample(names, rng.randrange(5)),
                          rng.sample(names, rng.randrange(3)),
                          [(rng.choice(names), rng.choice(names)) for _ in range(rng.randrange(3))])
                     for target in owners[i+1:] if rng.randrange(2)]
            graph.append(module(owner, None if rng.randrange(2) else rng.sample(names, rng.randrange(5)), edges))
        aliases = [[f'{owner}.{name}', f'{rng.choice(owners)}.{rng.choice(names)}']
                   for owner in owners for name in names if rng.randrange(5) == 0]
        result.append(dict(declarations=declarations, aliases=aliases, modules=graph,
                           queries=[[owner, name, depth] for owner in owners for name in names + ['missing'] for depth in [0, 62, 63, 64]]))
    return result


HEADER = '''(module reference.main)
(import "coil.alloc" :use *)
(import "coil.arraylist" :use *)
(import "coil.avec" :use *)
(import "coil.reader" :use [Sexp])
(import "coil.result" :use *)
(import "coil.scratch" :use [ScratchArena])
(import "coil.text" :use [sconcat3])
(import "coil.primitive" :as primitive)
; Fixture adapters expose only the table capabilities used by space-exported.
(defstruct ModImports [(reexports (ArrayList Use))])
(defstruct NameSpace [(names (ptr (ArrayList (slice u8))))])
(defn space-has? [(space (ptr NameSpace)) (name (slice u8))] (-> bool)
  (set-contains (.names space) name))
(defn decl-alias-list [] (-> (ptr (ArrayList DeclAliasEntry)))
  (primitive/alloc-static (ArrayList DeclAliasEntry)))
(defn boxed [T] [(a (dyn Allocator)) (value T)] (-> (ptr T))
  (match (create [T] a) (Some [p] (store! p value) p) (None [] (panic "allocation"))))
(defn answer [(value (Option (slice u8)))] (-> (slice u8))
  (match value (Some [text] text) (None [] "-")))
'''


def fixture(graphs, helpers, *, header=HEADER, after_graph=None, import_value="(ModImports :reexports edges)"):
    body = [header, '\n'.join(helpers.values()), '(defn main [] (-> i64)']
    for graph in graphs:
        body.append('''(let [(mut arena) (zeroed ScratchArena) initialized (init (mut arena) (malloc-allocator))
            a (allocator (mut arena)) (mut imports) (avec-new [ImpEntry] a) (mut exports) (avec-new [ExpEntry] a)
            names (boxed a (ArrayList::new [(slice u8)] a)) (mut space) (NameSpace :names names)]
            (defer (close! (mut arena)))
            (store! (decl-alias-list) (ArrayList::new [DeclAliasEntry] a))''')
        for name in graph['declarations']:
            body.append(f'(push! names {q(name)})')
        for name, target in graph['aliases']:
            body.append(f'(push! (decl-alias-list) (DeclAliasEntry :name {q(name)} :target {q(target)}))')
        for mod in graph['modules']:
            body.append('(let [(mut edges) (ArrayList::new [Use] a)]')
            for e in mod['edges']:
                body.append('''(let [selected (boxed a (ArrayList::new [(slice u8)] a))
                   excluded (boxed a (ArrayList::new [(slice u8)] a)) renamed (boxed a (ArrayList::new [Rename] a))]''')
                for name in e['selected']:
                    body.append(f'(push! selected {q(name)})')
                for name in e['excluded']:
                    body.append(f'(push! excluded {q(name)})')
                for old, new in e['renames']:
                    body.append(f'(push! renamed (Rename :from {q(old)} :to {q(new)}))')
                body.append(f'(push! (mut edges) (Use :target {q(e["target"])} :spec {"(UAll)" if e["all"] else "(UNames selected)"} :exclude excluded :renames renamed)))')
            body.append(f'(push! (mut imports) (ImpEntry :name {q(mod["name"])} :imp {import_value} :edit 0)))')
            if mod['exports'] is not None:
                body.append('(let [(mut public) (ArrayList::new [(slice u8)] a)]')
                for name in mod['exports']:
                    body.append(f'(push! (mut public) {q(name)})')
                body.append(f'(push! (mut exports) (ExpEntry :name {q(mod["name"])} :names public :forms (ArrayList::new [Sexp] a) :edit 0)))')
        for owner, name, depth in graph['queries']:
            body.append(f'(println "{{}}" (answer (space-exported (mut imports) (mut space) (mut exports) {q(owner)} {q(name)} a {depth})))')
        if after_graph is not None:
            body.extend(after_graph(graph))
        body.append(')')
    body.append('0)')
    return '\n'.join(body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--compiler', default='coil')
    args = parser.parse_args()
    compiler = Path(shutil.which(args.compiler) or args.compiler).resolve(strict=True)
    version = subprocess.check_output([str(compiler), '--version'], text=True).strip()
    revision = re.search(r'commit ([0-9a-f]+)', version).group(1)
    revision = subprocess.check_output(['git', 'rev-parse', revision], cwd=args.reference, text=True).strip()
    sources = {name: subprocess.check_output(['git', 'show', f'{revision}:src/compiler/frontend/{name}.coil'], cwd=args.reference).decode()
               for name in ['loader', 'resolve', 'expander', 'ast']}
    helpers = {name: definition(sources[source], name) for source, names in [
        ('loader', ['UseSpec', 'Rename', 'Use', 'ImpEntry', 'ExpEntry', 'use-refers']),
        ('resolve', ['set-contains', 'imports-find', 'exports-check']),
        ('ast', ['DeclAliasEntry', 'decl-alias-target']), ('expander', ['space-exported'])] for name in names}
    graphs = cases()
    driver = fixture(graphs, helpers)
    work = ROOT/'build/export-reference'
    work.mkdir(parents=True, exist_ok=True)
    (work/'Coil.toml').write_text('[package]\nname="reference"\nentry="main.coil"\nsource-roots=["."]\n')
    (work/'main.coil').write_text(driver)
    outputs = []
    for flags in [[], ['--debug-checks'], ['--release']]:
        result = subprocess.run([str(compiler), 'run', 'main.coil', *flags], cwd=work, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        outputs.append(result.stdout)
    assert len(set(outputs)) == 1, 'reference configurations disagree'
    answers = outputs[0].splitlines()
    assert len(answers) == sum(len(g['queries']) for g in graphs)
    cursor = 0
    for graph in graphs:
        graph['answers'] = [None if value == '-' else value for value in answers[cursor:cursor+len(graph['queries'])]]
        cursor += len(graph['queries'])
    evidence = dict(scope='Exact export traversal, import referring, export visibility and one-hop alias helpers. Fixture namespace membership and table storage; not source parsing or complete resolver parity.',
                    adapters=['NameSpace/space-has? exposes fixture declaration membership', 'ModImports retains only reexports', 'decl-alias-list exposes a fixture-owned alias table'],
                    compiler_version=version, compiler_sha256=digest(compiler.read_bytes()), reference_revision=revision,
                    source_sha256={n: digest(s.encode()) for n, s in sources.items()}, helper_sha256={n: digest(s.encode()) for n, s in helpers.items()},
                    driver_sha256=digest(driver.encode()), capture_script_sha256=digest(Path(__file__).read_bytes()),
                    configurations=['default', 'debug-checks', 'release'], equal_across_configurations=True, cases=graphs)
    (ROOT/'evidence/export-reference.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False)+'\n')
    print(f'Reference export lookup: {len(graphs)} graphs, {len(answers)} queries, three matching configurations')


if __name__ == '__main__':
    main()
