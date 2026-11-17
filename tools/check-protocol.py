#!/usr/bin/env python3
"""Validate protocol definitions and independently shaped generated drivers."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
args = argparse.ArgumentParser()
args.add_argument('--compiler', type=Path, default=ROOT/'build/schema-seed')
compiler = args.parse_args().compiler.resolve()
base = (ROOT/'languages/staging.protocol').read_bytes()
invalid = [
    (base + b'\n' + base, b'duplicate protocol declaration'),
    (base + b'\n(node Bad)', b'protocol module cannot contain schema declarations'),
    (base.replace(b'(start route)', b'(start route) (start install)'), b'duplicate protocol start'),
    (base.replace(b'(finish complete)', b'(finish complete) (finish other)'), b'duplicate protocol finish'),
    (base.replace(b'(start route)', b''), b'protocol needs one start and finish'),
    (base.replace(b'(start route)', b'(start absent)'), b'unknown protocol start state'),
    (base.replace(b'(budget requests 64)', b'(budget requests -1)'), b'protocol budget must be nonnegative'),
    (base.replace(b'(budget requests 64)', b'(budget requests 64) (budget requests 2)'), b'duplicate protocol budget'),
    (base.replace(b'(state install', b'(state route'), b'duplicate protocol state'),
    (base.replace(b'(on Done complete)', b'(on Done complete) (on Done install)'), b'duplicate protocol outcome'),
    (base.replace(b'(state install (on Ready invoke))', b'(state install)'), b'protocol state needs an outcome'),
    (base.replace(b'(on Done complete)', b'(on Done nowhere)'), b'unknown protocol target state'),
    (base.replace(b'(spend Request requests install)', b'(spend Request missing install)'), b'unknown protocol budget'),
    (base.replace(b'(spend Request requests install)', b'(on Request install)'), b'protocol cycle must spend a finite budget'),
    (base.replace(b'(on Ready invoke)', b'(on Ready install) (on Next invoke)'), b'protocol cycle must spend a finite budget'),
    (base.replace(b'(start route)', b'(start complete)'), b'unreachable protocol state'),
    (base.replace(b'(on Done complete)', b'(on bad/name complete)'), b'invalid protocol event name'),
    (base.replace(b'(budget requests 64)', b'(budget bad/name 64)'), b'invalid protocol name'),
    (base.replace(b'(spend Request requests install)', b'(spend Request requests)'), b'wrong syntax arity'),
    (base.replace(b'(spend Request requests install)', b'(spend-within Request requests -1 install)'), b'protocol edge ceiling must be within its budget'),
    (base.replace(b'(spend Request requests install)', b'(spend-within Request requests 65 install)'), b'protocol edge ceiling must be within its budget'),
    (base.replace(b'(spend Request requests install)', b'(spend-within Request missing 16 install)'), b'unknown protocol budget'),
    (base.replace(b'(on Done complete)', b'(on Done complete) (spend-within Done requests 16 install)'), b'duplicate protocol outcome'),
]
for spec, message in invalid:
    result = subprocess.run([str(compiler)], input=spec, capture_output=True)
    assert result.returncode != 0 and not result.stdout and message in result.stderr, (message, result)
    assert b'seed error at ' in result.stderr, result

other = b'''(module fixture.protocol)
(protocol (budget retries 2) (budget polling 3) (start fetch) (finish complete)
  (state fetch (on Ready poll) (spend Retry retries fetch))
  (state poll (on Loaded complete) (spend Wait polling poll)))
'''
linear = b'''(module fixture.protocol)
(protocol (start fetch) (finish complete) (state fetch (on Loaded complete)))
'''
linear_client = '''(module fixture.main)
(import "fixture.protocol" :as p)
(import "coil.result" :use *)
(import "coil.primitive" :use [fnptr-of])
(import "coil.cc" :as cc)
(defn fetch :cc (cc/C) [(value (ptr i64))] (-> (Result p/Event i64)) (Ok (p/Event-Loaded)))
(defn main [] (-> i64)
 (let [(mut value) 0 (mut handlers) (p/Handlers [i64 i64] :step-fetch (fnptr-of fetch))]
  (match (p/run (mut value) (mut handlers)) (Ok [_] 0) (Err [_] 1))))
'''
with tempfile.TemporaryDirectory(prefix='rewrite-protocol-') as directory:
    work = Path(directory)
    (work/'Coil.toml').write_text('[package]\nname="fixture"\nentry="main.coil"\nsource-roots=["."]\n')
    for spec, client in [(other, (ROOT/'tests/protocol-other.coil.in').read_text()), (linear, linear_client)]:
        (work/'generated.coil').write_bytes(subprocess.check_output([str(compiler)], input=spec))
        (work/'main.coil').write_text(client)
        for flags in [[], ['--debug-checks'], ['--release']]:
            subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
        if spec == other:
            (work/'main.coil').write_text(client.replace('(fnptr-of fetch)', '(fnptr-of wrong)'))
            rejected = subprocess.run(['coil', 'check', 'main.coil'], cwd=work, capture_output=True)
            assert rejected.returncode != 0 and b'bool' in rejected.stdout + rejected.stderr, rejected
    # A zero request budget still permits immediate completion, but no install.
    (work/'generated.coil').write_bytes(subprocess.check_output([str(compiler)], input=base.replace(b'rewrite.stageprotocol', b'fixture.protocol').replace(b'64', b'0')))
    client = (ROOT/'tests/protocol.coil').read_text().replace('rewrite.testprotocol', 'fixture.main').replace('rewrite.stageprotocol', 'fixture.protocol')
    # Keep the tested driver callbacks; use a dedicated zero-boundary assertion.
    client = client[:client.index('(defn main []')]+'''
(defn main [] (-> i64)
 (let [(mut state) (State :remaining 0 :installed 0 :resumed 0 :mode 0)
       (mut handlers) (p/Handlers [State i64] :step-route (fnptr-of route) :step-install (fnptr-of install) :step-invoke (fnptr-of invoke) :step-resume (fnptr-of resume))]
  (match (p/run (mut state) (mut handlers)) (Ok [_]) (Err [_] (panic "zero-budget completion")))
  (set! (.remaining state) 1)
  (match (p/run (mut state) (mut handlers))
   (Err [e] (match e (p/Exhausted [_ limit] (if (and (= limit 0) (= (.installed state) 0)) 0 1)) (_ 1)))
   (Ok [_] 1))))
'''
    (work/'main.coil').write_text(client)
    for flags in [[], ['--debug-checks'], ['--release']]:
        subprocess.run(['coil', 'run', 'main.coil', *flags], cwd=work, check=True)
print('Protocol shape/name/graph validation, independent budgets, acyclic drivers and typed effects passed')
