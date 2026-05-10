FROM node:20-alpine AS base
WORKDIR /app
COPY package.json .
RUN npm install

FROM base AS development
COPY . .
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM base AS builder
COPY . .
RUN npm run build

FROM caddy:2-alpine AS production
COPY --from=builder /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
