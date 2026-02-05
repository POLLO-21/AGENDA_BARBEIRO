#!/bin/bash

# Script para atualizar o sistema na VPS rapidamente
# Uso na VPS: ./update_vps.sh

APP_DIR="/var/www/barber_calendar"
USER_NAME="barber_app"

echo "--- Iniciando Atualização do Barber Calendar ---"

# 1. Entrar no diretório
cd $APP_DIR

# 2. Garantir permissões antes do pull (caso root tenha mexido em algo)
chown -R $USER_NAME:www-data $APP_DIR

# 3. Baixar código novo do Git
echo "[1/3] Baixando alterações do Git..."
git reset --hard # Garante que não há conflitos locais
git pull origin main

# 4. Atualizar dependências Python (caso tenha libs novas)
echo "[2/3] Verificando novas dependências..."
su - $USER_NAME -c "cd $APP_DIR && .venv/bin/pip install -r requirements.txt"

# 5. Reiniciar o serviço para aplicar mudanças
echo "[3/3] Reiniciando o servidor..."
systemctl restart barber_calendar

echo "--- Sucesso! O sistema foi atualizado. ---"
