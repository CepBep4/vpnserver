# Используем Ubuntu 24.04 как базовый образ
FROM ubuntu:24.04

# Устанавливаем переменные окружения
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Устанавливаем необходимые пакеты
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3.12-dev \
    python3-pip \
    curl \
    wget \
    unzip \
    ca-certificates \
    systemd \
    systemd-sysv \
    && rm -rf /var/lib/apt/lists/*

# Создаем символическую ссылку для python
RUN ln -s /usr/bin/python3.12 /usr/bin/python3 && \
    ln -s /usr/bin/python3.12 /usr/bin/python

# Устанавливаем Xray
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        XRAY_ARCH="64"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        XRAY_ARCH="arm64-v8a"; \
    else \
        echo "Unsupported architecture: $ARCH"; exit 1; \
    fi && \
    XRAY_VERSION=$(curl -s https://api.github.com/repos/XTLS/Xray-core/releases/latest | grep tag_name | cut -d '"' -f 4 | sed 's/v//') && \
    wget -q https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-linux-${XRAY_ARCH}.zip -O /tmp/xray.zip && \
    unzip -q /tmp/xray.zip -d /tmp/xray && \
    mv /tmp/xray/xray /usr/local/bin/xray && \
    chmod +x /usr/local/bin/xray && \
    rm -rf /tmp/xray.zip /tmp/xray

# Создаем директории для Xray
RUN mkdir -p /usr/local/etc/xray && \
    mkdir -p /var/log/xray

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости Python
COPY requirements.txt .
RUN pip3 install --upgrade pip && \
    pip3 install -r requirements.txt

# Копируем весь код приложения
COPY . .

# Создаем директорию для базы данных и логирования
RUN mkdir -p /app/data /app/logs && \
    chmod -R 755 /app

# Создаем volume для данных
VOLUME ["/app/data", "/usr/local/etc/xray", "/var/log/xray"]

# Копируем entrypoint скрипт
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Открываем порты
EXPOSE 8000 443

# Используем entrypoint для запуска
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

