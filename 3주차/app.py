from flask import Flask, render_template, request, redirect, url_for
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = 'some_secret_key'  

# YouTube Data API 설정
YOUTUBE_API_KEY = '보안상 업로드시 유튜브 API 키 삭제제'
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form.get('query')
        # YouTube에서 검색 (영상 타입만 검색)
        search_response = youtube.search().list(
            q=query,
            part="id,snippet",
            maxResults=10,
            type="video"
        ).execute()
        
        videos = []
        for item in search_response['items']:
            video_id = item['id']['videoId']
            title = item['snippet']['title']
            description = item['snippet']['description']
            videos.append({
                'video_id': video_id,
                'title': title,
                'description': description
            })
        return render_template('results.html', videos=videos, query=query)
    return render_template('search.html')

if __name__ == '__main__':
    app.run(debug=True)
