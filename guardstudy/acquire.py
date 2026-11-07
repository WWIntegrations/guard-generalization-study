"""Immutable NotInject acquisition. No dataset scripts, credentials or arbitrary URLs."""
import http.client
import ipaddress
import multiprocessing
import socket
import ssl
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from .io import StudyError, canonical, digest, loads, read_bytes, sha256, write_json, write_new, new_directory

REVISION='847ae76cf8fea5ed325429e569ae8cfef022d2e0'
GROUPS=('one','two','three')
PINS=(('one',10859,'5b1d3a8ec341205305efd8c6d2cabeb5ba0f594dd8726b08ee7fde1a46ddc6ec'),('two',11183,'a5a8c1b3b851b0b5acc3b6caf8bfee26d7da631b2967dd31ca90358df8883feb'),('three',13009,'d5c685b123570c092a0f374ba6bdf324b2026d905a2751a243eb2bb360d411a8'))
CARD=dict(filename='README.md',size=2973,sha256='ffaf685021522a526f94af2047e5099ec6b7439a462c67e0ecaca0d631a0d43f')

def source_lock():
    files=[dict(partition=g,filename=f'NotInject_{g}-00000-of-00001.parquet',size=n,sha256=h) for g,n,h in PINS]
    return dict(format='guardstudy.source.v1',repository='leolee99/NotInject',revision=REVISION,files=files,card=CARD.copy(),license='MIT')

def validate_url(url):
    try:
        p=urlsplit(url)
        if (p.scheme!='https' or not p.hostname or p.username is not None or p.password is not None
            or p.port not in (None,443) or p.fragment or any(ord(c)<33 or ord(c)>126 for c in url)):
            raise ValueError()
        p.hostname.encode('ascii')
    except (ValueError,UnicodeError): raise StudyError('unsafe_url') from None
    return p

def public_endpoint(host):
    answers=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM);valid=[]
    for family,kind,proto,_,address in answers:
        ip=ipaddress.ip_address(address[0])
        if (family not in (socket.AF_INET,socket.AF_INET6) or not ip.is_global or ip.is_multicast
            or '%' in address[0] or getattr(ip,'ipv4_mapped',None) or getattr(ip,'sixtofour',None)
            or getattr(ip,'teredo',None) or (len(address)>3 and address[3])): raise StudyError('private_dns')
        # Transition/reserved ranges differ between Python versions.
        for net in ('64:ff9b::/96','64:ff9b:1::/48','2001::/23','3fff::/20','5f00::/16','192.0.0.0/24','192.88.99.0/24'):
            network=ipaddress.ip_network(net)
            if ip.version==network.version and ip in network: raise StudyError('private_dns')
        valid.append((family,address))
    if not valid: raise StudyError('dns')
    return valid[0]

class PinnedConnection(http.client.HTTPSConnection):
    """DNS is resolved once; socket peer and TLS hostname are independently checked."""
    def __init__(self,host,endpoint,timeout):
        super().__init__(host,timeout=timeout,context=ssl.create_default_context());self.endpoint=endpoint
    def connect(self):
        family,address=self.endpoint;raw=socket.socket(family,socket.SOCK_STREAM)
        try:
            raw.settimeout(self.timeout);raw.connect(address)
            if ipaddress.ip_address(raw.getpeername()[0])!=ipaddress.ip_address(address[0]): raise StudyError('peer_mismatch')
            self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException: raw.close();raise

