import json
import unittest
from hsenv import release, distribution as D

class MixedFiles(unittest.TestCase):
    open_text='The purple mountain hides a silver lake beneath the morning stars.'
    private_text='The secret captain keeps a golden telescope behind the crimson curtains.'
    def fixture(self):
        raw=self.open_text.encode(); restricted=(self.open_text+' '+self.private_text).encode()
        p={'meta':{'sources':{
          'paper':{'file':'sources/open/paper.txt','sha256':D.sha256(raw),'distribution':{'tier':'hosted','licence':'CC-BY-4.0','attribution':'Synthetic author','format':'text'}},
          'reference':{'distribution':{'tier':'link','url':'https://example.org/reference','sha256':D.sha256(restricted),'format':'text'}}}},'distribution':{'strict':True,'held':{}}}
        sources={'paper':raw,'reference':restricted}
        doc={'evidence':[{'id':'e','sourceId':'paper','path':'sources/open/paper.txt','quote':self.open_text}], 'nodes':[{'fields':[{'value':'Summary: '+self.open_text,'evidenceIds':['e']}]}]}
        return p,sources,doc
    def allowed(self,name,p,s,c):return release.distributable(name,p,content=json.dumps(c) if isinstance(c,dict) else c,sources=s)
    def test_exact_hosted_file_and_reference_exclusion(self):
        p,s,d=self.fixture()
        self.assertTrue(self.allowed('sources/open/paper.txt',p,s,s['paper']))
        self.assertFalse(self.allowed('sources/open/reference.txt',p,s,s['reference']))
        self.assertFalse(self.allowed('sources/open/paper.txt',p,s,s['reference']))
        p['meta']['sources']['paper']['distribution']['licence']='unknown'
        self.assertFalse(self.allowed('sources/open/paper.txt',p,s,s['paper']))
    def test_program_verified_quotes_and_every_overlap(self):
        p,s,d=self.fixture();self.assertTrue(self.allowed('program.json',p,s,d))
        d['nodes'][0]['fields'][0]['value']+=' '+self.private_text
        self.assertFalse(self.allowed('program.json',p,s,d))
    def test_missing_evidence_and_forged_source_fail(self):
        for change in ['cite','hash','bytes','path','reference']:
            with self.subTest(change=change):
                p,s,d=self.fixture()
                if change=='cite':d['nodes'][0]['fields'][0]['evidenceIds']=[]
                if change=='hash':p['meta']['sources']['paper']['sha256']='0'*64
                if change=='bytes':s.pop('paper')
                if change=='path':d['evidence'][0]['path']='other.txt'
                if change=='reference':s['reference']=b'wrong reference'
                self.assertFalse(self.allowed('program.json',p,s,d))
    def test_reviews_scanned_not_blanket_allow(self):
        p,s,d=self.fixture()
        self.assertTrue(self.allowed('review/checks-latest.json',p,s,{'pass':True}))
        self.assertTrue(self.allowed('review/fidelity-review-1.md',p,s,'All computational checks passed.'))
        self.assertFalse(self.allowed('review/fidelity-review-1.md',p,s,self.private_text))
        self.assertFalse(self.allowed('review/checks-latest.json',p,s,{'text':self.private_text}))
        self.assertFalse(self.allowed('review/source.pdf',p,s,s['reference']))

    def test_held_text_never_exempted_by_hosted_evidence(self):
        p,s,d=self.fixture()
        p['distribution']['held']={'h1':{'kind':'text','source':'reference','text_sha256':D.text_sha256(self.open_text)}}
        self.assertFalse(release.distributable('program.json',p,content=json.dumps(d),sources=s,held_texts={'h1':self.open_text}))

    def test_mixed_cjk_window_and_unverified_title_remain_blocked(self):
        p,s,d=self.fixture()
        phrase='我用LongBrandName测量作业'
        s['reference']=phrase.encode()
        p['meta']['sources']['reference']['distribution']['sha256']=D.sha256(s['reference'])
        d['nodes'][0]['fields'][0]['value']='The survey prompt says '+phrase+' in this workflow.'
        self.assertFalse(self.allowed('program.json',p,s,d))
        p,s,d=self.fixture();d['source']={'title':self.private_text,'filename':'sources/open/paper.txt'}
        self.assertFalse(self.allowed('program.json',p,s,d))
