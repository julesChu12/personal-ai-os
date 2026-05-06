FROM python:3.11-slim

# 国内镜像源：apt (清华) + pip (清华)
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml /app/
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --upgrade pip \
    && pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e .

COPY . /app
EXPOSE 8000
