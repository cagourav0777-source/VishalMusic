from VISHALMUSIC.core.mongo import mongodb
from VISHALMUSIC.misc import db
from VISHALMUSIC.platforms.Youtube import YouTubeAPI

import asyncio
import re
import time
import aiohttp

yt = YouTubeAPI()
autoplay_db = mongodb.autoplay

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 PROTECTION SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECENT = {}
AUTO_PLAYING = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌍 LANGUAGE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

LANG_DB = {
    "punjabi": ["punjabi", "sidhu", "diljit", "karan", "ammy", "jatt"],
    "hindi": ["hindi", "bollywood", "arijit", "jubin", "atif"],
    "english": ["english", "ed sheeran", "taylor swift", "justin bieber"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎭 MOOD DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOOD_DB = {
    "sad": ["sad", "broken", "heart", "bewafa", "alone", "cry"],
    "love": ["love", "romantic", "ishq", "pyaar", "mohabbat"],
    "party": ["party", "dj", "dance", "club", "bhangra"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎤 ARTIST DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARTIST_DB = {
    "arijit singh": ["arijit", "arijit singh"],
    "atif aslam": ["atif", "atif aslam"],
    "sidhu moosewala": ["sidhu", "sidhu moosewala"],
    "diljit dosanjh": ["diljit", "diljit dosanjh"],
    "karan aujla": ["karan", "karan aujla"],
    "jubin nautiyal": ["jubin", "jubin nautiyal"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎬 MOVIE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOVIE_DB = {
    "animal": ["animal"],
    "kabir singh": ["kabir singh"],
    "aashiqui": ["aashiqui"],
    "shershaah": ["shershaah"],
    "pushpa": ["pushpa"],
    "kgf": ["kgf"],
    "pathaan": ["pathaan"],
    "tu jhoothi main makkaar": ["tu jhoothi"],
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌍 DETECT LANGUAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_lang(title):
    if not title:
        return "unknown"
    title = title.lower()
    for lang, keys in LANG_DB.items():
        if any(x in title for x in keys):
            return lang
    return "unknown"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎭 DETECT MOOD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_mood(title):
    if not title:
        return "normal"
    title = title.lower()
    for mood, keys in MOOD_DB.items():
        if any(x in title for x in keys):
            return mood
    return "normal"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎤 DETECT ARTIST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_artist(title):
    if not title:
        return ""
    title_lower = title.lower()
    for artist, keys in ARTIST_DB.items():
        if any(x in title_lower for x in keys):
            return artist
    parts = re.split(r"[-|(]", title)
    if len(parts) > 1:
        return parts[0].strip()
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎬 DETECT MOVIE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_movie(title):
    if not title:
        return ""
    title = title.lower()
    for movie, keys in MOVIE_DB.items():
        if any(x in title for x in keys):
            return movie
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔁 REPEAT CHECK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_repeat(chat_id, vidid):
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    current = time.time()
    RECENT[chat_id] = [(v, t) for v, t in RECENT[chat_id] if current - t < 7200]
    return vidid in [v for v, _ in RECENT[chat_id]]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ➕ ADD RECENT SONG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def add_recent(chat_id, vidid):
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id].append((vidid, time.time()))
    if len(RECENT[chat_id]) > 50:
        RECENT[chat_id] = RECENT[chat_id][-50:]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 SMART QUERY BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_smart_queries(title, artist, movie, lang, mood):
    queries = []

    clean_title = re.sub(
        r"official|video|lyrics|lyrical|hd|4k", "", title, flags=re.IGNORECASE
    ).strip()

    queries.append(clean_title)
    queries.append(f"{clean_title} official")
    queries.append(f"{clean_title} song")

    if artist:
        queries.append(f"{artist} songs")
        queries.append(f"{artist} best songs")

    if movie:
        queries.append(f"{movie} songs")
        queries.append(f"{movie} jukebox")

    if mood != "normal":
        queries.append(f"{mood} {lang} songs")

    if lang != "unknown":
        queries.append(f"{lang} trending songs")

    bad_words = ["slowed", "reverb", "lofi", "8d", "live", "mix", "dj remix", "bass boosted"]

    final = []
    for q in queries:
        if not any(x in q.lower() for x in bad_words):
            if q not in final:
                final.append(q)

    return final[:15]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎵 BEST SONG FINDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_best_song(chat_id, queries, last_title, artist, movie, mood, lang):
    candidates = []
    original_words = last_title.lower().split()

    for q in queries:
        try:
            details, vidid = await yt.track(q)
            if not vidid:
                continue

            title = details.get("title", "").lower()
            duration = details.get("duration_min", "0:00")

            bad_words = ["slowed", "reverb", "8d", "lofi", "live", "mix", "dj remix", "bass boosted"]
            if any(x in title for x in bad_words):
                continue

            if title.strip() == last_title.lower().strip():
                continue

            try:
                mins = int(duration.split(":")[0])
                if mins < 2 or mins > 8:
                    continue
            except Exception:
                pass

            score = 0

            match_count = sum(1 for w in original_words if w in title)
            score += match_count * 10

            if artist and artist.lower() in title:
                score += 30

            if movie and movie.lower() in title:
                score += 35

            if mood != "normal":
                if mood in title:
                    score += 10

            if any(x in title for x in LANG_DB.get(lang, [])):
                score += 10

            if not await is_repeat(chat_id, vidid):
                score += 40

            candidates.append((score, vidid, details))

        except Exception:
            continue

        await asyncio.sleep(0.3)

    candidates.sort(key=lambda x: x[0], reverse=True)

    if candidates:
        return candidates[0][1], candidates[0][2]

    return None, None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🖼 THUMBNAIL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_thumbnail_direct(video_id):
    urls = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
    ]
    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return url
            except Exception:
                continue
    return urls[-1]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 MAIN AUTOPLAY FUNCTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_play_next(client, chat_id):
    from VISHALMUSIC.utils.database import get_lang
    from VISHALMUSIC.utils.stream.stream import stream
    from VISHALMUSIC.core.call import VISHAL
    from strings import get_string

    # 🔥 DOUBLE PLAY FIX
    if AUTO_PLAYING.get(chat_id):
        return

    AUTO_PLAYING[chat_id] = True

    try:
        data = await autoplay_db.find_one({"chat_id": chat_id})

        if not data or not data.get("status"):
            return

        msg = await client.send_message(
            chat_id,
            "🔄 ꜱɪᴍɪʟᴀʀ ᴀᴜᴛᴏᴘʟᴀʏ → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ ꜱᴏɴɢ...",
        )

        queue = db.get(chat_id)
        last_title = "latest song"

        if queue and len(queue) > 0:
            last_title = queue[0].get("title", "latest song")

        lang = detect_lang(last_title)
        mood = detect_mood(last_title)
        artist = extract_artist(last_title)
        movie = detect_movie(last_title)

        print("━━━━━━━━━━━━━━━━━━")
        print(f"🎵 ꜱᴛʀᴇᴀᴍɪɴɢ → {last_title}")
        print(f"🎤 ᴀʀᴛɪꜱᴛ → {artist}")
        print(f"🎬 ᴍᴏᴠɪᴇ → {movie}")
        print(f"🎭 ᴍᴏᴏᴅ → {mood}")
        print(f"🌍 ʟᴀɴɢᴜᴀɢᴇ → {lang}")

        queries = build_smart_queries(last_title, artist, movie, lang, mood)

        vidid, details = await get_best_song(
            chat_id, queries, last_title, artist, movie, mood, lang
        )

        # 🔥 FALLBACK SYSTEM
        if not vidid and movie:
            details, vidid = await yt.track(f"{movie} songs")

        if not vidid and artist:
            details, vidid = await yt.track(f"{artist} songs")

        if not vidid:
            details, vidid = await yt.track(f"{lang} trending songs")

        if not vidid:
            await msg.edit_text("❌ ɴᴏ ꜱɪᴍɪʟᴀʀ ꜱᴏɴɢ ꜰᴏᴜɴᴅ")
            return

        await add_recent(chat_id, vidid)

        link = f"https://youtube.com/watch?v={vidid}"

        try:
            thumb = details.get("thumb", "")
            if not thumb.startswith("http"):
                thumb = await get_thumbnail_direct(vidid)
        except Exception:
            thumb = await get_thumbnail_direct(vidid)

        print(f"⚡ ꜱɪᴍɪʟᴀʀ ꜱᴏɴɢ ᴘʟᴀʏᴇᴅ → {details.get('title')}")
        print(f"🔗 ꜱᴛʀᴇᴀᴍ ʟɪɴᴋ → {link}")
        print("━━━━━━━━━━━━━━━━━━")

        language = await get_lang(chat_id)
        _ = get_string(language)

        # 🔥 STOP OLD STREAM SAFELY
        try:
            await VISHAL.stop_stream(chat_id)
            await asyncio.sleep(1)
        except Exception:
            pass

        # 🔥 PLAY NEW SONG
        await stream(
            _,
            client,
            0,
            {
                "link": link,
                "vidid": vidid,
                "title": details.get("title", "ꜱɪᴍɪʟᴀʀ ᴀᴜᴛᴏᴘʟᴀʏ"),
                "duration_min": details.get("duration_min", "00:00"),
                "thumb": thumb,
            },
            chat_id,
            "ꜱɪᴍɪʟᴀʀ ᴀᴜᴛᴏᴘʟᴀʏ",
            chat_id,
            video=False,
            streamtype="youtube",
        )

        try:
            await msg.delete()
        except Exception:
            pass

    except Exception as e:
        print(f"⚠️ ᴀᴜᴛᴏᴘʟᴀʏ ᴇʀʀᴏʀ → {e}")

    finally:
        AUTO_PLAYING.pop(chat_id, None)
