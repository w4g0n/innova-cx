FROM node:18-bullseye-slim

# -------------------------------
# System dependencies
# -------------------------------
# - ffmpeg + libsndfile1: audio decoding
# - python3 + pip: Whisper + analysis
# -------------------------------
RUN set -eux; \
    for i in 1 2 3; do \
      apt-get -o Acquire::Retries=5 update && \
      apt-get install -y --fix-missing --no-install-recommends \
        python3 \
        python3-dev \
        python3-pip \
        build-essential \
        ffmpeg \
        libsndfile1 && \
      break; \
      if [ "$i" = "3" ]; then \
        echo "apt install failed after 3 attempts"; \
        exit 1; \
      fi; \
      echo "apt install attempt ${i} failed; retrying in 5s..."; \
      sleep 5; \
    done; \
    rm -rf /var/lib/apt/lists/*

# -------------------------------
# App workspace
# -------------------------------
WORKDIR /app
ENV NODE_ENV=production

# -------------------------------
# Node dependencies (cached layer)
# -------------------------------
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force

# -------------------------------
# Python dependencies (cached layer)
# -------------------------------
COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# -------------------------------
# App source
# -------------------------------
COPY . .

# -------------------------------
# Runtime directories
# -------------------------------
# uploads      → incoming audio files
# transcripts  → future persistence / debugging
# -------------------------------
RUN mkdir -p /app/uploads /app/transcripts

# -------------------------------
# Runtime
# -------------------------------
EXPOSE 3001
CMD ["node", "index.js"]
