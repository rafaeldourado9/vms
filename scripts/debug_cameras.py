import urllib.request, json

req = urllib.request.Request('http://api:8000/api/v1/auth/token',
    data=json.dumps({'email':'admin@vms.com','password':'admin123'}).encode(),
    headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req, timeout=10) as r:
    token = json.loads(r.read())['access_token']

req2 = urllib.request.Request('http://api:8000/api/v1/cameras',
    headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req2, timeout=10) as r2:
    cameras = json.loads(r2.read())
    for c in cameras:
        print(f"ID: {c.get('id')}")
        print(f"Name: {c.get('name')}")
        keys = list(c.keys())
        print(f"Keys: {keys}")
        su = c.get('stream_urls')
        print(f"stream_urls: {su}")
        if su:
            print(f"  hls: {su.get('hls_url')}")
            print(f"  webrtc: {su.get('webrtc_url')}")
        print('---')
