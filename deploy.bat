@echo off
REM Deployment script for Oracle Cloud Server (Windows)
REM Usage: deploy.bat

echo 🚀 Starting deployment to Oracle Cloud...

REM Check if PuTTY is available
where plink >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ PuTTY (plink.exe) not found. Please install PuTTY tools.
    echo 📥 Download from: https://www.putty.org/
    pause
    exit /b 1
)

where pscp >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ PuTTY SCP (pscp.exe) not found. Please install PuTTY tools.
    echo 📥 Download from: https://www.putty.org/
    pause
    exit /b 1
)

REM Server details
set SERVER_IP=138.2.165.238
set SERVER_USER=opc
set PROJECT_NAME=memebot

echo 🌐 Connecting to server %SERVER_IP%...

REM Setup server
plink %SERVER_USER%@%SERVER_IP% -batch "sudo apt update && sudo apt upgrade -y"

REM Install Docker
plink %SERVER_USER%@%SERVER_IP% -batch "if ! command -v docker &> /dev/null; then curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh && sudo usermod -aG docker %USER%; fi"

REM Install Docker Compose
plink %SERVER_USER%@%SERVER_IP% -batch "if ! command -v docker-compose &> /dev/null; then sudo curl -L 'https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)' -o /usr/local/bin/docker-compose && sudo chmod +x /usr/local/bin/docker-compose; fi"

REM Create project directory
plink %SERVER_USER%@%SERVER_IP% -batch "mkdir -p ~/%PROJECT_NAME% && cd ~/%PROJECT_NAME% && mkdir -p data"

echo 📤 Copying files to server...

REM Copy files (exclude .git)
pscp -r -batch bot.py requirements.txt Dockerfile docker-compose.yml .env.example deploy.bat %SERVER_USER%@%SERVER_IP%:~/%PROJECT_NAME%/

echo 🔧 Setting up environment on server...

plink %SERVER_USER%@%SERVER_IP% -batch "cd ~/%PROJECT_NAME% && if [ ! -f .env ]; then cp .env.example .env && echo '⚠️  Please edit .env file with your BOT_TOKEN'; fi"

plink %SERVER_USER%@%SERVER_IP% -batch "cd ~/%PROJECT_NAME% && docker-compose down && docker-compose build && docker-compose up -d"

echo 📊 Container status:
plink %SERVER_USER%@%SERVER_IP% -batch "cd ~/%PROJECT_NAME% && docker-compose ps"

echo ✅ Deployment complete!
echo 🔗 Bot should be running on server: %SERVER_IP%
echo 📝 Don't forget to:
echo    1. Connect to server: plink %SERVER_USER%@%SERVER_IP%
echo    2. Edit ~/memebot/.env with your BOT_TOKEN
echo    3. Restart: cd ~/memebot && docker-compose restart
pause
