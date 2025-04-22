import os
import json
import base64
import requests
from flask import Flask, render_template, request, session, redirect, url_for, make_response

# ─── secrets.json 로드 ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
secrets_path = os.path.join(BASE_DIR, "secrets.json")
with open(secrets_path, "r", encoding="utf-8") as f:
    secrets = json.load(f)

SPOTIFY_CLIENT_ID     = secrets["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET = secrets["SPOTIFY_CLIENT_SECRET"]
YOUTUBE_API_KEY       = secrets["YOUTUBE_API_KEY"]
LASTFM_API_KEY        = secrets["LASTFM_API_KEY"]
# ───────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "replace_with_your_secret")

app.jinja_env.globals.update(enumerate=enumerate, zip=zip)

# =========================
# Spotify API (Client Credentials)
# =========================
def get_spotify_token():
    auth_str = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()
    r = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {b64_auth}"},
        data={"grant_type": "client_credentials"}
    )
    if not r.ok:
        app.logger.error("Spotify Token Error: %s", r.text)
        return None
    return r.json().get("access_token")

def search_spotify_tracks(query, token, limit=10):
    r = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": query, "type": "track", "limit": limit}
    )
    if not r.ok:
        app.logger.error("Search Error: %s", r.text)
        return []
    return r.json().get("tracks", {}).get("items", [])

def get_track_detail(track_id, token):
    r = requests.get(
        f"https://api.spotify.com/v1/tracks/{track_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    if not r.ok:
        app.logger.error("Track Detail Error: %s", r.text)
        return None
    return r.json()

# =========================
# Last.fm 추천
# =========================
def get_similar_tracks_lastfm(artist, track, limit=10):
    r = requests.get(
        "http://ws.audioscrobbler.com/2.0/",
        params={
            "method":  "track.getsimilar",
            "artist":  artist,
            "track":   track,
            "api_key": LASTFM_API_KEY,
            "format":  "json",
            "limit":   limit
        }
    )
    if not r.ok:
        app.logger.error("Last.fm Error: %s", r.text)
        return []
    return r.json().get("similartracks", {}).get("track", [])

def search_spotify_cover(artist_name, track_name, token):
    if not artist_name or not track_name:
        return ""
    r = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": f"{artist_name} {track_name}", "type": "track", "limit": 1}
    )
    if not r.ok:
        return ""
    items = r.json().get("tracks", {}).get("items", [])
    if not items:
        return ""
    images = items[0].get("album", {}).get("images", [])
    return images[0]["url"] if images else ""

# =========================
# YouTube Data API
# =========================
def search_youtube_video_id(query: str) -> str:
    """ 곡 제목+아티스트로 검색 후, 첫 번째 영상의 videoId 반환 """
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part":       "snippet",
            "q":          query,
            "key":        YOUTUBE_API_KEY,
            "maxResults": 1,
            "type":       "video"
        }
    )
    if not r.ok:
        app.logger.error("YouTube Search Error: %s", r.text)
        return ""
    items = r.json().get("items", [])
    return items[0]["id"]["videoId"] if items else ""

# =========================
# 세션 기반 플레이리스트 초기화
# =========================
def init_playlists():
    if "playlists" not in session:
        session["playlists"] = {}

# =========================
# 라우트 정의
# =========================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search", methods=["GET","POST"])
def search():
    if request.method == "POST":
        q = request.form.get("query","").strip()
        if not q:
            return redirect(url_for("search"))
        token = get_spotify_token()
        if not token:
            return "Spotify 토큰 발급 실패", 500
        results = search_spotify_tracks(q, token)
        init_playlists()
        return render_template("results.html",
                               query=q,
                               results=results,
                               playlist_names=list(session["playlists"].keys()))
    return render_template("search.html")

