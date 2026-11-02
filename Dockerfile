FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed for Playwright / Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    ca-certificates \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

# Copy application files
COPY . .

# Environment settings
ENV PYTHONUNBUFFERED=1
ENV DRY_RUN=false

# Run background hourly watcher daemon
CMD ["python", "main.py", "--watch", "--interval", "60"]

