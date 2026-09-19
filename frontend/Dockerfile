FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application files
COPY . .

# Expose port for Next.js dev server
EXPOSE 3000

# Run Next.js
CMD ["npm", "run", "dev"]
