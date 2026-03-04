FROM node:20-alpine

WORKDIR /app

# Install dependencies first (cache-friendly)
COPY package*.json ./
RUN npm ci

# Copy the rest of the frontend code
COPY . .
COPY docker-entrypoint.sh /usr/local/bin/frontend-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/frontend-entrypoint.sh \
  && chmod +x /usr/local/bin/frontend-entrypoint.sh

EXPOSE 5173

# Run Vite dev server
ENTRYPOINT ["/bin/sh", "/usr/local/bin/frontend-entrypoint.sh"]
CMD []
