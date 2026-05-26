import os
import io
import re
import asyncio
import datetime
import html
import warnings
from zoneinfo import ZoneInfo
from typing import List

# Suppress warnings
warnings.filterwarnings('ignore', category=SyntaxWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

from pyrogram import filters
from pyrogram.types import Message
from PIL import Image, ImageDraw, ImageFont

from VISHALMUSIC import app

# Configuration
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
FONT_PATH = os.environ.get("FONT_PATH", "")
ALLOW_OUT_OF_TIME_REPLY = os.environ.get("ALLOW_OUT_OF_TIME_REPLY", "").strip().lower() == "true"

# Greeting patterns
GOODNIGHT_RE = re.compile(r"\b(good\s*night|goodnight|gn|nighty|nite)\b", re.IGNORECASE)
GOODMORNING_RE = re.compile(r"\b(good\s*morning|goodmorning|gm|morning|subah)\b", re.IGNORECASE)

def is_good_morning(dt_local: datetime.datetime) -> bool:
    return 4 <= dt_local.hour < 12

def is_good_night(dt_local: datetime.datetime) -> bool:
    return dt_local.hour >= 20 or dt_local.hour < 4

def generate_thumbnail(lines: List[str], username: str = "", width: int = 1280, height: int = 720) -> bytes:
    try:
        bg_top = (20, 20, 60)
        bg_bottom = (80, 10, 50)

        img = Image.new("RGB", (width, height), bg_top)
        draw = ImageDraw.Draw(img)

        # Gradient background
        for y in range(height):
            ratio = y / (height - 1)
            r = int(bg_top[0] * (1 - ratio) + bg_bottom[0] * ratio)
            g = int(bg_top[1] * (1 - ratio) + bg_bottom[1] * ratio)
            b = int(bg_top[2] * (1 - ratio) + bg_bottom[2] * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Dark box overlay
        box_margin = 60
        draw.rectangle(
            [box_margin, box_margin, width - box_margin, height - box_margin],
            fill=(0, 0, 0, 180)
        )

        def load_font(size: int):
            try:
                if FONT_PATH and os.path.exists(FONT_PATH):
                    return ImageFont.truetype(FONT_PATH, size)
                font_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                    "C:\\Windows\\Fonts\\Arial.ttf"
                ]
                for fp in font_paths:
                    if os.path.exists(fp):
                        return ImageFont.truetype(fp, size)
            except:
                pass
            return ImageFont.load_default()

        title_font = load_font(72)
        sub_font = load_font(40)
        small_font = load_font(28)

        def get_text_size(text, font):
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                return bbox[2] - bbox[0], bbox[3] - bbox[1]
            except:
                try:
                    return draw.textsize(text, font=font)
                except:
                    return len(text) * font.size // 2, font.size

        # Center text
        center_x = width // 2
        total_text_height = 0
        line_heights = []
        fonts = [title_font if i == 0 else sub_font for i in range(len(lines))]
        
        for i, ln in enumerate(lines):
            w, h = get_text_size(ln, fonts[i])
            line_heights.append((w, h))
            total_text_height += h + 18
        
        start_y = (height - total_text_height) // 2
        y = start_y
        
        for i, ln in enumerate(lines):
            f = fonts[i]
            w, h = line_heights[i]
            x = center_x - w // 2
            # Shadow
            draw.text((x + 3, y + 3), ln, font=f, fill=(0, 0, 0))
            # Main text
            draw.text((x, y), ln, font=f, fill=(255, 240, 160))
            y += h + 18

        if username:
            user_text = f"— {username}"
            w, h = get_text_size(user_text, font=small_font)
            draw.text((width - w - 40, height - h - 30), user_text, font=small_font, fill=(220, 220, 220))

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=90)
        output.seek(0)
        return output.read()
        
    except Exception as e:
        print(f"Thumbnail error: {e}")
        # Fallback simple image
        fallback = Image.new("RGB", (800, 400), color=(20, 20, 60))
        fd = ImageDraw.Draw(fallback)
        y = 50
        for line in lines:
            fd.text((50, y), line, fill=(255, 240, 160))
            y += 50
        if username:
            fd.text((50, 300), f"— {username}", fill=(220, 220, 220))
        output = io.BytesIO()
        fallback.save(output, format="JPEG")
        output.seek(0)
        return output.read()

async def make_and_send_thumbnail(message: Message, lines: List[str], caption_text: str):
    try:
        uname = ""
        if message.from_user:
            uname = message.from_user.first_name or ""
            if message.from_user.last_name:
                uname += " " + message.from_user.last_name
        uname = (uname or "VISHAL").strip()

        img_bytes = await asyncio.to_thread(generate_thumbnail, lines, uname)
        
        await message.reply_photo(
            photo=img_bytes, 
            caption=caption_text, 
            disable_notification=True, 
            parse_mode="html"
        )
    except Exception as e:
        print(f"Send error: {e}")
        await message.reply_text(caption_text, disable_notification=True, parse_mode="html")

