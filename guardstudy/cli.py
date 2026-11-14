"""Explicit phase commands. Only run can execute model forwards."""
import argparse
import sys
from pathlib import Path
from .io import StudyError, PublicationError, canonical, read_json, write_json, write_new, new_directory

def main(argv=None):
    parser=argparse.ArgumentParser(prog='guardstudy',description='Frozen benign-only Guard evaluation and offline verification.')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('fetch','import','exposure','model-lock','freeze','run','evaluate','verify','report','seal'):
        p=sub.add_parser(name)
        p.add_argument('--json',action='store_true',help='print machine-readable JSON')
        if name in ('fetch','import','exposure','model-lock','freeze','run','evaluate','seal'): p.add_argument('--out-dir',type=Path,help='new directory (default: next free %s-out)'%name)
        if name=='import': p.add_argument('--raw-dir',required=True,type=Path)
        if name in ('exposure','freeze','run','evaluate','seal'): p.add_argument('--dataset',required=True,type=Path)
        if name=='exposure': p.add_argument('--private-inventory',required=True,type=Path)
        if name in ('freeze','evaluate','seal'): p.add_argument('--exposure',required=True,type=Path)
        if name=='freeze': p.add_argument('--model-lock',required=True,type=Path)
        if name in ('run','evaluate','seal'): p.add_argument('--protocol',required=True,type=Path)
        if name in ('run','model-lock'):
            p.add_argument('--base-dir',required=True,type=Path);p.add_argument('--adapter-dir',required=True,type=Path)
        if name in ('evaluate','seal'): p.add_argument('--predictions-dir',required=True,type=Path)
        if name=='seal': p.add_argument('--history',type=Path)
        if name in ('verify','report'): p.add_argument('--recorded-dir',required=True,type=Path)
        if name=='report': p.add_argument('--out',type=Path,help='also write a Markdown report to this new file')
    args=parser.parse_args(argv)
    try:
        if getattr(args,'out_dir',None) is None and hasattr(args,'out_dir'): args.out_dir=free_dir(args.command+'-out')
        result=_execute(args)
        print(_render(args,result))
        return 4 if result.get('status') in ('incomplete','inconclusive') and args.command not in ('verify','report') else 0
    except PublicationError as exc:
        print(canonical(dict(error=exc.code,observed_output=exc.observed_output,durability=exc.durability)).decode(),file=sys.stderr);return 3
    except StudyError as exc:
        print(canonical(dict(error=exc.code)).decode(),file=sys.stderr);return 2
    except (OSError,ValueError,KeyError,TypeError):
        print('{"error":"operation_failed"}',file=sys.stderr);return 3

def free_dir(stem):
    for n in range(1,10000):
        path=Path(stem if n==1 else '%s-%d'%(stem,n))
        if not path.exists() and not path.is_symlink(): return path
    raise PublicationError('output_exists')

def _render(args,result):
    public={k:v for k,v in result.items() if not k.startswith('_')}
    if args.json: return canonical(result['_report'] if args.command=='report' else public).decode()
    from . import summary
    if args.command=='verify': return summary.verify_text(result)
    if args.command=='report': return summary.report_text(result['_report'],args.out)
    if args.command=='exposure': return summary.exposure_text(result['_receipt'],args.out_dir)
    return canonical(public).decode()

def _execute(args):
    from .acquire import fetch_notinject,import_notinject
    from .exposure import audit_exposure
    from .protocol import freeze,model_lock,VARIANTS
    from .recorded import build_report,verify_recorded,load_verified_bundle,seal_recorded
    command=args.command
    if command=='fetch': return fetch_notinject(args.out_dir)
    if command=='verify': return verify_recorded(args.recorded_dir)
    if command=='report':
        from .render_report import render_report
        bundle=load_verified_bundle(args.recorded_dir)
        if args.out is not None: write_new(args.out,render_report(bundle['report']).encode())
        return dict(status=bundle['report']['status'],_report=bundle['report'])
    if command=='import':
        dataset=import_notinject(args.raw_dir);new_directory(args.out_dir);write_json(args.out_dir/'dataset.json',dataset)
        return dict(raw_rows=len(dataset['records']),unique_clusters=len(dataset['clusters']),dataset_digest=dataset['dataset_digest'])
    if command=='model-lock':
        lock=model_lock(args.base_dir,args.adapter_dir);new_directory(args.out_dir);write_json(args.out_dir/'model-lock.json',lock);return dict(status='model_locked')
    dataset=read_json(args.dataset,'dataset')
    if command=='exposure':
        inventory=read_json(args.private_inventory,limit=256*1024);receipt=audit_exposure(dataset,inventory)
        new_directory(args.out_dir);write_json(args.out_dir/'exposure-receipt.json',receipt)
        return dict(coverage=receipt['coverage'],exposure_digest=receipt['exposure_digest'],_receipt=receipt)
    if command=='freeze':
        protocol=freeze(dataset,read_json(args.exposure,'exposure'),read_json(args.model_lock,'model-lock'))
        new_directory(args.out_dir);write_json(args.out_dir/'protocol.json',protocol)
        return dict(status='frozen',protocol_digest=protocol['protocol_digest'])
    protocol=read_json(args.protocol,'protocol')
    if command=='run':
        from .runner import run_study
        outcome=run_study(protocol,dataset,dict(base_dir=str(args.base_dir),adapter_dir=str(args.adapter_dir)),args.out_dir)
        missing=sum(r['status']!='ok' for r in outcome['predictions'])
        return dict(status='incomplete' if missing else 'completed',predictions=len(outcome['predictions']),missing=missing)
    exposure=read_json(args.exposure,'exposure');predictions=[]
    for variant in VARIANTS:
        document=read_json(args.predictions_dir/(variant+'.json'),'predictions')
        if document['variant']!=variant or document['backend_kind']!='real_mlx': raise StudyError('prediction_origin')
        predictions.extend(document['records'])
    runtime=read_json(args.predictions_dir/'runtime.json')
    from .runtime import validate_runtime
    validate_runtime(runtime)
    outcome=dict(protocol_digest=protocol['protocol_digest'],backend_kind='real_mlx',predictions=predictions,runtime=runtime['variants'],runtime_metadata=runtime['metadata'])
    if command=='evaluate':
        report=build_report(protocol,dataset,exposure,outcome);new_directory(args.out_dir);write_json(args.out_dir/'report.json',report)
        return dict(status=report['status'])
    artifacts=dict(dataset=dataset,exposure=exposure,protocol=protocol)
    if args.history: artifacts['history']=read_json(args.history,limit=256*1024)
    receipt=seal_recorded(outcome,artifacts,args.out_dir)
    return dict(status=receipt['manifest']['computed_status'],observed_output=receipt['observed_output'],durability=receipt['durability'])

if __name__=='__main__': raise SystemExit(main())
