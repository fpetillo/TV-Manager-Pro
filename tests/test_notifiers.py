import requests
import pytest
import notifiers

@pytest.fixture
def store(tmp_path,monkeypatch):
    monkeypatch.setattr(notifiers,'DB',tmp_path/'test.db');notifiers.init()

@pytest.mark.parametrize('kind,expected',[
 ('discord',{'content','allowed_mentions'}),('slack',{'text','mrkdwn','link_names'}),
 ('telegram',{'chat_id','text'}),('gotify',{'title','message','priority'}),
 ('pushover',{'token','user','title','message'}),('pushbullet',{'type','title','body'})])
def test_native_payloads(kind,expected,monkeypatch):
    calls=[]
    class Response:
        status_code=200
        def json(self):return {'ok':True,'status':1}
    def post(url,**kwargs):calls.append((url,kwargs));return Response()
    monkeypatch.setattr(notifiers.requests,'post',post)
    result=notifiers.send({'kind':kind,'url':'https://example.test/hook','token':'secret','recipient':'recipient'},'downloaded',{'show':'Test','season':1,'episode':2,'private_path':'do not transmit'})
    assert result['ok'];url,call=calls[0];assert set(call['json'])==expected
    assert call['allow_redirects'] is False and call['timeout']==12
    assert 'private_path' not in str(call)
    if kind=='gotify':assert call['headers']['X-Gotify-Key']=='secret' and url.endswith('/message')
    if kind=='discord':assert call['json']['allowed_mentions']=={'parse':[]}

def test_credentials_mask_preserve_and_kind_change(store):
    sid=notifiers.save({'name':'Test','kind':'telegram','token':'secret','recipient':'chat'})
    row=notifiers.listing()[0];assert row['token']==row['recipient']==notifiers.MASK
    assert row['enabled']==0
    notifiers.save({**row,'name':'Renamed'})
    with pytest.raises(ValueError,match='token'):notifiers.save({**row,'kind':'pushover'})
    assert notifiers.listing()[0]['name']=='Renamed'

def test_filter_disable_and_status(store,monkeypatch):
    sid=notifiers.save({'name':'Test','kind':'telegram','token':'secret','recipient':'chat','enabled':True,'events':'downloaded'})
    calls=[]
    monkeypatch.setattr(notifiers,'send',lambda *args:calls.append(args) or {'ok':True,'message':'Delivered'})
    assert notifiers.dispatch('snatched',{})==[]
    assert notifiers.dispatch('downloaded',{})[0]['ok']
    assert notifiers.listing()[0]['last_result']=='Delivered'
    notifiers.save({'id':sid,'enabled':False})
    assert notifiers.dispatch('downloaded',{})==[] and len(calls)==1

def test_errors_do_not_disclose_tokens(monkeypatch):
    def fail(*args,**kwargs):raise requests.ConnectionError('https://secret-token-in-url')
    monkeypatch.setattr(notifiers.requests,'post',fail)
    result=notifiers.send({'kind':'telegram','token':'secret','recipient':'chat'},'test',{})
    assert not result['ok'] and 'secret' not in result['message']
