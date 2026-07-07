FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl gnupg git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install bgutil PO Token provider (auto-generates YouTube PO Tokens without cookies)
# Package not on npm registry — clone and build from GitHub
RUN git clone --single-branch --branch 1.3.1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /bgutil \
    && cd /bgutil/server && npm ci && npx tsc && npm prune --omit=dev

COPY . ./

ENV PYTHONUNBUFFERED=1

# Start bgutil PO Token server in background, then run bot
CMD ["sh", "-c", "node /bgutil/server/build/main.js & sleep 2 && python bot.py"]
