"""Private, per-session osu! authorization and practice recommendations."""
import copy
import json
import math
import os
from pathlib import Path
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from flask import Flask, jsonify, redirect, request, session, send_from_directory
import rosu_pp_py as rosu
import recommender

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / '.cache'
CACHE.mkdir(exist_ok=True)
DEVELOPMENT = os.environ.get('APP_ENV') == 'development'
PUBLIC_URL = os.environ.get('APP_URL', '').rstrip('/')
app = Flask(__name__, static_folder=None)
app.config.update(SECRET_KEY=os.environ.get('SESSION_SECRET') or secrets.token_hex(32),
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=not DEVELOPMENT,
                  SESSION_COOKIE_SAMESITE='Lax', MAX_CONTENT_LENGTH=8192)
SESSIONS = {}
LOCK = threading.RLock()
NETWORK_LOCK = threading.Lock()
LAST_REQUEST = 0
CALCULATOR = threading.Semaphore(1)
MAX_SESSIONS = 128
TTL = 6 * 3600


def remote(url, data=None, headers=None, method=None):
    global LAST_REQUEST
    with NETWORK_LOCK:
        time.sleep(max(0, 1.05 - (time.monotonic() - LAST_REQUEST)))
        LAST_REQUEST = time.monotonic()
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                body = response.read(8_000_001)
                if len(body) > 8_000_000:
                    raise ValueError('The osu! response was too large.')
                return body
        except urllib.error.HTTPError as error:
            message = {401: 'Your osu! session expired; sign in again.',
                       403: 'osu! denied access to this resource.',
                       429: 'osu! is limiting requests; please try again later.'}
            raise ValueError(message.get(error.code, 'osu! could not complete this request.')) from None
        except (urllib.error.URLError, TimeoutError):
            raise ValueError('osu! could not be reached; please try again later.') from None


def api(path, state):
    token = state['token']
    if time.time() >= token['expires']:
        value = json.loads(remote('https://osu.ppy.sh/oauth/token', json.dumps({
            'client_id': os.environ['OSU_CLIENT_ID'], 'client_secret': os.environ['OSU_CLIENT_SECRET'],
            'grant_type': 'refresh_token', 'refresh_token': token['refresh_token']}).encode(),
            {'Content-Type': 'application/json'}))
        token.update(access_token=value['access_token'], refresh_token=value['refresh_token'],
                     expires=time.time()+value['expires_in']-60)
    return json.loads(remote('https://osu.ppy.sh/api/v2/'+path, headers={
        'Authorization': 'Bearer '+token['access_token'], 'Accept': 'application/json',
        'x-api-version': '20220705'}))


def map_file(beatmap_id):
    path = CACHE / f'{int(beatmap_id)}.osu'
    if not path.exists():
        body = remote(f'https://osu.ppy.sh/osu/{int(beatmap_id)}')
        if not body.lstrip(b'\xef\xbb\xbf').startswith(b'osu file format'):
            raise ValueError('osu! did not return a beatmap file.')
        path.write_bytes(body)
    beatmap = rosu.Beatmap(path=str(path))
    if beatmap.is_suspicious():
        raise ValueError('This beatmap cannot be calculated.')
    return beatmap


def current():
    with LOCK:
        state = SESSIONS.get(session.get('sid'))
        if not state or state['expires'] < time.time():
            if state: SESSIONS.pop(session.get('sid'), None)
            session.pop('sid', None)
            return None
        state['expires'] = time.time()+TTL
        return state


def build(state):
    try:
        with CALCULATOR:
            if state.get('cancelled'): return
            state['status']['message'] = 'Reading your lazer scores…'
            user = api('me/osu', state)
            best = []
            for offset in range(0, 1000, 100):
                if state.get('cancelled'): return
                page = api(f'users/{user["id"]}/scores/best?mode=osu&legacy_only=0&limit=100&offset={offset}', state)
                best.extend(page)
                if len(page)<100: break
            recent = api(f'users/{user["id"]}/scores/recent?mode=osu&legacy_only=0&include_fails=1&limit=100', state)
            prefs = copy.deepcopy(state['prefs'])
            searches = {}
            parsed_maps = {}
            def private_api(path, _config):
                if state.get('cancelled'): raise ValueError('Calculation cancelled.')
                if path not in searches: searches[path] = api(path, state)
                return searches[path]
            def private_map(map_id):
                if state.get('cancelled'): raise ValueError('Calculation cancelled.')
                if map_id not in parsed_maps: parsed_maps[map_id] = map_file(map_id)
                return parsed_maps[map_id]
            # Publish a smaller, fully checked list before widening the search.
            for reference_limit, poor_limit, discovery_limit in ((12,4,4),(24,8,8)):
                if state.get('cancelled'): return
                prefs.update(reference_limit=reference_limit, poor_limit=poor_limit,
                             discovery_limit=discovery_limit)
                result = recommender.build(user, best, recent, prefs, private_api, private_map,
                                           state['status'], recommender.weighted_gain)
                result['updated'] = time.time()
                with LOCK:
                    if not state.get('cancelled'):
                        state['result'] = result
                        state['revision'] += 1
    except Exception as error:
        state['status']['error'] = str(error) if isinstance(error, ValueError) else 'The list could not be calculated; please try again.'
    finally:
        state['status']['busy'] = False


