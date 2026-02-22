FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY ai-models/MultiAgentPipeline/Orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy orchestrator source
COPY ai-models/MultiAgentPipeline/Orchestrator/ /app/
# Copy fuzzy prioritization agent used by orchestrator priority step
COPY ai-models/legacy/MultiAgentPipeline/PrioritizationAgent/ /app/prioritization_agent/
# Copy shared sentiment combiner module
COPY ai-models/legacy/MultiAgentPipeline/SentimentCombiner/ /app/sentiment_combiner/
# Copy sentiment model pipeline code and model assets for local inference
COPY ai-models/legacy/MultiAgentPipeline/SentimentAnalysisAgent_runtime/src/ /app/sentiment_pipeline/
COPY ai-models/legacy/MultiAgentPipeline/SentimentAnalysisAgent_runtime/src/models/ /app/sentiment_models/
# Copy saved Feature Engineering models (RF per target)
COPY ai-models/legacy/MultiAgentPipeline/FeatureEngineeringAgent_runtime/models/ /app/feature_engineering_models/

ENV PYTHONPATH=/app

EXPOSE 8004

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004", "--no-access-log"]
