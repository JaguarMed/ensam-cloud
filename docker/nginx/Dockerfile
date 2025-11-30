# ENSAM Cloud Platform - Nginx Reverse Proxy
FROM nginx:alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom config
COPY nginx.conf /etc/nginx/nginx.conf

# Create SSL directory
RUN mkdir -p /etc/nginx/ssl

# Create directory for Let's Encrypt
RUN mkdir -p /var/www/certbot

# Generate self-signed certificate for development
RUN apk add --no-cache openssl && \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/key.pem \
    -out /etc/nginx/ssl/cert.pem \
    -subj "/C=MA/ST=Rabat/L=Rabat/O=ENSAM/CN=localhost"

EXPOSE 80 443 8080

CMD ["nginx", "-g", "daemon off;"]





