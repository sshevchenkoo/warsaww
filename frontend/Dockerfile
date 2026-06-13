# Production image for the Next.js frontend (standalone output).
# Build:  docker build -t ghcr.io/<user>/warsaw-web:<tag> .
# By default NEXT_PUBLIC_API_URL is empty, so the browser calls the API with
# relative paths (/search, /health) — same origin as the site, routed by the
# ingress. Pass --build-arg NEXT_PUBLIC_API_URL=https://api.example.com to point
# the frontend at a separate API host instead.

FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S nodejs && adduser -S nextjs -G nodejs
# standalone output already contains the minimal node_modules + server.js
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
