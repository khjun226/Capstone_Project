import os
import requests
from flask import Flask, render_template, request, redirect, url_for, session
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = 'SECRET_KEY'

# =========================
# YouTube API 설정
# =========================
YOUTUBE_API_KEY = "YOUTUBE API KEY"
youtube = build(
    "youtube",
    "v3",
    developerKey=YOUTUBE_API_KEY,
    discoveryServiceUrl="https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest",
    cache_discovery=False
)

# =========================
# Last.fm API 설정
# =========================
LASTFM_API_KEY = "LASTFM API KEY"

def get_similar_tracks(artist, track):
    
    url = "http://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "track.getsimilar",
        "artist": artist,
        "track": track,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": 10
    }
    response = requests.get(url, params=params)
    data = response.json()
    if "similartracks" in data and "track" in data["similartracks"]:
        return data["similartracks"]["track"]
    return []


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search_page():
    return render_template('search.html')

@app.route('/search_results', methods=['POST'])
def search_results():
    
    title_query = request.form.get('query', '')
    artist_input = request.form.get('artist', '')
    

    search_query = f"{artist_input} {title_query} official audio"
    
    search_response = youtube.search().list(
        q=search_query,
        part='id,snippet',
        maxResults=3,
        type='video',
        videoCategoryId="10"
    ).execute()

    results = []
    for item in search_response.get('items', []):
        video_id = item['id']['videoId']
        full_title = item['snippet']['title']
        thumbnail = item['snippet']['thumbnails']['default']['url']
        
        results.append({
            'video_id': video_id,
            'title': title_query,
            'artist': artist_input,
            'thumbnail': thumbnail
        })

    return render_template('results.html', query=search_query, results=results)

@app.route('/playlist')
def playlist():
    playlist = session.get('playlist', [])
    return render_template('playlist.html', playlist=playlist)

@app.route('/add_to_playlist', methods=['POST'])
def add_to_playlist():
    video_id = request.form.get('video_id')
    title = request.form.get('title')
    if 'playlist' not in session:
        session['playlist'] = []
    session['playlist'].append({
        'video_id': video_id,
        'title': title
    })
    session.modified = True
    return redirect(url_for('playlist'))

@app.route('/delete_from_playlist', methods=['POST'])
def delete_from_playlist():
    # 삭제할 노래의 인덱스를 폼 데이터에서 받아옴
    index = request.form.get('index')
    if 'playlist' in session and index is not None:
        try:
            index = int(index)
            playlist = session.get('playlist', [])
            # 유효한 인덱스인지 확인 후 삭제
            if 0 <= index < len(playlist):
                playlist.pop(index)
                session['playlist'] = playlist
                session.modified = True
        except ValueError:
            pass
    return redirect(url_for('playlist'))


@app.route('/play', methods=['POST'])
def play():
    video_id = request.form.get('video_id')
    return f'''
    <html>
    <head><title>Now Playing</title></head>
    <body>
        <h1>Now Playing</h1>
        <iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>
        <br>
        <a href="{url_for('playlist')}">Back to Playlist</a>
    </body>
    </html>
    '''


@app.route('/recommend_lastfm', methods=['POST'])
def recommend_lastfm():
    """
    검색 결과에서 사용자가 선택한 노래의 제목과 아티스트 정보를 이용하여,
    Last.fm API로 유사 곡을 받아오고, 각 곡에 대해 YouTube에서 "official audio" 영상을 검색
    """
    title = request.form.get('title')
    artist = request.form.get('artist')
    if not title or not artist:
        message = "노래 제목과 아티스트 정보가 필요합니다."
        return render_template('lastfm_recommend.html', recommended=[], message=message)

    similar_tracks = get_similar_tracks(artist, title)
    recommended = []
    for track in similar_tracks:
        rec_title = track["name"]
        rec_artist = track["artist"]["name"]
        # YouTube API로 추천 트랙 검색 ("공식 오디오" 영상)
        query = f"{rec_artist} {rec_title} official audio"
        yt_response = youtube.search().list(
            q=query,
            part='id,snippet',
            maxResults=1,
            type='video',
            videoCategoryId="10"
        ).execute()
        yt_items = yt_response.get('items', [])
        if yt_items:
            yt_video_id = yt_items[0]['id']['videoId']
            yt_thumbnail = yt_items[0]['snippet']['thumbnails']['default']['url']
        else:
            yt_video_id = ""
            yt_thumbnail = ""
        recommended.append({
            'track_name': rec_title,
            'artist': rec_artist,
            'youtube_video_id': yt_video_id,
            'youtube_thumbnail': yt_thumbnail
        })

    return render_template('lastfm_recommend.html', recommended=recommended, message=None)

if __name__ == '__main__':
    app.run(debug=True)
