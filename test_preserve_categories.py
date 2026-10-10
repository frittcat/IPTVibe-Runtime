import unittest
from preserve_categories import preserve,capture
from live_overrides import blocks

def row(name, cat, url='https://example.org/video'):
    return f'canal: {name}\ncategoria: {cat}\nfonte: {url}\n\n'
class PreservationTest(unittest.TestCase):
    def test_new_protected_channel_is_retained_after_later_upstream_removal(self):
        library=capture(row('Nova série','24 Horas','https://new.example/video'),row('Serie','24 Horas'))
        merged,count=preserve(row('Atual','Esportes'),library)
        self.assertEqual(count,2);self.assertIn('Nova série',merged)
    def test_shortlisted_runtime_does_not_destroy_retained_alternative_candidates(self):
        old=row('Serie','24 Horas')+'fonte: https://backup.example/video\n'
        saved=capture(row('Serie','24 Horas'),old)
        self.assertIn('backup.example',saved)
    def test_missing_differentials_survive_repeated_sync(self):
        current=row('Atual','Esportes'); old=row('Serie','24 Horas')+row('Pluto','Pluto TV')+row('Antigo','Esportes')
        merged,count=preserve(current,old); self.assertEqual(count,2)
        self.assertEqual([name for name,_ in blocks(merged)],['Atual','Serie','Pluto'])
        again,count=preserve(merged,old);self.assertEqual(again,merged);self.assertEqual(count,0)
    def test_upstream_source_and_category_win_without_duplicates(self):
        current=row('Série','Infantil','https://new.example/video'); old=row('SÉRIE','24 Horas','https://old.example/video')
        merged,count=preserve(current,old);self.assertEqual(count,0);self.assertIn('new.example',merged);self.assertNotIn('old.example',merged)
    def test_candidate_uses_current_account_for_same_provider(self):
        current=row('Atual','Esportes','https://p.example/live/new/pass/1.ts'); old=row('Serie','24 Horas','https://p.example/live/old/secret/2.ts')
        merged,_=preserve(current,old);self.assertIn('/live/new/pass/2.ts',merged);self.assertNotIn('/old/secret/',merged)
if __name__=='__main__': unittest.main()
