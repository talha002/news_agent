# syntax=docker/dockerfile:1

FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e "."

EXPOSE 8000

ENV HOST=0.0.0.0
ENV PORT=8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
