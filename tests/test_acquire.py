import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from guardstudy.acquire import normalize_records, source_lock, verify_raw, public_endpoint, validate_url
from guardstudy.io import StudyError

def groups():
    return {g:[dict(prompt=f'Public example {g} {i}',word_list=['word']*n,category='source category') for i in range(113)] for g,n in [('one',1),('two',2),('three',3)]}
class AcquireTests(unittest.TestCase):
    def test_pins_and_duplicates(self):
        data=groups();data['two'][0]['prompt']=data['one'][0]['prompt']
        result=normalize_records(data)
        self.assertEqual(len(result['records']),339);self.assertEqual(len(result['clusters']),338)
        c=next(c for c in result['clusters'] if len(c['member_ids'])==2)
        self.assertEqual(c['partitions'],['one','two']);self.assertEqual(c['representative_id'],result['records'][0]['id'])
        self.assertEqual(sum(v['size'] for v in source_lock()['files']),35051)
    def test_invalid_rows(self):
        for change in [lambda d:d['one'].pop(),lambda d:d['one'][0].update(prompt=None),lambda d:d['two'][0].update(word_list=['x']),lambda d:d['one'][0].update(category=''),lambda d:d['one'][0].update(extra=1)]:
            d=groups();change(d)
            with self.assertRaises(StudyError): normalize_records(d)
    def test_raw_before_parser(self):
        root=Path(tempfile.mkdtemp(prefix='guardstudy-raw-test-'))
        for f in source_lock()['files']: (root/f['filename']).write_bytes(b'x'*f['size'])
        with self.assertRaises(StudyError): verify_raw(root)
    def test_url_and_private_dns(self):
        for url in ['http://example.org/x','https://user@example.org/x','https://example.org:444/x','https://example.org/\r\nx']:
            with self.assertRaises(StudyError): validate_url(url)
        with patch('guardstudy.acquire.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(StudyError): public_endpoint('example.org')

    def test_redirects_downgrade_overflow(self):
        from guardstudy.acquire import _https
        class Headers(dict):
            def get_all(self,name,default=None): return [self[name]] if name in self else default
        class Response:
            def __init__(self,status,headers,body=b'x'): self.status=status;self.headers=Headers(headers);self.body=body
            def read(self,limit): return self.body[:limit]
        class Connection:
            responses=[]
            def __init__(self,*a): pass
            def request(self,*a,**kw): pass
            def getresponse(self): return self.responses.pop(0)
            def close(self): pass
        for responses in [[Response(302,{'location':'https://example.org/x'}) for _ in range(4)],[Response(302,{'location':'http://example.org/x'})],[Response(200,{'Content-Length':'999999'})],[Response(200,{},b'x'*20)]]:
            Connection.responses=responses
            with patch('guardstudy.acquire.public_endpoint',return_value=(2,('8.8.8.8',443))),patch('guardstudy.acquire.PinnedConnection',Connection):
                with self.assertRaises(StudyError): _https('https://example.org/x',10)
