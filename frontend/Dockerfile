# syntax=docker/dockerfile:1.7

FROM node:25.6.1-bookworm-slim AS base
WORKDIR /app

FROM base AS build
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM base AS development
RUN useradd --create-home --shell /bin/bash codepilot
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN chown -R codepilot:codepilot /app
USER codepilot
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

FROM nginx:1.27.3-alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
