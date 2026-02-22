FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create models directory (for when real model is available)
RUN mkdir -p /app/models

EXPOSE 8002

# Default to mock mode
ENV USE_MOCK_MODEL=true

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8002"]
