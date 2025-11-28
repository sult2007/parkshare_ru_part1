FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Устанавливаем зависимости для FastAPI и LLM-клиента
RUN pip install --no-cache-dir fastapi uvicorn[standard] httpx pydantic

COPY services/llm_service /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
