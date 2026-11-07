import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from guardstudy.io import canonical, digest, read_json, write_new, safe_relative, StudyError, PublicationError

class IOTests(unittest.TestCase):
    def setUp(self): self.root=Path(tempfile.mkdtemp(prefix='guardstudy-test-'))
    def test_reject_ambiguous_json(self):
        for raw in [b'{"a":1,"a":2}',b'{"x":NaN}',b'{"x":Infinity}',b'{"x":"\\ud800"}',b'['*17+b'0'+b']'*17]:
            p=self.root/str(len(list(self.root.iterdir())));p.write_bytes(raw)
            with self.assertRaises(StudyError): read_json(p)
    def test_bounded_regular_reads(self):
        p=self.root/'input';p.write_bytes(b'{} ')
        with self.assertRaises(StudyError): read_json(p,limit=2)
        link=self.root/'link';link.symlink_to(p)
        with self.assertRaises(StudyError): read_json(link)
        fifo=self.root/'fifo';os.mkfifo(fifo)
        with self.assertRaises(StudyError): read_json(fifo)
    def test_relative(self):
        for value in ['../x','/x','a/../b','a//b','a\\b','a/./b','']:
            with self.assertRaises(StudyError): safe_relative(value)
        self.assertEqual(safe_relative('predictions/base.json'),'predictions/base.json')
    def test_create_only_and_hardlink(self):
        p=self.root/'file';write_new(p,b'{}')
        with self.assertRaises(PublicationError): write_new(p,b'bad')
        self.assertEqual(p.read_bytes(),b'{}');self.assertEqual(read_json(p),{})
        self.assertGreaterEqual(p.stat().st_nlink,2)
    def test_partial_write_before_publish(self):
        p=self.root/'file';original=os.write;calls=[]
        def fail(fd,data):
            if calls: raise OSError('private sentinel')
            calls.append(1);return original(fd,data[:1])
        with patch('guardstudy.io.os.write',side_effect=fail):
            with self.assertRaises(PublicationError) as e: write_new(p,b'long enough')
        self.assertFalse(p.exists());self.assertNotIn('sentinel',str(e.exception))
    def test_fsync_failure_after_link_keeps_file(self):
        p=self.root/'file';original=os.fsync;calls=[]
        def fail(fd):
            calls.append(1)
            if len(calls)==2: raise OSError()
            return original(fd)
        with patch('guardstudy.io.os.fsync',side_effect=fail):
            with self.assertRaises(PublicationError): write_new(p,b'{}')
        self.assertEqual(p.read_bytes(),b'{}')
    def test_canonical_domain(self):
        self.assertEqual(canonical({'z':1,'a':'é'}),b'{"a":"\\u00e9","z":1}')
        self.assertNotEqual(digest('a',{}),digest('b',{}))
