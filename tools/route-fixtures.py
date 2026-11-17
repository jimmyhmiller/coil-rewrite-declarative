"""Deterministic resolver inputs; shared capture/replay data, no result model."""
from pathlib import Path
import copy
import random
import runpy

ROOT = Path(__file__).resolve().parents[1]
E = runpy.run_path(str(ROOT/'tools/capture-export-reference.py'))
edge, module = E['edge'], E['module']


def imports(name, aliases=(), uses=(), core=None):
    return dict(name=name, aliases=list(aliases), uses=list(uses), core=core or edge('core'))


def cases():
    base = dict(declarations=['app.own','app.private','app.part.name','part.name','app..field','raw',
               'libs.foo','libs.private','other.foo','core.cond','core.hidden','core.missing','project.cond',
               'library.cond','project.only','caller.m','def.m','m','def.$scope7@def$m','lib.$scope9@def$m',
               'name.space.$scope7@name.space$m'],
               aliases=[['app.alias','libs.foo'],['app.chain','app.alias']],
               modules=[module('app', []),module('libs',['foo'])], queries=[],
               imports=[imports('app',[['l','libs'],['dup','libs'],['dup','other']], [edge('libs')],
                                edge('core', excluded=['hidden'], renames=[['cond','choose']])),
                        imports('amb',uses=[edge('libs'),edge('other')]), imports('core'),
                        imports('def',uses=[edge('lib')])],
               providers=[['cond','library',False],['cond','project',True],['missing','project',True],['only','project',True]],
               declared=['app.foo','app.own'], toolchain=['stdlib.user'], prelude='core')
    heads=['own','foo','alias','chain','part.name','.field','libs.private','l/private','l/foo','dup/foo',
           'libs/foo','other/foo','app/private','choose','cond','hidden','missing','only','raw','m','']
    base['route_queries']=[[h,m,b] for m in [None,'','app','amb','core','stdlib.user','caller','def'] for h in heads for b in [False,True]]
    base['head_queries']=[['m',scope,definition,fallback] for scope in [0,7,8,9,-1]
                          for definition in ['', 'def', 'name.space'] for fallback in [None,'caller','']]
    absent=copy.deepcopy(base)
    absent['imports']=[m for m in absent['imports'] if m['name']!='core']
    absent['head_queries']=[]
    # Provider entry spends a level: 63 edges succeed from the prelude at depth 0
    # and fail from the same selected provider at depth 1.
    chain=dict(declarations=['end.x'],aliases=[],modules=[module(f'c{i}',edges=[edge(f'c{i+1}' if i<62 else 'end')]) for i in range(63)],
               queries=[],imports=[imports(f'c{i}') for i in range(63)],providers=[],declared=[],toolchain=[],prelude='c0',
               route_queries=[['x',None,b] for b in [False,True]],head_queries=[])
    provider=copy.deepcopy(chain)
    provider['providers']=[['x','c0',False]]
    graphs=[base,absent,chain,provider]
    rng=random.Random(824173)
    for graph in E['cases']()[1:9]:
        graph['queries']=[]
        owners=[m['name'] for m in graph['modules']]
        graph.update(imports=[imports(owner,[['l',rng.choice(owners)]],
                               [edge(rng.choice(owners),bool(rng.randrange(2)),selected=['a','b'],renames=[['a','x']]) for _ in range(3)]) for owner in owners],
                     providers=[[name,rng.choice(owners),bool(rng.randrange(2))] for name in ['a','b','a']],
                     declared=[f'{rng.choice(owners)}.x'],toolchain=[owners[1]],prelude=owners[0],head_queries=[])
        graph['route_queries']=[[h,m,b] for m in [None,'']+owners for h in ['a','b','x','λ','l/a','m0/a','m1.a','.a','missing'] for b in [False,True]]
        graphs.append(graph)
    return graphs
