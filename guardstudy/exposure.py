"""Local comparison with a public receipt containing no private row identifiers."""
import re
from io import BytesIO
from collections import defaultdict, Counter
from pathlib import Path
import unicodedata
from .io import StudyError, read_bytes, loads, sha256, digest

def normalize_for_overlap(text): return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())
def shingles(text):
    words=re.findall(r'\w+',normalize_for_overlap(text))
    return frozenset(tuple(words[i:i+8]) for i in range(max(0,len(words)-7)))

def _texts(raw):
    for line in BytesIO(raw):
        if len(line)>1024**2: raise StudyError('private_row_limit')
        if not line.strip(): continue
        row=loads(line)
        if type(row) is not dict: raise StudyError('private_schema')
        if type(row.get('tekst')) is str: yield row['tekst'];continue
        messages=row.get('messages')
        if type(messages) is not list: raise StudyError('private_schema')
        user=[m.get('content') for m in messages if type(m) is dict and m.get('role')=='user']
        if not user or any(type(x) is not str for x in user): raise StudyError('private_schema')
        for text in user:
            if text.startswith('<text>\n') and text.endswith('\n</text>'): text=text[7:-8]
            yield text

def audit_exposure(dataset,inventory):
    if type(inventory) is not dict or set(inventory)!={'sources','declared_complete'} or type(inventory['declared_complete']) is not bool or type(inventory['sources']) is not list: raise StudyError('inventory_schema')
    public=dataset['records'];exact=defaultdict(list);normalized=defaultdict(list);inverted=defaultdict(set);sizes={};hits={}
    for i,row in enumerate(public):
        exact[sha256(row['text'].encode())].append(i)
        normalized[sha256(normalize_for_overlap(row['text']).encode())].append(i)
        grams=shingles(row['text']);sizes[i]=len(grams)
        for gram in grams: inverted[gram].add(i)
    sources=[];missing=[];ids=set()
    for source in inventory['sources']:
        if type(source) is not dict or set(source)!={'id','path','kind'} or not re.fullmatch(r'source-[0-9]{3,5}',source.get('id','')) or source['id'] in ids or source['kind'] not in ('prepared_rows','source_inserts','translations'): raise StudyError('inventory_schema')
        sid=source['id'];ids.add(sid)
        if type(source['path']) is not str or Path(source['path']).suffix!='.jsonl': raise StudyError('inventory_path')
        count=0
        try:
            raw=read_bytes(source['path'],64*1024**2)
            for text in _texts(raw):
                count+=1
                for i in exact.get(sha256(text.encode()),()): hits[i]=1
                for i in normalized.get(sha256(normalize_for_overlap(text).encode()),()): hits[i]=min(hits.get(i,2),2)
                grams=shingles(text)
                if grams:
                    shared=Counter(i for gram in grams for i in inverted.get(gram,()))
                    for i,intersection in shared.items():
                        if intersection/min(len(grams),sizes[i])>=.5: hits[i]=min(hits.get(i,3),3)
            if not count: raise StudyError('empty_source')
        except StudyError:
            missing.append(sid);continue
        sources.append(dict(id=sid,kind=source['kind'],sha256=sha256(raw),size=len(raw),records=count))
    coverage='complete_declared_inventory' if inventory['declared_complete'] and sources and not missing else 'partial'
    labels={1:'excluded_exact',2:'excluded_normalized',3:'excluded_ngram'}
    results=[dict(id=row['id'],reason=labels[hits[i]] if i in hits else 'unknown_short' if not sizes[i] else 'unknown_coverage' if coverage=='partial' else 'clear_under_audit') for i,row in enumerate(public)]
    core=dict(format='guardstudy.exposure.v1',dataset_digest=dataset['dataset_digest'],algorithm_version='exact-nfkc-word8-v1',normalization='NFKC_casefold_whitespace',tokenizer='unicode_regex_word',ngram_n=8,overlap_threshold=.5,sources=sources,coverage=coverage,missing_source_ids=missing,records=results,base_pretraining_exposure='unknown')
    return dict(**core,exposure_digest=digest('guardstudy.exposure.v1',core))

def cohorts(dataset,receipt):
    if receipt['dataset_digest']!=dataset['dataset_digest']: raise StudyError('exposure_binding')
    reasons={r['id']:r['reason'] for r in receipt['records']}
    if len(reasons)!=len(receipt['records']) or set(reasons)!={r['id'] for r in dataset['records']}: raise StudyError('exposure_membership')
    all_ids=[c['representative_id'] for c in dataset['clusters']]
    eligible=[c['representative_id'] for c in dataset['clusters'] if receipt['coverage']=='complete_declared_inventory' and all(reasons[x]=='clear_under_audit' for x in c['member_ids'])]
    return dict(raw_unique_descriptive=dict(representative_ids=all_ids,exposure='not_established'),audited_eligible_primary=dict(representative_ids=eligible,exposure='clear_under_declared_audit_only'))
