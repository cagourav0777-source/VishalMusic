import os
import io
import re
import asyncio
import datetime
import html
from zoneinfo import ZoneInfo
from typing import List

from pyrogram import filters, enums
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from PIL import Image, ImageDraw, ImageFont

from VISHALMUSIC import app

# =========================================================
# CONFIG
# =========================================================

TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")

FONT_PATH = os.environ.get(
    "FONT_PATH",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
)

ALLOW_OUT_OF_TIME_REPLY = bool(
    os.environ.get("ALLOW_OUT_OF_TIME_REPLY", "").strip()
)

# =========================================================
# GREETING DETECTORS
# =========================================================

GOODNIGHT_RE = re.compile(
    r"\b(good\s*night|goodnight|gn|nighty|nite)\b",
    re.IGNORECASE
)

GOODMORNING_RE = re.compile(
    r"\b(good\s*morning|goodmorning|gm|morning|subah)\b",
    re.IGNORECASE
)

# =========================================================
# TIME CHECK
# =========================================================

def is_good_morning(dt_local: datetime.datetime) -> bool:
    return 4 <= dt_local.hour < 12


def is_good_night(dt_local: datetime.datetime) -> bool:
    return dt_local.hour >= 20 or dt_local.hour < 4


# =========================================================
# FONT LOADER
# =========================================================

def load_font(size: int):

    try:

        if FONT_PATH and os.path.exists(FONT_PATH):
            return ImageFont.truetype(FONT_PATH, size)

    except Exception:
        pass

    return ImageFont.load_default()


# =========================================================
# THUMBNAIL GENERATOR
# =========================================================

def generate_thumbnail(
    lines: List[str],
    username: str = "",
    width: int = 1280,
    height: int = 720
) -> bytes:

    bg_top = (20, 20, 60)
    bg_bottom = (80, 10, 50)

    img = Image.new("RGBA", (width, height), bg_top)

    draw = ImageDraw.Draw(img)

    # Gradient Background
    for y in range(height):

        ratio = y / (height - 1)

        r = int(bg_top[0] * (1 - ratio) + bg_bottom[0] * ratio)
        g = int(bg_top[1] * (1 - ratio) + bg_bottom[1] * ratio)
        b = int(bg_top[2] * (1 - ratio) + bg_bottom[2] * ratio)

        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Overlay Box
    overlay = Image.new("RGBA", (width, height))

    od = ImageDraw.Draw(overlay)

    margin = 60

    od.rectangle(
        (margin, margin, width - margin, height - margin),
        fill=(0, 0, 0, 120)
    )

    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)

    # Fonts
    title_font = load_font(72)
    sub_font = load_font(42)
    small_font = load_font(28)

    fonts = [
        title_font if i == 0 else sub_font
        for i in range(len(lines))
    ]

    # Text Sizes
    total_height = 0

    line_sizes = []

    for i, line in enumerate(lines):

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=fonts[i]
        )

        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        line_sizes.append((w, h))

        total_height += h + 25

    start_y = (height - total_height) // 2

    # Draw Text
    y = start_y

    for i, line in enumerate(lines):

        font = fonts[i]

        w, h = line_sizes[i]

        x = (width - w) // 2

        # Shadow
        draw.text(
            (x + 3, y + 3),
            line,
            font=font,
            fill=(0, 0, 0)
        )

        # Main Text
        draw.text(
            (x, y),
            line,
            font=font,
            fill=(255, 240, 160)
        )

        y += h + 25

    # Username
    if username:

        user_text = f"— {username}"

        bbox = draw.textbbox(
            (0, 0),
            user_text,
            font=small_font
        )

        uw = bbox[2] - bbox[0]
        uh = bbox[3] - bbox[1]

        draw.text(
            (width - uw - 40, height - uh - 30),
            user_text,
            font=small_font,
            fill=(220, 220, 220)
        )

    # Save Image
    out = io.BytesIO()

    img.convert("RGB").save(
        out,
        format="JPEG",
        quality=90
    )

    out.seek(0)

    return out.read()


# =========================================================
# CAPTION + TEXT LINES
# =========================================================

def build_caption_and_lines(
    kind: str,
    display_name_html: str
):

    if kind == "goodnight":

        lines = [
            "🌙 ɢᴏᴏᴅ ɴɪɢʜᴛ 🌙",
            "sᴡᴇᴇᴛ ᴅʀᴇᴀᴍs"
        ]

        caption = (
            "🌙 <b>ɢᴏᴏᴅ ɴɪɢʜᴛ</b> 🌙\n\n"
            f"❍ 𐙚 ꒷꒦ ๋{display_name_html} ࣭ ꒷꒦ 💤\n\n"
            "❖ sʟᴇᴇᴘ ᴡᴇʟʟ ✨"
        )

    else:

        lines = [
            "☀️ ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ☀️",
            "ʜᴀᴠᴇ ᴀ ʙʀɪɢʜᴛ ᴅᴀʏ"
        ]

        caption = (
            "☀️ <b>ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ</b> ☀️\n\n"
            f"❍ 𐙚 ꒷꒦ ๋{display_name_html} ࣭ ꒷꒦ ☕\n\n"
            "❖ ᴘʀᴀʏ ғᴏʀ ᴀ ɢᴏᴏᴅ ᴅᴀʏ ✨"
        )

    return lines, caption


