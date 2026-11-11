"""Sequential, bounded subprocess supervision. Coordinator never imports MLX."""
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path
from .io import StudyError, canonical, loads, write_json, new_directory
from .protocol import VARIANTS, score, verify_protocol, verify_runtime_binding
from .schemas import fields, integer

class Worker:
    def __init__(self,command):
        self.proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True,env={'PATH':os.defpath,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1','MLX_MAX_OPS_PER_BUFFER':'10','MLX_MAX_MB_PER_BUFFER':'10'},cwd=Path(__file__).parent.parent)
        self.buffer=b'';self.selector=selectors.DefaultSelector();self.selector.register(self.proc.stdout,selectors.EVENT_READ)
    def request(self,message,seconds):
        start=time.monotonic();deadline=start+seconds
        try:
            raw=canonical(message)+b'\n'
            if len(raw)>2*1024**2: raise StudyError('worker_message_limit')
            # Worker load command can exceed pipe capacity, so use nonblocking IO for both ends.
            fd=self.proc.stdin.fileno();os.set_blocking(fd,False);offset=0
            while offset<len(raw):
                if time.monotonic()>=deadline: raise StudyError('worker_timeout')
                try: offset+=os.write(fd,raw[offset:])
                except BlockingIOError: time.sleep(.002)
            while b'\n' not in self.buffer:
                left=deadline-time.monotonic()
                if left<=0 or not self.selector.select(left): raise StudyError('worker_timeout')
                data=os.read(self.proc.stdout.fileno(),65536)
                if not data: raise StudyError('worker_exit')
                self.buffer+=data
                if len(self.buffer)>65536: raise StudyError('worker_message_limit')
            line,self.buffer=self.buffer.split(b'\n',1)
            result=loads(line)
            if type(result) is not dict: raise StudyError('worker_message')
            if result.get('kind')=='error':
                fields(result,'kind code')
                if result['code'] not in ('input_token_limit','backend_unavailable','runtime_binding','label_binding','nonfinite_logits','worker_failure'): raise StudyError('worker_message')
                raise StudyError(result['code'])
            return result
        except (OSError,ValueError) as exc:
            if isinstance(exc,StudyError): raise
            raise StudyError('worker_exit') from None
    def close(self):
        self.selector.close()
        if self.proc.poll() is None:
            # The worker can exit between poll() and killpg(). Its own group then holds
            # only a zombie: Linux reports ESRCH or succeeds, macOS reports EPERM.
            try: os.killpg(self.proc.pid,signal.SIGTERM)
            except (ProcessLookupError,PermissionError): pass
            try: self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try: os.killpg(self.proc.pid,signal.SIGKILL)
                except (ProcessLookupError,PermissionError): pass
                self.proc.wait(timeout=2)
        self.proc.stdin.close();self.proc.stdout.close()

def empty_prediction(protocol,variant,cluster,status,reason):
    result=dict(protocol_digest=protocol['protocol_digest'],variant=variant,representative_id=cluster['representative_id'],text_sha256=cluster['text_sha256'],status=status,reason=reason)
    result.update({k:None for k in ('logit_attack','logit_clean','delta','probability','decision','input_tokens','tokenize_ns','forward_ns','total_request_ns')})
    return result

def _memory(obj):
    fields(obj,'active cache peak rss')
    for v in obj.values():
        if v is not None: integer(v)
    return obj

def supervise(protocol,dataset,command,locations,backend_kind='fixture',test_deadlines=None):
    verify_protocol(protocol,dataset)
    if backend_kind not in ('fixture','real_mlx') or test_deadlines and backend_kind!='fixture': raise StudyError('backend_policy')
    load_limit,row_limit,run_limit=test_deadlines or (180,30,3600)
    deadline=time.monotonic()+run_limit;predictions=[];runtime=[];records={r['id']:r for r in dataset['records']}
    for variant in VARIANTS:
        worker=None;failed=True;failure='not_attempted_after_worker_failure';meta=dict(variant=variant,load_ns=None,warmup_ns=[],memory=[],failure=None)
        try:
            if time.monotonic()>=deadline: raise StudyError('run_timeout')
            worker=Worker(command)
            loaded=worker.request(dict(command='load',protocol=protocol,variant=variant,locations=locations),min(load_limit,deadline-time.monotonic()))
            fields(loaded,'kind load_ns label_tokens memory')
            if loaded['kind']!='loaded' or loaded['label_tokens']!=protocol['model_lock']['label_tokens']: raise StudyError('label_binding')
            integer(loaded['load_ns']);meta['load_ns']=loaded['load_ns'];meta['memory'].append(_memory(loaded['memory']))
            for i,text in enumerate(protocol['warmup']):
                start=time.monotonic_ns();answer=worker.request(dict(command='score',id=f'warmup-{i}',text=text),min(row_limit,deadline-time.monotonic()))
                _score_message(answer,f'warmup-{i}');meta['warmup_ns'].append(time.monotonic_ns()-start)
            failed=False
        except StudyError as exc: meta['failure']=exc.code
        except OSError: meta['failure']='worker_launch'
        try:
            for cluster in dataset['clusters']:
                row=empty_prediction(protocol,variant,cluster,'not_attempted',failure)
                if not failed:
                    start=time.monotonic_ns()
                    try:
                        if time.monotonic()>=deadline: raise StudyError('run_timeout')
                        answer=worker.request(dict(command='score',id=cluster['representative_id'],text=records[cluster['representative_id']]['text']),min(row_limit,deadline-time.monotonic()))
                        values=_score_message(answer,cluster['representative_id'])
                        row.update(values,status='ok',reason=None,total_request_ns=time.monotonic_ns()-start)
                        meta['memory'].append(_memory(answer['memory']))
                    except StudyError as exc:
                        row.update(status='invalid',reason=exc.code if exc.code in REASONS else 'worker_message',total_request_ns=time.monotonic_ns()-start)
                        # Input length is a deterministic per-row outcome; other failures stop this variant.
                        if exc.code!='input_token_limit': failed=True;meta['failure']=exc.code
                predictions.append(row)
        finally:
            if worker: worker.close()
        runtime.append(meta)
    from .runtime import metadata
    return dict(runtime_metadata=metadata(),format='guardstudy.outcome.v1',protocol_digest=protocol['protocol_digest'],backend_kind=backend_kind,predictions=predictions,runtime=runtime)

REASONS={'input_token_limit','backend_unavailable','runtime_binding','label_binding','nonfinite_logits','worker_failure','worker_timeout','worker_exit','worker_message','worker_message_limit','run_timeout','not_attempted_after_worker_failure'}

def _score_message(answer,expected):
    fields(answer,'kind id logit_attack logit_clean input_tokens tokenize_ns forward_ns memory')
    if answer['kind']!='score' or answer['id']!=expected: raise StudyError('worker_message')
    integer(answer['input_tokens'],1,4096);integer(answer['tokenize_ns']);integer(answer['forward_ns']);_memory(answer['memory'])
    return dict(**score(answer['logit_attack'],answer['logit_clean']),input_tokens=answer['input_tokens'],tokenize_ns=answer['tokenize_ns'],forward_ns=answer['forward_ns'])

def run_study(protocol,dataset,locations,out):
    verify_protocol(protocol,dataset);verify_runtime_binding(protocol,locations['base_dir'],locations['adapter_dir'])
    out=Path(out);new_directory(out)
    # Immutable receipt precedes launch. Never reuse a prior run directory.
    write_json(out/'protocol.json',protocol)
    outcome=supervise(protocol,dataset,[sys.executable,'-B','-m','guardstudy.worker_mlx'],locations,backend_kind='real_mlx')
    for variant in VARIANTS:
        write_json(out/(variant+'.json'),dict(format='guardstudy.predictions.v1',protocol_digest=protocol['protocol_digest'],variant=variant,backend_kind='real_mlx',records=[r for r in outcome['predictions'] if r['variant']==variant]))
    from .runtime import BUFFER_LIMITS
    write_json(out/'runtime.json',dict(format='guardstudy.runtime.v1',metadata=outcome['runtime_metadata'],variants=outcome['runtime'],buffer_limits=BUFFER_LIMITS))
    return outcome
