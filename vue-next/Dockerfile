# build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY . .
RUN npm install
RUN npm run build

# serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
