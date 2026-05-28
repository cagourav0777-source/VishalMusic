*import asyncio
import random
import re
import time

import aiohttp

from VISHALMUSIC import app
from VISHALMUSIC.core.mongo import mongodb
from VISHALMUSIC.misc import db
from VISHALMUSIC.platforms.Youtube import YouTubeAPI

yt = YouTubeAPI()
autoplay_db = mongodb.autoplay

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PROTECTION SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECENT = {}
AUTO_PLAYING = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🇮🇳 INDIAN LANGUAGE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

LANG_DB = {
    "hindi": ["hindi", "bollywood", "arijit", "jubin", "atif", "hindi song", "bollywood song"],
    "punjabi": ["punjabi", "sidhu", "diljit", "karan", "ammy", "jatt", "punjabi song"],
    "english": ["english", "ed sheeran", "taylor swift", "justin bieber", "english song"],
    "bhojpuri": ["bhojpuri", "pawan singh", "khesari", "bhojpuri song"],
    "haryanvi": ["haryanvi", "khasa", "masoom sharma", "haryanvi song"],
    "gujarati": ["gujarati", "gujju", "garba", "gujarati song"],
    "tamil": ["tamil", "tamil song", "kollywood", "anirudh", "tamil cinema"],
    "telugu": ["telugu", "telugu song", "tollywood", "devi sri", "telugu cinema"],
    "bengali": ["bengali", "bangla", "bengali song"],
    "marathi": ["marathi", "marathi song", "maharashtra"],
    "urdu": ["urdu", "urdu song", "pakistani", "nusrat"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎭 MOOD DATABASE (Indian Context)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOOD_DB = {
    "sad": ["sad", "broken", "heart", "bewafa", "alone", "cry", "dard", "tanha", "rula", "sad song"],
    "love": ["love", "romantic", "ishq", "pyaar", "mohabbat", "love song", "romantic song", "pyar", "ishq wala"],
    "party": ["party", "dj", "dance", "club", "bhangra", "party song", "dj song", "dance song", "masala"],
    "wedding": ["wedding", "shaadi", "marriage", "dulhan", "mehendi", "sangeet"],
    "devotional": ["devotional", "bhajan", "aarti", "mantra", "shiva", "krishna", "ram", "ganesha", "hanuman"],
    "oldschool": ["old", "classic", "90s", "80s", "kishore", "lata", "rafi", "old song", "retro", "purana"],
    "punjabi": ["punjabi", "sidhu", "diljit", "bhangra", "jatt", "punjabi song"],
    "sufi": ["sufi", "qawwali", "nusrat", "kalam", "sufiana"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎤 INDIAN ARTIST DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARTIST_DB = {
    "arijit singh": ["arijit", "arijit singh", "arijit song", "arijit new"],
    "atif aslam": ["atif", "atif aslam", "atif song"],
    "sidhu moosewala": ["sidhu", "sidhu moosewala", "sidhu song"],
    "diljit dosanjh": ["diljit", "diljit dosanjh", "diljit song"],
    "karan aujla": ["karan", "karan aujla", "karan song"],
    "jubin nautiyal": ["jubin", "jubin nautiyal", "jubin song"],
    "badshah": ["badshah", "badshah song", "badshah new"],
    "yo yo honey singh": ["honey singh", "yo yo", "brown rang", "yo yo honey singh"],
    "neha kakkar": ["neha kakkar", "neha song", "neha new"],
    "shreya ghoshal": ["shreya", "shreya ghoshal", "shreya song"],
    "sonu nigam": ["sonu", "sonu nigam", "sonu song"],
    "alka yagnik": ["alka", "alka yagnik", "alka song"],
    "udit narayan": ["udit", "udit narayan", "udit song"],
    "kumar sanu": ["kumar sanu", "kumar song"],
    "lata mangeshkar": ["lata", "lata mangeshkar", "lata song"],
    "kishore kumar": ["kishore", "kishore kumar", "kishore song"],
    "mohammad rafi": ["rafi", "mohammad rafi", "rafi song"],
    "ap dhillon": ["ap dhillon", "ap", "dhillon", "ap song"],
    "gurinder gill": ["gurinder gill", "gill", "gurinder song"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎬 INDIAN MOVIE DATABASE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

MOVIE_DB = {
    "animal": ["animal", "animal song", "animal movie"],
    "kabir singh": ["kabir singh", "kabir movie"],
    "aashiqui 2": ["aashiqui", "aashiqui 2", "aashiqui song"],
    "shershaah": ["shershaah", "shershaah song", "shershaah movie"],
    "pushpa": ["pushpa", "pushpa song", "pushpa movie", "srivali"],
    "kgf": ["kgf", "kgf song", "rocky bhai"],
    "pathaan": ["pathaan", "pathaan song", "shah rukh"],
    "jawan": ["jawan", "jawan song", "jawan movie"],
    "dunki": ["dunki", "dunki song", "dunki movie"],
    "gadar 2": ["gadar", "gadar 2", "gadar song"],
    "rocky aur rani": ["rocky", "rani", "rocky aur rani", "kjo"],
    "tu jhoothi main makkaar": ["tu jhoothi", "tjmm", "ranbir", "shraddha"],
    "bhool bhulaiyaa 2": ["bhool bhulaiyaa", "bb2", "kartik aaryan"],
    "brahmastra": ["brahmastra", "astra", "ranbir", "alia"],
    "tanhaji": ["tanhaji", "ajay devgn", "tanhaji song"],
    "chhichhore": ["chhichhore", "sushant", "chhichhore song"],
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TRENDING KEYWORDS (Indian)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

TRENDING_STYLES = [
    "latest hindi songs",
    "trending punjabi songs",
    "bollywood hits",
    "new indian music",
    "viral indian songs",
    "top 50 india",
    "indian hip hop",
    "indie indian",
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🌍 DETECT LANGUAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_lang(title):
    if not title:
        return "hindi"
    title = title.lower()
    for lang, keys in LANG_DB.items():
        if any(x in title for x in keys):
            return lang
    return "hindi"


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
        candidate = parts[0].strip()
        if len(candidate) < 30:
            return candidate
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
#  SMART QUERY BUILDER (Indian Focus)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_smart_queries(title, artist, movie, lang, mood):
    queries = []

    clean_title = re.sub(
        r"official|video|lyrics|lyrical|hd|4k|music|song|audio|full|hq",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    queries.append(clean_title)
    queries.append(f"{clean_title} song")
    queries.append(f"{clean_title} official")
    queries.append(f"{clean_title} lyrics")

    if artist:
        queries.append(f"{artist} songs")
        queries.append(f"{artist} hits")
        queries.append(f"{artist} best songs")
        if movie:
            queries.append(f"{artist} {movie} song")
        if lang:
            queries.append(f"{artist} {lang} songs")

    if movie:
        queries.append(f"{movie} songs")
        queries.append(f"{movie} all songs")
        queries.append(f"{movie} jukebox")
        queries.append(f"{movie} playlist")

    if mood == "sad":
        queries += ["sad hindi songs", "heartbreak songs hindi", "bewafa songs"]
    elif mood == "love":
        queries += ["romantic hindi songs", "love songs bollywood", "ishq wala song"]
    elif mood == "party":
        queries += ["party punjabi songs", "dj remix hindi", "dance songs bollywood"]
    elif mood == "wedding":
        queries += ["wedding songs hindi", "shaadi ke gane"]
    elif mood == "devotional":
        queries += ["bhajan", "aarti songs", "hanuman chalisa"]
    elif mood == "oldschool":
        queries += ["90s hindi songs", "old bollywood songs", "retro hindi songs"]
    elif mood == "sufi":
        queries += ["sufi songs hindi", "qawwali hits"]

    if lang == "hindi":
        queries += ["latest bollywood hits", "trending hindi songs 2025"]
    elif lang == "punjabi":
        queries += ["latest punjabi songs 2025", "punjabi hits"]
    elif lang == "bhojpuri":
        queries.append("bhojpuri hits")
    elif lang == "haryanvi":
        queries.append("haryanvi songs 2025")
    elif lang == "gujarati":
        queries.append("gujarati garba songs")
    elif lang == "tamil":
        queries.append("tamil hits")
    elif lang == "telugu":
        queries.append("telugu hits")
    elif lang == "bengali":
        queries.append("bengali songs")
    elif lang == "marathi":
        queries.append("marathi songs")
    elif lang == "urdu":
        queries.append("urdu songs")

    if len(queries) < 5:
        queries.extend(TRENDING_STYLES)

    bad_words = [
        "slowed", "reverb", "lofi", "8d", "live", "mix", "dj remix",
        "bass boosted", "cover", "karaoke", "instrumental", "sped up",
    ]

    final = []
    for q in queries:
        q_lower = q.lower()
        if not any(bad in q_lower for bad in bad_words):
            if q not in final and len(q) > 3:
                final.append(q)

    return final[:20]


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
            duration = details.get("duration_min", "0:00") or "0:00"

            bad_words = [
                "slowed", "reverb", "8d", "lofi", "live", "mix", "dj remix",
                "bass boosted", "cover", "karaoke", "instrumental", "sped up",
            ]
            if any(x in title for x in bad_words):
                continue

            if title.strip() == last_title.lower().strip():
                continue

            try:
                mins = int(duration.split(":")[0])
                if mins < 2 or mins > 10:
                    continue
            except Exception:
                pass

            score = 0

            match_count = sum(1 for w in original_words[:5] if w in title and len(w) > 3)
            score += match_count * 15

            if artist and artist.lower() in title:
                score += 50
                if title.startswith(artist.lower()):
                    score += 30

            if movie and movie.lower() in title:
                score += 45

            if any(x in title for x in LANG_DB.get(lang, [])):
                score += 20

            if mood != "normal":
                mood_keywords = MOOD_DB.get(mood, [])
                if any(x in title for x in mood_keywords):
                    score += 15

            if not await is_repeat(chat_id, vidid):
                score += 50

            candidates.append((score, vidid, details))

        except Exception:
            continue

        await asyncio.sleep(0.2)

    candidates.sort(key=lambda x: x[0], reverse=True)

    if candidates:
        best = candidates[0]
        return best[1], best[2]

    return None, None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🖼 THUMBNAIL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_thumbnail_direct(video_id):
    urls = [
        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
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
# 🇮🇳 INDIAN EMOJI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_indian_emoji():
    emojis = ["🇮🇳","🎧","❤️","🎶","✨","🎤","💖","🎵","🔥","💫","🎸","💕","🪩","🌙","💘","🥰","🎼","⚡","💞","🦋","🎶","💜","🎤","🌸","🕺","💃","💝","🎧","🌈","❣️","🪘","💗","✨","🔥"]
    return random.choice(emojis)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 MAIN AUTOPLAY FUNCTION
#
# FIX 1: Signature → (chat_id, original_chat_id, last_title)
#         call.py passes popped song's title so it's never empty
# FIX 2: mystic bug → send real app.send_message() first,
#         pass that message object to stream() not the client
# FIX 3: yt.track() verified to exist in YouTubeAPI — no change needed
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_play_next(
    chat_id: int,
    original_chat_id: int,
    last_title: str = "",
) -> bool:
    """
    Search for next Indian song smartly based on last song's context.
    Returns True if successfully started, False otherwise.
    """
    from VISHALMUSIC.utils.database import get_lang
    from VISHALMUSIC.utils.stream.stream import stream
    from VISHALMUSIC.core.call import VISHAL
    from strings import get_string

    # Double-play protection
    if AUTO_PLAYING.get(chat_id):
        return False

    AUTO_PLAYING[chat_id] = True

    try:
        data = await autoplay_db.find_one({"chat_id": chat_id})
        if not data or not data.get("status"):
            return False

        indian_emoji = get_indian_emoji()

        # FIX 2: Send real message — this becomes 'mystic' for stream()
        try:
            msg = await app.send_message(
                original_chat_id,
                f"{indian_emoji} ᴀᴜᴛᴏᴘʟᴀʏ → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ ꜱᴏɴɢ...........",
            )
        except Exception:
            return False

        # FIX 1: Use last_title passed from call.py (from popped item)
        # Fallback to queue if still available, else default
        if not last_title:
            queue = db.get(chat_id)
            if queue and len(queue) > 0:
                last_title = queue[0].get("title", "latest hindi song")
            else:
                last_title = "latest hindi song"

        lang = detect_lang(last_title)
        mood = detect_mood(last_title)
        artist = extract_artist(last_title)
        movie = detect_movie(last_title)

        queries = build_smart_queries(last_title, artist, movie, lang, mood)

        vidid, details = await get_best_song(
            chat_id, queries, last_title, artist, movie, mood, lang
        )

        # Fallback chain
        if not vidid and movie:
            details, vidid = await yt.track(f"{movie} all songs")

        if not vidid and artist:
            details, vidid = await yt.track(f"{artist} hits")

        if not vidid and lang:
            details, vidid = await yt.track(f"{lang} trending songs")

        if not vidid:
            details, vidid = await yt.track("latest bollywood hits 2025")

        if not vidid:
            try:
                await msg.edit_text("❌ ɴᴏ ꜱᴏɴɢ ꜰᴏᴜɴᴅ")
            except Exception:
                pass
            return False

        await add_recent(chat_id, vidid)

        link = f"https://youtube.com/watch?v={vidid}"

        try:
            thumb = details.get("thumb", "")
            if not thumb or not thumb.startswith("http"):
                thumb = await get_thumbnail_direct(vidid)
        except Exception:
            thumb = await get_thumbnail_direct(vidid)

        language = await get_lang(chat_id)
        _ = get_string(language)

        # Stop current stream cleanly before starting new one
        try:
            await VISHAL.stop_stream(chat_id)
            await asyncio.sleep(1)
        except Exception:
            pass

        # FIX 2: Pass msg (real message) as mystic — NOT the client
        await stream(
            _,
            msg,                                    # ← real message object
            app.id,
            {
                "link": link,
                "vidid": vidid,
                "title": details.get("title", "🇮🇳 ꜱɪᴍɪʟᴀʀ ɪɴᴅɪᴀɴ ꜱᴏɴɢ"),
                "duration_min": details.get("duration_min", "00:00"),
                "thumb": thumb,
            },
            chat_id,
            "🔁 ᴀᴜᴛᴏᴘʟᴀʏ",
            original_chat_id,
            video=False,
            streamtype="youtube",
        )

        try:
            await msg.delete()
        except Exception:
            pass

        return True

    except Exception:
        return False

    finally:
        AUTO_PLAYING.pop(chat_id, None)
