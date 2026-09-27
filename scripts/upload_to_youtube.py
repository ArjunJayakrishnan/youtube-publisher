"""
upload_to_youtube.py
=====================================
Uploads a finished video (+ thumbnail) to YouTube using the YouTube Data API v3.

ONE-TIME SETUP (do this once, not part of the automated workflow)
---------------------------------------------------------------------
1. Go to Google Cloud Console (console.cloud.google.com), create a project,
   and enable the "YouTube Data API v3".
2. Under "Credentials", create an OAuth client ID of type "Desktop app".
   Download the client_id and client_secret it gives you.
3. Run the small one-time script below ON YOUR OWN COMPUTER (not in GitHub
   Actions) to authorize your channel and get a refresh token:

       pip install google-auth-oauthlib
       python -c "
       from google_auth_oauthlib.flow import InstalledAppFlow
       flow = InstalledAppFlow.from_client_config(
           {'installed': {
               'client_id': 'YOUR_CLIENT_ID',
               'client_secret': 'YOUR_CLIENT_SECRET',
               'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
               'token_uri': 'https://oauth2.googleapis.com/token',
           }},
           scopes=['https://www.googleapis.com/auth/youtube.upload'],
       )
       creds = flow.run_local_server(port=0)
       print('REFRESH TOKEN:', creds.refresh_token)
       "

   This opens a browser once, asks you to log into the YouTube account you
   want to publish to, and prints a refresh token.
4. Store client_id, client_secret, and that refresh token as GitHub Secrets
   in the youtube-publisher repo: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET,
   YOUTUBE_REFRESH_TOKEN. The refresh token does not expire under normal use,
   so this is a genuine one-time setup.

WHAT THIS SCRIPT DOES EACH RUN
----------------------------------
Reads the video file, thumbnail, and metadata.json, and uploads them using
those stored credentials -- no browser/login needed at run time.
"""

import argparse
import json
import os
import sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def get_authenticated_service():
    client_id = os.environ["YOUTUBE_CLIENT_ID"]
    client_secret = os.environ["YOUTUBE_CLIENT_SECRET"]
    refresh_token = os.environ["YOUTUBE_REFRESH_TOKEN"]

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, video_path, metadata, privacy_status):
    body = {
        "snippet": {
            "title": metadata["video_title"],
            "description": metadata.get("video_description", ""),
            "tags": metadata.get("tags", []),
            "categoryId": "27",  # "Education" -- change if a different category fits your content better
        },
        "status": {
            "privacyStatus": privacy_status,   # "private", "unlisted", or "public"
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

    print(f"Uploading '{metadata['video_title']}' as {privacy_status}...")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"Upload complete. Video ID: {video_id}")
    print(f"URL: https://youtu.be/{video_id}")
    return video_id


def set_thumbnail(youtube, video_id, thumbnail_path):
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        print("No thumbnail provided/found -- skipping custom thumbnail.")
        return
    print("Setting custom thumbnail...")
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
    ).execute()
    print("Thumbnail set.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, help="Path to the final_video.mp4 file")
    parser.add_argument("--thumbnail", required=False, help="Path to the thumbnail.jpg file")
    parser.add_argument("--metadata", required=True, help="Path to metadata.json")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    args = parser.parse_args()

    if not os.path.exists(args.video):
        sys.exit(f"Video file not found: {args.video}")
    if not os.path.exists(args.metadata):
        sys.exit(f"metadata.json not found: {args.metadata}")

    with open(args.metadata, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    if "video_title" not in metadata:
        sys.exit("metadata.json is missing required field: video_title")

    youtube = get_authenticated_service()
    video_id = upload_video(youtube, args.video, metadata, args.privacy)
    set_thumbnail(youtube, video_id, args.thumbnail)


if __name__ == "__main__":
    main()