# Solicitar senha do portal NFS-e (cutover VPS)

Use este texto com a contabilidade / Domínio Contábil. **Não** cole a senha no chat do Cursor — peçam para devolver por canal seguro (cofre / 1Password / WhatsApp da empresa) e apliquem na VPS.

## Destinatário sugerido
Contabilidade responsável pelo CNPJ `56169351000185` (Nathalia Gabriela Serviços de Saúde Ltda) — Santa Rosa-RS.

## Assunto
Senha do portal NFS-e Santa Rosa (webservice IPM) — migração do sistema

## Corpo

```text
Olá,

Estamos finalizando a migração do sistema de emissão de NFS-e para o novo servidor
(https://vps12436.panel.icontainer.site/).

Para autenticar no webservice da prefeitura (IPM/Atende.Net) precisamos da
mesma senha de login do contribuinte no portal:

  https://nfse-santarosa.atende.net/
  CNPJ: 56169351000185

Não é a senha do dashboard Streamlit (usuário admin).

Se possível:
1) confirmem a senha atual, ou
2) usem "Recuperar Senha" no portal e nos enviem a nova por canal seguro.

Obrigado.
```

## Como aplicar na VPS (quem opera o servidor)

1. Dashboard → Configurações → Senha IPM → Salvar → Testar conexão  
   (login admin: `cat /root/rosafiscal_rotated_credentials.txt` via SSH), **ou**
2. Secret Cursor `IPM_SENHA` + `./deploy/scripts/agent_apply_ipm_senha.sh`, **ou**
3. Arquivo `/opt/rosafiscal/secrets/ipm_senha` (watcher aplica em ≤1 min)

Validar:
```bash
/opt/rosafiscal/deploy/scripts/post_cutover_check.sh
```
