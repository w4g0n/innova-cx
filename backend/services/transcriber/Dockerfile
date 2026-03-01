FROM node:18-bullseye-slim

# -------------------------------
# System dependencies
# -------------------------------
# - ffmpeg + libsndfile1: audio decoding
# - python3 + pip: Whisper + analysis
# -------------------------------
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    python3 \
    python3-pip \
    build-essential \
    ffmpeg \
    libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

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
