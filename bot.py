import asyncio
import base64
import binascii
import logging
import os
import re
import tempfile
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple

from telegram import Update
from telegram.constants import MessageEntityType, ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("video_downloader_bot")

class _RedactTelegramBotTokenFilter(logging.Filter):
    _token_re = re.compile(r"bot\d+:[A-Za-z0-9_-]+")
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except:
            return True
        msg = self._token_re.sub("bot<BOT_TOKEN>", msg)
        record.msg = msg
        record.args = ()
        return True

for handler in logging.getLogger().handlers:
    handler.addFilter(_RedactTelegramBotTokenFilter())
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

MAX_FILESIZE_MB = int(os.getenv("MAX_FILESIZE_MB", "49"))
MAX_FILESIZE_BYTES = MAX_FILESIZE_MB * 1024 * 1024
URL_REGEX = re.compile(r"(https?://\S+)", re.IGNORECASE)

# Domains that Telegram can natively embed video via community proxies
PROXY_DOMAINS = {
    "instagram.com": "ddinstagram.com",
    "www.instagram.com": "ddinstagram.com",
    "tiktok.com": "vxtiktok.com",
    "www.tiktok.com": "vxtiktok.com",
    "vm.tiktok.com": "vm.vxtiktok.com",
    "twitter.com": "fxtwitter.com",
    "www.twitter.com": "fxtwitter.com",
    "x.com": "fixvx.com",
    "www.x.com": "fixvx.com",
}

def _get_proxied_url(url: str) -> Optional[str]:
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = parsed.hostname.lower() if parsed.hostname else ""
        if hostname in PROXY_DOMAINS:
            new_hostname = PROXY_DOMAINS[hostname]
            return urllib.parse.urlunparse(parsed._replace(netloc=new_hostname))
    except Exception:
        pass
    return None

def _extract_url_from_message(update: Update) -> Optional[str]:
    message = update.effective_message
    if not message or not message.text:
        return None
    text = message.text
    for ent in message.entities or []:
        if ent.type == MessageEntityType.TEXT_LINK and ent.url:
            return ent.url
        if ent.type == MessageEntityType.URL:
            return text[ent.offset : ent.offset + ent.length]
    match = URL_REGEX.search(text)
    if not match:
        return None
    return match.group(1).rstrip(")].,!?")

