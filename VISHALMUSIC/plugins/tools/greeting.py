import os
import io
import re
import random
import math
import asyncio
import datetime
import html
from zoneinfo import ZoneInfo
from typing import List
from PIL import Image, ImageDraw, ImageFont
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode

from VISHALMUSIC import app

# ============ CONFIGURATION ============
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Kolkata")
FONT_PATH = os.environ.get("FONT_PATH", "")
ALLOW_OUT_OF_TIME_REPLY = os.environ.get("ALLOW_OUT_OF_TIME_REPLY", "false").lower() == "true"

# ============ GREETING PATTERNS ============
GOODNIGHT_RE = re.compile(r"\b(good\s*night|goodnight|gn|nighty|nite|g night|gud night)\b", re.IGNORECASE)
GOODMORNING_RE = re.compile(r"\b(good\s*morning|goodmorning|gm|morning|subah|gud morning|g morning)\b", re.IGNORECASE)

# ============ TIME CHECK FUNCTIONS ============
def is_good_morning(dt_local) -> bool:
    return 4 <= dt_local.hour < 12

def is_good_night(dt_local) -> bool:
    return dt_local.hour >= 20 or dt_local.hour < 4

# ============ SPECIAL THUMBNAIL GENERATOR ============
def generate_thumbnail(lines: List[str], username: str = "", width: int = 1280, height: int = 720) -> bytes:
    try:
        # Create base image
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)
        
        # Check if it's night or morning theme
        is_night = "goodnight" in str(lines).lower()
        
        # Beautiful gradient background
        if is_night:
            # Night theme - deep blue to purple
            colors = [(10, 20, 50), (40, 20, 70), (80, 30, 100)]
        else:
            # Morning theme - orange to yellow
            colors = [(255, 120, 50), (255, 180, 70), (255, 220, 100)]
        
        # Create smooth gradient
        for y in range(height):
            ratio = y / (height - 1)
            if ratio < 0.5:
                r = int(colors[0][0] * (1 - ratio*2) + colors[1][0] * (ratio*2))
                g = int(colors[0][1] * (1 - ratio*2) + colors[1][1] * (ratio*2))
                b = int(colors[0][2] * (1 - ratio*2) + colors[1][2] * (ratio*2))
            else:
                r2 = (ratio - 0.5) * 2
                r = int(colors[1][0] * (1 - r2) + colors[2][0] * r2)
                g = int(colors[1][1] * (1 - r2) + colors[2][1] * r2)
                b = int(colors[1][2] * (1 - r2) + colors[2][2] * r2)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # Add stars for night theme
        if is_night:
            random.seed(42)
            for _ in range(150):
                x = random.randint(0, width)
                y = random.randint(0, height // 2)
                size = random.randint(1, 3)
                brightness = random.randint(150, 255)
                draw.ellipse([(x, y), (x + size, y + size)], fill=(brightness, brightness, brightness))
        
        # Decorative border
        border_color = (255, 215, 0) if not is_night else (100, 150, 255)
        for i in range(5):
            draw.rectangle([(i, i), (width - i, height - i)], outline=border_color, width=2)
        
        # Main content box
        box_margin = 80
        box = [box_margin, box_margin, width - box_margin, height - box_margin]
        draw.rectangle(box, outline=border_color, width=3)
        draw.rectangle([box[0]+5, box[1]+5, box[2]-5, box[3]-5], outline=border_color, width=1)
        
        # Load fonts
        def load_font(size: int):
            try:
                if FONT_PATH and os.path.exists(FONT_PATH):
                    return ImageFont.truetype(FONT_PATH, size)
                
                font_options = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                    "C:\\Windows\\Fonts\\Arial.ttf"
                ]
                
                for font_path in font_options:
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
            except Exception:
                pass
            return ImageFont.load_default()
        
        # Draw main content
        title_font = load_font(96)
        sub_font = load_font(52)
        small_font = load_font(36)
        
        center_x = width // 2
        
        # Calculate text positions
        line_data = []
        total_height = 0
        
        for i, line in enumerate(lines):
            font = title_font if i == 0 else sub_font
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            line_data.append((line, font, w, h))
            total_height += h + 30
        
        start_y = (height - total_height) // 2
        current_y = start_y
        
        # Draw text
        for idx, (line, font, w, h) in enumerate(line_data):
            x = center_x - w // 2
            
            # Shadow effect
            draw.text((x + 3, current_y + 3), line, font=font, fill=(0, 0, 0))
            
            # Main text color
            if idx == 0:
                text_color = (150, 200, 255) if is_night else (255, 220, 100)
            else:
                text_color = (255, 240, 180)
            
            draw.text((x, current_y), line, font=font, fill=text_color)
            current_y += h + 30
        
        # Draw username
        if username:
            user_text = f"✨ {username} ✨"
            bbox = draw.textbbox((0, 0), user_text, font=small_font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text((width - w - 50, height - h - 30), user_text, font=small_font, fill=(255, 215, 0))
        
        # Save image to bytes
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=90)
        output.seek(0)
        return output.read()
        
    except Exception as e:
        print(f"Image generation error: {e}")
        # Return a simple error image
        img = Image.new("RGB", (800, 400), color=(50, 50, 80))
        draw = ImageDraw.Draw(img)
        draw.text((100, 180), "✨ Good Night ✨", fill=(255, 255, 255))
        output = io.BytesIO()
        img.save(output, format="JPEG")
        output.seek(0)
        return output.read()

