import unittest
from verified_hosts import make_hosts
import json

class HostRules(unittest.TestCase):
    def test_active_paid_and_linked_only(self):
        ids=["usr_00000000-0000-0000-0000-00000000000"+str(i) for i in range(4)]
        pages=[{"data":[{"type":"member","id":str(i),"attributes":{"patron_status":s,"currently_entitled_amount_cents":v}} for i,(s,v) in enumerate([("active_patron",500),("former_patron",500),("active_patron",0),("active_patron",800)])]}]
        mapping=json.dumps([{"member":str(i),"account":ids[i]} for i in [0,1,2]])
        result=make_hosts(pages,mapping,100,lambda uid:"Verified singer")
        self.assertEqual(result,{"version":1,"issued":100,"expires":21700,"hosts":["Verified singer"]})
        self.assertEqual(make_hosts(pages,"",100)["hosts"],[])
        self.assertEqual(make_hosts(pages,mapping,100,lambda _:None)["hosts"],[])
        with self.assertRaises(ValueError):
            make_hosts([],json.dumps([{"member":"1","account":ids[0]}]*2),100)
