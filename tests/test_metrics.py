import unittest
from guardstudy.metrics import summarize, paired, latency, wilson

def pred(i,decision='CLEAN',status='ok'):
    return dict(representative_id=str(i),decision=decision,status=status,forward_ns=100)
class MetricsTests(unittest.TestCase):
    def test_missing_is_not_clean(self):
        rows=[pred(i,'ATTACK' if i<2 else 'CLEAN') for i in range(8)]
        got=summarize(rows,[str(i) for i in range(10)])
        self.assertEqual((got['fp'],got['ok'],got['not_attempted']),(2,8,2))
        self.assertEqual(got['fpr_observed'],.25);self.assertEqual(got['coverage'],.8)
        self.assertEqual(got['fpr_bounds'],[.2,.4]);self.assertEqual(got['status'],'incomplete')
        self.assertIsNone(got['auroc']['value'])
    def test_empty(self):
        self.assertEqual(summarize([],[])['status'],'inconclusive')
        self.assertEqual(summarize([],['1'])['fpr_bounds'],[0,1])
        self.assertIsNone(wilson(0,0))
    def test_paired(self):
        a=[pred(i,'ATTACK') for i in range(3)];b=[pred(i) for i in range(3)]
        result=paired(a,b,['0','1','2','3'])
        self.assertEqual(result['mcnemar_exact_p'],.25);self.assertEqual(result['missing_pairs'],1)
        self.assertEqual(paired([],[],[])['mcnemar_exact_p'],None)
    def test_latency(self):
        r=latency([1,2,3,4]);self.assertEqual((r['mean'],r['median'],r['p95']),(2.5,2.5,4))
        self.assertIsNone(latency([])['median'])
