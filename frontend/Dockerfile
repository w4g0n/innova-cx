FROM node:20-alpine

WORKDIR /app

# Install dependencies first (cache-friendly)
COPY package*.json ./
RUN npm install

# Copy the rest of the frontend code
COPY . .

EXPOSE 5173

# Run Vite dev server
CMD ["npm", "run", "dev", "--", "--host"]