from types import SimpleNamespace
import requests
import advanced, engine

SERVER={'url':'http://plex.test','token':'private-token'}
XML=b'<MediaContainer><Directory key="2" type="show"><Location path="M:/TV"/><Location path="N:/TV"/></Directory><Directory key="3" type="movie"><Location path="M:/Movies"/></Directory></MediaContainer>'


def responses(monkeypatch,xml=XML,fail=False):
    calls=[]
    def get(url,**kwargs):
        calls.append((url,kwargs))
        if fail and url.endswith('/refresh'):raise requests.ConnectionError('private-token')
        return SimpleNamespace(content=xml,raise_for_status=lambda:None)
    monkeypatch.setattr(advanced.requests,'get',get)
    return calls


def test_foreign_path_scans_tv_section_once_without_invalid_path(monkeypatch):
    calls=responses(monkeypatch)
    result=advanced._refresh_plex(SERVER,'//nas/media/TV/New Show')
    assert result['ok'] and result['fallback']=='tv_libraries' and result['refreshed']==1
    assert len(calls)==2 and calls[1][0].endswith('/2/refresh')
    assert calls[1][1]['params']=={} and calls[1][1]['headers']['X-Plex-Token']=='private-token'


def test_matching_path_uses_targeted_scan_and_path_boundary(monkeypatch):
    calls=responses(monkeypatch)
    result=advanced._refresh_plex(SERVER,'n:/tv/New Show')
    assert result['targeted'] and calls[-1][1]['params']['path']=='n:/tv/New Show'
    result=advanced._refresh_plex(SERVER,'N:/TV-other/New Show')
    assert not result['targeted'] and calls[-1][1]['params']=={}


def test_no_tv_library_and_failed_scan_report_failure_without_token(monkeypatch):
    responses(monkeypatch,b'<MediaContainer/>')
    assert not advanced._refresh_plex(SERVER)['ok']
    responses(monkeypatch,fail=True)
    result=advanced._refresh_plex(SERVER)
    assert not result['ok'] and result['refreshed']==0 and 'private-token' not in str(result)


def test_postprocess_notifies_all_enabled_servers_and_deduplicates_full_scans(monkeypatch):
    monkeypatch.setattr(engine.advanced,'media_servers',lambda:[{'id':1,'name':'one','enabled':1},{'id':2,'name':'two','enabled':1},{'id':3,'name':'off','enabled':0}])
    calls=[];logs=[]
    def refresh(sid,show_id):
        calls.append((sid,show_id))
        return {'ok':sid==1,'fallback':'tv_libraries','message':'scan result'}
    monkeypatch.setattr(engine.advanced,'refresh_media_server_target',refresh)
    monkeypatch.setattr(engine,'log',lambda *a,**k:logs.append(a))
    result=engine._refresh_processed_shows({5,6})
    assert calls==[(1,5),(2,5),(2,6)]
    assert len(result)==3 and any(log[0]=='media_refresh_error' for log in logs)
