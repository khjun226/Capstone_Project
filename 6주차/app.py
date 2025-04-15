import os
import base64
import requests
from flask import Flask, render_template, request, session, redirect, url_for

app = Flask(__name__)
app.secret_key = 'YOUR_SECRET_KEY'  # 실제 값으로 교체

# =========================
# Spotify API 관련 설정 (Client Credentials Flow)
# =========================
SPOTIFY_CLIENT_ID = ""
SPOTIFY_CLIENT_SECRET = ""

def get_spotify_token():
    url = "https://accounts.spotify.com/api/token"
    auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode('utf-8')
    headers = {"Authorization": f"Basic {b64_auth}"}
    data = {"grant_type": "client_credentials"}
    r = requests.post(url, headers=headers, data=data)
    if r.status_code != 200:
        print("Spotify Token Error:", r.text)
        return None
    return r.json()["access_token"]

def search_spotify_tracks(query, token, limit=10):
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"q": query, "type": "track", "limit": limit}
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        print("Search Error:", r.text)
        return []
    data = r.json()
    return data.get("tracks", {}).get("items", [])

def get_track_detail(track_id, token):
    url = f"https://api.spotify.com/v1/tracks/{track_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        print("Track Detail Error:", r.text)
        return None
    return r.json()

def get_recommendations_for_track(track_data, token, limit=6):
    """
    주어진 트랙 데이터에서 트랙 ID와 대표 아티스트 ID를 추출하여,
    Spotify Recommendations API를 호출해 추천곡 목록을 반환합니다.
    """
    track_id = track_data.get("id")
    artist_id = track_data["artists"][0]["id"] if track_data.get("artists") else None
    url = "https://api.spotify.com/v1/recommendations"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"limit": limit}
    if track_id:
        params["seed_tracks"] = track_id
    if artist_id:
        params["seed_artists"] = artist_id
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        print("Recommendation Error:", r.status_code, r.text)
        return []
    data = r.json()
    return data.get("tracks", [])

LASTFM_API_KEY = ""

def get_similar_tracks_lastfm(artist, track):
    """
    Last.fm의 track.getsimilar 메서드를 사용하여 해당 곡과 유사한 추천곡 목록을 반환합니다.
    
    """
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
    try:
        data = response.json()
    except Exception as e:
        print("Last.fm JSON decoding error:", e)
        return []
    if "similartracks" in data and "track" in data["similartracks"]:
        return data["similartracks"]["track"]
    return []

def search_spotify_cover(artist_name, track_name, token):
    """
    artist_name, track_name을 합쳐서 Spotify에서 검색.
    첫 번째 결과의 앨범 커버 URL(가장 큰 이미지)을 반환하거나, 없으면 빈 문자열 반환.
    """
    if not artist_name or not track_name:
        return ""

    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {token}"}
    query = f"{artist_name} {track_name}"
    params = {
        "q": query,
        "type": "track",
        "limit": 1
    }
    r = requests.get(url, headers=headers, params=params)
    if r.status_code != 200:
        print("Spotify cover search error:", r.status_code, r.text)
        return ""
    data = r.json()
    items = data.get("tracks", {}).get("items", [])
    if not items:
        return ""
    # 첫 번째 검색 결과의 앨범 이미지
    images = items[0].get("album", {}).get("images", [])
    if images:
        # 가장 큰 이미지 (0번 인덱스가 보통 최대 사이즈)
        return images[0]["url"]
    return ""


# =========================
# 플레이리스트 관리 - 세션을 사용 (딕셔너리 구조: {playlist_name: [track, ...]})
# =========================
def init_playlists():
    if "playlists" not in session:
        session["playlists"] = {}

# =========================
# 라우트 설정
# =========================

# (1) 메인 페이지
@app.route("/")
def index():
    return render_template("index.html")

# (2) 검색 페이지 (GET: 폼, POST: 검색 후 결과 화면으로 전송)
@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if not query:
            return redirect(url_for("search"))
        token = get_spotify_token()
        if not token:
            return "Spotify 토큰 발급에 실패하였습니다."
        tracks = search_spotify_tracks(query, token)
        # 플레이리스트 목록(이미 생성되어 있으면) 불러오기
        init_playlists()
        playlist_names = list(session["playlists"].keys())
        return render_template("results.html", query=query, results=tracks, playlist_names=playlist_names)
    return render_template("search.html")

