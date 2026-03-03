FROM node:20-alpine

WORKDIR /app

# Install dependencies first (cache-friendly)
COPY package*.json ./
RUN npm ci

# Copy the rest of the frontend code
COPY . .
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 5173

# Run Vite dev server
ENTRYPOINT ["docker-entrypoint.sh"]
CMD []
