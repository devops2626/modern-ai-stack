# Frontend — Next.js 15 (patched for CVE-2026-44578)
FROM node:20-alpine

WORKDIR /app

# Install dependencies first (better layer caching)
COPY package.json package-lock.json* ./

# Fresh install every build so security bumps in package.json are always picked up.
# --legacy-peer-deps is not required for Next 15 + React 19, but kept as a safety net.
RUN npm install

# App source
COPY . .

EXPOSE 3000

# Dev server (hot reload via volume mount in docker-compose)
CMD ["npm", "run", "dev"]