def _pick_downloaded_file(tmpdir: str) -> str:
    paths = [p for p in Path(tmpdir).iterdir() if p.is_file()]
    if not paths:
        raise RuntimeError("Downloaded file not found")
    mp4s = [p for p in paths if p.suffix.lower() == ".mp4"]
    photos = [p for p in paths if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp", ".gif"]]
    candidates = mp4s or photos or paths
    best = max(candidates, key=lambda p: p.stat().st_size)
    return str(best)

def _download_media_sync(url: str, tmpdir: str) -> Tuple[str, str, str]:
    try:
        # 1. Гарантований запит на злиття відео та аудіо (виправлено проблему зі звуком)
        return _download_media_with_opts(url, tmpdir, {
            "format": os.getenv(
                "YTDLP_FORMAT",
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            ),
        })
    except DownloadError as e:
        msg_l = str(e).lower()
        if "video" in msg_l and ("merge" in msg_l or "audio" in msg_l or "ffmpeg" in msg_l):
            try:
                return _download_media_with_opts(url, tmpdir, {
                    "format": "bestaudio[ext=m4a]/bestaudio/best",
                })
            except DownloadError:
                pass
        try:
            return _download_media_with_opts(url, tmpdir, {
                "format": "worst/worst[ext=mp4]/worst",
            })
        except DownloadError:
            pass
        raise e

def _download_media_with_opts(url: str, tmpdir: str, format_opts: dict) -> Tuple[str, str, str]:
    ydl_opts = {
        "outtmpl": os.path.join(tmpdir, "%(title).200s-%(id)s.%(ext)s"),
        "format": format_opts.get("format", "best"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "retries": 3,
        "max_filesize": MAX_FILESIZE_BYTES,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        "embed_subs": False,
        "writesubtitles": False,
    }
    proxy = os.getenv("YTDLP_PROXY")
    if proxy:
        ydl_opts["proxy"] = proxy
    cookiefile_path = os.getenv("YTDLP_COOKIEFILE")
    cookies_b64 = os.getenv("YTDLP_COOKIES_B64")
    if cookiefile_path:
        ydl_opts["cookiefile"] = cookiefile_path
    elif cookies_b64:
        cookie_path = os.path.join(tmpdir, "cookies.txt")
        try:
            decoded = base64.b64decode(re.sub(r"\s+", "", cookies_b64))
        except binascii.Error as e:
            raise ValueError("Invalid YTDLP_COOKIES_B64 env var") from e
        with open(cookie_path, "wb") as f:
            f.write(decoded)
        ydl_opts["cookiefile"] = cookie_path

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if isinstance(info, dict) and info.get("entries"):
        info = next((e for e in info["entries"] if e), info)

    title = ""
    media_type = "video"
    if isinstance(info, dict):
        title = info.get("title") or ""
        if info.get("ext") in ["jpg", "jpeg", "png", "webp", "gif"]:
            media_type = "photo"
        elif info.get("_type") == "photo":
            media_type = "photo"
        elif info.get("vcodec") == "none" and info.get("acodec") != "none":
            media_type = "audio"
        elif format_opts.get("format", "").startswith("bestaudio"):
            media_type = "audio"

        for rd in info.get("requested_downloads") or []:
            fp = rd.get("filepath")
            if fp and os.path.isfile(fp):
                return fp, title, media_type

        fp = info.get("filepath") or info.get("_filename")
        if fp and os.path.isfile(fp):
            return fp, title, media_type

    return _pick_downloaded_file(tmpdir), title, media_type

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message: return
    await message.reply_text(
        "Привіт! Надішли посилання на відео (Instagram / TikTok / YouTube / X).\n"
        "Інстаграм, ТікТок та X(Twitter) я відкрию для тебе миттєво без обмежень. "
        "А інше відео — завантажу файлом."
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message: return
    url = _extract_url_from_message(update)
    if not url: return

    # 1. Спочатку спробуємо проксі для мікросервісів Telegram (Instagram, TikTok, Twitter)
    proxied_url = _get_proxied_url(url)
    if proxied_url:
        try:
            # Телеграм сам скачає і покаже кліп як нативне відео, просто надіславши лінк.
            await message.reply_text(
                f'<a href="{proxied_url}">📹 Відео готове (натисни або дивись тут):</a>\n{proxied_url}', 
                parse_mode=ParseMode.HTML
            )
            return  # Зупиняємо функцію, завантажувати файл на наш сервер вже не потрібно!
        except Exception as e:
            logger.error(f"Error sending proxy url: {e}")

    # 2. Якщо домен не підтримується через проксі (YouTube та інші) — качаємо класичними методами
    status_msg = await message.reply_text("📥 Завантажую відео (це може зайняти час)...")
    try:
        with tempfile.TemporaryDirectory(prefix="dl_") as tmpdir:
            try:
                file_path, title, media_type = await asyncio.to_thread(_download_media_sync, url, tmpdir)
            except DownloadError as e:
                msg = str(e).lower()
                if "max-filesize" in msg:
                    raise ValueError(f"Медіа занадто велике (ліміт {MAX_FILESIZE_MB}MB).") from e
                if "instagram" in msg and ("login required" in msg or "cookies" in msg or "429" in msg):
                    raise ValueError("Instagram тимчасово не працює для завантаження файлом.") from e
                raise
            size = os.path.getsize(file_path)
            if size > MAX_FILESIZE_BYTES:
                raise ValueError(f"Медіа занадто велике. Ліміт {MAX_FILESIZE_MB}MB.")
            caption = title[:1000] if title else None
            with open(file_path, "rb") as f:
                if media_type == "video":
                    await message.reply_video(video=f, caption=caption, supports_streaming=True)
                elif media_type == "photo":
                    await message.reply_photo(photo=f, caption=caption)
                elif media_type == "audio":
                    await message.reply_audio(audio=f, caption=caption)
                else:
                    await message.reply_document(document=f, caption=caption)
    except Exception as e:
        logger.exception("Failed to process url=%s", url)
        await message.reply_text(f"❌ Сталася помилка: {e}")
    finally:
        try: await status_msg.delete()
        except Exception: pass

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN env var is required")
    application = ApplicationBuilder().token(token).connect_timeout(30).read_timeout(120).write_timeout(120).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.run_polling()

if __name__ == "__main__":
    main()
