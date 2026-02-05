#!/bin/bash

# Script para configurar HTTPS (SSL) com Certbot
# Uso: sudo ./setup_ssl.sh

set -e

DOMAIN="barbercalendar.com.br"
WWW_DOMAIN="www.barbercalendar.com.br"

echo "--- Instalando Certbot e Plugin Nginx ---"
apt-get update
apt-get install -y certbot python3-certbot-nginx

echo "--- Obtendo Certificado SSL ---"
echo "O Certbot fará algumas perguntas (e-mail, termos de serviço)."
echo "Por favor, responda 'Y' (Sim) quando solicitado."

# Executa o certbot em modo interativo para o usuário preencher o e-mail se quiser
certbot --nginx -d $DOMAIN -d $WWW_DOMAIN

echo "--- Verificando renovação automática ---"
systemctl status certbot.timer

echo "--- Sucesso! Seu site agora é seguro (HTTPS) ---"
