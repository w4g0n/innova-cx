FROM node:18-bullseye

# -------------------------------
# System dependencies
# -------------------------------
# - ffmpeg + libsndfile1: audio decoding
# - python3 + pip: Whisper + analysis
# -------------------------------
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

# -------------------------------
# App workspace
# -------------------------------
WORKDIR /app

# -------------------------------
# Node dependencies (cached layer)
# -------------------------------
COPY package*.json ./
RUN npm install

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