# ============ SEND THUMBNAIL FUNCTION ============
async def make_and_send_thumbnail(message: Message, lines: List[str], caption_text: str):
    try:
        # Get username
        uname = ""
        uid = None
        if message.from_user:
            uid = message.from_user.id
            uname = message.from_user.first_name or ""
            if message.from_user.last_name:
                uname += " " + message.from_user.last_name
        
        if not uname.strip():
            uname = "Dear User"
        
        # Generate image
        img_bytes = await asyncio.to_thread(generate_thumbnail, lines, uname)
        
        # Create button
        button = InlineKeyboardMarkup([[
            InlineKeyboardButton("✨ Download ✨", url=f"https://t.me/{app.username if app.username else 'VISHALMUSIC'}")
        ]])
        
        # Send photo
        await message.reply_photo(
            photo=img_bytes,
            caption=caption_text,
            reply_markup=button,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        # Fallback text
        safe_name = html.escape(uname if uname else "User")
        await message.reply_text(
            f"{caption_text}\n\n— {safe_name}\n\n(✨ Image generated successfully!)",
            parse_mode=ParseMode.HTML
        )

# ============ CAPTION BUILDER ============
def build_caption_and_lines(kind: str, display_name_html: str):
    if kind == "goodnight":
        lines = ["❖ GOOD NIGHT ❖", "SWEET DREAMS"]
        caption = (
            "❖ ɢᴏᴏᴅ ɴɪɢʜᴛ ❖ sᴡᴇᴇᴛ ᴅʀᴇᴀᴍs\n\n"
            f"❍   𐙚 ꒷꒦ ๋{display_name_html} ࣭ ꒷꒦ 🎟️ 💤\n\n"
            "❖ ɢᴏ ᴛᴏ ➥ sʟᴇᴇᴘ ᴇᴀʀʟʏ"
        )
    else:
        lines = ["☀️ GOOD MORNING ☀️", "HAVE A BRIGHT DAY"]
        caption = (
            "☀️ ɢᴏᴏᴅ ᴍᴏʀɴɪɴɢ ☀️\n\n"
            f"❍   𐙚 ꒷꒦ ๋{display_name_html} ࣭ ꒷꒦ 🎟️ ☕\n\n"
            "❖ ᴘʀᴀʏ ғᴏʀ ᴀ ɢᴏᴏᴅ ᴅᴀʏ"
        )
    return lines, caption

# ============ MAIN HANDLER ============
@app.on_message(filters.text & ~filters.command(["goodnight", "goodmorning", "gn", "gm"]))
async def greet_detector_handler(client, message: Message):
    text = message.text or ""
    
    # Get local time
    try:
        msg_dt = message.date
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=ZoneInfo("UTC"))
        local_dt = msg_dt.astimezone(ZoneInfo(TIMEZONE))
    except:
        local_dt = datetime.datetime.now(ZoneInfo(TIMEZONE))
    
    is_gn = bool(GOODNIGHT_RE.search(text))
    is_gm = bool(GOODMORNING_RE.search(text))
    
    # Handle both matches
    if is_gn and is_gm:
        if is_good_night(local_dt):
            is_gm = False
        else:
            is_gn = False
    
    if not (is_gn or is_gm):
        return
    
    # Get user info
    uname = ""
    uid = None
    if message.from_user:
        uid = message.from_user.id
        uname = message.from_user.first_name or ""
        if message.from_user.last_name:
            uname += " " + message.from_user.last_name
    
    if not uname.strip():
        uname = "User"
    
    # Create mention
    if uid:
        display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname[:30])}</a>"
    else:
        display_html = html.escape(uname)
    
    # Send response
    if is_gn:
        if is_good_night(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
            lines, caption = build_caption_and_lines("goodnight", display_html)
            await make_and_send_thumbnail(message, lines, caption)
        else:
            await message.reply_text(
                f"✨ {html.escape(uname)}, abhi raat ka time nahi hai, phir bhi - Good Night! 🌙",
                parse_mode=ParseMode.HTML
            )
    elif is_gm:
        if is_good_morning(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
            lines, caption = build_caption_and_lines("goodmorning", display_html)
            await make_and_send_thumbnail(message, lines, caption)
        else:
            await message.reply_text(
                f"🌤️ {html.escape(uname)}, abhi subah ka time nahi hai, phir bhi - Good Morning!",
                parse_mode=ParseMode.HTML
            )

# ============ COMMAND HANDLERS ============
@app.on_message(filters.command(["goodnight", "gn"]))
async def cmd_goodnight(client, message: Message):
    try:
        msg_dt = message.date
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=ZoneInfo("UTC"))
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
    
    if not uname.strip():
        uname = "User"
    
    if uid:
        display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname[:30])}</a>"
    else:
        display_html = html.escape(uname)
    
    if is_good_night(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
        lines, caption = build_caption_and_lines("goodnight", display_html)
        await make_and_send_thumbnail(message, lines, caption)
    else:
        await message.reply_text(
            f"{html.escape(uname)}, abhi night time nahi hai. Still, send /goodnight",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["goodmorning", "gm"]))
async def cmd_goodmorning(client, message: Message):
    try:
        msg_dt = message.date
        if msg_dt.tzinfo is None:
            msg_dt = msg_dt.replace(tzinfo=ZoneInfo("UTC"))
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
    
    if not uname.strip():
        uname = "User"
    
    if uid:
        display_html = f"<a href='tg://user?id={uid}'>{html.escape(uname[:30])}</a>"
    else:
        display_html = html.escape(uname)
    
    if is_good_morning(local_dt) or ALLOW_OUT_OF_TIME_REPLY:
        lines, caption = build_caption_and_lines("goodmorning", display_html)
        await make_and_send_thumbnail(message, lines, caption)
    else:
        await message.reply_text(
            f"{html.escape(uname)}, abhi morning time nahi hai. Still, send /goodmorning",
            parse_mode=ParseMode.HTML
        )
