# Guia de Deploy - Agenda Barbeiro

Este guia descreve os passos para colocar o sistema no ar utilizando uma VPS (ex: Hostinger) com Ubuntu 22.04.

## 1. Preparação dos Arquivos
Certifique-se de que você tem todos os arquivos do projeto. Se estiver enviando do Windows, você pode compactar a pasta do projeto (exceto a pasta `.venv` e `__pycache__`) em um arquivo `.zip`.

**Arquivos essenciais:**
- `app.py`
- `storage.py`
- `requirements.txt`
- `setup_vps.sh`
- `templates/` (pasta)
- `static/` (pasta)
- `migrations.sql` (se houver)

## 2. Contratar VPS
1. Contrate um plano de VPS (ex: KVM 1 na Hostinger) com **Ubuntu 22.04 64bit**.
2. Anote o **IP** e a **senha de root** do servidor.

## 3. Acessar o Servidor
Use um terminal (PowerShell, CMD ou Git Bash) para acessar via SSH:
```bash
ssh root@SEU_IP_DA_VPS
# Digite a senha quando pedir
```

## 4. Enviar Arquivos
Você pode usar o comando `scp` (do seu computador local) para enviar o zip ou os arquivos:
```bash
# Exemplo (rode do seu computador, não da VPS):
scp -r "C:\caminho\para\agenda_barbeiro\*" root@SEU_IP_DA_VPS:/var/www/agenda_barbeiro_temp/
```
*Alternativa:* Se preferir, use um cliente SFTP como FileZilla.

## 5. Executar Script de Instalação
No terminal da VPS (SSH), mova os arquivos para o local correto (se não enviou direto) e rode o script:

```bash
# Dê permissão de execução
chmod +x setup_vps.sh

# Execute o script
sudo ./setup_vps.sh
```

O script irá:
1. Atualizar o sistema.
2. Instalar Python, Nginx e Gunicorn.
3. Configurar o firewall.
4. Criar o usuário de serviço.
5. Instalar as dependências do `requirements.txt`.
6. Gerar uma chave de segurança (`.env`).
7. Configurar e iniciar o servidor web.

## 6. Verificação
Acesse `http://SEU_IP_DA_VPS` no navegador. O sistema deve estar rodando.

## Observações
- O número do WhatsApp está configurado em `static/script.js`.
- O banco de dados `agenda.db` será criado automaticamente na primeira execução se não for enviado.
