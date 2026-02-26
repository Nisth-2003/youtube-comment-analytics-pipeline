import os
import time
import random
import re
import pandas as pd
from collections import Counter
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ===============================
# 🔑 PASTE YOUR API KEY
# ===============================
API_KEY = "your api key"

CHANNEL_HANDLE = "myskinq"
MASTER_FILE = "master_comments.xlsx"
KEYWORD_FILE = "top_keywords.xlsx"

youtube = build("youtube", "v3", developerKey=API_KEY)

# ===============================
# Utility
# ===============================

def human_delay(min_sec=1, max_sec=3):
    time.sleep(random.uniform(min_sec, max_sec))

def get_channel_id(handle):
    request = youtube.search().list(
        part="snippet",
        q=handle,
        type="channel",
        maxResults=1
    )
    response = request.execute()
    human_delay()
    return response["items"][0]["snippet"]["channelId"]

def get_all_video_ids(channel_id):
    video_ids = []

    request = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()

    uploads_playlist_id = request["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    next_page_token = None

    while True:
        response = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()

        for item in response["items"]:
            video_ids.append(item["contentDetails"]["videoId"])

        next_page_token = response.get("nextPageToken")
        human_delay()

        if not next_page_token:
            break

    return video_ids

# ===============================
# Scraping (INCLUDING REPLIES)
# ===============================

def scrape_video(video_id):

    all_rows = []
    next_page_token = None

    while True:
        try:
            response = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=100,
                pageToken=next_page_token,
                textFormat="plainText"
            ).execute()

            for item in response["items"]:

                top_comment = item["snippet"]["topLevelComment"]
                top_id = top_comment["id"]
                snippet = top_comment["snippet"]

                video_url = f"https://www.youtube.com/watch?v={video_id}"
                comment_url = f"{video_url}&lc={top_id}"

                # Add top-level comment
                all_rows.append({
                    "VideoID": video_id,
                    "VideoURL": video_url,
                    "CommentID": top_id,
                    "ParentCommentID": "",
                    "CommentURL": comment_url,
                    "Author": snippet["authorDisplayName"],
                    "Comment": snippet["textDisplay"],
                    "Likes": snippet["likeCount"],
                    "PublishedAt": snippet["publishedAt"]
                })

                # Add replies if exist
                if "replies" in item:
                    for reply in item["replies"]["comments"]:
                        reply_id = reply["id"]
                        reply_snippet = reply["snippet"]

                        reply_url = f"{video_url}&lc={reply_id}"

                        all_rows.append({
                            "VideoID": video_id,
                            "VideoURL": video_url,
                            "CommentID": reply_id,
                            "ParentCommentID": top_id,
                            "CommentURL": reply_url,
                            "Author": reply_snippet["authorDisplayName"],
                            "Comment": reply_snippet["textDisplay"],
                            "Likes": reply_snippet["likeCount"],
                            "PublishedAt": reply_snippet["publishedAt"]
                        })

            next_page_token = response.get("nextPageToken")
            human_delay()

            if not next_page_token:
                break

        except HttpError as e:
            if "commentsDisabled" in str(e):
                print(f"Comments disabled for {video_id}")
                break
            else:
                print("Error:", e)
                time.sleep(10)

    return all_rows

# ===============================
# Keyword Detection
# ===============================

STOPWORDS = {"the","is","a","an","and","or","to","of","in","on","for","this","that","it","with","i","you","we","they"}

def clean_text(text):
    text = text.lower()
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^a-zA-Z\s]", "", text)
    return text

def generate_keywords(df):
    words = []

    for comment in df["Comment"]:
        cleaned = clean_text(str(comment))
        for word in cleaned.split():
            if word not in STOPWORDS and len(word) > 3:
                words.append(word)

    counter = Counter(words)
    top_keywords = counter.most_common(50)

    pd.DataFrame(top_keywords, columns=["Keyword", "Frequency"]).to_excel(KEYWORD_FILE, index=False)
    print("Keyword file created")

# ===============================
# MAIN
# ===============================

print("Getting channel...")
channel_id = get_channel_id(CHANNEL_HANDLE)

print("Fetching videos...")
video_ids = get_all_video_ids(channel_id)

all_comments = []

for vid in video_ids:
    print("Scraping:", vid)
    rows = scrape_video(vid)
    all_comments.extend(rows)

if all_comments:
    df = pd.DataFrame(all_comments)
    df.drop_duplicates(subset=["CommentID"], inplace=True)
    df.to_excel(MASTER_FILE, index=False)
    print("Master Excel saved")

    generate_keywords(df)

print("Done 🚀")