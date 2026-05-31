import asyncio
import re
import time
import aiohttp
import json

from VISHALMUSIC import app
from VISHALMUSIC.core.mongo import mongodb
from VISHALMUSIC.misc import db
from VISHALMUSIC.platforms.Youtube import YouTubeAPI

yt = YouTubeAPI()
autoplay_db = mongodb.autoplay

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SYSTEM STORAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECENT = {}
RECENT_TITLES = {}
AUTO_PLAYING = {}
LAST_SONG_CONTEXT = {}  # 🔥 Stores last song details for context

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONTEXT SAVER (Save playing song details)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def save_song_context(chat_id, title, vidid, duration, artist=None, movie=None):
    """Save current playing song details for next autoplay"""
    LAST_SONG_CONTEXT[chat_id] = {
        "title": title,
        "vidid": vidid,
        "duration": duration,
        "artist": artist or extract_artist(title),
        "movie": movie or extract_movie(title),
        "timestamp": time.time(),
        "core_words": extract_core_words(title)
    }
    
    # Also save to database for persistence (optional)
    try:
        await mongodb.song_context.update_one(
            {"chat_id": chat_id},
            {"$set": LAST_SONG_CONTEXT[chat_id]},
            upsert=True
        )
    except:
        pass

async def get_song_context(chat_id):
    """Get saved context for chat"""
    if chat_id in LAST_SONG_CONTEXT:
        return LAST_SONG_CONTEXT[chat_id]
    
    # Try to load from database
    try:
        data = await mongodb.song_context.find_one({"chat_id": chat_id})
        if data:
            del data["_id"]
            LAST_SONG_CONTEXT[chat_id] = data
            return data
    except:
        pass
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DYNAMIC EXTRACTORS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def extract_core_words(title):
    """Extract unique meaningful words from title"""
    if not title:
        return []
    
    t = title.lower()
    t = re.sub(r"\([^)]*\)", "", t)
    t = re.sub(r"\[[^\]]*\]", "", t)
    
    for sep in [" - ", " | ", " — ", " ft ", " feat "]:
        if sep in t:
            t = t.split(sep)[0]
            break
    
    words = re.findall(r"[a-z]+(?:[a-z]+)*", t)
    noise = ["the", "and", "for", "with", "official", "video", "lyrics", "hd", "4k", "song", "new", "latest", "full", "audio"]
    
    result = []
    for w in words:
        if len(w) > 3 and w not in noise:
            result.append(w)
    
    return result

def extract_artist(title):
    """Extract artist name from title"""
    if not title:
        return ""
    
    t = title.strip()
    
    for sep in [" - ", " | ", " — ", " ft. ", " feat. ", " (", " ["]:
        if sep in t:
            candidate = t.split(sep)[0].strip()
            candidate = re.sub(r"(official|video|lyrics|hd|4k|new|latest|song)$", "", candidate, flags=re.I)
            candidate = re.sub(r"\s+", " ", candidate).strip()
            if len(candidate) > 2 and len(candidate) < 40:
                return candidate
    
    patterns = [
        r'^(.+?)\s+-\s+.+$',
        r'^(.+?)\s+\|\s+.+$',
        r'^(.+?)\s+\(.+\)$',
    ]
    for pattern in patterns:
        match = re.match(pattern, t)
        if match:
            artist = match.group(1).strip()
            if len(artist) > 2 and len(artist) < 40:
                return artist
    
    words = t.split()
    if len(words) > 2:
        candidate = " ".join(words[:3])
        if len(candidate) < 35:
            return candidate
    
    return ""

