"""Keep reviewed live repairs after upstream synchronizations; never log source URLs."""
import argparse, hashlib, json, re, concurrent.futures
from pathlib import Path

def identity(value): return hashlib.sha256(value.encode('utf-8')).hexdigest()
def blocks(text):
    result=[]
    for match in re.finditer(r'(?m)^canal\s*:\s*(.+)$',text):
        result.append((match.start(),match.group(1).strip()))
    return [(name,text[start:result[i+1][0] if i+1<len(result) else len(text)]) for i,(start,name) in enumerate(result)]
def source_blocks(block):
    matches=list(re.finditer(r'(?m)^fonte\s*:\s*(.+)$',block))
    return [(m.group(1).strip(),block[m.start():matches[i+1].start() if i+1<len(matches) else len(block)]) for i,m in enumerate(matches)]
def apply(path,health,replacements=None):
    text=path.read_text(encoding='utf-8'); rows=blocks(text)
    if not rows: return
    verified=set(health['verified']); failed=set(health['confirmed_unavailable'])
    def rank(source): return 2 if identity(source[0]) in failed else 0 if identity(source[0]) in verified else 1
    rows_by_name=dict(rows)
    accounts={}
    from audit_live import account
    import urllib.parse
    for _,block in rows:
        for url,_ in source_blocks(block):
            credentials=account(url)
            if credentials: accounts[urllib.parse.urlsplit(url).netloc]=credentials
    repaired=[]
    for name,block in rows:
        sources=source_blocks(block)
        blocked=set(health.get('wrong_identity',{}).get(name,[]))
        if name=='Band' and 'Band SP' in rows_by_name and any(identity(s[0]) in blocked for s in sources): sources=source_blocks(rows_by_name['Band SP'])
        sources=[s for s in sources if identity(s[0]) not in blocked]
        for entry in (replacements or {}).get(name,[]):
            url=entry.get('url')
            if not url and entry.get('account_host') in accounts:
                base,user,password=accounts[entry['account_host']]
                url=base+'/live/'+user+'/'+password+'/'+str(entry['stream_id'])+'.ts'
            if url and not any(s[0]==url for s in sources):
                chunk='fonte: '+url+'\n'
                for key in ('agente','referer'):
                    if entry.get(key):chunk+=key+': '+entry[key]+'\n'
                sources.insert(0,(url,chunk))
        if not sources:
            repaired.append(block); continue
        sources=sorted(sources,key=rank)
        compatibility_source=sources[:1]
        # Shortlists survive every upstream sync; never fill missing slots with known failures.
        sources=[s for s in sources if identity(s[0]) not in failed]
        approved=health.get('curated_sources',{}).get(name)
        trusted=[s for s in sources if identity(s[0]) in (set(approved) if approved is not None else verified)]
        candidates=trusted if trusted else sources[:1]
        chosen=[];families=set()
        for item in candidates:
            host=(urllib.parse.urlsplit(item[0]).hostname or '').lower()
            family='family-vvt' if host in ('vivlar.me','vaiagora.vip','tvonhdbr.com') else host
            if family and family in families:continue
            if family:families.add(family)
            chosen.append(item)
            if len(chosen)==3:break
        # Keep an unavailable channel parseable for older installed clients.
        # New clients exclude these hashes and show an unavailable state.
        sources=chosen or compatibility_source
        match=re.search(r'(?m)^fonte\s*:',block)
        header=block[:match.start()] if match else block.rstrip()+'\n'
        if name in health['logos']: header=re.sub(r'(?m)^logo\s*:.*$',lambda m:'logo: '+health['logos'][name],header)
        repaired.append(header+''.join(chunk.rstrip()+'\n' for _,chunk in sources)+'\n')
    path.write_text((text[:text.index(rows[0][1])]+''.join(repaired)).rstrip()+'\n',encoding='utf-8')
def main():
    p=argparse.ArgumentParser();p.add_argument('runtime');p.add_argument('--policy',default='live-health.json');p.add_argument('--replacements',default='live-replacements.json');p.add_argument('--probe',action='store_true');a=p.parse_args()
    health=json.loads(Path(a.policy).read_text(encoding='utf-8'))
    replacements=json.loads(Path(a.replacements).read_text(encoding='utf-8')) if Path(a.replacements).exists() else {}
    if a.probe:
        from audit_live import catalog, probe
        old=set(health['confirmed_unavailable']); requests={}
        for row in catalog(Path(a.runtime)/'catalogo.txt'):
            for source in row['sources']:
                key=identity(source['url'])
                if key not in old:continue
                headers={}
                if source.get('agente'):headers['User-Agent']=source['agente']
                if source.get('referer'):headers['Referer']=source['referer']
                requests.setdefault(key,[]).append((source['url'],headers))
        def recheck(item):
            key,variants=item
            results=[probe(url,headers) for url,headers in variants]
            failed=all(r.get('status')=='non_media' or r.get('code') in (404,410) for r in results)
            return key,failed
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
            health['confirmed_unavailable']=[key for key,failed in pool.map(recheck,requests.items()) if failed]
        print('Confirmed unavailable observations refreshed:',len(health['confirmed_unavailable']))
    for name in ('catalogo.txt','canais.txt','restritos.txt'):
        file=Path(a.runtime)/name
        if file.exists():apply(file,health,replacements)
    # Clients refresh the reviewed policy separately from the changing catalog.
    (Path(a.runtime)/'source-health.json').write_text(json.dumps(health,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Reviewed live overrides applied')
if __name__=='__main__':main()
