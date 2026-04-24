FROM node:22-alpine

WORKDIR /app

# Install dependencies first (cached layer)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source (overridden by volume mount in dev)
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--port", "3000"]
