"""Validated torrent descriptors and exact info-dictionary identity."""
import base64
import hashlib
import re
from urllib.parse import urlparse,parse_qs
import blackhole


def describe(url):
    if urlparse(url).scheme.lower()=='magnet':
        for item in parse_qs(urlparse(url).query).get('xt',[]):
            if item.lower().startswith('urn:btih:'):
                value=item[9:]
                if re.fullmatch('[a-fA-F0-9]{40}',value):return value.lower(),None
                if re.fullmatch('[a-zA-Z2-7]{32}',value):return base64.b32decode(value.upper()).hex(),None
        raise ValueError('A BitTorrent v1 info hash is required for this client.')
    data=blackhole.fetch_payload(url,'torrent');span=[];metadata=blackhole.bdecode(data,span)
    if not span or b'pieces' not in metadata[b'info']:raise ValueError('This client requires a BitTorrent v1 or hybrid torrent.')
    return hashlib.sha1(span[0]).hexdigest(),data
