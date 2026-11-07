"""Plain Markdown from verified metrics, with no HTML execution."""
import json

def render_report(report):
    lines=['# Guard benign false-positive study','',f"Study status: {report['status']}.",'',f"Raw rows: {report['counts']['raw_rows']}. Unique texts: {report['counts']['unique_clusters']}.",'']
    for name,cohort in report['cohorts'].items():
        lines.extend([f'## {name}',''])
        for variant,result in cohort['variants'].items():
            rate='undefined' if result['fpr_observed'] is None else f"{result['fpr_observed']:.6f}"
            lines.append(f"- {variant}: FP {result['fp']}/{result['ok']}; expected {result['expected']}; observed FPR {rate}; missing {result['invalid']+result['not_attempted']}; status {result['status']}.")
            lines.append(f"  Wilson 95%: {json.dumps(result['wilson95'])}; unconditional bounds: {json.dumps(result['fpr_bounds'])}.")
        lines.extend(['',f"Paired: {json.dumps(cohort['paired'],sort_keys=True)}",''])
    lines.extend(['## Limits','']+[f'- {x}' for x in report['limits']]+[''])
    return '\n'.join(lines)
