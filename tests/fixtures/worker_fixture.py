"""Synthetic worker for process failure tests. Never a recorded ML experiment."""
import json,os,sys,time
mode=sys.argv[1];count=0
for line in sys.stdin:
    m=json.loads(line)
    if m['command']=='load':
        if mode=='load_timeout': time.sleep(3)
        print(json.dumps({'kind':'loaded','load_ns':1,'label_tokens':{'ATTACK':[1,2],'CLEAN':[3]},'memory':{'active':None,'cache':None,'peak':None,'rss':None}}),flush=True)
    elif m['command']=='score':
        count+=1
        if count>2 and mode=='crash': os._exit(4)
        if count>2 and mode=='timeout': time.sleep(3)
        result={'kind':'score','id':m['id'],'logit_attack':-1.,'logit_clean':1.,'input_tokens':12,'tokenize_ns':1,'forward_ns':2,'memory':{'active':None,'cache':None,'peak':None,'rss':None}}
        if count>2 and mode=='bad_id': result['id']='wrong'
        if count>2 and mode=='nan': result['logit_attack']=float('nan')
        print(json.dumps(result),flush=True)
        if count>2 and mode=='exit_after_result': os._exit(0)
    else: break
