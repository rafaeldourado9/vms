FROM nginx:1.25-alpine

# Instala curl e bind-tools (para getent/nslookup)
RUN apk add --no-cache curl bind-tools

# Remove configuração padrão do nginx
RUN rm /etc/nginx/conf.d/default.conf

# Template da configuração (envsubst injeta DOMAIN em runtime)
COPY nginx.conf.template /etc/nginx/nginx.conf.template

# Script de entrypoint: substitui variáveis e inicia nginx
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Diretório para certificados TLS (montado em runtime via volume)
RUN mkdir -p /etc/nginx/certs /var/www/certbot

# Nginx escuta nas portas 80 (redirect) e 443 (HTTPS)
EXPOSE 80 443

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/health || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