def build_caption_and_lines(kind: str, display_name_html: str):
    if kind == "goodnight":
        lines = ["❖ GOOD NIGHT ❖", "SWEET DREAMS"]
        caption = f"❖ GOOD NIGHT ❖ SWEET DREAMS\n\n❍  𐙚 ꒷꒦ ๋{display_name_html} ࣭ ꒷꒦ 🎟️ 💤\n\n❖ GO TO SLEEP EARLY"
    else:
        lines = ["☀️ GOOD MORNING ☀️", "HAVE A BRIGHT DAY"]
        caption = f"☀️ GOOD MORNING ☀️\n\n❍  𐙚 ꒷꒦ ๋{display_name_html} ࣭ ꒷꒦ 🎟️ ☕\n\n❖ PRAY FOR A GOOD DAY"
    return lines, caption

# ========== MAIN HANDLER - HIGHEST GROUP (WON'T BLOCK OTHERS) ==========
# Using group=999 (very low priority) so other handlers run first
@app.on_message(filters.text & ~filters.command(["goodnight", "goodmorning"]), group=999)
async def greet_detector_handler(client, message: Message):
    # CRITICAL: Immediately check and return without doing anything if not greeting
    if not message.text:
        return
    
    # Skip if message is a command
    if message.text.startswith('/'):
        return
    
    # Skip bot messages
    if message.from_user and message.from_user.is_bot:
        return
    
    # Quick check for greeting words (fast exit if no match)
    text_lower = message.text.lower()
    if not any(word in text_lower for word in ['good', 'gn', 'night', 'morning', 'gm', 'nite', 'nighty', 'subah']):
        return
    
    # Now do regex check
    is_gn = bool(GOODNIGHT_RE.search(message.text))
    is_gm = bool(GOODMORNING_RE.search(message.text))
    
    if not is_gn and not is_gm:
        return  # Not a greeting, exit silently
    
    # If we reach here, it's a greeting - process it
    try:
        # Get local time
        try:
            msg_dt = message.date
            if msg_dt.tzinfo is None:
                msg_dt = msg_dt.replace(tzinfo=datetime.timezone.utc)
            local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
        except:
            local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))

        # Handle both matches
        if is_gn and is_gm:
            if is_good_night(local_dt):
                is_gm = False
            else:
                is_gn = False

        # Get user info
        uname = ""
        uid = None
        if message.from_user:
            uid = message.from_user.id
            uname = message.from_user.first_name or ""
            if message.from_user.last_name:
                uname += " " + message.from_user.last_name
        uname = uname.strip() or "VISHAL"

        # Build HTML mention
        if uid:
            display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname)}</a>"
        else:
            display_html = html.escape(uname)

        # Send response
        if is_gn:
            if is_good_night(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
                lines, caption = build_caption_and_lines("goodnight", display_html)
                await make_and_send_thumbnail(message, lines, caption)
        elif is_gm:
            if is_good_morning(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
                lines, caption = build_caption_and_lines("goodmorning", display_html)
                await make_and_send_thumbnail(message, lines, caption)
                
    except Exception as e:
        print(f"Greeting handler error: {e}")
        # Don't let errors affect other handlers

# ========== COMMAND HANDLERS - EVEN LOWER PRIORITY ==========
@app.on_message(filters.command("goodnight"), group=998)
async def cmd_goodnight(client, message: Message):
    if message.from_user and message.from_user.is_bot:
        return
    
    try:
        try:
            msg_dt = message.date
            if msg_dt.tzinfo is None:
                msg_dt = msg_dt.replace(tzinfo=datetime.timezone.utc)
            local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
        except:
            local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))

        uname = ""
        uid = None
        if message.from_user:
            uid = message.from_user.id
            uname = message.from_user.first_name or ""
            if message.from_user.last_name:
                uname += " " + message.from_user.last_name
        uname = uname.strip() or "VISHAL"

        if uid:
            display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname)}</a>"
        else:
            display_html = html.escape(uname)

        if is_good_night(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
            lines, caption = build_caption_and_lines("goodnight", display_html)
            await make_and_send_thumbnail(message, lines, caption)
        else:
            await message.reply_text(f"{html.escape(uname)}, good night! 🌙")
    except Exception as e:
        print(f"Command error: {e}")

@app.on_message(filters.command("goodmorning"), group=998)
async def cmd_goodmorning(client, message: Message):
    if message.from_user and message.from_user.is_bot:
        return
    
    try:
        try:
            msg_dt = message.date
            if msg_dt.tzinfo is None:
                msg_dt = msg_dt.replace(tzinfo=datetime.timezone.utc)
            local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
        except:
            local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))

        uname = ""
        uid = None
        if message.from_user:
            uid = message.from_user.id
            uname = message.from_user.first_name or ""
            if message.from_user.last_name:
                uname += " " + message.from_user.last_name
        uname = uname.strip() or "VISHAL"

        if uid:
            display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname)}</a>"
        else:
            display_html = html.escape(uname)

        if is_good_morning(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
            lines, caption = build_caption_and_lines("goodmorning", display_html)
            await make_and_send_thumbnail(message, lines, caption)
        else:
            await message.reply_text(f"{html.escape(uname)}, good morning! ☀️")
    except Exception as e:
        print(f"Command error: {e}")
