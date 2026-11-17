#!/usr/bin/env python3
"""Inventory immutable Git blobs, not a possibly changing working tree."""
import argparse
import collections
import hashlib
import json
import subprocess
from pathlib import Path


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def category(path):
    if path.startswith(('src/compiler/declarative/generated/', 'src/compiler/native/generated/')):
        return 'generated-backend'
    if path == 'src/compiler/cli/guide.coil':
        return 'generated-guide'
    if path == 'src/compiler/frontend/stdlib_manifest.coil':
        return 'mixed-manifest'
    if path.startswith('src/compiler/'):
        return 'compiler-other'
    if path.startswith('src/declarative/'):
        return 'backend-source-and-machinery'
    return 'supporting-source'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('repo', type=Path)
    ap.add_argument('--revision', default='HEAD')
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    revision = git(args.repo, 'rev-parse', args.revision + '^{commit}').decode().strip()
    entries = git(args.repo, 'ls-tree', '-rz', revision, '--', 'src', 'scripts', 'tests', 'docs').split(b'\0')
    files = []
    totals = collections.defaultdict(lambda: dict(files=0, bytes=0, physical_lines=0))
    # A single batch process avoids spawning one Git process per source file.
    objects = []
    for entry in entries:
        if not entry:
            continue
        metadata, path = entry.split(b'\t', 1)
        mode, kind, oid = metadata.split()
        if kind == b'blob':
            objects.append((path.decode(), oid.decode()))
    data = subprocess.check_output(
        ['git', '-C', str(args.repo), 'cat-file', '--batch'],
        input=''.join(oid + '\n' for _, oid in objects).encode())
    offset = 0
    for path, oid in objects:
        end = data.index(b'\n', offset)
        header = data[offset:end].split()
        size = int(header[2])
        content = data[end + 1:end + 1 + size]
        offset = end + 2 + size
        if b'\0' in content:
            continue
        group = category(path)
        row = dict(path=path, blob=oid, sha256=hashlib.sha256(content).hexdigest(),
                   category=group, bytes=size, physical_lines=len(content.splitlines()))
        files.append(row)
        for label in [group, 'all-text']:
            totals[label]['files'] += 1
            totals[label]['bytes'] += size
            totals[label]['physical_lines'] += row['physical_lines']
    result = dict(revision=revision, scope='Tracked text under src/scripts/tests/docs',
                  caveat='Categories are an inventory, not a final authored production LOC count. '
                  'compiler-other may contain further generated regions; supporting-source includes tests/docs. '
                  'No heuristic code-only count is claimed.', totals=dict(sorted(totals.items())), files=files)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['totals'], indent=2))


if __name__ == '__main__':
    main()
