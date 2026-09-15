"""Write real NZB/torrent payloads to configured downloader watch folders."""
from pathlib import Path
from urllib.parse import urlparse
import hashlib
import os
import re
import tempfile
import xml.etree.ElementTree as ET
import requests
import time


def bdecode(data,info_span=None):
    def item(at,depth=0):
        if depth>40 or at>=len(data):raise ValueError('Invalid torrent metadata')
        marker=data[at:at+1]
        if marker==b'i':
            end=data.index(b'e',at+1);return int(data[at+1:end]),end+1
        if marker in {b'l',b'd'}:
            result=[];spans=[];at+=1
            while at<len(data) and data[at:at+1]!=b'e':
                start=at;value,at=item(at,depth+1);result.append(value);spans.append((start,at))
            if at>=len(data):raise ValueError('Unterminated torrent metadata')
            if marker==b'd':
                if len(result)%2 or any(not isinstance(k,bytes) for k in result[::2]):raise ValueError('Invalid torrent dictionary')
                keys=result[::2]
                if keys!=sorted(set(keys)):raise ValueError('Torrent dictionary keys must be unique and sorted')
                if depth==0 and info_span is not None and b'info' in keys:
                    start,end=spans[2*keys.index(b'info')+1];info_span.append(data[start:end])
                return dict(zip(keys,result[1::2])),at+1
            return result,at+1
        end=data.index(b':',at);size=int(data[at:end]);start=end+1
        if size<0 or start+size>len(data):raise ValueError('Invalid torrent string')
        return data[start:start+size],start+size
    try:
        value,end=item(0)
        if end!=len(data):raise ValueError('Unexpected torrent data')
        return value
    except (IndexError,TypeError) as exc:raise ValueError('Invalid torrent metadata') from exc


def validate(data,protocol):
    if protocol=='nzb':
        if b'<!ENTITY' in data.upper():raise ValueError('NZB entity declarations are not accepted')
        try:root=ET.fromstring(data)
        except ET.ParseError as exc:raise ValueError('The provider did not return a valid NZB file') from exc
        if root.tag.split('}')[-1]!='nzb' or not any(n.tag.split('}')[-1]=='segment' and n.text for n in root.iter()):
            raise ValueError('The provider returned an empty or invalid NZB file')
    elif protocol=='torrent':
        info=bdecode(data)
        info=info.get(b'info') if isinstance(info,dict) else None
        if not isinstance(info,dict) or not info.get(b'name') or not isinstance(info.get(b'piece length'),int):
            raise ValueError('The provider did not return torrent metadata')
        if not isinstance(info.get(b'pieces'),bytes) and info.get(b'meta version')!=2:raise ValueError('Torrent is missing piece metadata')
    else:raise ValueError('Unsupported blackhole protocol')


def send(result,directory):
    if not directory:raise ValueError('Configure the downloader watch folder first.')
    data=fetch_payload(result['url'],result['protocol'])
    folder=Path(directory);folder.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(data).hexdigest()
    title=re.sub(r'[^A-Za-z0-9._ -]+','_',result.get('title','release'))[:120].strip(' .')
    destination=folder/f'tvmanager-{title}-{digest[:16]}.{result["protocol"]}'
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest()==digest:return str(destination)
        raise ValueError('Watch-folder destination already exists with different contents')
    fd,temp=tempfile.mkstemp(prefix='.tvmanager-',suffix='.part',dir=folder)
    try:
        with os.fdopen(fd,'wb') as output:output.write(data);output.flush();os.fsync(output.fileno())
        os.replace(temp,destination)
    finally:
        if Path(temp).exists():Path(temp).unlink()
    return str(destination)


def fetch_payload(url,protocol):
    if urlparse(url).scheme.lower() not in {'http','https'}:
        raise ValueError('A watch folder requires an NZB or torrent file URL. Send magnet links directly to a supported download client.')
    maximum=20*1024*1024;data=bytearray();deadline=time.monotonic()+120
    with requests.get(url,stream=True,timeout=(10,30)) as response:
        response.raise_for_status()
        for chunk in response.iter_content(65536):
            if time.monotonic()>deadline:raise ValueError("Descriptor download timed out")
            data.extend(chunk)
            if len(data)>maximum:raise ValueError('Downloader descriptor exceeds 20 MB')
    validate(bytes(data),protocol)
    return bytes(data)
