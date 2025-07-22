FROM nginx:alpine

# Copy the built MkDocs site (from repo root)
COPY site/ /usr/share/nginx/html/

# Copy nginx config from same directory
COPY docker/docs/nginx.conf /etc/nginx/nginx.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]