#!/usr/bin/env python3
"""Run isolated serial commands; retain outputs, wall time and sampled group RSS."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cwd', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--timeout', type=float, default=600)
    ap.add_argument('command', nargs=argparse.REMAINDER)
    args = ap.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or args.runs < 1 or args.timeout <= 0:
        ap.error('provide a command, positive run count and timeout')
    binary = Path(shutil.which(command[0]) or command[0]).resolve(strict=True)
    command[0] = str(binary)
    report = dict(command=command, cwd=str(args.cwd.resolve()), platform=platform.platform(),
                  binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  memory='Maximum sampled sum of RSS in the child process group, bytes; '
                  '50ms target sampling, includes shared pages per process, can miss short-lived peaks. '
                  'Detached descendants are not included.',
                  cache='No OS cache eviction. First and subsequent fresh-process runs are identified; '
                  'these are not proven cold-cache measurements.', runs=[])
    report['source_revision'] = subprocess.check_output(
        ['git', '-C', str(args.cwd), 'rev-parse', 'HEAD'], text=True).strip()
    report['source_status'] = subprocess.check_output(
        ['git', '-C', str(args.cwd), 'status', '--porcelain'], text=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for number in range(args.runs):
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            start = time.monotonic()
            proc = subprocess.Popen(command, cwd=args.cwd, stdout=out, stderr=err, start_new_session=True)
            peak = samples = 0
            timed_out = False
            while proc.poll() is None:
                snapshot = subprocess.check_output(['ps', '-axo', 'pgid=,rss='], text=True)
                rss = 0
                for line in snapshot.splitlines():
                    fields = line.split()
                    if len(fields) == 2 and int(fields[0]) == proc.pid:
                        rss += int(fields[1]) * 1024
                peak = max(peak, rss)
                samples += 1
                if time.monotonic() - start > args.timeout:
                    timed_out = True
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    break
                time.sleep(0.05)
            code = proc.wait()
            elapsed = time.monotonic() - start
            out.seek(0)
            err.seek(0)
            report['runs'].append(dict(run=number + 1, seconds=elapsed, sampled_group_peak_bytes=peak,
                                      samples=samples, exit=code, timed_out=timed_out,
                                      stdout=out.read().decode(errors='replace'),
                                      stderr=err.read().decode(errors='replace')))
            args.output.write_text(json.dumps(report, indent=2) + '\n')
            print(f'run {number + 1}: exit={code} wall={elapsed:.3f}s sampled RSS={peak} bytes', flush=True)
            if code or timed_out:
                raise SystemExit(1)


if __name__ == '__main__':
    main()
