# Google Cloud Run Dockerfile for Rotary Grant & SPC Orchestrator
FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr (essential for Cloud Run real-time logging)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8080 \
    HOST=0.0.0.0

WORKDIR /app

# Install system utilities needed for Playwright & Git
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser and its system shared libraries
RUN playwright install --with-deps chromium

# Copy application source code
COPY . .

# Expose default Cloud Run port
EXPOSE 8080

# Launch orchestrator
CMD ["python", "orchestrator.py"]
