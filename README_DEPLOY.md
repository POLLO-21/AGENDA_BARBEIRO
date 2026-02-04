# Guia Passo a Passo de Deploy - Barber Calendar

Este guia explica como colocar seu sistema no ar usando uma VPS (Servidor Virtual), como a da Hostinger.

## 1. Comprar a VPS (Na Hostinger)
1.  No painel da Hostinger, clique em **"Compre agora"** (ou "Setup" se já comprou) na seção VPS.
2.  Escolha o plano **VPS KVM 1** (suficiente para começar).
3.  Em **Imagem do Servidor** (Operating System), escolha **Ubuntu 22.04 64bit**.
4.  Defina uma **Senha de Root** forte e anote-a (você vai precisar dela!).
5.  Finalize a compra e aguarde a ativação.
6.  Anote o **Endereço IP** do seu servidor (ex: `192.168.1.50`).

## 2. Conectar ao Servidor
Você precisa de um terminal para controlar o servidor.
*   **Windows**: Abra o PowerShell ou CMD.
*   **Mac/Linux**: Abra o Terminal.

Digite o comando abaixo (troque pelo seu IP):
```powershell
ssh root@SEU_IP_DA_VPS
```
*   Digite `yes` se perguntar sobre autenticidade.
*   Digite a senha que você criou (o cursor não vai mexer enquanto você digita, é normal).

## 3. Baixar o Código (Via Git)
Agora que está dentro do servidor, vamos baixar seu projeto.
*(Se seu repositório for privado, você precisará gerar um token no GitHub ou usar a opção de upload manual via FileZilla)*.

```bash
# 1. Instale o Git (se não tiver)
apt update && apt install git -y

# 2. Clone seu repositório (Troque pela URL do SEU git)
git clone https://github.com/SEU_USUARIO/agenda_barbeiro.git

# 3. Entre na pasta
cd agenda_barbeiro
```

## 4. Instalar Tudo (Automático)
Criamos um script que faz todo o trabalho difícil (instala Python, Nginx, Banco de Dados, etc).

Estando dentro da pasta `agenda_barbeiro`, rode:

```bash
# Dar permissão de execução
chmod +x setup_vps.sh

# Rodar a instalação
./setup_vps.sh
```

O script vai levar alguns minutos. Quando terminar, ele dirá "Configuração Concluída!".

## 5. Testar
Abra seu navegador e digite o IP da VPS:
`http://SEU_IP_DA_VPS`

Seu sistema deve estar online!

---

## Dúvidas Comuns

### Como atualizar o site depois?
Se você fez alterações no código e subiu para o Git:
1.  Acesse a VPS (`ssh root@...`).
2.  Entre na pasta: `cd agenda_barbeiro`.
3.  Baixe as novidades: `git pull`.
4.  Rode o script de atualização (vamos criar um simples, ou apenas reinicie o serviço):
    ```bash
    systemctl restart barber_calendar
    ```

### O banco de dados zerou?
O banco de dados oficial fica em `/var/www/barber_calendar/instance/agenda.db` (ou na raiz, dependendo da configuração). O script de deploy não apaga o banco existente se você rodar novamente, mas cuidado ao substituir arquivos manualmente.
