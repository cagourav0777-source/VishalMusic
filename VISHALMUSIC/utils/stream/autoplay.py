"""
autoplay.py — YouTube-Style Autoplay for VishalMusic
=====================================================

How it works (identical to YouTube's own autoplay):
  1. Song ends → grab the video-id of the song that just finished.
  2. Run:  yt-dlp --dump-json <url>
     YouTube embeds its own "related_videos" list in every video page JSON.
  3. Walk that list; skip songs that are:
       • already played in the last 2 hours  (per-chat RECENT history)
       • shorter than 1:30 or longer than 8:00  (no shorts or 3-hour albums)
       • karaoke / live-concert / lofi / instrumental / mashup / jukebox / etc.
       • in a different language than the current song
  4. Download and play the first video that passes all checks.
  5. If yt-dlp can't fetch related videos (network, age-gate, etc.) → fall back
     to a smart search query that stays in the same language.

Language enforcement:
  • Hindi  → only Hindi / Bollywood songs next
  • Punjabi → only Punjabi songs next
  • Tamil / Telugu / Bengali / Bhojpuri / Haryanvi → same language
  • English → only English songs next
  • Hindi ↔ Punjabi ↔ Haryanvi ↔ Bhojpuri mix freely (same Indian family)
"""

import asyncio
import json
import random
import re
import time
from typing import Dict, List, Optional, Tuple

import aiohttp

from VISHALMUSIC import app
from VISHALMUSIC.core.mongo import mongodb
from VISHALMUSIC.misc import db
from VISHALMUSIC.platforms.Youtube import YouTubeAPI, _cookies_args, _exec_proc

yt = YouTubeAPI()
_autoplay_db = mongodb.autoplay


# ═══════════════════════════════════════════════════════════════════════════════
# 🔒  DOUBLE-TRIGGER LOCK
#     Timestamp-based — won't hang forever after a bot crash / restart.
#     A plain boolean lock gets stuck when the process dies mid-autoplay.
# ═══════════════════════════════════════════════════════════════════════════════

_AUTO_LOCK: Dict[int, float] = {}
_LOCK_TTL  = 60  # seconds — any lock older than this is treated as expired


def _lock_acquire(chat_id: int) -> bool:
    ts = _AUTO_LOCK.get(chat_id, 0)
    if ts and (time.time() - ts) < _LOCK_TTL:
        return False          # lock is still fresh → someone else is working
    _AUTO_LOCK[chat_id] = time.time()
    return True


def _lock_release(chat_id: int) -> None:
    _AUTO_LOCK.pop(chat_id, None)


# ═══════════════════════════════════════════════════════════════════════════════
# 🕒  RECENT HISTORY  (per chat, 2-hour TTL)
#     Stores {vidid: timestamp} so the same song never repeats within 2 hours
#     even if YouTube keeps recommending it.
# ═══════════════════════════════════════════════════════════════════════════════

_RECENT: Dict[int, Dict[str, float]] = {}
_RECENT_TTL = 7200  # 2 hours in seconds


def _mark_recent(chat_id: int, vidid: str) -> None:
    if chat_id not in _RECENT:
        _RECENT[chat_id] = {}
    # Expire old entries first to avoid unbounded growth
    now = time.time()
    _RECENT[chat_id] = {
        v: t for v, t in _RECENT[chat_id].items()
        if now - t < _RECENT_TTL
    }
    _RECENT[chat_id][vidid] = now


def _is_recent(chat_id: int, vidid: str) -> bool:
    bucket = _RECENT.get(chat_id, {})
    ts = bucket.get(vidid, 0)
    return bool(ts) and (time.time() - ts) < _RECENT_TTL


# ═══════════════════════════════════════════════════════════════════════════════
# ⏱  DURATION LIMITS
#     Normal songs: 1:30 – 8:00 (90 s – 480 s)
#     Anything above 8 minutes is an album / podcast / compilation / lecture.
#     Anything below 90 seconds is a short clip or jingle.
# ═══════════════════════════════════════════════════════════════════════════════

