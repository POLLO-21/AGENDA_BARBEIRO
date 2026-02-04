#!/bin/bash

# Script de Configuração Automática para Barber Calendar na VPS (Ubuntu 22.04)
# Uso: sudo ./setup_vps.sh

set -e

APP_DIR="/var/www/barber_calendar"
USER_NAME="barber_app"
DOMAIN_OR_IP="_" # "_" aceita qualquer IP ou domínio

# Diretório atual onde o script está rodando
CURRENT_DIR=$(pwd)

echo "--- Iniciando Configuração do Servidor ---"

# 1. Atualizar sistema
echo "[1/9] Atualizando pacotes do sistema..."
apt-get update && apt-get upgrade -y

# 2. Instalar dependências
echo "[2/9] Instalando Python, Nginx e ferramentas..."
apt-get install -y python3-pip python3-venv nginx git ufw acl

# 3. Configurar Firewall
echo "[3/9] Configurando Firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
# ufw enable # Ative manualmente se confirmar que tem acesso SSH

# 4. Criar usuário do sistema
if id "$USER_NAME" &>/dev/null; then
    echo "Usuário $USER_NAME já existe."
else
    echo "[4/9] Criando usuário de serviço $USER_NAME..."
    useradd -m -s /bin/bash $USER_NAME
fi

# 5. Configurar diretório da aplicação
echo "[5/9] Configurando diretório $APP_DIR..."
mkdir -p $APP_DIR

# Copiar arquivos do diretório atual para o diretório de destino (se não for o mesmo)
if [ "$CURRENT_DIR" != "$APP_DIR" ]; then
    echo "Copiando arquivos de $CURRENT_DIR para $APP_DIR..."
    cp -r ./* $APP_DIR/
    # Garantir que setup_vps.sh não seja copiado recursivamente se estiver dentro
fi

# Ajustar permissões
echo "Ajustando permissões..."
chown -R $USER_NAME:www-data $APP_DIR
chmod -R 775 $APP_DIR

# 6. Configurar Ambiente Virtual
echo "[6/9] Configurando Ambiente Virtual Python..."
su - $USER_NAME -c "cd $APP_DIR && python3 -m venv .venv"
su - $USER_NAME -c "cd $APP_DIR && .venv/bin/pip install -r requirements.txt" || echo "ERRO: Falha ao instalar requirements.txt"

# Gerar .env se não existir
echo "Verificando .env..."
su - $USER_NAME -c "cd $APP_DIR && if [ ! -f .env ]; then echo \"SECRET_KEY=$(openssl rand -hex 32)\" > .env; fi"

# Garantir permissão de escrita no banco de dados (se existir ou para a pasta instance)
su - $USER_NAME -c "mkdir -p $APP_DIR/instance"
chown -R $USER_NAME:www-data $APP_DIR/instance
chmod -R 775 $APP_DIR/instance

# 6. Configurar Gunicorn (Systemd Service)
echo "[7/8] Criando serviço Systemd para Gunicorn..."
cat > /etc/systemd/system/barber_calendar.service <<EOF
[Unit]
Description=Gunicorn instance to serve barber_calendar
After=network.target

[Service]
User=$USER_NAME
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/.venv/bin"
ExecStart=$APP_DIR/.venv/bin/gunicorn --workers 3 --bind unix:barber_calendar.sock -m 007 app:app

[Install]
WantedBy=multi-user.target
EOF

systemctl start barber_calendar
systemctl enable barber_calendar

# 7. Configurar Nginx
echo "[8/8] Configurando Nginx..."
cat > /etc/nginx/sites-available/barber_calendar <<EOF
server {
    listen 80;
    server_name $DOMAIN_OR_IP;

    location / {
        include proxy_params;
        proxy_pass http://unix:$APP_DIR/barber_calendar.sock;
    }
}
EOF

ln -sf /etc/nginx/sites-available/barber_calendar /etc/nginx/sites-enabled
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "--- Configuração Concluída! ---"
echo "Verifique se o serviço está rodando com: systemctl status barber_calendar"
echo "Acesse seu servidor pelo IP ou Domínio."
