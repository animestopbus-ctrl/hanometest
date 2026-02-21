FROM python:3.11-slim

# Developed by: LastPerson07 × RexBots
# Telegram: @RexBots_Official | @THEUPDATEDGUYS
# Project: Hanime Fetcher

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    wget curl gnupg \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    fonts-liberation libappindicator3-1 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium
RUN playwright install chromium && playwright install-deps chromium

# Copy project
COPY . .

# Create necessary directories
RUN mkdir -p downloads logs

CMD ["python", "-u", "bot.py"]
