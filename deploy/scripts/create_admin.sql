-- Cria/atualiza usuário admin na tabela usuarios (rode após o app criar as tabelas)
-- Uso:
--   docker compose exec -T db psql -U nfse -d nfse < deploy/scripts/create_admin.sql
--
-- Substitua o hash abaixo pelo gerado com:
--   python -c "import bcrypt; print(bcrypt.hashpw(b'SUA_SENHA', bcrypt.gensalt()).decode())"

INSERT INTO usuarios (username, password_hash, nome_completo, email, is_active, is_admin)
VALUES (
  'admin',
  '$2b$12$SM5AQL4rOtS0HFkZ.RLCRO8m9ZAynvPfojKTjA5Z5Fij6kxTWzite',
  'Administrador',
  'admin@localhost',
  true,
  true
)
ON CONFLICT (username) DO UPDATE
SET password_hash = EXCLUDED.password_hash,
    is_active = true,
    is_admin = true;
