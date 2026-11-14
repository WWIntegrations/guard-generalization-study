"""Short human-readable text for verify, report and exposure. Add --json for machine output."""
import unicodedata

def clean(value):
    """Escape control and format characters (ESC, CR, LF, bidi) before terminal output."""
    out=[]
    for ch in str(value):
        if unicodedata.category(ch).startswith('C'):
            code=ord(ch)
            out.append('\\x%02x'%code if code<256 else '\\u%04x'%code if code<65536 else '\\U%08x'%code)
        else: out.append(ch)
    return ''.join(out)

def _pct(x): return 'undefined' if x is None else '%.2f%%'%(100*x)

def verify_text(result):
    return '\n'.join(['integrity: %s'%clean(result['integrity']),'study status: %s'%clean(result['status']),
        'files verified: %s'%clean(result['files']),'protocol digest: %s'%clean(result['protocol_digest'])[:16],
        'producer durability: %s (integrity only, not who ran it or when)'%clean(result['producer_durability']),
        'Machine-readable output: add --json'])

def report_text(report, saved=None):
    lines=['Study status: %s. Backend: %s. Unique prompts: %s.'%(clean(report['status']),clean(report['backend_kind']),clean(report['counts']['unique_clusters']))]
    lines.append('Benign false-positive rate (lower is better; every prompt in this corpus is benign):')
    for name,cohort in report['cohorts'].items():
        lines.append('')
        lines.append('%s:'%clean(name))
        for variant,r in cohort['variants'].items():
            # A cohort with no successful predictions (for example an empty primary cohort) has no interval.
            interval='undefined' if r['wilson95'] is None else '%s to %s'%tuple(map(_pct,r['wilson95']))
            lines.append('  %-22s %3s / %-3s flagged  FPR %s  (Wilson 95%% %s)  missing %s'%(
                clean(variant),clean(r['fp']),clean(r['ok']),_pct(r['fpr_observed']),interval,clean(r['invalid']+r['not_attempted'])))
        p=cohort['paired']
        if p['delta_fpr_v2_minus_base'] is None: lines.append('  paired difference (v2 minus base): undefined over %s pairs'%clean(p['pairs']))
        else: lines.append('  paired difference (v2 minus base): %+.2f points, exact McNemar p = %.5f over %s pairs'%(
            100*p['delta_fpr_v2_minus_base'],p['mcnemar_exact_p'],clean(p['pairs'])))
    lines.append('')
    lines.append('Limits:')
    lines.extend('  - %s'%clean(x) for x in report['limits'])
    if saved is not None: lines.append('markdown report saved: %s'%clean(saved))
    lines.append('Markdown file: add --out FILE (new file only). Machine-readable output: add --json')
    return '\n'.join(lines)

def exposure_text(receipt, out_dir):
    reasons={}
    for row in receipt['records']: reasons[row['reason']]=reasons.get(row['reason'],0)+1
    lines=['exposure audit: coverage %s'%clean(receipt['coverage']),
           'public prompts checked: %d'%len(receipt['records'])]
    lines.extend('  %-20s %d'%(clean(k),v) for k,v in sorted(reasons.items()))
    lines.append('private sources read: %d, unreadable or empty: %d'%(len(receipt['sources']),len(receipt['missing_source_ids'])))
    lines.append('receipt saved: %s'%clean(out_dir/'exposure-receipt.json'))
    lines.append('The receipt holds hashes and counts only, never private text, paths or row ids.')
    lines.append('Machine-readable output: add --json')
    return '\n'.join(lines)