def extract_movie(title):
    """Extract movie name from title"""
    if not title:
        return ""
    
    t = title.lower()
    patterns = [
        r'from\s+([a-z0-9\s]+?)(?:\s+[a-z]+)?$',
        r'movie\s+([a-z0-9\s]+?)$',
        r'album\s+([a-z0-9\s]+?)$',
        r'\((?:from\s+)?([a-z0-9\s]+?)\)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, t)
        if match:
            candidate = match.group(1).strip()
            if len(candidate) > 2 and len(candidate) < 35:
                return candidate
    
    return ""

def normalize_title(title):
    if not title:
        return ""
    t = title.lower().strip()
    for sep in [" - ", " | ", " ft ", " feat "]:
        if sep in t:
            t = t.split(sep)[0]
    t = re.sub(r"[\(\[{].*?[\)\]}]", "", t)
    t = re.sub(r"\b(official|video|lyrics|hd|4k|song|audio|full|new|latest)\b", "", t)
    return re.sub(r"\s+", " ", t).strip()

def same_song(a, b):
    if not a or not b:
        return False
    a = a.lower().strip()
    b = b.lower().strip()
    
    if a == b:
        return True
    if len(a) > 5 and len(b) > 5:
        if a in b or b in a:
            return True
    
    words_a = set(a.split())
    words_b = set(b.split())
    if words_a and words_b:
        common = len(words_a & words_b)
        total = max(len(words_a), len(words_b))
        if common / total > 0.65:
            return True
    
    return False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REPEAT PROTECTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_repeat(chat_id, vidid, title=""):
    now = time.time()
    MEMORY_TIME = 86400  # 24 hours
    
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id] = [(v, t) for v, t in RECENT[chat_id] if now - t < MEMORY_TIME]
    
    if vidid in [v for v, _ in RECENT[chat_id]]:
        return True
    
    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id] = [(n, t) for n, t in RECENT_TITLES[chat_id] if now - t < MEMORY_TIME]
            for stored_norm, _ in RECENT_TITLES[chat_id]:
                if same_song(stored_norm, norm):
                    return True
    return False

async def add_recent(chat_id, vidid, title=""):
    if not vidid:
        return
    now = time.time()
    MEMORY_TIME = 86400
    
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id].append((vidid, now))
    if len(RECENT[chat_id]) > 200:
        RECENT[chat_id] = RECENT[chat_id][-200:]
    
    if title:
        norm = normalize_title(title)
        if norm and len(norm) >= 4:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id].append((norm, now))
            if len(RECENT_TITLES[chat_id]) > 200:
                RECENT_TITLES[chat_id] = RECENT_TITLES[chat_id][-200:]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  QUERY BUILDER (BASED ON CONTEXT)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_queries_from_context(context):
    """Build search queries based on saved context"""
    queries = []
    
    title = context.get("title", "")
    artist = context.get("artist", "")
    movie = context.get("movie", "")
    core_words = context.get("core_words", [])
    
    # Original title (highest priority)
    clean = normalize_title(title)
    if clean and len(clean) > 4:
        queries.append(clean)
    
    # Same artist
    if artist and len(artist) > 2:
        queries.append(f"{artist} songs")
        queries.append(f"{artist} new song")
        queries.append(f"{artist} hit")
    
    # Same movie
    if movie and len(movie) > 2:
        queries.append(f"{movie} songs")
        queries.append(f"{movie} song")
    
    # Artist + Movie combo
    if artist and movie:
        queries.insert(0, f"{artist} {movie} song")
    
    # Core words
    if len(core_words) >= 2:
        queries.append(" ".join(core_words[:3]))
    
    # Generic (low priority)
    queries.append("popular songs")
    queries.append("trending music")
    
    # Filter
    seen = set()
    final = []
    for q in queries:
        q_lower = q.lower()
        bad = ["slowed", "reverb", "lofi", "live", "cover", "remix", "english"]
        if not any(b in q_lower for b in bad):
            if q not in seen and len(q) > 3 and len(q) < 60:
                seen.add(q)
                final.append(q)
    
    return final[:12]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONTEXT SCORING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def calculate_context_score(new_title, context):
    """Score new song based on saved context"""
    if not context:
        return 50
    
    score = 0
    new_lower = new_title.lower()
    
    # Artist match (highest)
    artist = context.get("artist", "")
    if artist and artist.lower() in new_lower:
        score += 100
    
    # Movie match
    movie = context.get("movie", "")
    if movie and movie.lower() in new_lower:
        score += 80
    
    # Core words match
    core_words = context.get("core_words", [])
    for w in core_words:
        if len(w) > 3 and w in new_lower:
            score += 15
    
    # Title similarity
    old_title = context.get("title", "")
    similarity = calculate_similarity(old_title, new_title)
    score += similarity * 50
    
    return score

