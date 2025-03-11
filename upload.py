import yt_dlp
import requests
import json
import os
import time
import schedule
from flask import Flask, send_from_directory
import threading
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
DOWNLOAD_FOLDER = "downloads"

# Ensure download folder exists
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Flask app to serve videos
app = Flask(__name__)

@app.route('/videos/<filename>')
def serve_video(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename)

def run_flask():
    app.run(host="0.0.0.0", port=5000)

threading.Thread(target=run_flask, daemon=True).start()

# Load video URLs from JSON
def load_videos():
    with open("videos.json", "r") as file:
        return json.load(file)

def save_videos(data):
    with open("videos.json", "w") as file:
        json.dump(data, file, indent=4)

def get_direct_video_url(video_url):
    try:
        ydl_opts = {'quiet': True, 'format': 'best', 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info.get('url', None)
    except Exception as e:
        print(f"Error extracting video URL: {e}")
        return None

def download_video(video_url, filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    try:
        with requests.get(video_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return filepath
    except Exception as e:
        print(f"Download failed: {e}")
        return None

def upload_to_public_server(filepath):
    return f"https://your-render-app.onrender.com/videos/{os.path.basename(filepath)}"

def upload_video(filepath):
    print(f"Uploading: {filepath}")

    public_video_url = upload_to_public_server(filepath)
    if not public_video_url:
        print("❌ Failed to generate a public video URL.")
        return False

    upload_url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media"
    video_data = {
        "video_url": public_video_url,
        "caption": "🔥 Trending video! #viral",
        "access_token": ACCESS_TOKEN,
        "media_type": "REELS"
    }
    response = requests.post(upload_url, data=video_data)
    response_json = response.json()

    if "id" not in response_json:
        print("Upload failed:", response_json)
        return False

    video_id = response_json.get("id")

    publish_url = f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
    publish_data = {
        "creation_id": video_id,
        "access_token": ACCESS_TOKEN
    }
    publish_response = requests.post(publish_url, data=publish_data)

    if "id" in publish_response.json():
        print("✅ Upload successful!")

        # Delete the video after successful upload
        os.remove(filepath)
        print(f"Deleted file: {filepath}")

        return True
    else:
        print("❌ Publish failed:", publish_response.json())
        return False

def process_videos():
    data = load_videos()
    updated = False

    for video in data["videos"]:
        if not video["uploaded"]:
            print(f"Processing: {video['url']}")

            direct_video_url = get_direct_video_url(video["url"])
            if not direct_video_url:
                print("Failed to extract direct video URL")
                continue

            video_filename = f"video_{int(time.time())}.mp4"
            video_filepath = download_video(direct_video_url, video_filename)
            if not video_filepath:
                print("Skipping due to download failure")
                continue

            success = upload_video(video_filepath)
            if success:
                video["uploaded"] = True
                updated = True

            break

    if updated:
        save_videos(data)
process_videos() 
schedule.every(12).hours.do(process_videos)

print("✅ Instagram Auto-Upload Bot Started!")
while True:
    schedule.run_pending()
    time.sleep(10)
