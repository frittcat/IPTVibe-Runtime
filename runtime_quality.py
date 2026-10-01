"""Validate highlighted explicit VOD sources without publishing URLs or credentials.

Short provider IDs are left unresolved; HTTP failures/timeouts are inconclusive.
Only two definite non-media responses remove a title from promotional rows.
The catalog remains intact so a provider repair can recover on the next sync.
"""
import argparse
import concurrent.futures
import hashlib
import json
import time
import urllib.request
from pathlib import Path


def repair(value):
    for _ in range(2):
        before = value
        for charset in ('latin1', 'cp1252'):
            try:
                candidate = value.encode(charset).decode('utf-8')
                score = lambda x: x.count('Ã') + x.count('Â') + x.count('\ufffd')
                if score(candidate) < score(value): value = candidate
            except (UnicodeError, LookupError): pass
        if value == before: break
    return value


def classify(data, content_type=''):
    head = data.lstrip().lower()
    if head.startswith(b'#extm3u') or data[4:8] == b'ftyp' or data.startswith(b'\x1aE\xdf\xa3'):
        return 'media_header'
    if len(data) > 376 and data[0] == 0x47 and data[188] == 0x47 and data[376] == 0x47:
        return 'media_header'
    if head.startswith((b'<!doctype html', b'<html', b'<head', b'<body')):
        return 'non_media'
    if ('text/html' in content_type.lower() or 'application/json' in content_type.lower()) and len(data) < 8192:
        return 'non_media'
    return 'unknown'


def probe(url):
    try:
        req = urllib.request.Request(url, headers={'Range': 'bytes=0-4095', 'User-Agent': 'IPTVibe-Quality/1.2'})
        with urllib.request.urlopen(req, timeout=8) as response:
            return classify(response.read(4096), response.headers.get('Content-Type', ''))
    except Exception:
        return 'unknown'  # Never emit exception strings: they may include secret URLs.


def sources(runtime, title):
    for path in sorted((runtime / 'vod').glob('filmes-*.txt')):
        for line in path.read_text(encoding='utf-8').splitlines():
            parts = line.split('\t')
            if parts[0] == title:
                result = []
                for cell in parts[1:]:
                    for value in cell.split('|'):
                        candidate = value.split('=', 1)[-1]
                        result.append(candidate if candidate.startswith(('https://', 'http://')) else None)
                return result
    return []


def inspect(runtime, title):
    candidates = sources(runtime, title)
    if not candidates or any(value is None for value in candidates): return title, 'unresolved'
    first = [probe(url) for url in candidates]
    if 'media_header' in first: return title, 'media_header'
    if not all(value == 'non_media' for value in first): return title, 'unknown'
    second = [probe(url) for url in candidates]
    return title, 'quarantined' if all(value == 'non_media' for value in second) else 'unknown'


def run(runtime, check=False):
    repaired = 0
    for name in ('catalogo.txt', 'restritos.txt'):
        path = runtime / name
        if not path.exists(): continue
        lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith(('canal:', 'categoria:', 'qualidade:')):
                updated = repair(line)
                if updated != line: repaired += 1; lines[i] = updated
        path.write_text(''.join(lines), encoding='utf-8')
    highlights = runtime / 'vod/destaques.txt'
    lines = highlights.read_text(encoding='utf-8').splitlines(keepends=True)
    titles = []; current = ''
    for line in lines:
        parts = line.rstrip('\n').split('\t')
        if parts[0] == 'fila': current = parts[1]
        elif current == 'Em alta' and parts[0] == 'f': titles.append(parts[1])
    results = {}
    if check:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(inspect, runtime, title) for title in dict.fromkeys(titles)]
            results = dict(f.result() for f in futures)
        kept = []; row = ''
        for line in lines:
            parts = line.rstrip('\n').split('\t')
            if parts[0] == 'fila': row = parts[1]
            if row == 'Em alta' and parts[0] == 'f' and results.get(parts[1]) == 'quarantined': continue
            kept.append(line)
        highlights.write_text(''.join(kept), encoding='utf-8')
    status = {'schema': 1, 'checked_at': int(time.time()), 'repaired_labels': repaired,
              'scope': 'Em alta; explicit URLs only; media headers do not prove playback',
              'titles': {hashlib.sha256(k.encode()).hexdigest(): v for k, v in results.items()}}
    target = runtime / 'monitor/quality.json'; target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'repaired_labels': repaired, 'checked': len(results),
                      'quarantined': sum(v == 'quarantined' for v in results.values()),
                      'media_headers': sum(v == 'media_header' for v in results.values())}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('runtime', type=Path)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args(); run(args.runtime, args.probe)
