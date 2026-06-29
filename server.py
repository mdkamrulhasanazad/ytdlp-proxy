"""
ytdlp-proxy: a tiny backend that takes a video link (YouTube, TikTok,
Instagram, etc.) and uses yt-dlp to extract a direct, downloadable
video URL — no API key, no per-request cost.

Env vars (set in Render's Environment tab):
  CORS_URL  -> your website origin, e.g. https://thesavewave.blogspot.com
  PORT      -> Render sets this automatically
"""

import os
import yt_dlp
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

CORS_URL = os.environ.get("CORS_URL", "*")
CORS(app, origins=CORS_URL)


def extract_best_format(info):
    """Pick the best progressive (video+audio combined) format if possible,
    otherwise fall back to the best available format yt-dlp reports."""
    formats = info.get("formats", [])

    progressive = [
        f for f in formats
        if f.get("vcodec") != "none" and f.get("acodec") != "none" and f.get("url")
    ]

    if progressive:
        progressive.sort(key=lambda f: f.get("height") or 0, reverse=True)
        return progressive[0]

    # Fall back to whatever yt-dlp considers the best single URL
    if info.get("url"):
        return info

    video_only = [f for f in formats if f.get("vcodec") != "none" and f.get("url")]
    if video_only:
        video_only.sort(key=lambda f: f.get("height") or 0, reverse=True)
        return video_only[0]

    return None


@app.route("/")
def home():
    return "ytdlp-proxy is running. Use GET /fetch?url=VIDEO_LINK"


@app.route("/fetch")
def fetch():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": True, "message": 'Missing "url" query parameter.'}), 400

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "format": "best",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        return jsonify({"error": True, "message": f"yt-dlp failed: {str(e)}"}), 500

    best = extract_best_format(info)
    if not best or not best.get("url"):
        return jsonify({"error": True, "message": "No downloadable format was found for this link."}), 404

    title = info.get("title", "video")
    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()[:60] or "video"

    return jsonify({
        "error": False,
        "status": "tunnel",
        "url": best["url"],
        "filename": f"{safe_title}.mp4",
        "quality": f'{best.get("height", "")}p' if best.get("height") else "unknown",
        "title": title
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
