FROM python:3.11-slim

# Install Node.js 20, curl, ca-certificates
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files first for layer caching
COPY ai_social_agent/requirements.txt ./ai_social_agent/
RUN pip install --no-cache-dir -r ai_social_agent/requirements.txt

COPY ai_social_agent/whatsapp_bridge/package*.json ./ai_social_agent/whatsapp_bridge/
RUN cd ai_social_agent/whatsapp_bridge && npm install --omit=dev

# Copy application files
COPY . .

# Grant executable permission to start script
RUN chmod +x ./ai_social_agent/start_cloud.sh

ENV PORT=10000
ENV PYTHONUNBUFFERED=1
ENV WHATSAPP_MODE=linked_device
ENV WHATSAPP_BRIDGE_URL=http://127.0.0.1:3001

EXPOSE 10000

CMD ["./ai_social_agent/start_cloud.sh"]
