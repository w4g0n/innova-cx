# Demo Setup Guide

Quick setup guide for running the InnovaCX demo with all AI services.

## Prerequisites

- Docker Desktop running
- Model files for sentiment analysis (optional, mock mode available)

## 1. Start Demo Services

```bash
docker-compose --profile dev up --build -d
```

This starts: **frontend** (5173), **chatbot** (8001), **whisper** (3001), **sentiment** (8002)

To run only the app + API + database (without chatbot/whisper/sentiment):

```bash
docker-compose --profile frontend up --build -d
```

This starts: **frontend** (5173), **backend** (8000), **postgres** (5433)

## 2. First Run - Chatbot Model Download

On first startup, the chatbot container downloads Falcon3-1B-Instruct (~2.5GB). Monitor progress:

```bash
docker logs -f innovacx-chatbot
```

Wait until you see `Application startup complete` before testing the chatbot.

Subsequent starts are instant (model cached in Docker volume).

## 3. Sentiment Model (Optional)

By default the sentiment service runs in **mock mode** (keyword-based analysis). To use the real RoBERTa model:

1. Set env vars in a `.env` file at the project root (copy from `.env.example`):

```env
USE_MOCK_MODEL=false
SENTIMENT_MODEL_PATH=C:/Users/ali/Desktop/Model
```

2. Rebuild:

```bash
docker-compose --profile dev up --build sentiment -d
```

3. Verify:

```bash
docker logs innovacx-sentiment
# Should show: "Real model loaded successfully"
```

## 4. Verify All Services

```bash
# Chatbot
curl -X POST http://localhost:8001/api/chat -H "Content-Type: application/json" -d "{\"message\":\"What leasing options are available?\"}"

# Sentiment
curl -X POST http://localhost:8002/analyze -H "Content-Type: application/json" -d "{\"text\":\"The AC has been broken for 3 days\"}"

# Whisper (requires audio file)
curl http://localhost:3001/
```

## 5. Open the Demo

Open **http://localhost:5173** in your browser.

### Chatbot Demo
1. Click "Chat with Nova" widget (bottom right)
2. Click **Inquiry**
3. Type a question (e.g. "What are the leasing options?")
4. Falcon3-1B generates a response (~5-15 seconds on CPU)

### Sentiment Demo
1. Navigate to Fill a Form
2. Switch to **Audio** mode
3. Record a complaint (e.g. "The air conditioning has been broken for three days")
4. After transcription, sentiment analysis runs automatically
5. Open browser console (F12) to see `[Sentiment Analysis]` logs with model predictions

### Audio Transcription Demo
1. Same as above - the Whisper service transcribes live audio recordings
2. Supports both Audio mode on the form and the chatbot mic button

## Stopping

```bash
docker-compose --profile frontend down
```

## Ports

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 5173 | React app (Vite) |
| Chatbot | 8001 | Falcon3-1B-Instruct LLM |
| Sentiment | 8002 | RoBERTa sentiment analysis |
| Whisper | 3001 | Audio transcription |

## Troubleshooting

**Chatbot restarting?** Check logs: `docker logs innovacx-chatbot`. Usually means model download failed - ensure internet access.

**CORS errors?** Rebuild the failing service: `docker-compose --profile frontend up --build <service> -d`

**Sentiment not working?** Ensure the container is running: `docker ps --filter "name=innovacx-sentiment"`
