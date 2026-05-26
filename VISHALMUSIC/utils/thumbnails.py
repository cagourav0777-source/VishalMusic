import os
import re
import random
import aiofiles
import aiohttp
import requests

from bs4 import BeautifulSoup
from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps,
)

from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL
from VISHALMUSIC.core.dir import CACHE_DIR


# ============================================
# SIZE SETTINGS
# ============================================

WIDTH = 1280
HEIGHT = 720

PANEL_W, PANEL_H = 763, 545
PANEL_X = (WIDTH - PANEL_W) // 2
PANEL_Y = 88

TRANSPARENCY = 170
INNER_OFFSET = 36

THUMB_W, THUMB_H = 542, 273
THUMB_X = PANEL_X + (PANEL_W - THUMB_W) // 2
THUMB_Y = PANEL_Y + INNER_OFFSET

TITLE_X = 377
META_X = 377

TITLE_Y = THUMB_Y + THUMB_H + 10
META_Y = TITLE_Y + 45

BAR_X, BAR_Y = 388, META_Y + 45
BAR_RED_LEN = 280
BAR_TOTAL_LEN = 480

ICONS_W, ICONS_H = 415, 45
ICONS_X = PANEL_X + (PANEL_W - ICONS_W) // 2
ICONS_Y = BAR_Y + 48

MAX_TITLE_WIDTH = 580


# ============================================
# COLORS
# ============================================

ACCENTS = [
    (255, 0, 102),
    (255, 51, 153),
    (255, 102, 204),
    (0, 204, 255),
    (102, 204, 255),
    (153, 102, 255),
]


# ============================================
# TEXT LIMIT
# ============================================

def trim_to_width(text, font, max_width):

    ellipsis = "..."

    if font.getlength(text) <= max_width:
        return text

    for i in range(len(text), 0, -1):

        t = text[:i] + ellipsis

        if font.getlength(t) <= max_width:
            return t

    return ellipsis


# ============================================
# RANDOM ANIME WALLPAPER
# ============================================

async def get_random_wallpaper():

    try:

        url = "https://wallpapercave.com/anime-girl-laptop-wallpapers"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        images = []

        for img in soup.find_all("img"):

            src = img.get("src")

            if not src:
                continue

            if "wallpapers" in src:

                if src.startswith("//"):
                    src = "https:" + src

                elif src.startswith("/"):
                    src = "https://wallpapercave.com" + src

                images.append(src)

        if not images:
            return None

        return random.choice(images)

    except Exception as e:
        print(f"Wallpaper Error: {e}")
        return None


# ============================================
# DOWNLOAD IMAGE
# ============================================

async def download_image(url, save_path):

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(url) as resp:

                if resp.status == 200:

                    async with aiofiles.open(
                        save_path,
                        "wb"
                    ) as f:

                        await f.write(await resp.read())

                    return True

    except Exception as e:
        print(e)

    return False


# ============================================
# MAIN FUNCTION
# ============================================

