"""
Configuração e gerenciamento de conexões com PostgreSQL.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from .settings import settings

# Base para modelos SQLAlchemy
Base = declarative_base()

# Engine assíncrona
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    poolclass=NullPool,  # Para Streamlit, evita problemas com pool
    future=True
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager para obter sessão do banco de dados.
    
    Uso:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_database():
    """Inicializa o banco de dados criando todas as tabelas."""
    from sqlalchemy import text

    # Garante que os modelos estejam registrados no metadata antes do create_all
    from src.database import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Amplia / cria colunas em bases já existentes (create_all não altera)
        if settings.DATABASE_URL.startswith("postgresql"):
            alters = [
                "ALTER TABLE nfse_emissoes ALTER COLUMN hash_transacao TYPE VARCHAR(128)",
                "ALTER TABLE nfse_emissoes ALTER COLUMN protocolo TYPE VARCHAR(128)",
                "ALTER TABLE nfse_emissoes ALTER COLUMN cpf_tomador TYPE VARCHAR(14)",
                "ALTER TABLE nfse_emissoes ALTER COLUMN url_nfse TYPE VARCHAR(1000)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cnpj VARCHAR(14)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS inscricao_municipal VARCHAR(30)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS razao_social VARCHAR(200)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nome_fantasia VARCHAR(150)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cert_password VARCHAR(255)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS logradouro VARCHAR(125)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS numero VARCHAR(20)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS complemento VARCHAR(60)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS bairro VARCHAR(60)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS municipio VARCHAR(60)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS uf VARCHAR(2)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS cep VARCHAR(8)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_contato VARCHAR(100)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS telefone VARCHAR(20)",
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS codigo_municipio VARCHAR(7)",
            ]
            for stmt in alters:
                try:
                    await conn.execute(text(stmt))
                except Exception:
                    # Tabela/coluna inexistente ou já no tamanho certo — ignora
                    pass


async def close_database():
    """Fecha todas as conexões do banco de dados."""
    await engine.dispose()
