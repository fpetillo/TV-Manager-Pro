"""Shared listener configuration for source and packaged launchers."""
from __future__ import annotations

import ipaddress
import os
import socket

import dbcore


def validate(host, port):
    host = str(host or '').strip()
    if host.lower() == 'localhost':
        host = '127.0.0.1'
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError('Enter an IP address, such as 192.168.1.11, or 0.0.0.0 for all IPv4 interfaces.') from None
    if '%' in host or address.is_multicast or host == '255.255.255.255':
        raise ValueError('Choose a local unicast IP address or an all-interfaces address.')
    if isinstance(port, bool) or not str(port).strip().isascii() or not str(port).strip().isdigit():
        raise ValueError('Enter a whole-number port from 1 to 65535.')
    port = int(port)
    if not 1 <= port <= 65535:
        raise ValueError('Enter a port from 1 to 65535.')
    return {'host': str(address), 'port': port}


def is_local_only(host):
    return ipaddress.ip_address(host).is_loopback


def read(db, environ=None):
    env = os.environ if environ is None else environ
    with dbcore.connect(db, readonly=True, wal=False) as c:
        values = {r['name'].lower(): r['value'] for r in c.execute(
            "SELECT name,value FROM settings WHERE lower(section)='tvmanager' AND lower(name) IN ('listen_host','listen_port')")}
    host = env.get('TVMANAGER_BIND_HOST') or values.get('listen_host') or env.get('HOST') or '127.0.0.1'
    port = env.get('TVMANAGER_BIND_PORT') or values.get('listen_port') or env.get('PORT') or '5050'
    return validate(host, port)


def ensure_local_address(host):
    family = socket.AF_INET6 if ':' in host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.bind((host, 0))
    except OSError:
        raise ValueError('This IP address is not available on this computer. Choose one of its local addresses or 0.0.0.0.') from None


def save(db, body, admin_configured, auth_enabled, environ=None):
    env = os.environ if environ is None else environ
    if env.get('TVMANAGER_BIND_HOST') or env.get('TVMANAGER_BIND_PORT'):
        raise ValueError('A temporary TVMANAGER_BIND override is active. Remove it and restart before saving Network settings.')
    if not isinstance(body, dict):
        raise ValueError('Network settings must include an address and port.')
    config = validate(body.get('host'), body.get('port'))
    ensure_local_address(config['host'])
    with dbcore.connect(db) as c:
        c.execute('BEGIN IMMEDIATE')
        for name, value in [('listen_host', config['host']), ('listen_port', str(config['port']))]:
            c.execute("DELETE FROM settings WHERE lower(section)='tvmanager' AND lower(name)=?", (name,))
            c.execute("INSERT INTO settings(section,name,value,is_secret,source,updated_at) VALUES('TVManager',?,?,0,'tvmanager',CURRENT_TIMESTAMP)", (name, value))
        c.commit()
    return config


def addresses():
    found = {'127.0.0.1', '0.0.0.0'}
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = result[4][0]
            if not address.startswith('169.254.'):
                found.add(address)
    except OSError:
        pass
    return sorted(found)


def url(config):
    host = config['host']
    if host in {'0.0.0.0', '::'}:
        return None
    return f"http://{'[' + host + ']' if ':' in host else host}:{config['port']}"


def status(db, active, environ=None):
    env = os.environ if environ is None else environ
    desired = read(db, env)
    return dict(config=desired, active=active, restart_required=desired != active,
                addresses=addresses(), url=url(desired),
                override=bool(env.get('TVMANAGER_BIND_HOST') or env.get('TVMANAGER_BIND_PORT')))


def prepare(config, admin_configured, auth_enabled):
    ensure_local_address(config['host'])
    return config
