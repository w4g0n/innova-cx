FROM node:20-alpine

WORKDIR /app

# Install dependencies first (cache-friendly)
COPY package*.json ./
RUN npm ci

# Copy the rest of the frontend code
COPY . .

EXPOSE 5173

# Run Vite dev server
ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]
CMD []