def start_build(state):
    with LOCK:
        if state['status']['busy']: return
        if time.time()-state['last_build']<60:
            raise ValueError('Wait a minute before calculating again.')
        state['last_build'] = time.time()
        state['status'] = {'busy': True, 'message': 'Your list is waiting to be calculated…', 'error': None}
        threading.Thread(target=build, args=(state,), daemon=True).start()


@app.after_request
def protect(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if not DEVELOPMENT: response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response


@app.errorhandler(413)
def large(_error):
    return jsonify(error='The request was too large.'), 413


@app.get('/health')
def health():
    return jsonify(ok=True)


@app.get('/api/state')
def read_state():
    state = current()
    available = bool(PUBLIC_URL and os.environ.get('OSU_CLIENT_ID') and os.environ.get('OSU_CLIENT_SECRET'))
    if not state:
        return jsonify(configured=False, available=available, username='', result=None,
                       state={'busy':False,'message':'','error':None}, csrf=None)
    with LOCK:
        return jsonify(configured=True, available=available, username=state['user']['username'],
                       result=state['result'], state=dict(state['status']),
                       userId=state['user']['id'], csrf=state['csrf'], revision=state['revision'])


@app.get('/auth/login')
def login():
    if not PUBLIC_URL or not os.environ.get('OSU_CLIENT_ID') or not os.environ.get('OSU_CLIENT_SECRET'):
        return redirect('/?auth_error=unavailable')
    expected = request.args.get('user_id','').strip()
    if expected and (not expected.isdigit() or len(expected)>12):
        return redirect('/?auth_error=id')
    session['oauth_state'] = secrets.token_urlsafe(32)
    session['oauth_started'] = time.time()
    session['expected_id'] = expected
    query = urllib.parse.urlencode({'client_id':os.environ['OSU_CLIENT_ID'],
        'redirect_uri': PUBLIC_URL+'/auth/callback', 'response_type':'code',
        'scope':'public identify', 'state':session['oauth_state']})
    return redirect('https://osu.ppy.sh/oauth/authorize?'+query)


@app.get('/auth/callback')
def callback():
    expected = session.pop('oauth_state', None)
    started = session.pop('oauth_started', 0)
    expected_id = session.pop('expected_id', '')
    received = request.args.get('state','')
    if not expected or not secrets.compare_digest(expected,received) or time.time()-started>600:
        return redirect('/?auth_error=state')
    if request.args.get('error') or not request.args.get('code'):
        return redirect('/?auth_error=denied')
    try:
        token = json.loads(remote('https://osu.ppy.sh/oauth/token', json.dumps({
            'client_id':os.environ['OSU_CLIENT_ID'], 'client_secret':os.environ['OSU_CLIENT_SECRET'],
            'grant_type':'authorization_code', 'code':request.args['code'],
            'redirect_uri':PUBLIC_URL+'/auth/callback'}).encode(), {'Content-Type':'application/json'}))
        state = {'token':{**token,'expires':time.time()+token['expires_in']-60},
                 'expires':time.time()+TTL, 'prefs':{'max_stars':12,'blocked_ids':[],'mod_caps':{}},
                 'result':None, 'status':{'busy':False,'message':'','error':None},
                 'csrf':secrets.token_urlsafe(32), 'revision':0, 'last_build':0}
        state['user'] = api('me/osu',state)
        if expected_id and expected_id != str(state['user']['id']):
            return redirect('/?auth_error=mismatch')
        with LOCK:
            for sid, old in list(SESSIONS.items()):
                if old['expires']<time.time():
                    old['cancelled']=True
                    del SESSIONS[sid]
            if len(SESSIONS)>=MAX_SESSIONS: return redirect('/?auth_error=busy')
            old = SESSIONS.pop(session.get('sid'),None)
            if old: old['cancelled']=True
            session.clear()
            session['sid'] = secrets.token_urlsafe(32)
            SESSIONS[session['sid']] = state
        # Restore only non-credential preferences from this browser before the first build.
        return redirect('/?connected=1')
    except Exception:
        return redirect('/?auth_error=failed')


@app.post('/api/<action>')
def change(action):
    if request.headers.get('Origin') != PUBLIC_URL:
        return jsonify(error='This request must come from this website.'),403
    state = current()
    if not state: return jsonify(error='Sign in with osu! first.'),401
    if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),state['csrf']):
        return jsonify(error='Your session changed; reload the page.'),403
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload,dict): return jsonify(error='Invalid request.'),400
    try:
        with LOCK:
            if action == 'disconnect':
                state['cancelled'] = True
                SESSIONS.pop(session.get('sid'),None)
                session.clear()
                return jsonify(ok=True)
            if action == 'refresh':
                start_build(state)
            elif action == 'preferences':
                if state['status']['busy']: return jsonify(error='Wait for the current calculation to finish.'),409
                cap = float(payload.get('max_stars',12))
                if not math.isfinite(cap) or not 1<=cap<=12: raise ValueError('Choose a limit between 1 and 12 stars.')
                blocked = payload.get('blocked_ids',state['prefs']['blocked_ids'])
                caps = payload.get('mod_caps',state['prefs']['mod_caps'])
                if not isinstance(blocked,list) or len(blocked)>500 or not all(type(i) is int and i>0 for i in blocked):
                    raise ValueError('Invalid map feedback.')
                if not isinstance(caps,dict) or len(caps)>30 or not all(isinstance(k,str) and len(k)<300 and isinstance(v,(int,float)) and math.isfinite(v) and 1<=v<=12 for k,v in caps.items()):
                    raise ValueError('Invalid mod limits.')
                state['prefs'] = {'max_stars':cap,'blocked_ids':blocked,'mod_caps':caps}
                if state['result']:
                    state['result']['maxStars']=cap
                    for list_key in ('maps','farmMaps'):
                        state['result'][list_key]=[m for m in state['result'].get(list_key,[]) if m['id'] not in blocked and m['stars']<=min(cap,caps.get(m['modKey'],12))]
                    state['revision']+=1
            elif action == 'feedback':
                if state['status']['busy']: return jsonify(error='Wait for the current calculation to finish.'),409
                result=state['result'] or {}
                row=next((m for m in result.get('maps',[])+result.get('farmMaps',[])
                          if m['id']==payload.get('id') and (not payload.get('key') or m['key']==payload['key'])),None)
                if not row: raise ValueError('That map is no longer in your list.')
                limit=max(1,row['stars']-.25)
                prefs=state['prefs'];prefs['blocked_ids']=list(set(prefs['blocked_ids']+[row['id']]))
                prefs['mod_caps'][row['modKey']]=min(prefs['mod_caps'].get(row['modKey'],12),limit)
                for list_key in ('maps','farmMaps'):
                    state['result'][list_key]=[m for m in state['result'].get(list_key,[]) if m['id'] not in prefs['blocked_ids'] and m['stars']<=prefs['mod_caps'].get(m['modKey'],12)]
                state['revision']+=1
                return jsonify(ok=True,limit=prefs['mod_caps'][row['modKey']],preferences=prefs)
            elif action == 'reset-feedback':
                if state['status']['busy']: return jsonify(error='Wait for the current calculation to finish.'),409
                state['prefs']['blocked_ids']=[];state['prefs']['mod_caps']={}
            else:
                return jsonify(error='Not found.'),404
        return jsonify(ok=True,preferences=state['prefs'])
    except (ValueError,TypeError):
        return jsonify(error='Check the settings and try again.'),400


@app.get('/')
def home():
    return send_from_directory(ROOT,'index.html')


@app.get('/<path:name>')
def assets(name):
    # A static host must never expose the server code, cached maps or user state.
    if name not in {'style.css','app.js','hosted.js','favicon.ico'}:
        return jsonify(error='Not found.'),404
    return send_from_directory(ROOT,name)
