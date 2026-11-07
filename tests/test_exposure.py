import json
import tempfile
import unittest
from pathlib import Path
from guardstudy.acquire import normalize_records
from guardstudy.exposure import audit_exposure, cohorts, normalize_for_overlap, shingles
from tests.test_acquire import groups
class ExposureTests(unittest.TestCase):
    def inventory(self,text):
        root=Path(tempfile.mkdtemp(prefix='guardstudy-private-test-'));p=root/'private.jsonl'
        p.write_text(json.dumps({'tekst':text,'id':'PRIVATE_ROW_SENTINEL'})+'\n')
        return dict(sources=[dict(id='source-001',path=str(p),kind='prepared_rows')],declared_complete=True)
    def test_normalization(self):
        self.assertEqual(normalize_for_overlap('Ａ B\n C'),'a b c')
        self.assertEqual(len(shingles('one two three four five six seven eight nine')),2)
    def test_exact_receipt_redaction(self):
        d=normalize_records(groups());receipt=audit_exposure(d,self.inventory(d['records'][0]['text']))
        self.assertEqual(receipt['records'][0]['reason'],'excluded_exact')
        out=json.dumps(receipt)
        for sentinel in ['PRIVATE_ROW_SENTINEL','private.jsonl','/Users/','Public example one 0']: self.assertNotIn(sentinel,out)
    def test_partial_and_short_never_primary(self):
        d=normalize_records(groups());r=audit_exposure(d,dict(sources=[],declared_complete=False))
        self.assertEqual(r['coverage'],'partial');self.assertEqual(cohorts(d,r)['audited_eligible_primary']['representative_ids'],[])
        r=audit_exposure(d,self.inventory('A completely different sentence containing at least eight different words.'))
        self.assertEqual(r['records'][0]['reason'],'unknown_short')
    def test_normalized_and_ngram(self):
        g=groups();g['one'][0]['prompt']='Alpha beta gamma delta epsilon zeta eta theta iota kappa'
        d=normalize_records(g)
        r=audit_exposure(d,self.inventory('ALPHA  BETA GAMMA DELTA EPSILON ZETA ETA THETA IOTA KAPPA'))
        self.assertEqual(r['records'][0]['reason'],'excluded_normalized')
        r=audit_exposure(d,self.inventory('prefix alpha beta gamma delta epsilon zeta eta theta iota kappa suffix'))
        self.assertEqual(r['records'][0]['reason'],'excluded_ngram')

    def test_streaming_parity_with_repeated_shingles(self):
        public=['a b c d e f g h i j','a b c d e f g h a b c d e f g h','short']
        private=['prefix a b c d e f g h i j suffix','A B C D E F G H A B C D E F G H','unrelated words with eight completely distinct values for audit']
        g=groups()
        for i,t in enumerate(public): g['one'][i]['prompt']=t
        dataset=normalize_records(g)
        root=Path(tempfile.mkdtemp());source=root/'private.jsonl';source.write_text(''.join(json.dumps({'tekst':t})+'\n' for t in private))
        receipt=audit_exposure(dataset,dict(sources=[dict(id='source-001',path=str(source),kind='prepared_rows')],declared_complete=True))
        for i,text in enumerate(public):
            s=shingles(text)
            expected='excluded_exact' if text in private else 'excluded_normalized' if normalize_for_overlap(text) in [normalize_for_overlap(t) for t in private] else 'excluded_ngram' if s and any(shingles(t) and len(s&shingles(t))/min(len(s),len(shingles(t)))>=.5 for t in private) else 'unknown_short' if not s else 'clear_under_audit'
            self.assertEqual(receipt['records'][i]['reason'],expected)

    def test_memory_does_not_scale_with_all_private_shingles(self):
        import tracemalloc
        root=Path(tempfile.mkdtemp());source=root/'private.jsonl'
        with source.open('w') as stream:
            for i in range(2000):
                stream.write(json.dumps({'tekst':' '.join(f'word{i}_{j}' for j in range(100))})+'\n')
        dataset=normalize_records(groups())
        tracemalloc.start()
        try:
            audit_exposure(dataset,dict(sources=[dict(id='source-001',path=str(source),kind='prepared_rows')],declared_complete=True))
            _,peak=tracemalloc.get_traced_memory()
        finally: tracemalloc.stop()
        self.assertLess(peak,16*1024**2)