# =========================================================
# SEND IMAGE
# =========================================================

async def make_and_send_thumbnail(
    message: Message,
    lines: List[str],
    caption_text: str
):

    try:

        uname = "VISHAL"

        uid = None

        if message.from_user:

            uid = message.from_user.id

            uname = message.from_user.first_name or ""

            if message.from_user.last_name:
                uname += " " + message.from_user.last_name

        uname = uname.strip()

        # Generate Image
        img_bytes = await asyncio.to_thread(
            generate_thumbnail,
            lines,
            uname
        )

        # Convert Bytes -> File
        photo = io.BytesIO(img_bytes)

        photo.name = "greeting.jpg"

        # Button
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✦ ᴅᴏᴡɴʟᴏᴀᴅ ɪᴍᴀɢᴇ",
                        url=f"https://t.me/{app.username or ''}"
                    )
                ]
            ]
        )

        # Send Photo
        await message.reply_photo(
            photo=photo,
            caption=caption_text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=kb,
            disable_notification=True
        )

    except Exception as e:

        await message.reply_text(
            f"⚠️ Thumbnail generator error:\n\n{e}"
        )


# =========================================================
# MAIN MESSAGE HANDLER
# =========================================================

@app.on_message(filters.text)
async def greet_detector_handler(client, message: Message):

    text = message.text or ""

    # Local Time
    try:

        msg_dt = message.date

        if msg_dt.tzinfo is None:

            msg_dt = msg_dt.replace(
                tzinfo=datetime.timezone.utc
            )

        local_dt = msg_dt.astimezone(
            ZoneInfo(TIMEZONE)
        )

    except Exception:

        local_dt = datetime.datetime.now(
            ZoneInfo(TIMEZONE)
        )

    # Detect
    is_gn = bool(GOODNIGHT_RE.search(text))

    is_gm = bool(GOODMORNING_RE.search(text))

    # User
    uname = "VISHAL"

    uid = None

    if message.from_user:

        uid = message.from_user.id

        uname = message.from_user.first_name or ""

        if message.from_user.last_name:
            uname += " " + message.from_user.last_name

    uname = uname.strip()

    # Mention
    if uid:

        display_html = (
            f"<a href='tg://user?id={uid}'>"
            f"{html.escape(uname)}</a>"
        )

    else:

        display_html = html.escape(uname)

    # Good Night
    if is_gn:

        if is_good_night(local_dt) or ALLOW_OUT_OF_TIME_REPLY:

            lines, caption = build_caption_and_lines(
                "goodnight",
                display_html
            )

            await make_and_send_thumbnail(
                message,
                lines,
                caption
            )

        else:

            await message.reply_text(
                f"🌙 {html.escape(uname)}, "
                f"abhi night time nahi hai."
            )

    # Good Morning
    elif is_gm:

        if is_good_morning(local_dt) or ALLOW_OUT_OF_TIME_REPLY:

            lines, caption = build_caption_and_lines(
                "goodmorning",
                display_html
            )

            await make_and_send_thumbnail(
                message,
                lines,
                caption
            )

        else:

            await message.reply_text(
                f"☀️ {html.escape(uname)}, "
                f"abhi morning time nahi hai."
            )


# =========================================================
# COMMAND: /goodmorning
# =========================================================

@app.on_message(filters.command("goodmorning"))
async def cmd_goodmorning(client, message: Message):

    uid = message.from_user.id

    uname = message.from_user.first_name or "User"

    display_html = (
        f"<a href='tg://user?id={uid}'>"
        f"{html.escape(uname)}</a>"
    )

    lines, caption = build_caption_and_lines(
        "goodmorning",
        display_html
    )

    await make_and_send_thumbnail(
        message,
        lines,
        caption
    )


# =========================================================
# COMMAND: /goodnight
# =========================================================

@app.on_message(filters.command("goodnight"))
async def cmd_goodnight(client, message: Message):

    uid = message.from_user.id

    uname = message.from_user.first_name or "User"

    display_html = (
        f"<a href='tg://user?id={uid}'>"
        f"{html.escape(uname)}</a>"
    )

    lines, caption = build_caption_and_lines(
        "goodnight",
        display_html
    )

    await make_and_send_thumbnail(
        message,
        lines,
        caption
    )
