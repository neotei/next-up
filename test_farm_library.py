import sys,json,gzip,os,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fast_recommender as f
library=f.browse_catalog()
assert len(library['maps'])>8000 and len({m['id'] for m in library['maps']})>1000
assert all(0<=m['farmScore']<=100 and m['curve'] for m in library['maps'])
assert all('userId' not in m and 'accuracy' not in m for m in library['maps'])
# Community evidence leads, and equal maps become more repeatable when shorter.
a=copy.deepcopy(next(m for m in f.MAPS if m['curve'] and m['farm']['weight']>0));b=copy.deepcopy(a)
a['farm']['weight']=1;b['farm']['weight']=.000001
original=f.MAPS
try:
 f.MAPS=[a,b];rows=f.browse_catalog()['maps'];assert rows[0]['farmScore']>rows[1]['farmScore']
 b['farm']['weight']=1;b['features']['length']=300;a['features']['length']=45
 rows=f.browse_catalog()['maps'];assert rows[0]['farmScore']>rows[1]['farmScore']
finally:f.MAPS=original
os.environ['APP_ENV']='development'
import app_server as server
response=server.app.test_client().get('/api/farm-library')
assert response.status_code==200 and response.headers['Content-Encoding']=='gzip'
assert 'public' in response.headers['Cache-Control']
assert len(json.loads(gzip.decompress(response.data))['maps'])==len(library['maps'])
assert server.app.test_client().get('/farm-browser.js').status_code==200
print('PASS: 8,000+ public variants, community-led farm score, short-map preference and compressed public catalogue without session data.')
