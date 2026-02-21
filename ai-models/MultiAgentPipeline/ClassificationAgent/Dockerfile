FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements and install (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and API
COPY src/ /app/src/
COPY api.py /app/api.py

ENV PYTHONPATH=/app/src

EXPOSE 8003

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8003"]
