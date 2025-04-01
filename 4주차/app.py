import os
from flask import Flask, render_template, request, redirect, url_for, session
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'

# 유튜브 API 키 (실제 API 키로 교체)
YOUTUBE_API_KEY = "보안상 API KEY 비공개"

# YouTube Data API 클라이언트 생성
youtube = build(
    "youtube",
    "v3",
    developerKey=YOUTUBE_API_KEY,
    discoveryServiceUrl="https://www.googleapis.com/discovery/v1/apis/youtube/v3/rest",
    cache_discovery=True
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search')
def search_page():
    return render_template('search.html')

@app.route('/search_results', methods=['POST'])
def search_results():
    query = request.form.get('query', '')
    # 검색 결과 상위 3개 영상 (간단히 "similar" 키워드를 덧붙임)
    search_response = youtube.search().list(
        q=query + " similar",
        part='id,snippet',
        maxResults=3,
        type='video'
    ).execute()

    results = []
    for item in search_response.get('items', []):
        video_id = item['id']['videoId']
        title = item['snippet']['title']
        thumbnail = item['snippet']['thumbnails']['default']['url']
        results.append({
            'video_id': video_id,
            'title': title,
            'thumbnail': thumbnail
        })

    return render_template('results.html', query=query, results=results)

@app.route('/recommend', methods=['POST'])
def recommend():
    """
    추천 영상: 선택한 영상과 같은 가수(채널)의 다른 곡과 관련(유사 장르) 영상을 제공
    """
    video_id = request.form.get('video_id')

    # 선택한 영상의 세부 정보를 가져와 채널 ID 획득
    video_response = youtube.videos().list(
        part="snippet",
        id=video_id
    ).execute()

    if not video_response.get('items'):
        return "Video not found", 404

    channel_id = video_response['items'][0]['snippet']['channelId']

    # 같은 가수의 다른 곡 (채널 내 다른 영상) 검색, 최대 3개
    same_artist_response = youtube.search().list(
        channelId=channel_id,
        part="id,snippet",
        type="video",
        maxResults=5,  
    ).execute()

    same_artist_results = []
    for item in same_artist_response.get('items', []):
        vid = item['id']['videoId']
        # 본 영상은 제외
        if vid == video_id:
            continue
        same_artist_results.append({
            'video_id': vid,
            'title': item['snippet']['title'],
            'thumbnail': item['snippet']['thumbnails']['default']['url']
        })
        if len(same_artist_results) >= 3:
            break

    # 유사 장르 영상 (관련 영상) 검색, 최대 3개
    related_response = youtube.search().list(
        relatedToVideoId=video_id,
        part="id,snippet",
        type="video",
        maxResults=3,
    ).execute()

    related_results = []
    for item in related_response.get('items', []):
        vid = item['id']['videoId']
        # 혹시 본 영상이 포함된다면 배제
        if vid == video_id:
            continue
        related_results.append({
            'video_id': vid,
            'title': item['snippet']['title'],
            'thumbnail': item['snippet']['thumbnails']['default']['url']
        })

    return render_template('recommend.html', 
                           same_artist_results=same_artist_results, 
                           related_results=related_results)

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

    return redirect(url_for('show_playlist'))

@app.route('/playlist')
def show_playlist():
    playlist = session.get('playlist', [])
    return render_template('playlist.html', playlist=playlist)

@app.route('/play', methods=['POST'])
def play():
    video_id = request.form.get('video_id')
    return f'''
    <html>
    <head>
        <title>Now Playing</title>
    </head>
    <body>
        <h1>Now Playing</h1>
        <iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" 
                frameborder="0" allowfullscreen></iframe>
        <br>
        <a href="{url_for('show_playlist')}">Back to Playlist</a>
    </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True)
