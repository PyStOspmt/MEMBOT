# MemeBot - Telegram Video/Photo Downloader

## Features
- 🎥 Download videos from YouTube, Instagram, TikTok, etc.
- 📸 Download photos from social media platforms
- 🔊 Fixed audio extraction and video merging issues
- 🔄 Automatic fallback to audio-only if video fails
- 📱 Supports multiple media formats
- 🛡️ Error handling and retry mechanisms

## Quick Deploy to Oracle Cloud

### Prerequisites
- Oracle Cloud server with IP: `138.2.165.238`
- SSH access with user: `opc`
- Bot token from @BotFather

### Windows Deployment
1. Install [PuTTY](https://www.putty.org/) (for plink.exe and pscp.exe)
2. Run:
```cmd
deploy.bat
```

### Linux/Mac Deployment
1. Make script executable:
```bash
chmod +x deploy.sh
```
2. Run:
```bash
./deploy.sh
```

### Manual Deployment Steps
1. Connect to server:
```bash
ssh opc@138.2.165.238
```

2. Install Docker:
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

3. Install Docker Compose:
```bash
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

4. Create project directory:
```bash
mkdir -p ~/memebot && cd ~/memebot
mkdir -p data
```

5. Copy project files to server

6. Setup environment:
```bash
cp .env.example .env
# Edit .env with your BOT_TOKEN
```

7. Deploy:
```bash
docker-compose up -d
```

## Configuration
Edit `.env` file:
- `BOT_TOKEN`: Your Telegram bot token (required)
- `MAX_FILESIZE_MB`: Maximum file size (default: 49)
- `YTDLP_PROXY`: Optional proxy for yt-dlp
- `YTDLP_COOKIES_B64`: Base64 encoded cookies for Instagram

## Management Commands
```bash
# View logs
docker-compose logs -f memebot

# Restart bot
docker-compose restart memebot

# Stop bot
docker-compose down

# Update bot
docker-compose down
docker-compose pull
docker-compose up -d
```

## Troubleshooting
- Check logs: `docker-compose logs memebot`
- Verify BOT_TOKEN is correct
- Ensure server has enough disk space
- Check internet connectivity for media downloads

## Support
For issues with specific platforms, configure cookies or proxy in `.env` file.
