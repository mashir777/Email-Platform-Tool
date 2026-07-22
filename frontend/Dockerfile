# --- build SPA ---
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# Same-origin deploy: leave empty so browser calls /api on this host
ARG VITE_API_BASE_URL=
ARG VITE_TRACKING_PUBLIC_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_TRACKING_PUBLIC_BASE_URL=$VITE_TRACKING_PUBLIC_BASE_URL

RUN npm run build

# --- nginx gateway ---
FROM nginx:1.27-alpine

COPY nginx.docker.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
