import urllib.request, json

req = urllib.request.Request('http://api:8000/api/v1/auth/token',
    data=json.dumps({'email':'admin@vms.com','password':'admin123'}).encode(),
    headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req, timeout=10) as r:
    token = json.loads(r.read())['access_token']

req2 = urllib.request.Request('http://api:8000/api/v1/cameras',
    headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req2, timeout=10) as r2:
    for c in json.loads(r2.read()):
        su = c.get('stream_urls', {})
        print(f"Camera: {c['name']}")
        print(f"  hls:    {su.get('hls_url','N/A')}")
        print(f"  webrtc: {su.get('webrtc_url','N/A')}")
        print()
