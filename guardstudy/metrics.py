"""Single-class, missingness-aware descriptive statistics; no threshold fitting."""
import math
import statistics
from .io import StudyError

def wilson(fp,n):
    if type(fp) is not int or type(n) is not int or not 0<=fp<=n: raise StudyError('counts')
    if not n: return None
    z=1.96;p=fp/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    width=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-width),min(1,center+width)]

def latency(values):
    if any(type(x) is not int or x<0 for x in values): raise StudyError('duration')
    values=sorted(values);n=len(values)
    return dict(n=n,mean=statistics.mean(values) if n else None,median=statistics.median(values) if n else None,
                p95=values[math.ceil(.95*n)-1] if n else None,min=values[0] if n else None,max=values[-1] if n else None)

def _index(records):
    d={}
    for r in records:
        k=r['representative_id']
        if k in d: raise StudyError('duplicate_prediction')
        d[k]=r
    return d

def summarize(records,cohort):
    ids=cohort['representative_ids'] if isinstance(cohort,dict) else cohort
    if len(ids)!=len(set(ids)): raise StudyError('duplicate_cohort')
    index=_index(records);selected=[index[x] for x in ids if x in index];n=len(ids)
    ok=[r for r in selected if r['status']=='ok'];invalid=sum(r['status']=='invalid' for r in selected)
    missing=n-len(ok);fp=sum(r['decision']=='ATTACK' for r in ok)
    result=dict(expected=n,attempted=len(ok)+invalid,ok=len(ok),invalid=invalid,not_attempted=missing-invalid,
        fp=fp,clean=len(ok)-fp,coverage=len(ok)/n if n else None,fpr_observed=fp/len(ok) if ok else None,
        wilson95=wilson(fp,len(ok)),fpr_bounds=[fp/n,(fp+missing)/n] if n else None,
        status='inconclusive' if not n else 'incomplete' if missing else 'completed',
        forward_ns=latency([r['forward_ns'] for r in ok]))
    for k in ['recall','precision','auroc','attack_success_rate','binary_f1']:
        result[k]=dict(value=None,reason='single_class_benign_corpus')
    return result

def paired(base,tuned,cohort):
    ids=cohort['representative_ids'] if isinstance(cohort,dict) else cohort
    a=_index(base);b=_index(tuned)
    counts=dict(only_base_fp=0,only_v2_fp=0,both_fp=0,both_clean=0)
    for key in ids:
        if key not in a or key not in b or a[key]['status']!='ok' or b[key]['status']!='ok': continue
        x=a[key]['decision']=='ATTACK';y=b[key]['decision']=='ATTACK'
        label='both_fp' if x and y else 'only_base_fp' if x else 'only_v2_fp' if y else 'both_clean'
        counts[label]+=1
    n=sum(counts.values());lo=min(counts['only_base_fp'],counts['only_v2_fp']);discord=counts['only_base_fp']+counts['only_v2_fp']
    p=min(1,2*sum(math.comb(discord,k) for k in range(lo+1))/(2**discord)) if discord else 1
    return dict(**counts,pairs=n,missing_pairs=len(ids)-n,delta_fpr_v2_minus_base=(counts['only_v2_fp']-counts['only_base_fp'])/n if n else None,mcnemar_exact_p=p if n else None)
