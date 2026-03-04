#!/bin/bash

# Script de Migração para Docker - Barber Calendar
# Este script automatiza a transição do Systemd para Docker mantendo os dados.

set -e

APP_DIR="/var/www/barber_calendar"
NGINX_CONF="/etc/nginx/sites-available/barber_calendar"

echo "--- Iniciando Migração para Docker ---"

# 1. Instalar Docker e Compose se não existirem
if ! command -v docker &> /dev/null; then
    echo "[1/5] Instalando Docker..."
    sudo apt-get update
    sudo apt-get install -y docker.io docker-compose-plugin
    sudo systemctl enable docker
    sudo systemctl start docker
fi

# 2. Entrar no diretório
cd $APP_DIR

# 3. Parar o serviço antigo (Systemd)
echo "[2/5] Parando serviço antigo (Systemd)..."
sudo systemctl stop barber_calendar || true
sudo systemctl disable barber_calendar || true

# 4. Construir e subir o container
echo "[3/5] Construindo e iniciando container Docker..."
sudo docker compose build
sudo docker compose up -d

# 5. Atualizar Nginx para apontar para o Docker (Porta 8000)
echo "[4/5] Atualizando configuração do Nginx..."
# Backup da config atual
sudo cp $NGINX_CONF "${NGINX_CONF}.bak"

# Substitui o proxy_pass de socket unix para localhost:8000
sudo sed -i "s|proxy_pass http://unix:$APP_DIR/barber_calendar.sock;|proxy_pass http://127.0.0.1:8000;|" $NGINX_CONF

# 6. Reiniciar Nginx
echo "[5/5] Reiniciando Nginx..."
sudo nginx -t
sudo systemctl restart nginx

echo "--- Migração Concluída com Sucesso! ---"
echo "O sistema agora está rodando dentro do Docker."
echo "Os dados antigos foram preservados via volume ./instance."
