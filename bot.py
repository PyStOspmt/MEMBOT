import asyncio
import base64
import binascii
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from telegram import Update
from telegram.constants import MessageEntityType
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("video_downloader_bot")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

MAX_FILESIZE_MB = int(os.getenv("MAX_FILESIZE_MB", "49"))
MAX_FILESIZE_BYTES = MAX_FILESIZE_MB * 1024 * 1024

URL_REGEX = re.compile(r"(https?://\S+)", re.IGNORECASE)


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
    candidates = mp4s or paths
    best = max(candidates, key=lambda p: p.stat().st_size)
    return str(best)


def _download_video_sync(url: str, tmpdir: str) -> Tuple[str, str]:
    ydl_opts = {
        "outtmpl": os.path.join(tmpdir, "%(title).200s-%(id)s.%(ext)s"),
        "format": os.getenv(
            "YTDLP_FORMAT",
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]/best",
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "retries": 3,
        "max_filesize": MAX_FILESIZE_BYTES,
        "quiet": True,
        "no_warnings": True,
    }

    cookiefile_path = os.getenv("YTDLP_COOKIEFILE")
    cookies_b64 = os.getenv("YTDLP_COOKIES_B64")

    if cookiefile_path:
        ydl_opts["cookiefile"] = cookiefile_path
    elif cookies_b64:
        cookie_path = os.path.join(tmpdir, "cookies.txt")
        try:
            decoded = base64.b64decode(re.sub(r"\s+", "", cookies_b64))
        except binascii.Error as e:
            raise ValueError(
                "Invalid YTDLP_COOKIES_B64 env var (must be base64-encoded cookies.txt)"
            ) from e

        with open(cookie_path, "wb") as f:
            f.write(decoded)

        ydl_opts["cookiefile"] = cookie_path

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if isinstance(info, dict) and info.get("entries"):
        info = next((e for e in info["entries"] if e), info)

    title = ""
    if isinstance(info, dict):
        title = info.get("title") or ""

        for rd in info.get("requested_downloads") or []:
            fp = rd.get("filepath")
            if fp and os.path.isfile(fp):
                return fp, title

        fp = info.get("filepath") or info.get("_filename")
        if fp and os.path.isfile(fp):
            return fp, title

    return _pick_downloaded_file(tmpdir), title


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    await message.reply_text(
        "Надішли посилання на відео (Instagram / TikTok / YouTube тощо) — я спробую його скачати і відправити сюди."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    url = _extract_url_from_message(update)
    if not url:
        return

    status_msg = await message.reply_text("Завантажую відео...")

    try:
        with tempfile.TemporaryDirectory(prefix="dl_") as tmpdir:
            try:
                file_path, title = await asyncio.to_thread(_download_video_sync, url, tmpdir)
            except DownloadError as e:
                msg = str(e)
                if "max-filesize" in msg or "max-filesize" in repr(e):
                    raise ValueError(
                        f"Відео занадто велике (ліміт {MAX_FILESIZE_MB}MB). Спробуй коротше/меншу якість."
                    ) from e

                msg_l = msg.lower()
                if "instagram" in msg_l and (
                    "login required" in msg_l
                    or "rate-limit" in msg_l
                    or "cookies" in msg_l
                    or "requested content is not available" in msg_l
                ):
                    raise ValueError(
                        "Instagram часто вимагає логін/cookies. Додай в Render env `YTDLP_COOKIES_B64` (base64 з cookies.txt) або `YTDLP_COOKIEFILE`."
                    ) from e
                raise

            size = os.path.getsize(file_path)
            if size > MAX_FILESIZE_BYTES:
                raise ValueError(
                    f"Відео занадто велике (≈{size / 1024 / 1024:.1f}MB). Ліміт {MAX_FILESIZE_MB}MB."
                )

            caption = title[:1000] if title else None
            with open(file_path, "rb") as f:
                await message.reply_video(
                    video=f,
                    caption=caption,
                    supports_streaming=True,
                )

    except Exception as e:
        logger.exception("Failed to process url=%s", url)
        await message.reply_text(f"Помилка: {e}")

    finally:
        try:
            await status_msg.delete()
        except Exception:
            pass


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN env var is required")

    application = (
        ApplicationBuilder()
        .token(token)
        .connect_timeout(30)
        .read_timeout(120)
        .write_timeout(120)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()


if __name__ == "__main__":
    main()
