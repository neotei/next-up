"""Persistent authentication regressions, using synthetic authorization only."""
import json,os,secrets,sys,time
from pathlib import Path
from unittest.mock import patch
os.environ.update(APP_ENV='development',APP_URL='http://localhost',SESSION_SECRET='synthetic-stable-key',OSU_CLIENT_ID='1',OSU_CLIENT_SECRET='synthetic-client-secret')
sys.path.insert(0,str(Path(__file__).resolve().parent))
import app_server as s
from remember import RememberCookie,LIFETIME,CHUNK_SIZE,session_secret
s.app.config['TESTING']=True

def fixture():
    return {'user':{'id':44,'username':'Independent','statistics':{'pp':2222}},
            'token':{'access_token':'synthetic-access','refresh_token':'synthetic-refresh','expires':time.time()+3600},
            'expires':time.time()+s.TTL,'csrf':'original-csrf','prefs':{'max_stars':12,'blocked_ids':[],'mod_caps':{}},
            'result':None,'status':{'busy':False,'message':'','error':None},'revision':0,'last_build':0}

sid=secrets.token_urlsafe(32);state=fixture();s.SESSIONS[sid]=state
browser=s.app.test_client()
with browser.session_transaction() as session:session['sid']=sid
response=browser.get('/api/state')
remember=browser.get_cookie(s.REMEMBER_NAME)
assert remember and remember.http_only and remember.same_site=='Lax' and remember.expires
assert 'Max-Age=2592000' in '\n'.join(response.headers.getlist('Set-Cookie'))
assert 'synthetic-access' not in remember.value and 'synthetic-refresh' not in remember.value
assert 'synthetic-access' not in response.get_data(as_text=True)
assert RememberCookie('different-secret').decode(remember.value) is None
# Production can derive a stable, domain-separated key from its existing private app secret.
key=session_secret(None,'synthetic-client-secret')
assert key==session_secret(None,'synthetic-client-secret') and key!='synthetic-client-secret'
assert key!=session_secret(None,'different-client-secret')
first,second=RememberCookie(key).encode(sid,state)
assert RememberCookie(session_secret(None,'synthetic-client-secret')).decode(first,second)['user']['id']==44
assert s.REMEMBER.decode(remember.value[:-5]+'wrong') is None
# A browser may return with only its durable cookie, after both the volatile
# browser session and all server memory have gone away.
returned=s.app.test_client();returned.set_cookie(s.REMEMBER_NAME,remember.value)
s.SESSIONS.clear()
with patch.object(s,'remote',side_effect=AssertionError('Unexpired sign-in should restore without osu! traffic')):
    data=returned.get('/api/state').json
assert data['configured'] and data['userId']==44 and data['csrf']!='original-csrf'
assert s.app.test_client().get('/api/state').json['configured'] is False
# Refreshing a restored expired access token replaces the saved refresh token.
restored=s.SESSIONS[sid];restored['token']['expires']=0
with patch.object(s,'remote',return_value=json.dumps({'access_token':'new-access','refresh_token':'new-refresh','expires_in':3600}).encode()) as remote:
    response=returned.get('/api/state')
assert remote.call_count==1 and 'refresh_token' in remote.call_args.args[1].decode()
saved=s.REMEMBER.decode(returned.get_cookie(s.REMEMBER_NAME).value)
assert saved['token']['refresh_token']=='new-refresh'
# A lost response must not suppress retransmitting rotated authorization on
# the next request. Compare the actual incoming cookie, not a server-side ack.
returned.set_cookie(s.REMEMBER_NAME,remember.value)
response=returned.get('/api/state')
assert any(s.REMEMBER_NAME+'=' in h and 'Max-Age=2592000' in h for h in response.headers.getlist('Set-Cookie'))
# Large provider tokens use two bounded HttpOnly cookies, with integrity over both.
large=fixture();large['token']['access_token']=secrets.token_urlsafe(2000)
first,second=s.REMEMBER.encode(sid,large)
assert second and len(first)<=CHUNK_SIZE+2 and len(second)<=CHUNK_SIZE
assert s.REMEMBER.decode(first,second)['user']['id']==44
assert s.REMEMBER.decode(first,second[:-5]+'wrong') is None
expired=s.REMEMBER.cipher.encrypt_at_time(json.dumps({'v':1}).encode(),int(time.time()-LIFETIME-1)).decode()
assert s.REMEMBER.decode('1.'+expired) is None
# Logout clears persistence, cancels work and revokes the current provider token.
csrf=returned.get('/api/state').json['csrf']
with patch.object(s,'remote',return_value=b'') as remote:
    response=returned.post('/api/disconnect',json={},headers={'Origin':'http://localhost','X-CSRF-Token':csrf})
assert response.status_code==200 and returned.get_cookie(s.REMEMBER_NAME) is None
assert remote.call_args.kwargs['method']=='DELETE' and remote.call_args.args[0].endswith('/oauth/tokens/current')
assert returned.get('/api/state').json['configured'] is False
# Expired/revoked provider authorization clears remembered sign-in rather than looping.
returned.set_cookie(s.REMEMBER_NAME,remember.value);s.SESSIONS.clear()
with patch.object(s,'ensure_token',side_effect=s.AuthorizationExpired('Expired')):
    response=returned.get('/api/state')
assert not response.json['configured'] and returned.get_cookie(s.REMEMBER_NAME) is None
# Check production cookie attributes separately, without using real credentials.
s.DEVELOPMENT=False
secure=s.app.test_client();sid=secrets.token_urlsafe(32);s.SESSIONS[sid]=fixture()
with secure.session_transaction() as session:session['sid']=sid
response=secure.get('/api/state')
headers='\n'.join(response.headers.getlist('Set-Cookie'))
assert 'Secure' in headers and 'HttpOnly' in headers and 'SameSite=Lax' in headers
print('PASS: durable encrypted sign-in, server/browser restart restoration, isolated accounts, rotation retry, split-cookie integrity, expiry, revocation and production cookie attributes.')
