"""Extract reviewed TV archives into an isolated, reusable staging folder."""
from pathlib import Path, PurePosixPath
from contextlib import closing
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import time
import zipfile
import media_operations

MEDIA={'.mkv','.mp4','.avi','.mov','.m4v','.ts','.wmv','.mpg','.mpeg'}
SIDECARS={'.srt','.ass','.ssa','.sub','.vtt','.nfo','.jpg','.jpeg','.png'}


def configure_rar(tool=''):
    import rarfile
    if tool:rarfile.UNRAR_TOOL=tool
    elif shutil.which('tar'):rarfile.BSDTAR_TOOL=shutil.which('tar')
    setup=rarfile.tool_setup(force=True)
    if setup.setup['open_cmd'][0]=='BSDTAR_TOOL':
        class BSDTarSetup(rarfile.ToolSetup):
            def open_cmdline(self,pwd,rarfn,filefn=None):
                if pwd:raise ValueError('This extractor does not support encrypted RAR files.')
                # rarfile puts -- between -f and its filename; bsdtar interprets it as the filename.
                command=[rarfile.BSDTAR_TOOL,'-x','--to-stdout','-f',rarfn,'--']
                if filefn:command.append(filefn)
                return command
        rarfile.CURRENT_SETUP=BSDTarSetup(rarfile.BSDTAR_CONFIG)


def safe_name(name):
    name=str(name).replace('\\','/')
    path=PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in {'..','.'} or ':' in p or p.endswith((' ','.')) or re.match(r'(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',p) for p in path.parts):
        raise ValueError('Unsafe archive member: '+name)
    return path


def checksum(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def _save(folder,manifest):
    temp=folder/'manifest.tmp';temp.write_text(json.dumps(manifest,indent=2),encoding='utf-8');os.replace(temp,folder/'manifest.json')


def prepare(source,staging,*,max_bytes=100*1024**3,max_members=2000,timeout=600,unrar_path=''):
    source=Path(source).resolve();staging=Path(staging).resolve();staging.mkdir(exist_ok=True)
    if not source.is_file():raise ValueError('Archive is unavailable.')
    before=source.stat();identity=f'{source}:{before.st_size}:{before.st_mtime_ns}'
    folder=staging/hashlib.sha256(identity.encode()).hexdigest();folder.mkdir(exist_ok=True)
    with media_operations.exclusive(folder):
        manifest_file=folder/'manifest.json'
        if manifest_file.exists():
            manifest=json.loads(manifest_file.read_text(encoding='utf-8'))
            paths=[]
            for item in manifest['files']:
                if item.get('processed'):continue
                file=folder/'files'/str(safe_name(item['name']))
                if not file.is_file() or checksum(file)!=item['sha256']:raise ValueError('Staged archive content changed. Review the staging folder before retrying.')
                if file.suffix.lower() in MEDIA:paths.append(file)
            return paths
        if source.suffix.lower()=='.zip':
            archive=zipfile.ZipFile(source)
        elif source.suffix.lower()=='.rar':
            import rarfile
            if unrar_path:rarfile.UNRAR_TOOL=unrar_path
            elif shutil.which("tar"):rarfile.BSDTAR_TOOL=shutil.which("tar")
            archive=rarfile.RarFile(source)
        else:raise ValueError('Supported TV archive formats are ZIP and RAR.')
        with closing(archive):
            members=archive.infolist()
            if len(members)>max_members:raise ValueError('Archive contains too many members.')
            selected=[];names=set();total=0
            for item in members:
                name=safe_name(item.filename)
                link=stat.S_ISLNK(getattr(item,'external_attr',0)>>16) or bool(getattr(item,'file_redir',None))
                if link:raise ValueError('Archive links are not permitted.')
                if item.isdir() if hasattr(item,'isdir') else item.is_dir():continue
                lowered=str(name).casefold()
                if lowered in names:raise ValueError('Archive has duplicate or case-colliding members.')
                names.add(lowered)
                if name.suffix.lower() not in MEDIA|SIDECARS:continue
                total+=item.file_size
                if total>max_bytes or item.file_size>max_bytes:raise ValueError('Archive exceeds the extraction size limit.')
                selected.append((item,name))
            if shutil.disk_usage(staging).free<total+64*1024**2:raise ValueError('Not enough space to extract this archive.')
            output=folder/'files';output.mkdir(exist_ok=True)
            manifest={'archive':str(source),'identity':identity,'files':[]}
            deadline=time.monotonic()+timeout
            for item,name in selected:
                target=output/str(name);target.parent.mkdir(parents=True,exist_ok=True)
                if target.exists():raise ValueError('An incomplete extraction exists. Review its staging folder before retrying.')
                if source.suffix.lower()=='.rar':
                    import process_runner
                    # The child owns any decompressor process; timeout terminates that process tree.
                    command=[sys.executable,'--archive-worker'] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve()),'--rar-member']
                    process_runner.run(command+[str(source),item.filename,str(target),str(max_bytes),unrar_path],cwd=folder,timeout=max(1,int(deadline-time.monotonic())))
                else:
                    with archive.open(item) as src,target.open('xb') as dst:
                        written=0
                        while chunk:=src.read(1024*1024):
                            written+=len(chunk)
                            if written>item.file_size or written>max_bytes:raise ValueError('Archive expanded beyond its declared size.')
                            if time.monotonic()>deadline:raise ValueError('Archive extraction timed out.')
                            dst.write(chunk)
                if target.stat().st_size!=item.file_size:raise ValueError('Extracted archive member has the wrong size.')
                manifest['files'].append({'name':str(name),'size':item.file_size,'sha256':checksum(target)})
            after=source.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Archive changed during extraction.')
            _save(folder,manifest)
            return [output/item['name'] for item in manifest['files'] if Path(item['name']).suffix.lower() in MEDIA]


def mark_processed(path,staging):
    path=Path(path).resolve();staging=Path(staging).resolve()
    if not path.is_relative_to(staging):return
    relative=path.relative_to(staging)
    if len(relative.parts)<3 or relative.parts[1]!='files':return
    folder=staging/relative.parts[0]
    with media_operations.exclusive(folder):
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        for item in manifest['files']:
            if Path(item['name'])==Path(*relative.parts[2:]):item['processed']=True
        _save(folder,manifest)


def extract_rar_member(arguments):
    if len(arguments)!=5:raise SystemExit('Invalid archive worker arguments')
    import rarfile
    source,member,target,limit,tool=arguments
    configure_rar(tool)
    with rarfile.RarFile(source) as archive,archive.open(member) as src,Path(target).open('xb') as dst:
        size=0
        while chunk:=src.read(1024*1024):
            size+=len(chunk)
            if size>int(limit):raise ValueError('Archive expansion limit exceeded')
            dst.write(chunk)


if __name__=='__main__':
    if len(sys.argv)!=7 or sys.argv[1]!='--rar-member':raise SystemExit('Internal archive worker')
    extract_rar_member(sys.argv[2:])
