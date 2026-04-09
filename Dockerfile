FROM nginx:alpine
COPY docs/ /usr/share/nginx/html/
EXPOSE 80
