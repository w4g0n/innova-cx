FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY backend/orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy DSPy signal files so priority.py can import them at /app/dspy/
RUN mkdir -p /app/dspy
COPY ai-models/DSPY/signals.py /app/dspy/signals.py
COPY ai-models/DSPY/prioritySignature.py /app/dspy/priority_signature.py

# Copy orchestrator source
COPY backend/orchestrator/ /app/

ENV PYTHONPATH=/app

EXPOSE 8004

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
