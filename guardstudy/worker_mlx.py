"""Optional offline MLX forward worker. Importing this module does not import MLX."""
import json
import os
import resource
import sys
import tempfile
import time
from pathlib import Path
from .io import StudyError, canonical, loads
from .protocol import classifier_messages, verify_runtime_binding, PUBLIC_ADAPTER_CONFIG, score
from .schemas import fields

def _offline(event,args):
    if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo','socket.bind'): raise StudyError('network_forbidden')

def worker_main():
    sys.addaudithook(_offline);model=None;tokenizer=None;mx=None;labels=None
    def memory():
        values={}
        for name,method in [('active','get_active_memory'),('cache','get_cache_memory'),('peak','get_peak_memory')]:
            try: values[name]=int(getattr(mx,method)())
            except (AttributeError,RuntimeError): values[name]=None
        try: values['rss']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except (AttributeError,ValueError): values['rss']=None
        return values
    while True:
        raw=sys.stdin.buffer.readline(2*1024**2+1)
        if not raw: return 0
        if len(raw)>2*1024**2 or not raw.endswith(b'\n'): return 2
        try:
            message=loads(raw);command=message.get('command')
            if command=='load':
                fields(message,'command protocol variant locations')
                if model is not None: raise StudyError('worker_failure')
                protocol=message['protocol'];locations=message['locations'];fields(locations,'base_dir adapter_dir')
                verify_runtime_binding(protocol,locations['base_dir'],locations['adapter_dir'])
                import mlx.core as mx
                from mlx_lm import load
                start=time.monotonic_ns();adapter=None
                if message['variant']=='qwen3_1_7b_lora_v2':
                    stage=Path(tempfile.mkdtemp(prefix='guardstudy-adapter-'))
                    with (stage/'adapter_config.json').open('xb') as f: f.write(canonical(PUBLIC_ADAPTER_CONFIG))
                    os.link((Path(locations['adapter_dir'])/'adapters.safetensors').resolve(),stage/'adapters.safetensors')
                    adapter=str(stage)
                elif message['variant']!='qwen3_1_7b_base': raise StudyError('worker_failure')
                model,tokenizer=load(str(Path(locations['base_dir']).resolve()),adapter_path=adapter,lazy=False)
                labels={label:tokenizer.encode(label) for label in ('ATTACK','CLEAN')}
                if labels!=protocol['model_lock']['label_tokens']: raise StudyError('label_binding')
                result=dict(kind='loaded',load_ns=time.monotonic_ns()-start,label_tokens=labels,memory=memory())
            elif command=='score':
                fields(message,'command id text')
                if model is None or type(message['text']) is not str: raise StudyError('worker_failure')
                start=time.monotonic_ns()
                ids=tokenizer.apply_chat_template(classifier_messages(message['text']),add_generation_prompt=True,enable_thinking=False,return_dict=False)
                token_ns=time.monotonic_ns()-start
                if len(ids)>4096: raise StudyError('input_token_limit')
                if not ids: raise StudyError('worker_failure')
                start=time.monotonic_ns();logits=model(mx.array(ids)[None])[0,-1]
                attack=logits[labels['ATTACK'][0]].item();clean=logits[labels['CLEAN'][0]].item()
                forward_ns=time.monotonic_ns()-start;score(attack,clean)
                result=dict(kind='score',id=message['id'],logit_attack=attack,logit_clean=clean,input_tokens=len(ids),tokenize_ns=token_ns,forward_ns=forward_ns,memory=memory())
            elif command=='close': return 0
            else: raise StudyError('worker_failure')
        except BaseException as exc:
            code=exc.code if isinstance(exc,StudyError) and exc.code in {'input_token_limit','backend_unavailable','runtime_binding','label_binding','nonfinite_logits'} else 'worker_failure'
            result=dict(kind='error',code=code)
        sys.stdout.buffer.write(canonical(result)+b'\n');sys.stdout.buffer.flush()

if __name__=='__main__': raise SystemExit(worker_main())
