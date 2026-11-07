"""Bounded, strict inputs and create-only publication on a local filesystem."""
import hashlib
import json
import math
import os
import stat
import tempfile
from pathlib import Path, PurePosixPath

class StudyError(ValueError):
    """An intentionally safe, bounded error code, never raw source text."""
    def __init__(self, code):
        self.code=code
        super().__init__(code)

class PublicationError(StudyError):
    def __init__(self, code='publication_io', observed_output='unknown'):
        self.observed_output=observed_output
        self.durability='uncertain'
        super().__init__(code)

def safe_relative(value):
    if (type(value) is not str or not value or '\\' in value or '\x00' in value
            or value.startswith('/') or any(x in ('','.','..') for x in value.split('/'))):
        raise StudyError('unsafe_path')
    return value

def check_tree(obj, depth=0):
    if depth>16: raise StudyError('json_depth')
    if isinstance(obj,str):
        try: obj.encode('utf-8')
        except UnicodeError: raise StudyError('unicode') from None
    elif isinstance(obj,float):
        if not math.isfinite(obj): raise StudyError('nonfinite')
    elif type(obj) is dict:
        for k,v in obj.items():
            if type(k) is not str: raise StudyError('json_key')
            check_tree(k,depth+1);check_tree(v,depth+1)
    elif type(obj) is list:
        for v in obj: check_tree(v,depth+1)
    elif obj is not None and type(obj) not in (bool,int): raise StudyError('json_type')

def canonical(obj):
    check_tree(obj)
    return json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()

def sha256(data): return hashlib.sha256(data).hexdigest()
def digest(domain,obj): return sha256(domain.encode('ascii')+b'\n'+canonical(obj))

def _pairs(items):
    result={}
    for k,v in items:
        if k in result: raise StudyError('duplicate_key')
        result[k]=v
    return result

def loads(raw):
    try:
        obj=json.loads(raw,object_pairs_hook=_pairs,parse_constant=lambda _: (_ for _ in ()).throw(StudyError('nonfinite')))
        check_tree(obj)
        return obj
    except (UnicodeError,json.JSONDecodeError,RecursionError): raise StudyError('json_invalid') from None

def read_bytes(path,limit):
    path=Path(path)
    # O_NONBLOCK prevents a raced FIFO open from waiting indefinitely.
    flags=os.O_RDONLY|os.O_NONBLOCK|getattr(os,'O_NOFOLLOW',0)
    try:
        fd=os.open(path,flags)
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode): raise StudyError('not_regular')
            if info.st_size>limit: raise StudyError('size_limit')
            parts=[];count=0
            with os.fdopen(fd,'rb',closefd=False) as stream:
                while True:
                    chunk=stream.read(min(65536,limit+1-count))
                    if not chunk: break
                    parts.append(chunk);count+=len(chunk)
                    if count>limit: raise StudyError('size_limit')
            raw=b''.join(parts)
            if len(raw)>limit: raise StudyError('size_limit')
            return raw
        finally: os.close(fd)
    except OSError: raise StudyError('read_failed') from None

def read_json(path,kind=None,limit=None):
    from .schemas import LIMITS, validate
    raw=read_bytes(path,limit if limit is not None else LIMITS.get(kind,2*1024*1024))
    obj=loads(raw)
    if kind: validate(kind,obj)
    return obj

def fsync_dir(path):
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_DIRECTORY',0)|getattr(os,'O_NOFOLLOW',0))
    try: os.fsync(fd)
    finally: os.close(fd)

def write_new(path,data,staging=None):
    """A failure AFTER link may leave a complete final file. No rollback."""
    path=Path(path)
    if type(data) is not bytes: raise StudyError('bytes_required')
    try:
        if not path.parent.is_dir() or path.parent.is_symlink(): raise StudyError('unsafe_parent')
        stage=Path(tempfile.mkdtemp(prefix='.guardstudy-stage-',dir=staging or path.parent.parent))
        fd=os.open(stage/'payload',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            offset=0
            while offset<len(data):
                n=os.write(fd,data[offset:])
                if n<=0: raise OSError()
                offset+=n
            os.fsync(fd)
        finally: os.close(fd)
        os.link(stage/'payload',path,follow_symlinks=False)
        fsync_dir(path.parent)
    except FileExistsError: raise PublicationError('output_exists') from None
    except OSError: raise PublicationError() from None

def write_json(path,obj,staging=None): write_new(path,canonical(obj)+b'\n',staging)

def new_directory(path):
    try:
        Path(path).mkdir(mode=0o700)
        fsync_dir(Path(path).parent)
    except FileExistsError: raise PublicationError('output_exists') from None
    except OSError: raise PublicationError() from None