_MIN_SEC = 90
_MAX_SEC = 480


def _duration_ok(seconds: int) -> bool:
    return _MIN_SEC <= seconds <= _MAX_SEC


def _parse_duration_min(dur_str: str) -> int:
    """Convert 'M:SS' or 'H:MM:SS' string to total seconds. Returns 0 on failure."""
    try:
        parts = [int(p) for p in str(dur_str).split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    except Exception:
        pass
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# 🌐  LANGUAGE DETECTION
#     Step 1: Unicode script ranges (most reliable — works for non-Roman titles)
#     Step 2: Romanised keyword hints (for "Arijit Singh", "Diljit Dosanjh" etc.)
#     Step 3: Pure-Latin title with no Indian hints → English
#     Default fallback: "hindi"  (safe for an Indian music bot)
# ═══════════════════════════════════════════════════════════════════════════════

_RE_DEVANAGARI = re.compile(r"[\u0900-\u097F]")  # Hindi / Marathi / Nepali
_RE_GURMUKHI   = re.compile(r"[\u0A00-\u0A7F]")  # Punjabi
_RE_TAMIL      = re.compile(r"[\u0B80-\u0BFF]")
_RE_TELUGU     = re.compile(r"[\u0C00-\u0C7F]")
_RE_BENGALI    = re.compile(r"[\u0980-\u09FF]")
_RE_LATIN_ONLY = re.compile(r"^[A-Za-z0-9 .,'\-!&()\[\]]+$")

# Keyword → language mapping (checked in order; more specific first)
_KEYWORD_LANG: List[Tuple[str, List[str]]] = [
    ("punjabi",  [
        "punjabi", "sidhu moosewala", "diljit", "karan aujla", "ammy virk",
        "ap dhillon", "moosewala", "bhangra", "jatt", "gurnam bhullar",
        "babbu maan", "satinder sartaaj",
    ]),
    ("haryanvi", ["haryanvi", "khasa aala chahar", "masoom sharma", "renuka panwar"]),
    ("bhojpuri", ["bhojpuri", "pawan singh", "khesari lal", "nirahua"]),
    ("hindi",    [
        "hindi", "bollywood", "arijit singh", "jubin nautiyal", "atif aslam",
        "neha kakkar", "shreya ghoshal", "sonu nigam", "kishore kumar",
        "lata mangeshkar", "mohammed rafi", "kumar sanu", "udit narayan",
        "badshah", "yo yo honey singh", "vishal mishra", "armaan malik",
        "darshan raval", "b praak", "jassi gill",
    ]),
    ("tamil",    ["tamil", "kollywood", "anirudh", "sid sriram", "harrish jayaraj"]),
    ("telugu",   ["telugu", "tollywood", "devi sri prasad", "thaman"]),
    ("bengali",  ["bengali", "bangla", "arijit singh bengali"]),
    ("english",  ["english"]),
]

# Languages that mix freely (Indian family)
_INDIAN_FAMILY = {"hindi", "punjabi", "haryanvi", "bhojpuri", "urdu"}


def _detect_lang(title: str) -> str:
    """Return the language key for a song title."""
    if _RE_DEVANAGARI.search(title): return "hindi"
    if _RE_GURMUKHI.search(title):   return "punjabi"
    if _RE_TAMIL.search(title):      return "tamil"
    if _RE_TELUGU.search(title):     return "telugu"
    if _RE_BENGALI.search(title):    return "bengali"

    tl = title.lower()
    for lang, hints in _KEYWORD_LANG:
        if any(h in tl for h in hints):
            return lang

    # Pure Latin characters with no Indian hints → assume English
    if _RE_LATIN_ONLY.match(title.strip()):
        return "english"

    return "hindi"  # safe default for Indian music bot


def _lang_compatible(title: str, want: str) -> bool:
    """
    Return True if the candidate song's language is compatible with `want`.
    The Indian family (hindi/punjabi/haryanvi/bhojpuri) can mix freely.
    If title is empty we can't tell → allow it.
    """
    if not title.strip():
        return True
    got = _detect_lang(title)
    if got == want:
        return True
    if want in _INDIAN_FAMILY and got in _INDIAN_FAMILY:
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# 🚫  BAD-CONTENT FILTER
#     Titles containing these keywords are almost never normal music tracks.
# ═══════════════════════════════════════════════════════════════════════════════

_BAD_KEYWORDS = {
    "slowed", "reverb", "8d audio", "lofi", "lo-fi", "lo fi",
    "live concert", "live performance", "live at", "karaoke",
    "instrumental", "bass boosted", "sped up", "nightcore",
    "cover by", "reaction", "interview", "behind the scenes",
    "making of", "#shorts", "podcast", "lecture", "full album",
    "full movie", "jukebox", "mashup", "medley", "nonstop",
    "non stop", "4 hours", "3 hours", "2 hours", "1 hour",
}


def _title_ok(title: str) -> bool:
    t = title.lower()
    return not any(bad in t for bad in _BAD_KEYWORDS)


# ═══════════════════════════════════════════════════════════════════════════════
# 📡  STEP 1 — Fetch YouTube's related_videos list via yt-dlp
#     YouTube embeds the same related-video list it shows on the sidebar
#     directly inside the video page JSON.  yt-dlp exposes it as
#     info["related_videos"].  This is exactly how YouTube's own autoplay works.
# ═══════════════════════════════════════════════════════════════════════════════

async def _fetch_related(vidid: str) -> List[dict]:
    """
    Ask yt-dlp to dump the full JSON for a video URL.
    Parse out the related_videos list.
    Returns [] on any failure.
    """
    url = f"https://www.youtube.com/watch?v={vidid}"
    try:
        stdout, _ = await asyncio.wait_for(
            _exec_proc("yt-dlp", *_cookies_args(), "--dump-json", "--no-playlist", url),
            timeout=25,
        )
    except Exception:
        return []

    if not stdout:
        return []

    try:
        info = json.loads(stdout.decode("utf-8", errors="ignore"))
        related = info.get("related_videos") or []
        return related if isinstance(related, list) else []
    except Exception:
        return []


def _extract_vidid(item: dict) -> str:
    """Pull the video-id out of a related_videos entry."""
    vid = item.get("id") or ""
    if vid and len(vid) >= 11:
        return vid
    # Sometimes it's buried in a url field
    url = item.get("url", "") or item.get("webpage_url", "")
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""


def _pick_related(chat_id: int, related: List[dict], want_lang: str) -> Optional[str]:
    """
    Walk YouTube's related list in order (YouTube sorts by relevance).
    Return the first video-id that:
      • is not in RECENT history
      • has a valid, non-empty id
      • passes duration check (90 s – 480 s)
      • passes title/content filter (no karaoke, live, etc.)
      • matches the current song's language

    If nothing matches the language, do a second pass ignoring language so we
    never return silence (better to play a nearby-language track than nothing).
    """
    def _check(item: dict, enforce_lang: bool) -> Optional[str]:
        vid = _extract_vidid(item)
        if not vid:
            return None
        if _is_recent(chat_id, vid):
            return None
        title = item.get("title") or ""
        if not _title_ok(title):
            return None
        if item.get("is_live"):
            return None
        dur = item.get("duration")
        if dur is not None:
            try:
                sec = int(dur)
                if not _duration_ok(sec):
                    return None
            except (ValueError, TypeError):
                pass
        if enforce_lang and not _lang_compatible(title, want_lang):
            return None
        return vid

    # First pass: language enforced
    for item in related:
        r = _check(item, enforce_lang=True)
        if r:
            return r

    # Second pass: relax language (better than silence)
    for item in related:
        r = _check(item, enforce_lang=False)
        if r:
            return r

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# 🔍  STEP 2 (FALLBACK) — Smart search when yt-dlp can't get related videos
#     Builds language-aware queries so we never play English after Hindi etc.
# ═══════════════════════════════════════════════════════════════════════════════

_NOISE_RE = re.compile(
    r"\b(official|video|lyrics|lyrical|audio|full|hd|hq|4k|"
    r"song|music|new|latest|visualizer|teaser|promo)\b",
    re.IGNORECASE,
)

# Artist keyword → full name (used to build better search queries)
_ARTIST_MAP = {
    "arijit":      "arijit singh",
    "jubin":       "jubin nautiyal",
    "atif":        "atif aslam",
    "sidhu":       "sidhu moosewala",
    "diljit":      "diljit dosanjh",
    "karan aujla": "karan aujla",
    "ammy":        "ammy virk",
    "badshah":     "badshah",
    "neha kakkar": "neha kakkar",
    "shreya":      "shreya ghoshal",
    "honey singh": "yo yo honey singh",
    "ap dhillon":  "ap dhillon",
    "b praak":     "b praak",
    "jassi gill":  "jassi gill",
    "darshan":     "darshan raval",
    "armaan":      "armaan malik",
}

# Language-specific generic pools — used when no artist can be extracted
_LANG_POOL: Dict[str, List[str]] = {
    "hindi": [
        "trending hindi songs 2025", "latest bollywood hits 2025",
        "popular hindi love songs 2025", "new bollywood songs 2025",
        "best arijit singh songs", "best jubin nautiyal songs",
        "hindi romantic songs 2025", "bollywood party songs 2025",
        "sad hindi songs 2025", "best atif aslam hindi songs",
        "top bollywood songs 2024 2025", "hit hindi songs",
    ],
    "punjabi": [
        "trending punjabi songs 2025", "latest punjabi hits 2025",
        "best diljit dosanjh songs", "karan aujla songs 2025",
        "new punjabi songs 2025", "top punjabi songs playlist",
        "punjabi love songs 2025", "ap dhillon songs",
    ],
    "english": [
        "trending english pop songs 2025", "top english hits 2025",
        "popular english songs 2025", "best pop songs 2024 2025",
        "new english songs 2025", "top billboard hits 2025",
    ],
    "tamil": [
        "trending tamil songs 2025", "kollywood hits 2025",
        "best anirudh ravichander songs", "new tamil songs 2025",
        "sid sriram songs", "top tamil songs playlist",
    ],
    "telugu": [
        "trending telugu songs 2025", "tollywood hits 2025",
        "new telugu songs 2025", "best telugu songs playlist",
    ],
    "bhojpuri": [
        "trending bhojpuri songs 2025", "bhojpuri hits 2025",
        "pawan singh songs", "khesari lal songs", "bhojpuri love songs",
    ],
    "haryanvi": [
        "trending haryanvi songs 2025", "haryanvi hits 2025",
        "khasa aala chahar songs", "masoom sharma songs",
    ],
    "bengali": [
        "trending bengali songs 2025", "bangla hits 2025",
        "popular bangla songs playlist",
    ],
}


def _clean_title(title: str) -> str:
    """Strip noise words and parenthetical content from a song title."""
    t = _NOISE_RE.sub("", title)
    for sep in (" - ", " | ", " — ", " ft.", " feat.", " Ft.", " x "):
        if sep in t:
            t = t.split(sep)[0]
            break
    t = re.sub(r"[\(\[\{][^\)\]\}]{0,50}[\)\]\}]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _detect_artist(title: str) -> str:
    """Return the full artist name if a known keyword is found in the title."""
    tl = title.lower()
    for key, full in _ARTIST_MAP.items():
        if key in tl:
            return full
    return ""


def _build_queries(title: str, lang: str) -> List[str]:
    """
    Build an ordered list of search queries for the fallback path.
    Artist-specific queries come first, then language-specific pools.
    """
    clean  = _clean_title(title)
    artist = _detect_artist(title)
    pool   = _LANG_POOL.get(lang, _LANG_POOL["hindi"]).copy()
    random.shuffle(pool)

    queries: List[str] = []
    if artist:
        queries.append(f"{artist} best songs")
        queries.append(f"{artist} latest hits")
    if clean and len(clean) > 3:
        queries.append(f"{clean} similar songs")

    queries.extend(pool)
    return queries[:12]


async def _fallback_search(
    chat_id: int,
    title: str,
    last_vidid: str,
    lang: str,
) -> Tuple[Optional[str], Optional[dict]]:
    """
    Try each query from _build_queries() in order.
    Returns (vidid, details) for the first result that:
      • is not the song that just ended
      • is not in RECENT history
      • passes duration check
      • is compatible with the current language
    Returns (None, None) if nothing is found.
    """
    for query in _build_queries(title, lang):
        try:
            details, vidid = await yt.track(query)
        except Exception:
            await asyncio.sleep(0.2)
            continue

        if not vidid:
            continue
        if vidid == last_vidid:
            continue
        if _is_recent(chat_id, vidid):
            continue

        # Duration check using the "M:SS" string from yt.track()
        dur_str = details.get("duration_min") or "0:00"
        sec = _parse_duration_min(str(dur_str))
        if sec and not _duration_ok(sec):
            continue

        # Title filter (no karaoke etc.)
        result_title = details.get("title", "")
        if not _title_ok(result_title):
            continue

        # Language check
        if result_title and not _lang_compatible(result_title, lang):
            continue

        return vidid, details

    return None, None


# ═══════════════════════════════════════════════════════════════════════════════
# 🖼  THUMBNAIL HELPER
#     yt.track() already gives us a thumb URL, but sometimes it's empty or
#     low-resolution.  This tries the best available YouTube thumbnail CDN URLs.
# ═══════════════════════════════════════════════════════════════════════════════

async def _best_thumb(vidid: str, details_thumb: str = "") -> str:
    if details_thumb and details_thumb.startswith("http"):
        return details_thumb
    urls = [
        f"https://img.youtube.com/vi/{vidid}/maxresdefault.jpg",
        f"https://img.youtube.com/vi/{vidid}/hqdefault.jpg",
        f"https://img.youtube.com/vi/{vidid}/mqdefault.jpg",
    ]
    try:
        async with aiohttp.ClientSession() as sess:
            for url in urls:
                try:
                    async with sess.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                        if r.status == 200:
                            return url
                except Exception:
                    continue
    except Exception:
        pass
    return urls[-1]  # last resort


# ═══════════════════════════════════════════════════════════════════════════════
# 🎲  COSMETIC HELPER
# ═══════════════════════════════════════════════════════════════════════════════

_EMOJIS = [
    "🇮🇳", "🎧", "❤️", "🎶", "✨", "🎤", "💖", "🎵", "🔥", "💫",
    "🎸", "💕", "🪩", "🌙", "💘", "🥰", "🎼", "⚡", "💞", "🦋",
    "💜", "🌸", "🕺", "💃", "💝", "🌈", "❣️", "🪘", "💗", "🎹",
]


def _emoji() -> str:
    return random.choice(_EMOJIS)


# ═══════════════════════════════════════════════════════════════════════════════
# 🚀  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

async def auto_play_next(
    chat_id: int,
    original_chat_id: int,
    last_title: str = "",
    last_vidid: str = "",
) -> bool:
    """
    Called by call.py → play() when the queue runs empty and autoplay is ON.

    Returns True  → successfully started the next song.
    Returns False → autoplay is OFF, or no suitable song was found.

    Flow:
      1. Acquire a per-chat timestamp lock (prevents double-trigger).
      2. Check autoplay is enabled for this chat in MongoDB.
      3. Mark the just-finished song in RECENT history.
      4. Detect the language of the just-finished song.
      5. Ask yt-dlp for YouTube's own related_videos list.
      6. Pick the first valid, non-repeated, same-language related video.
      7. If no suitable related video → smart search fallback (same language).
      8. Download and start playing via stream().
    """
    from strings import get_string
    from VISHALMUSIC.utils.database import get_lang
    from VISHALMUSIC.utils.stream.stream import stream

    # ── 1. Double-trigger guard ─────────────────────────────────────────────
    if not _lock_acquire(chat_id):
        return False

    try:
        # ── 2. Autoplay ON/OFF check ────────────────────────────────────────
        data = await _autoplay_db.find_one({"chat_id": chat_id})
        if not data or not data.get("status"):
            return False

        # ── 3. Mark finished song as recently played ────────────────────────
        # Do this BEFORE searching so it can never be picked again.
        if last_vidid:
            _mark_recent(chat_id, last_vidid)

        # ── Send "fetching…" status message ────────────────────────────────
        try:
            status_msg = await app.send_message(
                original_chat_id,
                f"{_emoji()} ᴀᴜᴛᴏᴘʟᴀʏ → ꜰᴇᴛᴄʜɪɴɢ ɴᴇxᴛ ꜱᴏɴɢ...",
            )
        except Exception:
            return False

        # ── 4. Resolve last title if not supplied ───────────────────────────
        if not last_title:
            q = db.get(chat_id)
            last_title = (q[0].get("title", "") if q else "") or "latest hindi song"

        # ── 5. Detect language of the song that just ended ──────────────────
        # Every subsequent step uses this so we stay in the same language.
        song_lang = _detect_lang(last_title)

        # ── 6. PRIMARY: YouTube's own related_videos ────────────────────────
        next_vidid: Optional[str]  = None
        next_details: Optional[dict] = None

        if last_vidid:
            related = await _fetch_related(last_vidid)
            if related:
                picked = _pick_related(chat_id, related, song_lang)
                if picked:
                    # Fetch full metadata (title, duration, thumb) for the
                    # picked video-id so we can display it properly.
                    try:
                        next_details, next_vidid = await yt.track(
                            f"https://www.youtube.com/watch?v={picked}"
                        )
                        # yt.track() might return a different vidid when it
                        # resolves the URL through search; trust our pick.
                        next_vidid = picked
                    except Exception:
                        next_vidid   = picked
                        next_details = None

        # ── 7. FALLBACK: smart language-aware search ────────────────────────
        # Activates when:
        #   • last_vidid was empty (user played via text search, not a URL)
        #   • yt-dlp couldn't fetch related videos (network/age-gate)
        #   • all related videos were already in RECENT
        if not next_vidid:
            next_vidid, next_details = await _fallback_search(
                chat_id, last_title, last_vidid, song_lang
            )

        if not next_vidid:
            try:
                await status_msg.edit_text("❌ ᴀᴜᴛᴏᴘʟᴀʏ: ɴᴏ ꜱᴜɪᴛᴀʙʟᴇ ꜱᴏɴɢ ꜰᴏᴜɴᴅ")
            except Exception:
                pass
            return False

        # ── Mark the new song in RECENT before starting ─────────────────────
        _mark_recent(chat_id, next_vidid)

        # ── 8. Build metadata dict for stream() ─────────────────────────────
        yt_link = f"https://youtube.com/watch?v={next_vidid}"

        if next_details:
            title       = next_details.get("title")       or "🎵 ᴀᴜᴛᴏᴘʟᴀʏ ꜱᴏɴɢ"
            duration_min = next_details.get("duration_min") or "0:00"
            raw_thumb    = next_details.get("thumb")        or ""
        else:
            title        = "🎵 ᴀᴜᴛᴏᴘʟᴀʏ ꜱᴏɴɢ"
            duration_min = "0:00"
            raw_thumb    = ""

        thumb = await _best_thumb(next_vidid, raw_thumb)

        # ── Call stream() exactly as the normal play flow does ───────────────
        language = await get_lang(chat_id)
        _ = get_string(language)

        await stream(
            _,
            status_msg,
            app.id,
            {
                "link":         yt_link,
                "vidid":        next_vidid,
                "title":        title,
                "duration_min": duration_min,
                "thumb":        thumb,
            },
            chat_id,
            "🔁 ᴀᴜᴛᴏᴘʟᴀʏ",
            original_chat_id,
            video=False,
            streamtype="youtube",
        )

        try:
            await status_msg.delete()
        except Exception:
            pass

        return True

    except Exception:
        return False

    finally:
        _lock_release(chat_id)
