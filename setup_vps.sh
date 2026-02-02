#!/bin/bash

# Script de Configuração Automática para Agenda Barbeiro na VPS (Ubuntu 22.04)
# Uso: sudo ./setup_vps.sh

set -e

APP_DIR="/var/www/agenda_barbeiro"
USER_NAME="barbeiro_app"
DOMAIN_OR_IP="seu_dominio_ou_ip_aqui" # Será substituído pelo usuário ou detectado automaticamente

echo "--- Iniciando Configuração do Servidor ---"

# 1. Atualizar sistema
echo "[1/8] Atualizando pacotes do sistema..."
apt-get update && apt-get upgrade -y

# 2. Instalar dependências
echo "[2/8] Instalando Python, Nginx e ferramentas..."
apt-get install -y python3-pip python3-venv nginx git ufw

# 3. Configurar Firewall
echo "[3/8] Configurando Firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
# ufw enable # Comentado para evitar bloqueio acidental se não estiver interativo, ative manualmente se desejar

# 4. Criar usuário do sistema para a aplicação (segurança)
if id "$USER_NAME" &>/dev/null; then
    echo "Usuário $USER_NAME já existe."
else
    echo "[4/8] Criando usuário de serviço $USER_NAME..."
    useradd -m -s /bin/bash $USER_NAME
fi

# 5. Configurar diretório da aplicação
echo "[5/8] Configurando diretório $APP_DIR..."
mkdir -p $APP_DIR
# Permissões: usuário barbeiro_app é dono, mas grupo www-data tem acesso
chown -R $USER_NAME:www-data $APP_DIR
chmod -R 775 $APP_DIR

echo "IMPORTANTE: Agora você deve fazer upload dos arquivos do projeto para $APP_DIR"
echo "Pressione ENTER quando os arquivos estiverem lá (ou CTRL+C para cancelar e rodar depois)..."
# Em um script 100% automático poderíamos pular isso, mas aqui precisamos garantir que os arquivos existam
# Para facilitar, vamos assumir que o usuário vai rodar este script APÓS subir os arquivos, ou o script cria a estrutura básica.

# Vamos criar o venv de qualquer forma
echo "[6/8] Configurando Ambiente Virtual Python..."
su - $USER_NAME -c "cd $APP_DIR && python3 -m venv .venv"
su - $USER_NAME -c "cd $APP_DIR && .venv/bin/pip install -r requirements.txt" || echo "AVISO: requirements.txt não encontrado ou erro na instalação. Verifique o upload dos arquivos."

# Gerar .env com SECRET_KEY seguro se não existir
echo "Gerando .env com chave de segurança..."
su - $USER_NAME -c "cd $APP_DIR && if [ ! -f .env ]; then echo \"SECRET_KEY=$(openssl rand -hex 32)\" > .env; fi"

# 6. Configurar Gunicorn (Systemd Service)
echo "[7/8] Criando serviço Systemd para Gunicorn..."
cat > /etc/systemd/system/agenda_barbeiro.service <<EOF
[Unit]
Description=Gunicorn instance to serve agenda_barbeiro
After=network.target

[Service]
User=$USER_NAME
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/.venv/bin"
ExecStart=$APP_DIR/.venv/bin/gunicorn --workers 3 --bind unix:agenda_barbeiro.sock -m 007 app:app

[Install]
WantedBy=multi-user.target
EOF

systemctl start agenda_barbeiro
systemctl enable agenda_barbeiro

# 7. Configurar Nginx
echo "[8/8] Configurando Nginx..."
cat > /etc/nginx/sites-available/agenda_barbeiro <<EOF
server {
    listen 80;
    server_name $DOMAIN_OR_IP;

    location / {
        include proxy_params;
        proxy_pass http://unix:$APP_DIR/agenda_barbeiro.sock;
    }
}
EOF

ln -sf /etc/nginx/sites-available/agenda_barbeiro /etc/nginx/sites-enabled
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "--- Configuração Concluída! ---"
echo "Verifique se o serviço está rodando com: systemctl status agenda_barbeiro"
echo "Acesse seu servidor pelo IP ou Domínio."