@app.route("/track/<track_id>")
def track_detail(track_id):
    token = get_spotify_token()
    if not token:
        return "Spotify 토큰 발급 실패", 500
    track = get_track_detail(track_id, token)
    if not track:
        return f"트랙 정보를 불러올 수 없습니다. (ID={track_id})", 404

    recs = get_similar_tracks_lastfm(track["artists"][0]["name"], track["name"])
    for rec in recs:
        rec["album_image"] = search_spotify_cover(
            rec["artist"]["name"], rec["name"], token
        )

    init_playlists()
    return render_template("track_detail.html",
                           track=track,
                           recommendations=recs,
                           playlist_names=list(session["playlists"].keys()))

@app.route("/playlists")
def playlists():
    init_playlists()
    return render_template("playlists.html",
                           playlists=session["playlists"])

@app.route("/playlist/<playlist_name>")
def playlist_detail(playlist_name):
    init_playlists()
    return render_template("playlist_detail.html",
                           playlist_name=playlist_name,
                           tracks=session["playlists"].get(playlist_name, []))

@app.route("/add_to_playlist", methods=["POST"])
def add_to_playlist():
    init_playlists()
    name = request.form.get("playlist_name", "").strip() or "default"
    session["playlists"].setdefault(name, [])

    # 클라이언트에서 넘어온 최소 정보
    track_id  = request.form.get("song_id", "")
    title     = request.form.get("title", "")
    artist    = request.form.get("artist", "")
    thumbnail = request.form.get("thumbnail", "")

    # 최초 한번만 YouTube 검색 → ID 확보
    youtube_q = f"{title} {artist}"
    youtube_id = search_youtube_video_id(youtube_q) or ""

    song = {
      "spotify_id": track_id,
      "youtube_id": youtube_id,
      "title":      title,
      "artist":     artist,
      "thumbnail":  thumbnail
    }

    if song["spotify_id"] and song["youtube_id"]:
        session["playlists"][name].append(song)
        session.modified = True

    # 원래 페이지로 돌아가기
    next_url = request.form.get("next") or request.referrer or url_for("index")
    return redirect(next_url)

@app.route("/move_song", methods=["POST"])
def move_song():
    name = request.form.get("playlist_name", "")
    try:
        idx = int(request.form.get("index", "-1"))
    except ValueError:
        return redirect(url_for("playlist_detail", playlist_name=name))

    direction = request.form.get("direction")
    lst = session.get("playlists", {}).get(name, [])
    if direction == "up" and 0 < idx < len(lst):
        lst[idx-1], lst[idx] = lst[idx], lst[idx-1]
        session.modified = True
    elif direction == "down" and 0 <= idx < len(lst)-1:
        lst[idx], lst[idx+1] = lst[idx+1], lst[idx]
        session.modified = True

    return redirect(url_for("playlist_detail", playlist_name=name))

@app.route("/delete_song", methods=["POST"])
def delete_song():
    name = request.form.get("playlist_name","")
    try:
        idx = int(request.form.get("index","-1"))
    except ValueError:
        idx = -1
    lst = session["playlists"].get(name, [])
    if 0 <= idx < len(lst):
        lst.pop(idx)
        session.modified = True
    return redirect(url_for("playlist_detail", playlist_name=name))

@app.route("/delete_playlist", methods=["POST"])
def delete_playlist():
    name = request.form.get("playlist_name","")
    if name in session["playlists"]:
        session["playlists"].pop(name)
        session.modified = True
    return redirect(url_for("playlists"))

# ====================================
# ▶ 플레이어 화면: YouTube IFrame + Custom UI
# ====================================
@app.route("/player/<playlist_name>")
def player(playlist_name):
    init_playlists()
    tracks = session["playlists"].get(playlist_name, [])
    video_ids = []
    for t in tracks:
        vid = t.get("youtube_id", "")
        if not vid:
            q = f"{t.get('title','')} {t.get('artist','')}"
            vid = search_youtube_video_id(q) or ""
            t["youtube_id"] = vid
            session.modified = True
        video_ids.append(vid)

    return render_template(
         "player.html",
         playlist_name=playlist_name,
         tracks=tracks,
         video_ids=video_ids
    )

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"]        = "no-cache"
    response.headers["Expires"]       = "0"
    return response

if __name__ == "__main__":
    app.run(debug=True)
