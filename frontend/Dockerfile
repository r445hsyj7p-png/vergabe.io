FROM node:22-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM base AS development
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM base AS builder
COPY . .
RUN npm run build

FROM caddy:2-alpine AS production
COPY --from=builder /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
