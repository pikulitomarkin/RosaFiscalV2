"""
Modelos ORM do banco de dados usando SQLAlchemy.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Numeric, Text
from sqlalchemy.sql import func
from datetime import datetime

from config.database import Base


class NFSeEmissao(Base):
    """Registro de emissões de NFS-e."""
    
    __tablename__ = 'nfse_emissoes'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identificação
    hash_transacao = Column(String(128), unique=True, index=True, nullable=False)
    numero_nfse = Column(String(80), index=True)  # chave Sefin nacional ~50 chars
    protocolo = Column(String(128), index=True)
    codigo_verificacao = Column(String(20))
    
    # Tomador
    cpf_tomador = Column(String(14), index=True, nullable=False)
    nome_tomador = Column(String(150), nullable=False)
    
    # Status
    status = Column(String(20), nullable=False, index=True)  # sucesso, erro, pendente
    mensagem = Column(Text)
    
    # Dados do serviço
    valor_servico = Column(Numeric(10, 2))
    valor_iss = Column(Numeric(10, 2))
    descricao_servico = Column(Text)
    
    # Timestamps
    data_emissao = Column(DateTime, default=datetime.utcnow)
    data_processamento = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=func.now())
    
    # Metadata
    url_nfse = Column(String(1000))
    usuario = Column(String(50))
    
    def __repr__(self):
        return f"<NFSeEmissao(id={self.id}, hash={self.hash_transacao[:8]}..., status={self.status})>"


class LogProcessamento(Base):
    """Log de processamentos em lote."""
    
    __tablename__ = 'logs_processamento'
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identificação do lote
    batch_id = Column(String(36), unique=True, index=True)  # UUID
    
    # Estatísticas
    total_registros = Column(Integer, nullable=False)
    sucessos = Column(Integer, default=0)
    erros = Column(Integer, default=0)
    
    # Arquivos processados
    nome_arquivo = Column(String(255))
    tamanho_arquivo = Column(Integer)  # bytes
    
    # Timing
    inicio_processamento = Column(DateTime, default=datetime.utcnow)
    fim_processamento = Column(DateTime)
    duracao_segundos = Column(Integer)
    
    # Usuário
    usuario = Column(String(50))
    
    # Status
    status = Column(String(20), default='processando')  # processando, concluido, erro
    
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now())
    
    def __repr__(self):
        return f"<LogProcessamento(id={self.id}, batch={self.batch_id}, total={self.total_registros})>"


class Usuario(Base):
    """Usuários do sistema (login Streamlit + emissor NFS-e nacional)."""
    
    __tablename__ = 'usuarios'
    
    id = Column(Integer, primary_key=True, index=True)
    
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # Perfil
    nome_completo = Column(String(150))
    email = Column(String(100), unique=True)

    # Perfil fiscal por usuário (API Sefin nacional — mTLS)
    cnpj = Column(String(14), nullable=True)
    inscricao_municipal = Column(String(30), nullable=True)
    razao_social = Column(String(200), nullable=True)
    nome_fantasia = Column(String(150), nullable=True)
    cert_password = Column(String(255), nullable=True)  # senha do A1 (PFX)
    # Endereço do prestador (por usuário)
    logradouro = Column(String(125), nullable=True)
    numero = Column(String(20), nullable=True)
    complemento = Column(String(60), nullable=True)
    bairro = Column(String(60), nullable=True)
    municipio = Column(String(60), nullable=True)
    uf = Column(String(2), nullable=True)
    cep = Column(String(8), nullable=True)
    email_contato = Column(String(100), nullable=True)
    telefone = Column(String(20), nullable=True)
    codigo_municipio = Column(String(7), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now())
    last_login = Column(DateTime)
    
    def __repr__(self):
        return f"<Usuario(id={self.id}, username={self.username}, cnpj={self.cnpj})>"