async def get_thumb(videoid: str):

    cache_path = os.path.join(
        CACHE_DIR,
        f"{videoid}_anime.png"
    )

    if os.path.exists(cache_path):
        return cache_path

    # ============================================
    # YOUTUBE DATA
    # ============================================

    results = VideosSearch(
        f"https://www.youtube.com/watch?v={videoid}",
        limit=1
    )

    try:

        results_data = await results.next()

        data = results_data.get("result", [])[0]

        title = re.sub(
            r"\W+",
            " ",
            data.get("title", "Unknown Title")
        ).title()

        thumbnail = data.get(
            "thumbnails",
            [{}]
        )[0].get("url", YOUTUBE_IMG_URL)

        duration = data.get("duration")

        views = data.get(
            "viewCount",
            {}
        ).get("short", "Unknown Views")

    except Exception:

        title = "Unknown Title"
        thumbnail = YOUTUBE_IMG_URL
        duration = "0:00"
        views = "Unknown Views"

    # ============================================
    # LIVE CHECK
    # ============================================

    is_live = (
        not duration or
        str(duration).lower() in [
            "live",
            "live now",
            ""
        ]
    )

    end_text = "LIVE" if is_live else duration

    # ============================================
    # DOWNLOAD THUMBNAIL
    # ============================================

    thumb_path = os.path.join(
        CACHE_DIR,
        f"{videoid}_thumb.jpg"
    )

    await download_image(
        thumbnail,
        thumb_path
    )

    # ============================================
    # RANDOM BACKGROUND FROM WEBSITE
    # ============================================

    anime_path = os.path.join(
        CACHE_DIR,
        f"{videoid}_anime_bg.jpg"
    )

    anime_url = await get_random_wallpaper()

    bg_loaded = False

    if anime_url:

        ok = await download_image(
            anime_url,
            anime_path
        )

        if ok:

            try:

                bg = Image.open(anime_path).convert("RGBA")

                bg = bg.resize(
                    (WIDTH, HEIGHT)
                )

                bg_loaded = True

            except:
                pass

    # fallback
    if not bg_loaded:

        bg = Image.open(
            thumb_path
        ).convert("RGBA")

        bg = bg.resize(
            (WIDTH, HEIGHT)
        )

    # ============================================
    # PREMIUM EFFECTS
    # ============================================

    bg = bg.filter(
        ImageFilter.GaussianBlur(8)
    )

    dark = Image.new(
        "RGBA",
        bg.size,
        (0, 0, 0, 120)
    )

    bg = Image.alpha_composite(
        bg,
        dark
    )

    bg = ImageEnhance.Brightness(
        bg
    ).enhance(0.75)

    accent = random.choice(ACCENTS)

    # ============================================
    # GLASS PANEL
    # ============================================

    panel = bg.crop((
        PANEL_X,
        PANEL_Y,
        PANEL_X + PANEL_W,
        PANEL_Y + PANEL_H
    ))

    overlay = Image.new(
        "RGBA",
        (PANEL_W, PANEL_H),
        (255, 255, 255, TRANSPARENCY)
    )

    frosted = Image.alpha_composite(
        panel,
        overlay
    )

    mask = Image.new(
        "L",
        (PANEL_W, PANEL_H),
        0
    )

    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, PANEL_W, PANEL_H),
        50,
        fill=255
    )

    bg.paste(
        frosted,
        (PANEL_X, PANEL_Y),
        mask
    )

    draw = ImageDraw.Draw(bg)

    # ============================================
    # FONTS
    # ============================================

    try:

        title_font = ImageFont.truetype(
            "VISHALMUSIC/assets/thumb/font2.ttf",
            36
        )

        regular_font = ImageFont.truetype(
            "VISHALMUSIC/assets/thumb/font.ttf",
            20
        )

    except:

        title_font = ImageFont.load_default()
        regular_font = ImageFont.load_default()

    # ============================================
    # THUMBNAIL
    # ============================================

    thumb = Image.open(
        thumb_path
    ).convert("RGBA")

    thumb = thumb.resize(
        (THUMB_W, THUMB_H)
    )

    thumb_mask = Image.new(
        "L",
        thumb.size,
        0
    )

    ImageDraw.Draw(thumb_mask).rounded_rectangle(
        (0, 0, THUMB_W, THUMB_H),
        25,
        fill=255
    )

    bg.paste(
        thumb,
        (THUMB_X, THUMB_Y),
        thumb_mask
    )

    # ============================================
    # TITLE
    # ============================================

    title = trim_to_width(
        title,
        title_font,
        MAX_TITLE_WIDTH
    )

    draw.text(
        (TITLE_X + 2, TITLE_Y + 2),
        title,
        font=title_font,
        fill=(0, 0, 0)
    )

    draw.text(
        (TITLE_X, TITLE_Y),
        title,
        font=title_font,
        fill=accent
    )

    draw.text(
        (META_X, META_Y),
        f"YouTube | {views}",
        font=regular_font,
        fill=(40, 40, 40)
    )

    # ============================================
    # PROGRESS BAR
    # ============================================

    draw.line(
        (
            BAR_X,
            BAR_Y,
            BAR_X + BAR_TOTAL_LEN,
            BAR_Y
        ),
        fill="black",
        width=6
    )

    draw.line(
        (
            BAR_X,
            BAR_Y,
            BAR_X + BAR_RED_LEN,
            BAR_Y
        ),
        fill=accent,
        width=6
    )

    # ============================================
    # HEART
    # ============================================

    try:

        heart_font = ImageFont.truetype(
            "VISHALMUSIC/assets/thumb/font2.ttf",
            24
        )

    except:

        heart_font = ImageFont.load_default()

    draw.text(
        (
            BAR_X + BAR_RED_LEN - 15,
            BAR_Y - 32
        ),
        "♡",
        font=heart_font,
        fill=accent
    )

    # ============================================
    # TIME
    # ============================================

    draw.text(
        (BAR_X, BAR_Y + 15),
        "00:00",
        font=regular_font,
        fill="black"
    )

    draw.text(
        (
            BAR_X + BAR_TOTAL_LEN - 90,
            BAR_Y + 15
        ),
        end_text,
        font=regular_font,
        fill=accent
    )

    # ============================================
    # PLAYER ICONS
    # ============================================

    icons_path = "VISHALMUSIC/assets/thumb/play_icons.png"

    if os.path.exists(icons_path):

        icons = Image.open(
            icons_path
        ).convert("RGBA")

        icons = icons.resize(
            (ICONS_W, ICONS_H)
        )

        gray = icons.convert("L")

        colored = ImageOps.colorize(
            gray,
            black="black",
            white=f"rgb{accent}"
        ).convert("RGBA")

        colored.putalpha(
            icons.split()[-1]
        )

        bg.paste(
            colored,
            (ICONS_X, ICONS_Y),
            colored
        )

    # ============================================
    # SAVE
    # ============================================

    bg.save(cache_path)

    # ============================================
    # CLEANUP
    # ============================================

    try:
        os.remove(thumb_path)
    except:
        pass

    try:
        os.remove(anime_path)
    except:
        pass

    return cache_path
