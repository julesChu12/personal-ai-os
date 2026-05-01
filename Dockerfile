FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git curl build-essential && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml /app/
RUN pip install --upgrade pip && pip install -e .
COPY . /app
EXPOSE 8000
