import unittest
from unittest.mock import patch
import sync_patrons as sync

def member(i, name='Friend', status='active_patron', amount=300, tier='1'):
    return {'type':'member','id':str(i),'attributes':{'full_name':name,'patron_status':status,'currently_entitled_amount_cents':amount,'email':'PRIVATE'},'relationships':{'currently_entitled_tiers':{'data':[{'type':'tier','id':tier}]}}}

class FeedTests(unittest.TestCase):
    def page(self, members):
        return {'data':members,'included':[{'type':'tier','id':'1','attributes':{'title':'Void Tier','amount_cents':300}},{'type':'tier','id':'2','attributes':{'title':'Future Tier','amount_cents':900}}]}
    def test_paid_hidden_free_and_declined(self):
        result=sync.make_feed([self.page([member(1),member(2,None),member(3,status='former_patron'),member(4,amount=0),member(5,status='declined_patron')])],{'tier_colors':{'Void Tier':'#ff4a60'}},'TEST')
        self.assertEqual(result['patrons'],[{'name':'Friend','tier':'Void Tier','color':'#FF4A60'}])
        self.assertNotIn('email',str(result)); self.assertNotIn('PRIVATE',str(result)); self.assertNotIn('amount',str(result))
    def test_pagination_dedupe_alias_mask_and_tier_change(self):
        result=sync.make_feed([self.page([member(1),member(2)]),self.page([member(1,tier='2'),member(3,None)])],{'display_names':{'1':'Public Alias','3':'Must stay masked'},'hide_member_ids':['2']})
        self.assertEqual(len(result['patrons']),1);self.assertEqual(result['patrons'][0]['name'],'Public Alias');self.assertEqual(result['patrons'][0]['tier'],'Future Tier')
    def test_large_list(self):
        result=sync.make_feed([self.page([member(i,'User '+str(i)) for i in range(1200)])],{})
        self.assertEqual(len(result['patrons']),1200)
    def test_bad_color_preserves_no_output(self):
        with self.assertRaises(ValueError):sync.make_feed([self.page([member(1)])],{'tier_colors':{'Void Tier':'red'}})
    def test_unknown_tier_and_clean_names(self):
        result=sync.make_feed([self.page([member(1,'A\nB\x00',tier='999')])],{})
        self.assertEqual(result['patrons'][0]['name'],'AB');self.assertEqual(result['patrons'][0]['tier'],'Supporter')
    @patch('sync_patrons.request_json')
    def test_pagination_credentials_never_leave_patreon(self, request):
        request.return_value={'data':[],'links':{'next':'https://evil.example/collect'}}
        with self.assertRaises(ValueError):sync.pages_from_api('SECRET','123')
        self.assertEqual(request.call_count,1)
    @patch('sync_patrons.request_json')
    def test_complete_pagination(self, request):
        request.side_effect=[{'data':[],'links':{'next':sync.API+'campaigns/123/members?page%5Bcursor%5D=NEXT'}},{'data':[],'links':{}}]
        self.assertEqual(len(sync.pages_from_api('SECRET','123')),2)
    def test_empty_list_valid(self):
        self.assertEqual(sync.make_feed([self.page([])],{})['patrons'],[])

if __name__=='__main__': unittest.main()
