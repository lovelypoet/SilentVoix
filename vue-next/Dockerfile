# build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Empty VITE_API_URL => api.js falls back to /api, which nginx proxies to the api service.
ARG VITE_API_URL=
ARG VITE_EMOTION_MODEL_URL=
ENV VITE_API_URL=$VITE_API_URL \
    VITE_EMOTION_MODEL_URL=$VITE_EMOTION_MODEL_URL
RUN npm run build

# serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
