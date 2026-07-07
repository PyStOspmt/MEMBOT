FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install bgutil PO Token provider (auto-generates YouTube PO Tokens without cookies)
RUN npm install -g bgutil-ytdlp-pot-provider

COPY . ./

ENV PYTHONUNBUFFERED=1

# Start bgutil PO Token server in background, then run bot
CMD ["sh", "-c", "bgutil-pot-provider & sleep 2 && python bot.py"]
