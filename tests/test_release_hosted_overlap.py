"""Licensed provenance exempts only exact verified text slots, never arbitrary prose."""
import copy
import unittest
from hsenv import distribution as D, release

class HostedOverlap(unittest.TestCase):
    text = 'The purple mountain hides a silver lake beneath the morning stars.'
    def fixture(self):
        raw = self.text.encode()
        p = {'meta': {'sources': {
            'open': {'sha256': D.sha256(raw), 'distribution': {'tier': 'hosted', 'licence': 'CC-BY-4.0', 'attribution': 'Synthetic author', 'format': 'text'}},
            'ref': {'distribution': {'tier': 'link', 'url': 'https://example.org/reference', 'format': 'text'}}}},
            'data': {'item': {'text': self.text, 'cite': {'source': 'open', 'label': 'verbatim'}}}}
        return p, {'open': raw, 'ref': raw}
    def test_exact_cited_hash_verified_overlap_allowed(self):
        p,s = self.fixture()
        q,r = release.project(p,sources=s)
        self.assertEqual(q['data']['item']['text'],self.text)
        self.assertEqual(r['held'],0)
    def test_uncited_wrong_hash_missing_source_and_partial_source_rejected(self):
        for change in ['cite','hash','source','partial']:
            with self.subTest(change=change):
                p,s=self.fixture()
                if change=='cite': p['data']['item'].pop('cite')
                if change=='hash': p['meta']['sources']['open']['sha256']='0'*64
                if change=='source': s.pop('open')
                if change=='partial':
                    s['open']=b'The purple mountain'
                    p['meta']['sources']['open']['sha256']=D.sha256(s['open'])
                with self.assertRaises(release.ProjectionError): release.project(p,sources=s)
    def test_other_screen_slot_is_not_exempted(self):
        p,s=self.fixture();p['data']['uncited']={'text':self.text}
        with self.assertRaises(release.ProjectionError): release.project(p,sources=s)
    def test_bound_cell_key_only_not_arbitrary_key(self):
        p,s=self.fixture();s['ref']=b'charity present'
        p['analysis']={'effects':[{'compute':{'op':'interaction','a_levels':['charity'],'b_levels':['present']},'reported':{'cells':{'charity|present':{'mean':1}}}}]}
        release.project(p,sources=s)
        p['analysis']['effects'][0]['compute']['b_levels']=['absent']
        with self.assertRaises(release.ProjectionError): release.project(p,sources=s)
        p,s=self.fixture();s['ref']=b'charity present';p['data']['charity|present']={}
        with self.assertRaises(release.ProjectionError): release.project(p,sources=s)
