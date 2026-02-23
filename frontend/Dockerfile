# === frontend Dockerfile ===
# Multi-stage build: Node.js build -> Nginx serve

# ---------- build stage ----------
FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies first (cache layer)
COPY package.json package-lock.json ./
RUN npm ci --no-audit

# Copy source and build
COPY . .
RUN npm run build

# ---------- runtime stage ----------
FROM nginx:1.27-alpine

LABEL maintainer="J2LAB <dev@j2lab.com>"
LABEL description="J2LAB Platform Frontend (React SPA)"

# Remove default nginx config
RUN rm -rf /etc/nginx/conf.d/default.conf /usr/share/nginx/html/*

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx config for SPA routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
