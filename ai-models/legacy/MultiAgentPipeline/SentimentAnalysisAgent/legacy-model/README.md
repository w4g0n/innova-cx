# Sentiment Analysis Service

FastAPI service for analyzing text sentiment using RoBERTa model or mock mode.

## Quick Start (Mock Mode)

Mock mode works out of the box - no model file needed.

```bash
# From project root
docker-compose --profile frontend up --build

# Test the service
curl http://localhost:8002/health
curl -X POST http://localhost:8002/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"The AC has been broken for 3 days"}'
```

## Using the Real Model

### 1. Prepare your model files

Place your trained model files in a folder on your machine (NOT in the repo):

```
C:\models\sentiment\
  model.pt               # ~500MB trained model
  tokenizer.json         # Tokenizer data
  tokenizer_config.json  # Tokenizer configuration
  training_history.csv   # Training metrics (optional)
```

### 2. Update docker-compose.yml

Edit the `sentiment` service in `docker-compose.yml`:

```yaml
sentiment:
  profiles: ["frontend"]
  build: ./backend/sentiment-service
  container_name: innovacx-sentiment
  restart: unless-stopped
  environment:
    USE_MOCK_MODEL: "false"          # Change to false
    MODEL_PATH: /app/models
  volumes:
    - C:/models/sentiment:/app/models  # Add this line (your local path)
  ports:
    - "8002:8002"
  networks:
    - innovacx-network
```

### 3. Start the services

```bash
docker-compose --profile frontend up --build
```

### 4. Verify real model is loaded

```bash
curl http://localhost:8002/health
# Should return: {"status":"healthy","mock_mode":false}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/analyze` | POST | Analyze text sentiment |
| `/analyze-combined` | POST | Analyze text + audio features |

### POST /analyze

Request:
```json
{
  "text": "The air conditioning has been broken for three days"
}
```

Response:
```json
{
  "text_sentiment": -0.65,
  "text_urgency": 0.70,
  "keywords": ["AC", "broken"],
  "category": "negative",
  "processing_time_ms": 23.4,
  "mock_mode": true
}
```

### POST /analyze-combined

Request:
```json
{
  "text": "The air conditioning has been broken",
  "audio_features": {
    "mean_energy": 0.08,
    "mean_pitch": 180.5
  }
}
```

Response:
```json
{
  "text_sentiment": -0.65,
  "audio_sentiment": -0.3,
  "combined_sentiment": -0.54,
  "urgency": 0.70,
  "keywords": ["AC", "broken"],
  "confidence": 0.85,
  "mock_mode": true
}
```

## Sentiment Categories

| Score Range | Category |
|-------------|----------|
| -1.0 to -0.6 | very_negative |
| -0.6 to -0.2 | negative |
| -0.2 to 0.2 | neutral |
| 0.2 to 0.6 | positive |
| 0.6 to 1.0 | very_positive |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_MOCK_MODEL` | `true` | Use keyword-based mock analysis |
| `MODEL_PATH` | `/app/models` | Path to model files inside container |

## For Frontend Team

The sentiment analysis is called automatically after audio transcription in `CustomerFillForm.jsx`. The `sentimentAnalysis` state contains the API response.

See the commented section in `CustomerFillForm.jsx` (lines 451-495) for example UI implementation.
