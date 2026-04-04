# ---- Stage 1: Dependencies ----
FROM node:20-alpine AS deps

ENV COREPACK_ENABLE_STRICT=1
RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml ./

RUN pnpm install --ignore-scripts

# ---- Stage 2: Builder ----
FROM node:20-alpine AS builder

ENV COREPACK_ENABLE_STRICT=1
RUN corepack enable

WORKDIR /app

COPY . .
COPY --from=deps /app/node_modules ./node_modules

ARG NEXT_PUBLIC_API_URL="/api"
ARG NEXT_PUBLIC_WS_URL=""
ARG WIRE_FORMAT="json"

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL
ENV WIRE_FORMAT=$WIRE_FORMAT
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN mkdir -p public

RUN pnpm build

# ---- Stage 3: Runner ----
FROM node:20-alpine AS runner

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

WORKDIR /app

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 -G nodejs nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
