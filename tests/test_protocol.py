import copy
import unittest
from guardstudy.protocol import freeze, verify_protocol, classifier_messages, LABELS, PUBLIC_ADAPTER_CONFIG, score, implementation_manifest
from guardstudy.io import StudyError, digest
from guardstudy.acquire import normalize_records
from guardstudy.exposure import audit_exposure
from tests.test_acquire import groups

def protocol_fixture():
    d=normalize_records(groups());e=audit_exposure(d,dict(sources=[],declared_complete=False))
    lock=dict(format='guardstudy.model-lock.v1',base_repository='mlx-community/Qwen3-1.7B-4bit',base_revision='3b1b1768f8f8cf8351c712464f906e86c2b8269e',base_files=copy.deepcopy(__import__('guardstudy.base_origin',fromlist=['PINNED_BASE']).PINNED_BASE),adapter_sha256='04d37a57a02a1a16310435218d833fe614480989fc7b6279b856d62cd7e7d4f5',adapter_size=19947012,adapter_config=PUBLIC_ADAPTER_CONFIG,adapter_config_digest=digest('guardstudy.adapter-config.v1',PUBLIC_ADAPTER_CONFIG),label_tokens={'ATTACK':[1,2],'CLEAN':[3]},runtime_pins={'mlx':'0.32.4','mlx-lm':'0.32.2','numpy':'2.5.4','transformers':'5.20.2'})
    return d,e,freeze(d,e,lock)
class ProtocolTests(unittest.TestCase):
    def test_freeze_detects_changes(self):
        d,e,p=protocol_fixture();verify_protocol(p,d)
        for key,value in [('threshold',.4),('max_input_tokens',True),('unknown',1)]:
            q=copy.deepcopy(p);q[key]=value
            with self.assertRaises(StudyError): verify_protocol(q,d)
    def test_messages_do_not_add_metadata(self):
        prompt='public <text> content';m=classifier_messages(prompt)
        self.assertEqual(m[1],{'role':'user','content':'<text>\n'+prompt+'\n</text>'})
        self.assertEqual(len(m),2)
    def test_stable_score_and_tie(self):
        self.assertEqual(score(0,0)['decision'],'ATTACK')
        self.assertEqual(score(-1000,1000)['probability'],0)
        with self.assertRaises(StudyError): score(float('nan'),0)
    def test_invalid_label_tokens(self):
        d,e,p=protocol_fixture();lock=p['model_lock'];lock['label_tokens']['CLEAN']=[1]
        with self.assertRaises(StudyError): freeze(d,e,lock)

    def test_base_origin_is_not_an_arbitrary_frozen_directory(self):
        d,e,p=protocol_fixture();lock=copy.deepcopy(p['model_lock']);lock['base_files'][0]['sha256']='f'*64
        with self.assertRaises(StudyError): freeze(d,e,lock)

    def test_constant_types_not_python_coercion(self):
        from guardstudy.schemas import validate
        d,e,p=protocol_fixture();p['chat_options']['add_generation_prompt']=1
        p['protocol_digest']=digest('guardstudy.protocol.v1',{k:v for k,v in p.items() if k!='protocol_digest'})
        with self.assertRaises(StudyError): validate('protocol',p)

    def test_huge_integer_logits_fail_with_bounded_error(self):
        for a,c in [(10**400,0),(10**400,-10**400),(10**308,-10**308)]:
            with self.assertRaises(StudyError): score(a,c)
