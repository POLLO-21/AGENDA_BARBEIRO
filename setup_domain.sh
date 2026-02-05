#!/bin/bash

# Script para configurar o domínio barbercalendar.com.br no Nginx
# Uso: sudo ./setup_domain.sh

set -e

DOMAIN="barbercalendar.com.br www.barbercalendar.com.br"
APP_DIR="/var/www/barber_calendar"

echo "--- Configurando Domínio $DOMAIN ---"

# Atualizar configuração do Nginx
echo "Atualizando arquivo /etc/nginx/sites-available/barber_calendar..."

cat > /etc/nginx/sites-available/barber_calendar <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        include proxy_params;
        proxy_pass http://unix:$APP_DIR/barber_calendar.sock;
    }
}
EOF

# Testar configuração
echo "Testando configuração do Nginx..."
nginx -t

# Recarregar Nginx
echo "Recarregando Nginx..."
systemctl reload nginx

echo "--- Sucesso! O servidor agora aceita conexões para $DOMAIN ---"
echo "Nota: O acesso só funcionará quando o DNS (Registro.br/Hostinger) propagar."
