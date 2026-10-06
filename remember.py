"""Authenticated, encrypted browser persistence without a server-side credential database."""
import base64
import hashlib
import json
import time
from cryptography.fernet import Fernet, InvalidToken

LIFETIME = 30 * 24 * 3600
RENEW_AFTER = 24 * 3600
CHUNK_SIZE = 3400

class RememberCookie:
    def __init__(self, secret):
        # Domain separation keeps this key distinct from Flask's cookie-signing key.
        key = hashlib.sha256(b'next-up/remember/v1\0' + str(secret).encode()).digest()
        self.cipher = Fernet(base64.urlsafe_b64encode(key))

    def encode(self, sid, state):
        t = state['token']; u = state['user']
        value = {'v':1, 'sid':sid, 'token':{k:t[k] for k in ('access_token','refresh_token','expires')},
                 'user':{'id':u['id'],'username':u['username'],'statistics':{'pp':u.get('statistics',{}).get('pp',0)}}}
        encrypted = self.cipher.encrypt(json.dumps(value,separators=(',',':')).encode()).decode()
        if len(encrypted)>CHUNK_SIZE*2:
            raise ValueError('Authorization is too large to remember safely.')
        return ('1.'+encrypted,'') if len(encrypted)<=CHUNK_SIZE else ('2.'+encrypted[:CHUNK_SIZE],encrypted[CHUNK_SIZE:])

    def decode(self, first, second=''):
        try:
            if len(first)>CHUNK_SIZE+2 or len(second)>CHUNK_SIZE:return None
            if first.startswith('1.'):encrypted=first[2:]
            elif first.startswith('2.') and second:encrypted=first[2:]+second
            else:return None
            raw=self.cipher.decrypt(encrypted.encode(),ttl=LIFETIME)
            value=json.loads(raw)
            if value.get('v')!=1 or not isinstance(value.get('sid'),str) or len(value['sid'])!=43:return None
            u=value['user'];t=value['token']
            if type(u.get('id')) is not int or u['id']<=0 or not isinstance(u.get('username'),str):return None
            if not all(isinstance(t.get(k),str) and t[k] for k in ('access_token','refresh_token')):return None
            if not isinstance(t.get('expires'),(int,float)):return None
            value['issued']=self.cipher.extract_timestamp(encrypted.encode())
            return value
        except (InvalidToken,ValueError,TypeError,KeyError,UnicodeError):
            return None

    @staticmethod
    def version(state):
        token=state['token']
        return (token.get('access_token'),token.get('refresh_token'),token.get('expires'))
