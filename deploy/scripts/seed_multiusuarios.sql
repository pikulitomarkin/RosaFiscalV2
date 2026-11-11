-- Seed complementar (preferir seed_multiusuarios.py para bcrypt fresco).
-- Garante colunas do perfil fiscal nacional.

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cnpj VARCHAR(14);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS inscricao_municipal VARCHAR(30);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS razao_social VARCHAR(200);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome_fantasia VARCHAR(150);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cert_password VARCHAR(255);

-- Usuários: rode deploy/scripts/seed_multiusuarios.py no container app
--   nathalia / medico  → CNPJ 56169351000185
--   empresa2 / medico  → CNPJ a preencher em Configurações + PFX
