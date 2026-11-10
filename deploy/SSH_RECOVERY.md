# Recuperação SSH VPS RosaFiscal

## O que aconteceu (evidência)
O Cloud Agent da migração **não desabilitou** login por senha.

Confirmado na VPS (`sshd -T`):
- `PasswordAuthentication yes`
- `PermitRootLogin yes`

O que travou o acesso de agentes novos:

1. **Senha root rotacionada** → só em `/root/rosafiscal_rotated_credentials.txt` na VPS.
2. **Chave SSH do agente** em `/root/.ssh/authorized_keys` (`cursor-agent-rosafiscal-20261105`).
3. A **chave privada** ficou no VM efêmero do Cloud Agent e sumiu no reboot do ambiente.
4. A senha antiga do painel (16 chars) **não funciona mais**.

Porta 22 aberta; métodos: `publickey,password`.

## Caminho recomendado: Terminal do ICP (iContainer)

O painel de controle da VPS (não o app Streamlit) está em:

**https://vps12436.panel.icontainer.site:2090/admin**

(credenciais do e-mail “Setup and Usage Instructions” / portal do cliente iContainer)

1. Login no ICP.
2. Menu **Server → Terminal**.
3. No terminal web (já como root do host), rode:

```bash
cat /root/rosafiscal_rotated_credentials.txt
mkdir -p /root/.ssh && chmod 700 /root/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAIzVVbceUBZMfbnyC/L08wPIaEsVtJdib/05SryzN7O cursor-cloud-rosafiscal-20261110' >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
```

4. Avise neste chat. O agente valida SSH e roda `./deploy/scripts/agent_deploy_vps.sh`.

Wiki iContainer: https://wiki.icontainer.run/en/Acessando-terminal-ssh

## Alternativas
- **Reset Root Password** no ICP + secret Cursor `SSHPASS` com a nova senha.
- Restaurar a chave privada antiga (`SHA256:Sd7sCsZK…`) como `ROSAFISCAL_SSH_KEY`, se ainda existir no cofre.

## O que NÃO funciona
- `SSHPASS` = senha antiga do painel.
- Chave `…20261110` deste agente **antes** de ser adicionada ao `authorized_keys`.
- Brute-force SSH (fail2ban).

## Fail2ban (importante)
O Cloud Agent viu a porta 22 alternar entre `Permission denied` e `Connection refused` após tentativas falhas.  
No Terminal do ICP, além de autorizar a chave, rode:

```bash
fail2ban-client set sshd unbanip --all 2>/dev/null || fail2ban-client reload sshd
# ou: bash /opt/rosafiscal/deploy/scripts/icp_recover_ssh.sh
# (após git pull do branch — se o script ainda não estiver na VPS, cole o conteúdo de deploy/scripts/icp_recover_ssh.sh)
```

O agente **não** deve continuar tentando senha até a chave estar autorizada.

## App (sem SSH)
- https://vps12436.panel.icontainer.site/  (Streamlit)
- http://184.107.179.79:8501
- ICP: https://vps12436.panel.icontainer.site:2090/admin