def calculate_similarity(t1, t2):
    if not t1 or not t2:
        return 0
    words1 = set(re.findall(r"[a-z]+", t1.lower()))
    words2 = set(re.findall(r"[a-z]+", t2.lower()))
    words1 = {w for w in words1 if len(w) > 2}
    words2 = {w for w in words2 if len(w) > 2}
    if not words1 or not words2:
        return 0
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FIND SONG (BASED ON CONTEXT)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def find_song_based_on_context(chat_id, context, last_vidid):
    """Find next song based on saved context"""
    if not context:
        return None, None
    
    queries = build_queries_from_context(context)
    candidates = []
    
    for q in queries:
        try:
            info, vid = await yt.track(q)
            if not vid or vid == last_vidid:
                continue
            
            title = info.get("title", "").lower()
            duration = info.get("duration_min", "0:00")
            
            # Duration check
            try:
                if ":" in duration:
                    mins = int(duration.split(":")[0])
                else:
                    mins = int(float(duration))
                if mins < 1.5 or mins > 8:
                    continue
            except:
                continue
            
            # No compilations
            t_lower = title.lower()
            comp_patterns = [r'top\s+\d+', r'\d+\s+hits', r'non[- ]?stop', r'jukebox', r'playlist']
            if any(re.search(p, t_lower) for p in comp_patterns):
                continue
            
            # Score based on context
            score = calculate_context_score(title, context)
            
            # Repeat check
            if await is_repeat(chat_id, vid, title):
                continue
            
            if score > 30:
                candidates.append((score, vid, info))
                
        except Exception:
            continue
        await asyncio.sleep(0.1)
    
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1], candidates[0][2]
    
    return None, None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  THUMBNAIL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def get_thumbnail(vid):
    async with aiohttp.ClientSession() as s:
        for url in [f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg", f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"]:
            try:
                async with s.get(url) as r:
                    if r.status == 200:
                        return url
            except:
                continue
    return f"https://img.youtube.com/vi/{vid}/mqdefault.jpg"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN AUTOPLAY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def auto_play_next(chat_id, original_chat_id, last_title="", last_vidid=""):
    from VISHALMUSIC.utils.database import get_lang
    from VISHALMUSIC.utils.stream.stream import stream
    from strings import get_string
    
    if AUTO_PLAYING.get(chat_id):
        return False
    
    AUTO_PLAYING[chat_id] = True
    
    try:
        data = await autoplay_db.find_one({"chat_id": chat_id})
        if not data or not data.get("status"):
            return False
        
        # 🔥 Add current song to recent BEFORE searching
        if last_vidid and last_title:
            await add_recent(chat_id, last_vidid, last_title)
            # 🔥 Save context for next search
            await save_song_context(chat_id, last_title, last_vidid, "00:00")
        
        await app.send_message(original_chat_id, "🔄 ᴀᴜᴛᴏᴘʟᴀʏ → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ ʙᴀꜱᴇᴅ ᴏɴ ᴄᴜʀʀᴇɴᴛ ꜱᴏɴɢ...")
        
        # Get saved context
        context = await get_song_context(chat_id)
        
        # If no context, create from last_title
        if not context and last_title:
            context = {
                "title": last_title,
                "vidid": last_vidid,
                "artist": extract_artist(last_title),
                "movie": extract_movie(last_title),
                "core_words": extract_core_words(last_title)
            }
        
        # Find next song based on context
        vid, info = await find_song_based_on_context(chat_id, context, last_vidid)
        
        # Fallbacks
        if not vid and context:
            artist = context.get("artist", "")
            if artist:
                info, vid = await yt.track(f"{artist} songs")
        if not vid:
            info, vid = await yt.track("popular songs")
        if not vid:
            info, vid = await yt.track("trending music")
        
        if not vid:
            return False
        
        new_title = info.get("title", "")
        await add_recent(chat_id, vid, new_title)
        
        # 🔥 Save new song context for next autoplay
        await save_song_context(chat_id, new_title, vid, info.get("duration_min", "00:00"))
        
        await stream(
            get_string(await get_lang(chat_id)),
            None,
            app.id,
            {
                "link": f"https://youtube.com/watch?v={vid}",
                "vidid": vid,
                "title": info.get("title", "🎵 ꜱᴏɴɢ"),
                "duration_min": info.get("duration_min", "00:00"),
                "thumb": await get_thumbnail(vid),
            },
            chat_id,
            "🔁 ᴀᴜᴛᴏᴘʟᴀʏ",
            original_chat_id,
            video=False,
            streamtype="youtube",
        )
        return True
        
    except Exception as e:
        return False
    finally:
        AUTO_PLAYING.pop(chat_id, None)
