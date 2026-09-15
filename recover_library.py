import app_paths
"""Offline recovery utility for an installation that cannot open its web UI."""
import argparse
import json
from pathlib import Path
import library_recovery
import runtime_guard


def main():
    parser=argparse.ArgumentParser(description='Review and stage a TV Manager restore without starting the web server.')
    parser.add_argument('--base',type=Path,default=app_paths.application_root(),help='TV Manager installation folder')
    parser.add_argument('action',choices=['status','preview','stage','cancel'])
    parser.add_argument('--backup',help='Full path to a TV Manager database or backup ZIP')
    parser.add_argument('--config',help='Optional restorable configuration snapshot directory')
    parser.add_argument('--confirm',help='Use RESTORE to confirm staging the reviewed backup')
    args=parser.parse_args();base=args.base.resolve()
    if not (base/'app.py').is_file():parser.error('Choose the TV Manager installation folder.')
    try:
        if args.action=='status':result=library_recovery.status(base)
        else:
            runtime_guard.acquire(base)
            if args.action=='cancel':result=library_recovery.cancel(base)
            else:
                if not args.backup:parser.error('--backup is required')
                result=library_recovery.preview(base,args.backup,args.config)
                if args.action=='stage':
                    if args.confirm!='RESTORE':parser.error('Preview the backup, then use --confirm RESTORE to stage it.')
                    result=library_recovery.stage(base,result)
        print(json.dumps(result,indent=2,ensure_ascii=True))
    except (ValueError,OSError,RuntimeError) as exc:parser.exit(1,str(exc)+'\n')


if __name__=='__main__':main()