def _https(url,limit):
    deadline=time.monotonic()+10
    for redirect in range(4):
        p=validate_url(url);endpoint=public_endpoint(p.hostname)
        connection=PinnedConnection(p.hostname,endpoint,max(.001,deadline-time.monotonic()))
        try:
            path=p.path or '/'
            if p.query: path+='?'+p.query
            connection.request('GET',path,headers={'Accept-Encoding':'identity','User-Agent':'guardstudy/1','Connection':'close'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):
                locations=response.headers.get_all('location',[])
                if redirect==3 or len(locations)!=1: raise StudyError('redirect_limit')
                url=urljoin(url,locations[0]);continue
            if response.status!=200: raise StudyError('http_status')
            if response.headers.get('Content-Encoding','identity').lower()!='identity': raise StudyError('content_encoding')
            lengths=response.headers.get_all('Content-Length',[])
            if len(lengths)>1 or lengths and (not lengths[0].isdigit() or len(lengths[0])>6 or int(lengths[0])>limit): raise StudyError('size_limit')
            if lengths and response.headers.get('Transfer-Encoding'): raise StudyError('framing')
            raw=response.read(limit+1)
            if len(raw)>limit: raise StudyError('size_limit')
            if lengths and len(raw)!=int(lengths[0]): raise StudyError('truncated')
            return dict(body_hex=raw.hex(),origin_path=f'https://{p.hostname}{p.path}')
        finally: connection.close()
    raise StudyError('redirect_limit')

def _child(pipe,operation,args):
    try:
        result=_https(*args) if operation=='https' else _decode_parquet(*args)
        pipe.send_bytes(canonical(dict(ok=True,result=result)))
    except BaseException as exc:
        pipe.send_bytes(canonical(dict(ok=False,code=exc.code if isinstance(exc,StudyError) else 'source_unavailable')))
    finally: pipe.close()

def bounded_child(operation,args,timeout,limit):
    ctx=multiprocessing.get_context('spawn');reader,writer=ctx.Pipe(duplex=False)
    proc=ctx.Process(target=_child,args=(writer,operation,args));proc.start();writer.close()
    try:
        if not reader.poll(timeout): raise StudyError('source_timeout')
        try: message=loads(reader.recv_bytes(limit))
        except (OSError,EOFError): raise StudyError('source_message') from None
        if not message['ok']: raise StudyError(message['code'])
        return message['result']
    finally:
        reader.close()
        if proc.is_alive(): proc.terminate()
        proc.join(timeout=2)
        if proc.is_alive(): proc.kill();proc.join(timeout=2)

def fetch_notinject(out):
    out=Path(out);new_directory(out);(out/'raw').mkdir(mode=0o700)
    lock=source_lock();receipts=[]
    for f in [*lock['files'],lock['card']]:
        remote=('data/' if 'partition' in f else '')+f['filename']
        url=f'https://huggingface.co/datasets/leolee99/NotInject/resolve/{REVISION}/{remote}'
        response=bounded_child('https',(url,16384),10,40000);raw=bytes.fromhex(response['body_hex'])
        if len(raw)!=f['size'] or sha256(raw)!=f['sha256']: raise StudyError('source_hash')
        write_new((out/'raw' if 'partition' in f else out)/f['filename'],raw,staging=out.parent)
        receipts.append(dict(filename=f['filename'],size=len(raw),sha256=sha256(raw),origin_path=response['origin_path']))
    write_json(out/'source-lock.json',lock);write_json(out/'acquisition.json',dict(format='guardstudy.acquisition.v1',files=receipts))
    return dict(files=4,raw_bytes=35051,card_bytes=2973)

def verify_raw(raw_dir):
    root=Path(raw_dir);files=source_lock()['files']
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()}!={f['filename'] for f in files}: raise StudyError('source_file_set')
    for f in files:
        raw=read_bytes(root/f['filename'],16384)
        if len(raw)!=f['size'] or sha256(raw)!=f['sha256']: raise StudyError('source_hash')
    return files

def _decode_parquet(raw_dir):
    # Verify again in the parser process before any third-party parser sees bytes.
    files=verify_raw(raw_dir)
    import pyarrow as pa
    import pyarrow.parquet as pq
    if pa.__version__!='26.0.0': raise StudyError('parser_version')
    groups={}
    for f in files:
        raw=read_bytes(Path(raw_dir)/f['filename'],16384)
        if sha256(raw)!=f['sha256']: raise StudyError('source_hash')
        tablefile=pq.ParquetFile(pa.BufferReader(raw));schema=tablefile.schema_arrow
        if schema.names!=['prompt','word_list','category'] or tablefile.metadata.num_rows!=113: raise StudyError('parquet_schema')
        string=lambda t:pa.types.is_string(t) or pa.types.is_large_string(t)
        words=schema.field('word_list').type
        if not string(schema.field('prompt').type) or not string(schema.field('category').type) or not (pa.types.is_list(words) or pa.types.is_large_list(words)) or not string(words.value_type): raise StudyError('parquet_schema')
        table=tablefile.read()
        if any(c.null_count for c in table.columns): raise StudyError('parquet_null')
        groups[f['partition']]=table.to_pylist()
    return groups

def import_notinject(raw_dir):
    verify_raw(raw_dir)
    return normalize_records(bounded_child('parquet',(str(raw_dir),),30,2*1024**2))

def normalize_records(groups):
    if type(groups) is not dict or set(groups)!=set(GROUPS): raise StudyError('partitions')
    records=[];clusters={};decoded=0
    for group,size,rawhash in PINS:
        rows=groups[group]
        if type(rows) is not list or len(rows)!=113: raise StudyError('row_count')
        for i,row in enumerate(rows):
            if type(row) is not dict or set(row)!={'prompt','word_list','category'}: raise StudyError('row_fields')
            text=row['prompt'];category=row['category'];words=row['word_list']
            if type(words) is not list or len(words)!=GROUPS.index(group)+1: raise StudyError('word_count')
            for value,limit in [(text,16384),(category,128),*((w,1024) for w in words)]:
                if type(value) is not str or not value.strip(): raise StudyError('source_string')
                try: length=len(value.encode('utf-8'))
                except UnicodeError: raise StudyError('unicode') from None
                if length>limit: raise StudyError('source_string_limit')
                decoded+=length
            if decoded>1024**2: raise StudyError('decoded_limit')
            h=sha256(text.encode());rid=f'notinject:{REVISION}:{group}:{i:03d}'
            records.append(dict(id=rid,partition=group,source_path=f'data/NotInject_{group}-00000-of-00001.parquet',source_row=i,source_raw_sha256=rawhash,text=text,text_sha256=h,category=category,word_list=words,label='CLEAN',label_basis='author_dataset_card'))
            cluster=clusters.setdefault(h,dict(text_sha256=h,representative_id=rid,member_ids=[],partitions=[],categories=[]))
            cluster['member_ids'].append(rid)
            if group not in cluster['partitions']: cluster['partitions'].append(group)
            if category not in cluster['categories']: cluster['categories'].append(category)
    core=dict(format='guardstudy.dataset.v1',source_revision=REVISION,records=records,clusters=list(clusters.values()))
    return dict(**core,dataset_digest=digest('guardstudy.dataset.v1',core))
