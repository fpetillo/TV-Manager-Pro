"""Bounded execution of explicitly configured local processing helpers."""
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path


def run(arguments, *, cwd, timeout=60, output_limit=4*1024*1024):
    if not arguments or not Path(arguments[0]).is_absolute() or not Path(arguments[0]).is_file():
        raise ValueError('Choose an existing executable using its full path.')
    if Path(arguments[0]).suffix.lower() in {'.bat','.cmd'}:
        raise ValueError('Use an executable or interpreter directly; shell command files are not accepted.')
    flags={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {'start_new_session':True}
    with tempfile.TemporaryFile() as output:
        proc=subprocess.Popen([str(a) for a in arguments],cwd=str(cwd),stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,shell=False,**flags)
        deadline=time.monotonic()+max(1,min(int(timeout),3600))
        reason=None
        while proc.poll() is None:
            if time.monotonic()>deadline:reason='Processing helper timed out'
            if os.fstat(output.fileno()).st_size>output_limit:reason='Processing helper exceeded its output limit'
            if reason:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,timeout=10)
                else:os.killpg(proc.pid,signal.SIGKILL)
                proc.wait(timeout=10)
                break
            time.sleep(.1)
        if os.fstat(output.fileno()).st_size>output_limit:reason='Processing helper exceeded its output limit'
        output.seek(0);message=output.read(4000).decode('utf-8',errors='replace')
        if reason:raise ValueError(reason)
        if proc.returncode:raise ValueError(f'Processing helper exited with code {proc.returncode}: {message}')
        return {'ok':True,'output':message,'exit_code':proc.returncode}