# (3) 노래 상세(추천) 페이지
@app.route("/track/<track_id>")
def track_detail(track_id):
    token = get_spotify_token()
    if not token:
        return "Spotify 토큰 발급 실패."
    
    # Spotify API로 트랙 상세 정보 가져오기
    track_data = get_track_detail(track_id, token)
    if not track_data:
        return f"트랙 정보를 불러올 수 없습니다. (track_id={track_id})"
    
    # Last.fm 추천곡 (track.getsimilar)
    artist_name = track_data["artists"][0]["name"] if track_data.get("artists") else ""
    recommendations = get_similar_tracks_lastfm(artist_name, track_data["name"])
    
    # 추천곡마다 Spotify API 검색을 통해 앨범 이미지를 가져와서 보강
    for rec in recommendations:
        rec_artist = rec["artist"]["name"]   # Last.fm 추천 곡의 아티스트
        rec_title = rec["name"]             # Last.fm 추천 곡의 제목
        
        # Spotify에서 검색한 앨범 커버 URL
        cover_url = search_spotify_cover(rec_artist, rec_title, token)
        
        # Last.fm 추천 데이터에 'album_image' 필드로 저장 (템플릿에서 사용)
        rec["album_image"] = cover_url if cover_url else ""  # 없으면 빈 문자열
    
    return render_template("track_detail.html", track=track_data, recommendations=recommendations)



# (4) 플레이리스트 관련 라우트
# 플레이리스트 목록 보기
@app.route("/playlists")
def playlists():
    init_playlists()
    return render_template("playlists.html", playlists=session["playlists"])

# 특정 플레이리스트 상세(노래 목록 및 삭제 기능)
@app.route("/playlist/<playlist_name>")
def playlist_detail(playlist_name):
    init_playlists()
    playlists = session.get("playlists", {})
    if playlist_name not in playlists:
        return f"플레이리스트 '{playlist_name}'가 존재하지 않습니다."
    return render_template("playlist_detail.html", playlist_name=playlist_name, tracks=playlists[playlist_name])

# (5) 노래 추가: 검색 결과나 추천 결과에서 플레이리스트에 추가하는 기능  
@app.route("/add_to_playlist", methods=["POST"])
def add_to_playlist():
    init_playlists()
    # 기존 플레이리스트 선택 및 새 플레이리스트 이름 입력
    playlist_name = request.form.get("playlist_name", "").strip()
    new_playlist_name = request.form.get("new_playlist_name", "").strip()
    # 우선 새 플레이리스트 이름이 입력되면 해당 이름으로 생성
    if new_playlist_name:
        playlist_name = new_playlist_name
    # fallback: 만약 둘 다 없다면 기본값으로 'default'
    if not playlist_name:
        playlist_name = "default"
    if playlist_name not in session["playlists"]:
        session["playlists"][playlist_name] = []
    
    # 노래 정보 (Spotify 트랙에서 얻은 데이터)
    track_id = request.form.get("track_id")
    preview_url = request.form.get("preview_url")
    track_name = request.form.get("track_name")
    artist = request.form.get("artist")
    album_image = request.form.get("album_image")
    
    # 플레이리스트에 노래 추가
    session["playlists"][playlist_name].append({
         "track_id": track_id,
         "preview_url": preview_url,
         "track_name": track_name,
         "artist": artist,
         "album_image": album_image
    })
    session.modified = True
    return redirect(url_for("playlist_detail", playlist_name=playlist_name))

# (6) 플레이리스트에서 노래 삭제
@app.route("/delete_song", methods=["POST"])
def delete_song():
    playlist_name = request.form.get("playlist_name")
    index = request.form.get("index")
    if not playlist_name or index is None:
        return redirect(url_for("playlists"))
    try:
        idx = int(index)
    except ValueError:
        return redirect(url_for("playlist_detail", playlist_name=playlist_name))
    init_playlists()
    if playlist_name in session["playlists"] and 0 <= idx < len(session["playlists"][playlist_name]):
        session["playlists"][playlist_name].pop(idx)
        session.modified = True
    return redirect(url_for("playlist_detail", playlist_name=playlist_name))

if __name__ == "__main__":
    app.run(debug=True)
