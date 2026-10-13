FROM node:20-slim

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application files
COPY . .

# Set environment variables for production build
ENV NODE_ENV=production
ENV HOSTNAME="0.0.0.0"
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_OPTIONS="--max-old-space-size=2048"

# Build production bundle with Webpack
RUN npm run build

# Expose port for Next.js server
EXPOSE 3000

# Run production Next.js
CMD ["npm", "run", "start"]
