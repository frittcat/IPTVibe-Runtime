"""Preserve IPTVibe's owned 24-hour/Pluto inventory without overriding newer upstream rows."""
import argparse, json, re, unicodedata
from pathlib import Path
from urllib.parse import urlsplit
from live_overrides import blocks, source_blocks
from runtime_quality import repair
from audit_live import account

CATEGORIES = {'24 Horas', 'Pluto TV'}
def key(name): return unicodedata.normalize('NFKC', repair(name)).casefold().strip()
def category(block):
    match = re.search(r'(?m)^categoria:\s*(.+)$', block)
    return repair(match.group(1).strip()) if match else ''

def preserve(current, retained):
    rows = blocks(current); present = {key(name) for name, _ in rows}
    accounts = {}
    for _, block in rows:
        for url, _ in source_blocks(block):
            credentials = account(url)
            if credentials: accounts[urlsplit(url).netloc] = credentials
    appended = []
    for name, block in blocks(retained):
        if category(block) not in CATEGORIES or key(name) in present: continue
        # Use the latest authorized mirror account for the same provider and stream ID.
        # This is only a candidate, never playback qualification.
        def refresh(match):
            url = match.group(1).strip(); old = account(url); current_account = accounts.get(urlsplit(url).netloc)
            if old and current_account:
                base, user, password = current_account
                stream = urlsplit(url).path.rsplit('/', 1)[-1]
                url = base + '/live/' + user + '/' + password + '/' + stream
            return 'fonte: ' + url
        block = re.sub(r'(?m)^fonte:\s*(.+)$', refresh, block)
        appended.append(block.rstrip()); present.add(key(name))
    return current.rstrip() + ('\n\n' + '\n\n'.join(appended) if appended else '') + '\n', len(appended)

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('runtime', type=Path); p.add_argument('--retained', type=Path, default=Path('retained-categories.txt')); a = p.parse_args()
    target = a.runtime / 'catalogo.txt'; merged, count = preserve(target.read_text(encoding='utf-8'), a.retained.read_text(encoding='utf-8'))
    target.write_text(merged, encoding='utf-8')
    print(json.dumps({'restored_missing_channels': count}))
