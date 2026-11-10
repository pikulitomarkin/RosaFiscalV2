# Recuperação SSH VPS RosaFiscal

## O que aconteceu (evidência)
O Cloud Agent da migração (`cursor/migracao-vps-ddd1`, ~2026-11-05) **não desabilitou** login por senha.

Confirmado na VPS na época (`sshd -T`):
- `PasswordAuthentication yes`
- `PermitRootLogin yes`

O que mudou e “travou” o acesso de agentes novos:

1. **Senha root rotacionada** (`chpasswd` + `openssl rand`) → valor só em  
   `/root/rosafiscal_rotated_credentials.txt` (chmod 600) **dentro da VPS**.
2. **Chave SSH do agente** instalada em `/root/.ssh/authorized_keys`  
   (`cursor-agent-rosafiscal-20261105`, fingerprint `SHA256:Sd7sCsZK…`).
3. A **chave privada** ficou só em `~/.ssh/rosafiscal_vps` do VM efêmero do agente  
   e **não** foi salva em secret Cursor / Git / artifact. No reboot do ambiente Cloud Agent, essa chave sumiu.
4. A senha antiga do painel (16 chars) **não funciona mais**.

Porta 22 continua aberta; autenticações oferecidas: `publickey,password`.

## Caminhos de acesso (ordem)

### 1) Console / VNC do provedor iContainer (recomendado)
No painel de hospedagem que criou a VPS `vps12436` / `184.107.179.79` (não confundir com o app Streamlit):

1. Abra **Console / VNC / KVM / Recovery**.
2. Login como `root` (use “reset root password” do painel se o console não aceitar a senha).
3. Leia as credenciais rotacionadas:
   ```bash
   cat /root/rosafiscal_rotated_credentials.txt
   ```
4. Autorize o Cloud Agent atual (pubkey):
   ```bash
   mkdir -p /root/.ssh && chmod 700 /root/.ssh
   echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAIzVVbceUBZMfbnyC/L08wPIaEsVtJdib/05SryzN7O cursor-cloud-rosafiscal-20261110' >> /root/.ssh/authorized_keys
   chmod 600 /root/.ssh/authorized_keys
   ```
5. (Opcional) Atualize o secret Cursor `SSHPASS` com `ROOT_PASSWORD` do arquivo.
6. Avise o agente → `./deploy/scripts/agent_deploy_vps.sh`

### 2) Reset de senha root no painel do provedor
Se o console não tiver a senha atual: use a ação **Reset Root Password** do iContainer e coloque o novo valor no secret `SSHPASS`.

### 3) Chave antiga do agente (só se ainda existir no cofre)
Fingerprint da chave que está em `authorized_keys` da VPS:  
`SHA256:Sd7sCsZK4O0C+UuZutiH1YoagxWICULnJsR8vJyBHgU`  
Se alguém salvou essa privada como `ROSAFISCAL_SSH_KEY`, restaure em `~/.ssh/rosafiscal_vps`.

## O que NÃO funciona
- Secret `SSHPASS` = senha antiga do painel (já invalidada).
- Chave gerada neste Cloud Agent (`…20261110`) — **ainda não** está em `authorized_keys`.
- Brute-force SSH (fail2ban ativo).

## App ainda no ar (sem SSH)
- https://vps12436.panel.icontainer.site/
- http://184.107.179.79:8501
