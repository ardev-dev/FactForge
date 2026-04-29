"""Run AFTER reauth to upload L00600."""
import sys, json
sys.path.insert(0, '.')
from utils.youtube_helper import get_youtube_client, get_next_publish_date
from googleapiclient.http import MediaFileUpload

yt = get_youtube_client()
md = json.load(open('output/L00600/metadata.json'))
publish_at = get_next_publish_date('long')
print(f"Publish: {publish_at}")

body = {
    'snippet': {
        'title': md['title_selected'], 'description': md['description'],
        'tags': md['tags'], 'categoryId': md.get('category_id', '27'),
    },
    'status': {
        'privacyStatus': 'private', 'publishAt': publish_at,
        'selfDeclaredMadeForKids': False,
    }
}
media = MediaFileUpload('output/L00600/video.mp4', mimetype='video/mp4', chunksize=-1, resumable=True)
print("📤 uploading 143 MB...")
req = yt.videos().insert(part='snippet,status', body=body, media_body=media)
resp = None
while resp is None:
    _, resp = req.next_chunk()
yid = resp['id']
print(f"✅ {yid} | https://youtu.be/{yid}")

for pl_id, name in [
    ('PLin03akGsSdZ582q8ntqxDeROE-7xZZ7r', 'Big Pharma Exposed'),
    ('PLin03akGsSdb4hduHdgPkZmQ4lXkYlSYP', 'Corporate Greed Files'),
]:
    yt.playlistItems().insert(part="snippet", body={
        'snippet': {'playlistId': pl_id, 'resourceId':{'kind':'youtube#video','videoId':yid}}
    }).execute()
    print(f"📂 {name}")

data = json.load(open('state/pending_uploads.json'))
data['pending'].append({
    'id': 'L00600', 'title': md['title_selected'],
    'video_file': 'output/L00600/video.mp4', 'metadata_file': 'output/L00600/metadata.json',
    'youtube_id': yid, 'publish_at': publish_at, 'status': 'scheduled',
    'type': 'long', 'scheduled': True, 'niche': 'Big Industry Exposed',
})
with open('state/pending_uploads.json','w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("✅ state updated")
