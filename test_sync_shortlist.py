import tempfile,unittest
from pathlib import Path
from live_overrides import apply,identity,blocks,source_blocks
class SyncShortlistTest(unittest.TestCase):
 def test_disabled_host_does_not_hide_channel_with_available_candidate(self):
  import json
  health={'verified':[],'confirmed_unavailable':[],'logos':{}}
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'catalogo.txt';(p.parent/'monitor').mkdir();(p.parent/'monitor/fontes.json').write_text(json.dumps({'desativados':['bad.example']}))
   p.write_text('canal: Serie\ncategoria: 24 Horas\nfonte: https://bad.example/live\nfonte: https://candidate.example/live\n')
   apply(p,health);self.assertEqual([url for url,_ in source_blocks(blocks(p.read_text())[0][1])],['https://candidate.example/live'])
 def test_sync_preserves_max_and_fewer_qualified_sources(self):
  urls=['https://a.example/1','https://a.example/2','https://b.example/1','https://c.example/1','https://d.example/1']
  health={'verified':[identity(u) for u in urls],'confirmed_unavailable':[],'logos':{},'curated_sources':{'Premiere 5':[identity(urls[0]),identity(urls[2])]}}
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'catalogo.txt';original='# header\ncanal: Premiere 5\ncategoria: Esportes\n'+''.join('fonte: '+u+'\n' for u in urls)
   p.write_text(original);apply(p,health);first=p.read_text();self.assertEqual(len(source_blocks(blocks(first)[0][1])),2)
   p.write_text(original);apply(p,health);self.assertEqual(p.read_text(),first)
 def test_diversity_and_cap(self):
  urls=['https://'+v+'.example/1' for v in ['a','b','c','d']]
  health={'verified':[identity(u) for u in urls],'confirmed_unavailable':[],'logos':{}}
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'restritos.txt';p.write_text('canal: test\n'+''.join('fonte: '+u+'\n' for u in urls));apply(p,health);self.assertEqual(len(source_blocks(blocks(p.read_text())[0][1])),3)
 def test_three_approved_streams_from_one_provider_are_retained(self):
  urls=['https://one.example/'+str(value) for value in range(4)]
  health={'verified':[identity(u) for u in urls],'confirmed_unavailable':[],'logos':{}}
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'catalogo.txt';p.write_text('canal: test\n'+''.join('fonte: '+u+'\n' for u in urls));apply(p,health)
   self.assertEqual([u for u,_ in source_blocks(blocks(p.read_text())[0][1])],urls[:3])
 def test_known_failure_removed(self):
  good='https://a.example/1';bad='https://b.example/1'
  health={'verified':[identity(good)],'confirmed_unavailable':[identity(bad)],'logos':{}}
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'catalogo.txt';p.write_text('canal: test\nfonte: '+bad+'\nfonte: '+good);apply(p,health);self.assertEqual([v[0] for v in source_blocks(blocks(p.read_text())[0][1])],[good])
if __name__=='__main__':unittest.main()
