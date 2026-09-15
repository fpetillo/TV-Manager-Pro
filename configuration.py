"""Typed controls and validation for supported operational settings."""
from urllib.parse import urlparse

BOOL_NAMES=set("rename_episodes move_associated_files process_automatically randomize_providers use_nzbs use_torrents unpack ignore_season_zero_counts automation_enabled auto_grab simulation_mode subtitle_scan_network_paths refresh_media_servers_after_process sab_forced torrent_paused email_tls api_auth_enabled".split())
CHOICES={('general','nzb_method'):['','sabnzbd','nzbget','blackhole'],
         ('general','torrent_method'):['','qbittorrent','transmission','deluge','utorrent','rtorrent','download_station','blackhole'],
         ('general','process_method'):['move','copy','hardlink','symlink','symlink_reversed']}
RANGES={'recent_days':(1,90),'max_searches_per_run':(1,200),'metadata_missing_limit':(1,2000),
        'artwork_refresh_limit':(1,2000),'background_worker_limit':(1,16),'subtitle_scan_max_seconds':(1,3600),
        'subtitle_scan_max_candidates':(1,10000),'email_port':(1,65535),'archive_max_bytes':(1048576,1099511627776),
        'archive_max_seconds':(1,3600),'archive_max_members':(1,100000)}
EDITORS={('general','root_dirs'):('/library-storage','Edit Library Locations'),
         ('tvmanager','postprocess_scripts'):('/postprocess','Edit Processing Scripts'),
         ('tvmanager','calendar_token_hash'):('/upcoming','Manage Calendar Subscription')}


def metadata(section,name,known=False):
    key=(section.lower(),name.lower());name=key[1]
    result={'control':'text','support':'Native setting' if known else 'Imported setting; native behavior not verified'}
    if key in EDITORS:
        result.update(control='editor',editor=EDITORS[key][0],editor_label=EDITORS[key][1])
    elif key in CHOICES:result.update(control='choice',choices=CHOICES[key])
    elif name in BOOL_NAMES:result['control']='boolean'
    elif name in RANGES or name.endswith('_frequency'):
        lo,hi=RANGES.get(name,(1,525600));result.update(control='number',minimum=lo,maximum=hi)
    return result


def validate(section,name,value):
    value=str(value if value is not None else '')
    if len(value)>65536 or '\x00' in value:raise ValueError('The setting is too long or contains an invalid character.')
    spec=metadata(section,name)
    if spec['control']=='editor':raise ValueError('Use '+spec['editor_label']+' to change this setting.')
    if spec['control']=='boolean':
        lowered=value.strip().lower()
        if lowered in {'1','true','yes','on'}:return '1'
        if lowered in {'0','false','no','off'}:return '0'
        raise ValueError('Choose On or Off.')
    if spec['control']=='choice':
        value=value.strip().lower()
        if value not in spec['choices']:raise ValueError('Choose one of the supported options.')
    if spec['control']=='number':
        try:number=int(value)
        except ValueError:raise ValueError('Enter a whole number.') from None
        if not spec['minimum']<=number<=spec['maximum']:raise ValueError(f"Enter a value from {spec['minimum']} to {spec['maximum']}.")
        value=str(number)
    if name.lower() in {'torrent_host','sab_host','nzbget_host'} and value:
        parsed=urlparse(value)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Enter an HTTP/HTTPS address. Use the separate credential fields.')
    return value
