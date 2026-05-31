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
LAST_SONG_CONTEXT = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STRONG NORMALIZATION (Fix for Diwaniyat repeat)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def normalize_title_strong(title):
    """Super strong normalization - removes everything except core words"""
    if not title:
        return ""
    
    t = title.lower().strip()
    
    # Remove everything after separators
    for sep in [" - ", " | ", " — ", " ft ", " feat ", " (", " [", " {"]:
        if sep in t:
            t = t.split(sep)[0]
            break
    
    # Remove bracketed content
    t = re.sub(r"[\(\[{][^\)\]\}]*[\)\]}]", "", t)
    
    # Remove all special characters
    t = re.sub(r"[^a-z0-9\s]", "", t)
    
    # Remove common noise words
    noise = [
        "official", "video", "music", "audio", "lyrics", "lyrical", "lyric",
        "full", "hd", "hq", "4k", "8k", "song", "new", "latest", "remix",
        "cover", "reaction", "visualizer", "teaser", "promo", "slowed",
        "reverb", "lofi", "sped", "up", "version", "original", "mix", "dj"
    ]
    
    for w in noise:
        t = re.sub(rf"\b{w}\b", "", t)
    
    # Remove extra spaces
    t = re.sub(r"\s+", " ", t).strip()
    
    return t


def is_same_song_strong(title1, title2):
    """Strong check if two titles are the same song"""
    if not title1 or not title2:
        return False
    
    n1 = normalize_title_strong(title1)
    n2 = normalize_title_strong(title2)
    
    if not n1 or not n2:
        return False
    
    # Exact match after normalization
    if n1 == n2:
        return True
    
    # One contains the other
    if len(n1) > 3 and len(n2) > 3:
        if n1 in n2 or n2 in n1:
            return True
    
    # Word overlap (80% or more)
    words1 = set(n1.split())
    words2 = set(n2.split())
    
    if words1 and words2:
        common = len(words1 & words2)
        total = max(len(words1), len(words2))
        ratio = common / total if total > 0 else 0
        
        if ratio >= 0.8:
            return True
    
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONTEXT FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def save_song_context(chat_id, title, vidid, duration, artist=None, movie=None):
    """Save current playing song details"""
    LAST_SONG_CONTEXT[chat_id] = {
        "title": title,
        "vidid": vidid,
        "duration": duration,
        "artist": artist or extract_artist(title),
        "movie": movie or extract_movie(title),
        "timestamp": time.time(),
        "core_words": extract_core_words(title)
    }
    
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REPEAT PROTECTION (48 hours memory)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def is_repeat(chat_id, vidid, title=""):
    now = time.time()
    MEMORY_TIME = 172800  # 48 HOURS
    
    # VIDID check
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id] = [(v, t) for v, t in RECENT[chat_id] if now - t < MEMORY_TIME]
    
    if vidid in [v for v, _ in RECENT[chat_id]]:
        return True
    
    # Strong title check
    if title:
        if chat_id not in RECENT_TITLES:
            RECENT_TITLES[chat_id] = []
        
        RECENT_TITLES[chat_id] = [(n, t) for n, t in RECENT_TITLES[chat_id] if now - t < MEMORY_TIME]
        
        norm_title = normalize_title_strong(title)
        
        for stored_norm, _ in RECENT_TITLES[chat_id]:
            if is_same_song_strong(stored_norm, norm_title):
                return True
    
    return False

async def add_recent(chat_id, vidid, title=""):
    if not vidid:
        return
    
    now = time.time()
    MEMORY_TIME = 172800  # 48 hours
    MAX_HISTORY = 300
    
    # Add VIDID
    if chat_id not in RECENT:
        RECENT[chat_id] = []
    RECENT[chat_id].append((vidid, now))
    if len(RECENT[chat_id]) > MAX_HISTORY:
        RECENT[chat_id] = RECENT[chat_id][-MAX_HISTORY:]
    
    # Add strong normalized title
    if title:
        norm_title = normalize_title_strong(title)
        if norm_title and len(norm_title) >= 3:
            if chat_id not in RECENT_TITLES:
                RECENT_TITLES[chat_id] = []
            RECENT_TITLES[chat_id].append((norm_title, now))
            if len(RECENT_TITLES[chat_id]) > MAX_HISTORY:
                RECENT_TITLES[chat_id] = RECENT_TITLES[chat_id][-MAX_HISTORY:]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  QUERY BUILDER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_queries_from_context(context):
    """Build search queries based on saved context"""
    queries = []
    
    title = context.get("title", "")
    artist = context.get("artist", "")
    movie = context.get("movie", "")
    core_words = context.get("core_words", [])
    
    # Original title (highest priority)
    clean = normalize_title_strong(title)
    if clean and len(clean) > 4:
        queries.append(clean)
    
    # Same artist
    if artist and len(artist) > 2:
        queries.append(f"{artist} songs")
        queries.append(f"{artist} new song")
    
    # Same movie
    if movie and len(movie) > 2:
        queries.append(f"{movie} songs")
    
    # Artist + Movie combo
    if artist and movie:
        queries.insert(0, f"{artist} {movie} song")
    
    # Core words
    if len(core_words) >= 2:
        queries.append(" ".join(core_words[:3]))
    
    # Generic
    queries.append("popular songs")
    queries.append("trending music")
    
    # Filter
    seen = set()
    final = []
    for q in queries:
        q_lower = q.lower()
        bad = ["slowed", "reverb", "lofi", "live", "cover", "remix", "english", "top", "hits", "jukebox"]
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
    new_normalized = normalize_title_strong(new_title)
    
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
    old_normalized = normalize_title_strong(old_title)
    
    if old_normalized and new_normalized:
        if old_normalized == new_normalized:
            score -= 200  # Same song = big penalty
        elif old_normalized in new_normalized or new_normalized in old_normalized:
            score -= 100
    
    return score

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FIND SONG
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
            
            # Duration check (1.5 to 8 minutes)
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
            comp_patterns = [r'top\s+\d+', r'\d+\s+hits', r'non[- ]?stop', r'jukebox', r'playlist', r'best of']
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
        
        # Add current song to recent
        if last_vidid and last_title:
            await add_recent(chat_id, last_vidid, last_title)
            await save_song_context(chat_id, last_title, last_vidid, "00:00")
        
        await app.send_message(original_chat_id, "🔄 ᴀᴜᴛᴏᴘʟᴀʏ → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ...")
        
        # Get saved context
        context = await get_song_context(chat_id)
        
        if not context and last_title:
            context = {
                "title": last_title,
                "vidid": last_vidid,
                "artist": extract_artist(last_title),
                "movie": extract_movie(last_title),
                "core_words": extract_core_words(last_title)
            }
        
        # Find next song
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
        
    except Exception:
        return False
    finally:
        AUTO_PLAYING.pop(chat_id, None)
