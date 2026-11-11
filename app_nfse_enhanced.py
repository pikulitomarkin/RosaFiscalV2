"""
Dashboard Streamlit APRIMORADO para Emissão de NFS-e Nacional.
Agora com funcionalidade de download de XML e PDF!
"""
import streamlit as st
import asyncio
import re
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys
import os
import base64
from io import BytesIO
import json
import zipfile
import bcrypt
import psycopg2

# Adiciona diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

# Imports do projeto
from config.settings import settings
from config.database import init_database
from src.auth.authentication import auth_manager
from src.pdf.extractor import pdf_extractor
from src.api.nfse_service import get_nfse_service
from src.database.repository import NFSeRepository, LogRepository
from src.models.schemas import ProcessingResult, PrestadorServico, TomadorServico, Servico
from src.utils.logger import app_logger
from src.utils.certificate import get_certificate_manager

# IPM: emissão via Atende.Net (Basic Auth — certificado não necessário para envio)
from src.api.ipm_soap_client import IPMSoapClient as _IPMSoapClient


def _gerar_pdf_nota_ipm(nota: dict) -> bytes:
    """
    Gera PDF da NFS-e IPM no layout idêntico ao emitido pela Prefeitura de Santa Rosa-RS.
    """
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.2*cm, rightMargin=1.2*cm,
                            topMargin=1.2*cm, bottomMargin=1.2*cm)
    styles = getSampleStyleSheet()

    AZUL   = colors.HexColor("#1a3a6e")
    CINZA  = colors.HexColor("#f2f2f2")
    BRANCO = colors.white
    PRETO  = colors.black

    def P(text, fs=7, bold=False, align=TA_LEFT, color=PRETO, font=None, leading=None):
        fn = font or ('Helvetica-Bold' if bold else 'Helvetica')
        return Paragraph(text, ParagraphStyle('_', parent=styles['Normal'],
                         fontSize=fs, fontName=fn, textColor=color,
                         alignment=align, leading=leading or (fs + 2)))

    def label(text):
        return P(text, fs=6, color=colors.HexColor("#555555"))

    def secao(text):
        return Table([[P(text, fs=8, bold=True, color=BRANCO)]],
                     colWidths=[W],
                     style=[('BACKGROUND', (0,0), (-1,-1), AZUL),
                            ('TOPPADDING', (0,0), (-1,-1), 3),
                            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                            ('LEFTPADDING', (0,0), (-1,-1), 6)])

    def grid_style(alternado=True):
        base = [('BOX', (0,0), (-1,-1), 0.5, PRETO),
                ('INNERGRID', (0,0), (-1,-1), 0.3, colors.lightgrey),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ('LEFTPADDING', (0,0), (-1,-1), 5),
                ('RIGHTPADDING', (0,0), (-1,-1), 3)]
        return TableStyle(base)

    W = 18.6 * cm

    # — Dados da nota —
    numero       = str(nota.get('numero', 'N/A'))
    chave        = str(nota.get('chave_acesso', ''))
    data_emissao = str(nota.get('data_emissao', ''))
    tomador_nome = str(nota.get('tomador_nome', 'NI'))
    tomador_cpf  = str(nota.get('tomador_cpf', 'NI'))
    tomador_cep  = str(nota.get('tomador_cep', 'NI'))
    tomador_bairro    = str(nota.get('tomador_bairro', 'NI'))
    tomador_logradouro= str(nota.get('tomador_logradouro', 'NI'))
    valor        = float(nota.get('valor', 0))
    aliquota     = float(nota.get('aliquota_iss', 2.01))
    descricao    = str(nota.get('descricao', 'CONSULTA MEDICA'))
    codigo_serv  = str(nota.get('codigo_servico', '40303'))
    link         = str(nota.get('link_nfse', '') or '')

    data_fato = data_emissao.split()[0] if data_emissao else ''

    # Formatar CPF/CNPJ
    cpf_c = tomador_cpf.replace('.','').replace('-','').replace('/','')
    if len(cpf_c) == 11:
        cpf_fmt = f"{cpf_c[:3]}.{cpf_c[3:6]}.{cpf_c[6:9]}-{cpf_c[9:]}"
    elif len(cpf_c) == 14:
        cpf_fmt = f"{cpf_c[:2]}.{cpf_c[2:5]}.{cpf_c[5:8]}/{cpf_c[8:12]}-{cpf_c[12:]}"
    else:
        cpf_fmt = tomador_cpf

    valor_fmt     = f"{valor:.2f}".replace('.', ',')
    aliquota_fmt  = f"{aliquota:.2f}%"

    # Prestador (fixo para Nathalia Gabriela)
    PR_NOME  = "NATHALIA GABRIELA SERVICOS DE SAUDE LTDA"
    PR_CNPJ  = "56.169.351/0001-85"
    PR_END   = "RUA TARQUÍNIO DE OLIVEIRA - 249"
    PR_CEP   = "98.789-104"
    PR_BAIRRO= "CRUZEIRO"
    PR_MUN   = "SANTA ROSA - RIO GRANDE DO SUL"
    PR_IM    = "56937"
    PR_EMAIL = "cadastro@dominiocontabil.com.br"
    PR_TEL   = "(48) 3632-7480 - Celular: (48) 93632-7480"

    story = []

    # ── 1. CABEÇALHO: Prestador (esq) + NFS-e info (dir) ──────────────────────
    prest_inner = Table([
        [P(PR_NOME, fs=8, bold=True)],
        [P(f"CNPJ: {PR_CNPJ}", fs=7)],
        [P(f"{PR_END},", fs=7)],
        [P(f"CEP: {PR_CEP} - Bairro: {PR_BAIRRO}", fs=7)],
        [P(f"Município: {PR_MUN}", fs=7)],
        [P(f"Insc. Municipal: {PR_IM} - Insc. Estadual:", fs=7)],
        [P(f"Email: {PR_EMAIL} Telefone: {PR_TEL}", fs=7)],
    ], colWidths=[12.8*cm],
       style=[('TOPPADDING',(0,0),(-1,-1),1), ('BOTTOMPADDING',(0,0),(-1,-1),1),
              ('LEFTPADDING',(0,0),(-1,-1),4)])

    nfse_inner = Table([
        [label("Número da NFS-e"), label("Situação")],
        [P(numero, fs=14, bold=True, align=TA_CENTER), P("Emitida", fs=8, bold=True)],
        [label("Tipo"), P("")],
        [P("Preenchido", fs=7), P("")],
        [label("Autenticidade"), P("")],
        [P("Ver rodapé", fs=6, color=colors.blue), P("")],
    ], colWidths=[2.8*cm, 3.0*cm],
       style=[('TOPPADDING',(0,0),(-1,-1),1), ('BOTTOMPADDING',(0,0),(-1,-1),1),
              ('LEFTPADDING',(0,0),(-1,-1),4)])

    header = Table([[prest_inner, nfse_inner]], colWidths=[12.8*cm, 5.8*cm])
    header.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.6, PRETO),
        ('LINEBEFORE', (1,0), (1,-1), 0.5, PRETO),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(header)
    story.append(Spacer(1, 1.5*mm))

    # ── 2. TÍTULO ──────────────────────────────────────────────────────────────
    titulo_t = Table([[P("Nota Fiscal de Serviço Eletrônica - Série NFS-e",
                         fs=10, bold=True, align=TA_CENTER)]],
                     colWidths=[W])
    titulo_t.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.6, PRETO),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(titulo_t)
    story.append(Spacer(1, 1.5*mm))

    # ── 3. LOGOS + IDENTIFICADOR ──────────────────────────────────────────────
    id_inner = Table([
        [label("Identificador")],
        [P(chave, fs=6.5, font='Courier', align=TA_CENTER)],
    ], colWidths=[7.0*cm],
       style=[('TOPPADDING',(0,0),(-1,-1),1), ('BOTTOMPADDING',(0,0),(-1,-1),1)])

    logos_t = Table([[
        P("ESTADO DO RIO GRANDE DO SUL\nPREFEITURA MUNICIPAL DE SANTA ROSA\nSECRETARIA MUNICIPAL DE FAZENDA",
          fs=7, bold=True),
        P("SANTA ROSA\nBERÇO NACIONAL DA SOJA", fs=7, bold=True, align=TA_CENTER),
        P("NFS-e\nNacional", fs=8, bold=True, align=TA_CENTER),
        id_inner,
    ]], colWidths=[5.0*cm, 3.0*cm, 3.6*cm, 7.0*cm])
    logos_t.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.6, PRETO),
        ('INNERGRID', (0,0), (-1,-1), 0.4, PRETO),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(logos_t)
    story.append(Spacer(1, 1.5*mm))

    # ── 4. DATAS ───────────────────────────────────────────────────────────────
    datas_t = Table([
        [label("Data Fato Gerador"), label("Data/Hora Emissão")],
        [P(data_fato, fs=8, bold=True), P(data_emissao, fs=8, bold=True)],
    ], colWidths=[W/2, W/2])
    datas_t.setStyle(grid_style())
    story.append(datas_t)
    story.append(Spacer(1, 1.5*mm))

    # ── 5. TOMADOR ─────────────────────────────────────────────────────────────
    story.append(secao("TOMADOR DO SERVIÇO"))
    tomador_t = Table([
        [label("Nome/Razão Social"), label(""), label("CPF/CNPJ")],
        [P(tomador_nome, fs=7.5), P(""), P(cpf_fmt, fs=7.5)],
        [label("Endereço"), label("Número"), label("Complemento")],
        [P(tomador_logradouro, fs=7), P("NI", fs=7), P("NÃO INFORMADO", fs=7)],
        [label("Bairro"), label("CEP"), label("Cidade")],
        [P(tomador_bairro, fs=7), P(tomador_cep, fs=7), P("Santa Rosa - RS", fs=7)],
        [label("País"), label("Telefone"), label("Email")],
        [P("Brasil - BR - 1058", fs=7), P("Não Informado", fs=7), P("Não Informado", fs=7)],
    ], colWidths=[W*0.45, W*0.20, W*0.35])
    tomador_t.setStyle(grid_style())
    story.append(tomador_t)
    story.append(Spacer(1, 1.5*mm))

    # ── 6. SERVIÇOS ────────────────────────────────────────────────────────────
    story.append(secao("DESCRIÇÃO DOS SERVIÇOS PRESTADOS"))
    cw = [1.9*cm, 2.1*cm, 1.7*cm, 2.1*cm, 2.3*cm, 2.3*cm, 2.3*cm, 3.9*cm]
    servico_t = Table([
        [label("Serviço"), label("Local Prestação"), label("Alíquota"),
         label("Situação Trib."), label("Valor Serviço"),
         label("Desc. Incondic."), label("Valor Dedução"), label("Valor ISS")],
        [P(codigo_serv, fs=7, bold=True), P("8847", fs=7, bold=True),
         P(aliquota_fmt, fs=7, bold=True), P("TI", fs=7, bold=True),
         P(valor_fmt, fs=7, bold=True), P("0,00", fs=7),
         P("0,00", fs=7), P("SIMPLES NACIONAL", fs=6.5, bold=True)],
    ], colWidths=cw)
    servico_t.setStyle(grid_style())
    story.append(servico_t)

    desc_t = Table([
        [label("Descrição do Serviço:")],
        [P(descricao, fs=7)],
    ], colWidths=[W])
    desc_t.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 0.5, PRETO),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(desc_t)
    story.append(Spacer(1, 1.5*mm))

    # ── 7. TOTAIS ──────────────────────────────────────────────────────────────
    cw5 = [W/5]*5
    totais_t = Table([
        [label("Valor Total"), label("Desc. Incondicional"), label("Dedução"),
         label("Base de Cálculo"), label("ISSQN")],
        [P(valor_fmt, fs=7, bold=True), P("0,00", fs=7), P("0,00", fs=7),
         P(valor_fmt, fs=7, bold=True), P("SIMPLES NACIONAL", fs=6.5, bold=True)],
        [label("ISSRF"), label("IR"), label("INSS"), label("CSLL"), label("COFINS")],
        [P("0,00", fs=7)]*5,
        [label("PIS"), label("Outras Retenções"), label("Total Trib. Federais"),
         label("Desc. Condicional"), label("Valor Líquido")],
        [P("0,00", fs=7), P("0,00", fs=7), P("0,00", fs=7),
         P("0,00", fs=7), P(valor_fmt, fs=7, bold=True)],
    ], colWidths=cw5)
    totais_t.setStyle(grid_style())
    story.append(totais_t)
    story.append(Spacer(1, 3*mm))

    # ── 8. RODAPÉ ──────────────────────────────────────────────────────────────
    s_rod = ParagraphStyle('rod', parent=styles['Normal'], fontSize=6.5, leading=9)
    s_chave = ParagraphStyle('chave', parent=styles['Normal'], fontSize=7,
                             fontName='Courier', leading=10,
                             backColor=colors.HexColor("#eeeeee"))

    story.append(P(f"Descrição dos subitens da Lista de Serviço em acordo com a Lei Complementar 116/03.", fs=6.5))
    story.append(P(f"{codigo_serv} - Clínicas, sanatórios, manicômios, casas de saúde, prontos-socorros, ambulatórios e congêneres.", fs=6.5))
    story.append(Spacer(1, 1*mm))
    story.append(P("TI - Tributada Integralmente", fs=6.5))
    story.append(P(f"({codigo_serv}) Serviço tributado no município do prestador", fs=6.5))
    story.append(P("Contribuinte enquadrado como Simples - Homologado de ISS ou ISS em regime estimado/fixo", fs=6.5))
    story.append(Spacer(1, 2*mm))

    if link:
        story.append(P("A veracidade das informações declaradas na NFS-e podem ser consultadas no site:", fs=6.5))
        story.append(Paragraph(f"<link href='{link}' color='blue'>{link}</link>", s_rod))
        story.append(Spacer(1, 2*mm))

    story.append(P("Chave de Acesso NFS-e Nacional", fs=6, color=colors.grey))
    story.append(Paragraph(chave, s_chave))

    doc.build(story)
    buf.seek(0)
    return buf.read()


def _gerar_zip_pdfs_ipm(links_nfse: list) -> tuple:
    """
    Gera PDFs das NFS-e e empacota em ZIP.

    Estratégia:
    1. Se nota dict com dados completos → gera PDF local via ReportLab
    2. Fallback: tenta baixar do portal (pode falhar por reCAPTCHA)

    Args:
        links_nfse: lista de (nome, numero, link, xml_path) ou dicts com dados da nota

    Returns:
        (BytesIO com o ZIP, int com quantidade de PDFs gerados com sucesso, list de erros)
    """
    import io

    zip_buffer = io.BytesIO()
    gerados = 0
    erros = []

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, entrada in enumerate(links_nfse, 1):
            # Suporte a dict (nota completa) ou tupla legada
            if isinstance(entrada, dict):
                nota = entrada
                nome = nota.get('tomador_nome', f'nota_{i}')
                numero = nota.get('numero', str(i))
            else:
                if len(entrada) == 4:
                    nome, numero, link, xml_path = entrada
                else:
                    nome, numero, link = entrada
                    xml_path = None
                nota = {'tomador_nome': nome, 'numero': numero, 'link_nfse': link}

            nome_arquivo = f"nfse_{numero or i:03}_{re.sub(r'[^A-Za-z0-9]', '_', nome)[:20]}.pdf"

            # --- Gera PDF dos dados locais ---
            try:
                pdf_bytes = _gerar_pdf_nota_ipm(nota)
                zf.writestr(nome_arquivo, pdf_bytes)
                gerados += 1
                app_logger.info(f"PDF gerado: {nome_arquivo} ({len(pdf_bytes)} bytes)")
            except Exception as e:
                erros.append(f"#{i} {nome}: {e}")
                app_logger.warning(f"Erro ao gerar PDF de {nome}: {e}")

    if erros:
        app_logger.warning(f"PDFs com erro ({len(erros)}): {erros}")

    zip_buffer.seek(0)
    return zip_buffer, gerados, erros

# Configuração da página
st.set_page_config(
    page_title="NFS-e Automation Pro",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================================
# FUNÇÕES DE PERSISTÊNCIA DE DADOS
# ============================================================================

# Diretório de dados persistentes (Railway ou local)
# Se RAILWAY_VOLUME_MOUNT_PATH existe, usa ele diretamente (já aponta para /app/data)
# Senão, cria pasta 'data' no diretório local
DATA_DIR = Path(os.getenv('RAILWAY_VOLUME_MOUNT_PATH', './data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)
PERSISTENCE_FILE = DATA_DIR / "nfse_emitidas.json"

def save_emitted_nfse():
    """Salva as NFS-e emitidas em arquivo JSON (cache local) e no banco de dados."""
    # 1. Salva no arquivo JSON como cache local
    try:
        PERSISTENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PERSISTENCE_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.emitted_nfse, f, ensure_ascii=False, indent=2)
        app_logger.info(f"Notas salvas em {PERSISTENCE_FILE}: {len(st.session_state.emitted_nfse)} registros")
    except Exception as e:
        app_logger.error(f"Erro ao salvar JSON local: {e}")

    # 2. Salva no banco de dados (fonte primária)
    try:
        _sync_notas_para_db(st.session_state.emitted_nfse)
    except Exception as e:
        app_logger.error(f"Erro ao salvar no banco de dados: {e}")


def load_emitted_nfse():
    """Carrega NFS-e emitidas — prioriza banco de dados, fallback para JSON."""
    # 1. Tenta carregar do banco de dados
    try:
        notas_db = _load_notas_do_db()
        if notas_db:
            app_logger.info(f"Notas carregadas do banco: {len(notas_db)} registros")
            return notas_db
    except Exception as e:
        app_logger.warning(f"Banco indisponível, usando JSON local: {e}")

    # 2. Fallback: arquivo JSON local
    try:
        if PERSISTENCE_FILE.exists():
            with open(PERSISTENCE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                app_logger.info(f"Notas carregadas do JSON: {len(data)} registros")
                return data
    except Exception as e:
        app_logger.error(f"Erro ao carregar JSON local: {e}")
    return []


def _sync_notas_para_db(notas: list):
    """Salva notas no banco de dados (upsert por chave_acesso)."""
    from sqlalchemy import select
    from src.database.models import NFSeEmissao
    from config.database import AsyncSessionLocal

    def _trunc(value, size: int) -> str:
        text_val = str(value or '')
        return text_val[:size] if size > 0 else text_val

    async def _upsert():
        salvas = 0
        for nota in notas:
            chave = nota.get('chave_acesso') or nota.get('numero')
            if not chave or chave == 'N/A':
                continue
            chave = _trunc(chave, 128)
            cpf = str(nota.get('tomador_cpf', '') or '').replace('.', '').replace('-', '').replace('/', '')
            try:
                async with AsyncSessionLocal() as session:
                    stmt = select(NFSeEmissao).where(NFSeEmissao.hash_transacao == chave)
                    result = await session.execute(stmt)
                    existing = result.scalar_one_or_none()
                    if existing:
                        continue  # já existe, não duplica

                    emissao = NFSeEmissao(
                        hash_transacao=chave,
                        numero_nfse=_trunc(nota.get('numero', ''), 20),
                        protocolo=_trunc(chave, 128),
                        cpf_tomador=(cpf[:14] if cpf else '00000000000'),
                        nome_tomador=_trunc(nota.get('tomador_nome', ''), 150),
                        status='sucesso',
                        url_nfse=_trunc(nota.get('link_nfse'), 1000) or None,
                        valor_servico=nota.get('valor'),
                        valor_iss=nota.get('iss'),
                        descricao_servico=nota.get('descricao'),
                        usuario=_trunc(st.session_state.get('username', 'admin'), 50),
                    )
                    session.add(emissao)
                    await session.commit()
                    salvas += 1
            except Exception as e:
                app_logger.error(f"Falha ao persistir nota {chave}: {e}")
        app_logger.info(f"Sync DB concluído: {salvas} novas notas persistidas")

    asyncio.run(_upsert())


def _load_notas_do_db() -> list:
    """Carrega todas as notas com sucesso do banco de dados."""
    from sqlalchemy import select
    from src.database.models import NFSeEmissao
    from config.database import AsyncSessionLocal

    async def _query():
        async with AsyncSessionLocal() as session:
            stmt = select(NFSeEmissao).where(
                NFSeEmissao.status == 'sucesso'
            ).order_by(NFSeEmissao.created_at.desc())
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [
                {
                    'chave_acesso': r.hash_transacao,
                    'numero': r.numero_nfse or 'N/A',
                    'data_emissao': r.created_at.strftime("%d/%m/%Y %H:%M:%S") if r.created_at else 'N/A',
                    'tomador_nome': r.nome_tomador,
                    'tomador_cpf': r.cpf_tomador,
                    'valor': float(r.valor_servico or 0),
                    'iss': float(r.valor_iss or 0),
                    'xml_path': None,
                    'pdf_path': None,
                    'link_nfse': r.url_nfse,
                }
                for r in rows
            ]

    return asyncio.run(_query())


# ============================================================================
# FUNÇÕES DE SESSÃO E AUTENTICAÇÃO
# ============================================================================

def init_session_state():
    """Inicializa variáveis de sessão."""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'page' not in st.session_state:
        st.session_state.page = 'login'
    if 'emitted_nfse' not in st.session_state:
        # Carrega notas salvas do arquivo
        st.session_state.emitted_nfse = load_emitted_nfse()
    if 'last_emission' not in st.session_state:
        st.session_state.last_emission = None


def _sync_database_dsn() -> str:
    """DSN síncrono (psycopg2) a partir de DATABASE_URL / settings."""
    raw = os.getenv("DATABASE_URL") or getattr(settings, "DATABASE_URL", "")
    return str(raw).replace("postgresql+asyncpg://", "postgresql://", 1)


def autenticar_usuario_db(username: str, password: str) -> bool:
    """Autentica usuário via tabela usuarios (Postgres) ou fallback ADMIN_*."""
    dsn = _sync_database_dsn()
    if dsn.startswith("postgresql://"):
        try:
            conn = psycopg2.connect(dsn)
            cur = conn.cursor()
            cur.execute(
                "SELECT password_hash, is_active FROM usuarios WHERE username = %s",
                (username,)
            )
            row = cur.fetchone()
            conn.close()
            if row:
                password_hash, is_active = row
                if is_active and bcrypt.checkpw(
                    password.encode("utf-8"), password_hash.encode("utf-8")
                ):
                    return True
                # Senha do banco não bate — tenta fallback ADMIN_* abaixo
            # Usuário inexistente no banco: também tenta fallback ADMIN_*
        except Exception as e:
            app_logger.error(f"Erro ao autenticar via banco: {e}")

    # Fallback: credenciais ADMIN_* do .env (bootstrap / senha redefinida na VPS)
    try:
        return auth_manager.authenticate_user(username, password)
    except Exception as e:
        app_logger.error(f"Erro no fallback de autenticação: {e}")
        return False


def login_page():
    """Renderiza página de login."""
    st.title("🔐 Sistema de Emissão NFS-e")
    st.markdown("### Portal de Automação de Notas Fiscais")
    st.caption("API Nacional (Sefin) · Santa Rosa-RS · multiusuário")
    st.caption("URL oficial: https://vps12436.panel.icontainer.site/")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        with st.form("login_form"):
            st.markdown("#### Credenciais de Acesso")
            username = st.text_input("Usuário", placeholder="nathalia ou guilherme")
            password = st.text_input("Senha", type="password", placeholder="Digite sua senha")
            submit = st.form_submit_button("🚀 Entrar", use_container_width=True)

            if submit:
                if autenticar_usuario_db(username, password):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.token = "authenticated"
                    st.session_state.page = 'dashboard'
                    st.session_state.emitted_nfse = load_emitted_nfse()
                    try:
                        from src.users.profile import ensure_user_columns
                        ensure_user_columns()
                    except Exception:
                        pass
                    st.success("✅ Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha inválidos")


def logout():
    """Realiza logout."""
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.token = None
    st.session_state.page = 'login'
    st.session_state.emitted_nfse = []
    st.session_state.last_emission = None
    st.rerun()


# ============================================================================
# DASHBOARD PRINCIPAL
# ============================================================================

def render_dashboard():
    """Renderiza dashboard principal."""
    st.sidebar.title("⚙️ Menu Principal")
    st.sidebar.markdown(f"👤 **Usuário:** {st.session_state.username}")
    st.sidebar.caption("Produção: vps12436.panel.icontainer.site")
    try:
        from src.users.profile import cert_pronto, get_user_profile, read_cert_subject
        _prof = get_user_profile(st.session_state.username or "")
        if _prof and _prof.cnpj:
            st.sidebar.caption(f"CNPJ {_prof.cnpj}")
            if _prof.razao_social:
                st.sidebar.caption(_prof.razao_social)
        elif _prof:
            st.sidebar.caption("CNPJ não configurado")
        if _prof and not cert_pronto(_prof):
            subj = read_cert_subject(_prof)
            perfil_cnpj = re.sub(r"\D", "", _prof.cnpj or "")
            if subj.get("cnpj") and perfil_cnpj and subj["cnpj"] != perfil_cnpj:
                st.sidebar.error("Certificado ≠ CNPJ do perfil")
            else:
                st.sidebar.warning("Certificado A1 pendente")
    except Exception:
        pass
    st.sidebar.markdown("---")

    # Sem certificado A1 → abre Configurações na 1ª visita
    menu_opts = [
        "📊 Dashboard",
        "📤 Emissão Individual",
        "📋 Emissão em Lote",
        "📜 NFS-e Emitidas",
        "⚙️ Configurações",
    ]
    try:
        from src.users.profile import cert_pronto, get_user_profile
        _p = get_user_profile(st.session_state.username or "")
        if _p and not cert_pronto(_p) and not st.session_state.get("_cert_prompt_shown"):
            st.session_state.menu_navigation = "⚙️ Configurações"
            st.session_state._cert_prompt_shown = True
    except Exception:
        pass

    menu = st.sidebar.radio(
        "Navegação",
        menu_opts,
        key="menu_navigation",
    )
    
    if st.sidebar.button("🚪 Sair", use_container_width=True):
        logout()
    
    # Renderiza página selecionada
    if menu == "📊 Dashboard":
        render_overview()
    elif menu == "📤 Emissão Individual":
        render_single_emission()
    elif menu == "📋 Emissão em Lote":
        render_batch_emission()
    elif menu == "📜 NFS-e Emitidas":
        render_emitted_nfse_list()
    elif menu == "⚙️ Configurações":
        render_settings()


def render_overview():
    """Renderiza página de overview."""
    from src.users.profile import cert_pronto, get_user_profile
    from src.utils.runtime_config import get_emission_backend

    st.title("📊 Dashboard - Visão Geral")
    profile = get_user_profile(st.session_state.username or "")
    razao = (profile.razao_social if profile and profile.razao_social else "—")
    cnpj = (profile.cnpj if profile and profile.cnpj else "—")
    st.caption(f"Emissor: {razao} · CNPJ {cnpj} · backend={get_emission_backend()}")
    if not profile or not cert_pronto(profile):
        st.warning(
            "Certificado A1 ou CNPJ ainda não configurados. Vá em **⚙️ Configurações**, "
            "informe o CNPJ e envie o PFX com a senha do certificado."
        )

    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("NFS-e Emitidas", len(st.session_state.emitted_nfse))
    
    with col2:
        total_valor = sum([nfse.get('valor', 0) for nfse in st.session_state.emitted_nfse])
        st.metric("Valor Total", f"R$ {total_valor:,.2f}")
    
    with col3:
        st.metric("Sistema", "✅ Operacional")
    
    with col4:
        st.metric("Cert A1", "✅ OK" if profile and cert_pronto(profile) else "⚠️ Pendente")
    
    st.markdown("---")
    
    # Últimas emissões
    st.markdown("### 📋 Últimas Emissões")
    
    if st.session_state.emitted_nfse:
        for nfse in reversed(st.session_state.emitted_nfse[-5:]):
            with st.expander(f"🧾 NFS-e #{nfse.get('numero', 'N/A')} - {nfse.get('data_emissao', 'N/A')}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Chave de Acesso:** `{nfse.get('chave_acesso', 'N/A')}`")
                    st.markdown(f"**Tomador:** {nfse.get('tomador_nome', 'N/A')}")
                    st.markdown(f"**CPF/CNPJ:** {nfse.get('tomador_cpf', 'N/A')}")
                
                with col2:
                    st.markdown(f"**Valor:** R$ {nfse.get('valor', 0):,.2f}")
                    st.markdown(f"**ISS:** R$ {nfse.get('iss', 0):,.2f}")
                    
                    # Botões de download
                    if nfse.get('link_nfse'):
                        st.link_button("📄 PDF da NFS-e (Prefeitura)", nfse['link_nfse'])
    else:
        st.info("ℹ️ Nenhuma NFS-e emitida ainda")


# ============================================================================
# EMISSÃO INDIVIDUAL
# ============================================================================

def render_single_emission():
    """Renderiza página de emissão individual."""
    from src.utils.runtime_config import get_shared_tax_config

    st.title("📤 Emissão Individual de NFS-e")
    st.markdown("Emita uma NFS-e única com dados preenchidos manualmente")
    st.markdown("---")
    
    with st.form("single_emission_form"):
        st.markdown("### 👤 Dados do Tomador")
        
        col1, col2 = st.columns(2)
        
        with col1:
            tomador_cpf = st.text_input(
                "CPF/CNPJ do Tomador *",
                placeholder="000.000.000-00",
                help="CPF ou CNPJ do cliente que está recebendo o serviço"
            )
            
            tomador_nome = st.text_input(
                "Nome/Razão Social *",
                placeholder="Nome completo ou razão social"
            )
        
        with col2:
            tomador_email = st.text_input(
                "E-mail",
                placeholder="cliente@email.com"
            )
            
            tomador_telefone = st.text_input(
                "Telefone",
                placeholder="(00) 00000-0000"
            )
        
        st.markdown("### 🏠 Endereço do Tomador")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            tomador_cep = st.text_input("CEP", placeholder="00000-000")
        with col2:
            tomador_logradouro = st.text_input("Logradouro", placeholder="Rua, Avenida...")
        with col3:
            tomador_numero = st.text_input("Número", placeholder="123")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            tomador_bairro = st.text_input("Bairro", placeholder="Centro")
        with col2:
            tomador_cidade = st.text_input("Cidade", placeholder="Porto Alegre")
        with col3:
            tomador_uf = st.selectbox(
                "UF",
                ["RS", "SP", "RJ", "MG", "PR", "SC", "BA", "PE", "CE", "DF", "GO", "ES", "PA", "MA", 
                 "MT", "MS", "RO", "AC", "AM", "RR", "AP", "TO", "AL", "SE", "RN", "PB", "PI"]
            )
        
        st.markdown("### 💼 Dados do Serviço")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            valor_servico = st.number_input(
                "Valor do Serviço (R$) *",
                min_value=0.01,
                value=100.00,
                step=10.00,
                format="%.2f"
            )
        
        with col2:
            aliquota_iss = st.number_input(
                "Alíquota ISS (%) *",
                min_value=0.0,
                max_value=5.0,
                value=2.01,
                step=0.01,
                format="%.2f"
            )
        
        with col3:
            item_lista = st.text_input(
                "Item Lista LC 116/2003 *",
                value="40303",
                help="Código IPM do serviço (5 dígitos, sem pontos). Ex: 40303 = Clínicas e congêneres"
            )
        
        descricao_servico = st.text_area(
            "Descrição do Serviço *",
            value="Prestação de serviços conforme contrato",
            height=100,
            help="Descrição detalhada do serviço prestado"
        )
        
        hash_paciente = st.text_input(
            "Hash do Paciente",
            help="Hash do paciente (opcional - aparecerá na DANFSE)"
        )
        
        discriminacao = st.text_area(
            "Discriminação Adicional",
            height=80,
            help="Informações adicionais sobre o serviço (opcional)"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            incentivador_cultural = st.checkbox("Incentivador Cultural")
        
        with col2:
            simples_nacional = st.checkbox("Optante pelo Simples Nacional", value=True)
        
        st.markdown("---")
        
        # Botão de emissão
        submitted = st.form_submit_button(
            "🚀 Emitir NFS-e",
            use_container_width=True,
            type="primary"
        )
    
    # Processar submissão FORA do form
    if submitted:
        from src.users.profile import cert_pronto, get_user_profile
        # Validação básica
        if not tomador_cpf or not tomador_nome or not valor_servico:
            st.error("❌ Preencha todos os campos obrigatórios (*)")
        else:
            profile = get_user_profile(st.session_state.username or "")
            if not profile or not cert_pronto(profile):
                st.error(
                    "❌ Certificado A1 / CNPJ não configurados. Vá em **⚙️ Configurações**, "
                    "envie o PFX com a senha do certificado e salve o CNPJ."
                )
            else:
                cpf_limpo = tomador_cpf.replace('.', '').replace('-', '').replace('/', '')

                registro = {
                    "cpf": cpf_limpo,
                    "nome": tomador_nome,
                    "hash": hash_paciente or "",
                    "bairro": tomador_bairro or "NAO INFORMADO",
                    "cep": (tomador_cep or "").replace("-", "") or "00000000",
                    "logradouro": tomador_logradouro or "NAO INFORMADO",
                }
                _tax = get_shared_tax_config()
                config_servico = {
                    "valor": valor_servico,
                    "aliquota_iss": aliquota_iss,
                    "item_lista": item_lista.replace(".", ""),
                    "descricao": hash_paciente if hash_paciente and hash_paciente.strip() else descricao_servico,
                    "simples_nacional": simples_nacional,
                    "mei": bool(_tax.get("mei", False)) if simples_nacional else False,
                    "op_simp_nac": (
                        1 if not simples_nacional
                        else int(_tax.get("op_simp_nac") or (2 if _tax.get("mei") else 3))
                    ),
                    "reg_ap_trib_sn": int(_tax.get("reg_ap_trib_sn") or 1),
                }

                with st.spinner("⏳ Emitindo NFS-e via API Nacional (Sefin)... Por favor aguarde..."):
                    try:
                        results = asyncio.run(
                            get_nfse_service(st.session_state.username).emitir_nfse_lote(
                                [registro], config_servico
                            )
                        )
                        r = results[0]
                        sucesso = r.status == "sucesso"

                        if sucesso:
                            st.success("✅ NFS-e emitida com sucesso!")

                            nfse_data = {
                                'chave_acesso': r.numero_nfse or r.protocolo or 'N/A',
                                'numero': r.numero_nfse or 'N/A',
                                'data_emissao': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                'tomador_nome': tomador_nome,
                                'tomador_cpf': tomador_cpf,
                                'tomador_bairro': tomador_bairro or 'NI',
                                'tomador_cep': tomador_cep or 'NI',
                                'tomador_logradouro': tomador_logradouro or 'NI',
                                'valor': valor_servico,
                                'iss': valor_servico * (aliquota_iss / 100),
                                'aliquota_iss': aliquota_iss,
                                'descricao': hash_paciente if hash_paciente and hash_paciente.strip() else descricao_servico,
                                'codigo_servico': item_lista.replace(".", ""),
                                'xml_path': None,
                                'pdf_path': None,
                                'link_nfse': r.link_nfse,
                                'usuario': st.session_state.username,
                            }

                            st.session_state.emitted_nfse.append(nfse_data)
                            st.session_state.last_emission = nfse_data
                            save_emitted_nfse()

                            st.markdown("---")
                            st.markdown("### ✅ NFS-e Emitida com Sucesso!")

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Número/Chave", (r.numero_nfse or 'N/A')[:24])
                            with col2:
                                st.metric("Valor", f"R$ {valor_servico:,.2f}")
                            with col3:
                                st.metric("ISS", f"R$ {valor_servico * (aliquota_iss / 100):,.2f}")

                            st.markdown("**🔑 Chave de acesso:**")
                            st.code(r.numero_nfse or r.protocolo or 'N/A', language=None)

                            if r.link_nfse:
                                st.markdown("**📄 PDF da NFS-e:**")
                                st.link_button("Baixar PDF da NFS-e", r.link_nfse)

                        else:
                            st.error(f"❌ Erro ao emitir NFS-e: {r.mensagem or 'Erro desconhecido'}")

                    except Exception as e:
                        st.error(f"❌ Erro ao emitir NFS-e: {str(e)}")
                        app_logger.error(f"Erro na emissão individual Sefin: {e}", exc_info=True)


# ============================================================================
# EMISSÃO EM LOTE (MANTIDO DO ORIGINAL)
# ============================================================================

def _processar_emissao_lote(
    records_to_process,
    valor_servico,
    aliquota_iss,
    item_lista,
    descricao_servico,
    discriminacao,
    simples_nacional=True,
):
    """Processa emissão em lote FORA do st.form para não interromper o Streamlit."""
    from src.users.profile import cert_pronto, get_user_profile
    from src.utils.runtime_config import get_shared_tax_config

    username = st.session_state.username or ""
    profile = get_user_profile(username)
    _tax = get_shared_tax_config()
    if not profile or not cert_pronto(profile):
        st.error(
            "❌ Certificado A1 / CNPJ não configurados. Vá em **⚙️ Configurações**, "
            "envie o PFX com a senha do certificado e tente o lote novamente."
        )
        return

    st.markdown("### 4️⃣ Processamento em Andamento")

    # Barra de progresso
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Painel de logs em tempo real
    log_expander = st.expander("📋 Ver Logs Detalhados", expanded=False)
    log_text = log_expander.empty()
    logs = []

    resultados = []
    sucessos = 0
    falhas = 0

    DELAY_ENTRE_EMISSOES = 2   # segundos entre cada nota do lote (throttling)

    def _emitir_sefin_registro(registro_dict, config_dict):
        """Emite uma NFS-e via API Nacional (Sefin) com certificado do usuário."""
        results = asyncio.run(
            get_nfse_service(username).emitir_nfse_lote([registro_dict], config_dict)
        )
        r = results[0]
        return {
            "sucesso": r.status == "sucesso",
            "chave_acesso": r.numero_nfse or r.protocolo or "N/A",
            "numero": r.numero_nfse or "N/A",
            "xml_path": None,
            "pdf_path": None,
            "link_nfse": r.link_nfse,
            "mensagem": r.mensagem or "",
        }

    for idx, record in enumerate(records_to_process):
        status_text.text(f"⏳ Processando {idx+1}/{len(records_to_process)}: {record.get('nome', 'N/A')}...")

        try:
            log_msg = f"[{idx+1}/{len(records_to_process)}] Processando: {record.get('nome', 'N/A')}"
            logs.append(log_msg)
            log_text.code("\n".join(logs[-20:]))
            app_logger.info(log_msg)

            cpf_cnpj = (record.get('cpf') or '').replace('.', '').replace('-', '').replace('/', '')
            hash_paciente = record.get('hash', '') or ''
            app_logger.info(f"[{idx+1}] CPF limpo: {cpf_cnpj}, Hash: {hash_paciente}")

            descricao_com_hash = hash_paciente if hash_paciente else descricao_servico
            discriminacao_com_hash = discriminacao if discriminacao else ""
            if hash_paciente:
                if discriminacao_com_hash:
                    discriminacao_com_hash += f"\nHash do Paciente: {hash_paciente}"
                else:
                    discriminacao_com_hash = f"Hash do Paciente: {hash_paciente}"

            # Valor fixo do formulário (> 0) substitui o valor do PDF
            if valor_servico > 0:
                valor_nota = valor_servico
                fonte_valor = "formulário (fixo)"
            else:
                valor_nota = record.get('valor') or 0
                fonte_valor = "PDF"
            app_logger.info(f"[{idx+1}] Emitindo via Sefin (valor={valor_nota}, fonte={fonte_valor}, user={username})...")

            _reg = {
                "cpf": cpf_cnpj,
                "nome": record.get("nome", ""),
                "hash": hash_paciente,
                "bairro": record.get("bairro", "NAO INFORMADO"),
                "cep": (record.get("cep") or "").replace("-", "") or "00000000",
                "logradouro": record.get("logradouro", "NAO INFORMADO"),
            }
            _sn = bool(simples_nacional)
            _cfg = {
                "valor": float(valor_nota),
                "aliquota_iss": aliquota_iss,
                "item_lista": (item_lista or "40303").replace(".", ""),
                "descricao": descricao_com_hash,
                "simples_nacional": _sn,
                "mei": bool(_tax.get("mei", False)) if _sn else False,
                "op_simp_nac": (
                    1 if not _sn else int(_tax.get("op_simp_nac") or (2 if _tax.get("mei") else 3))
                ),
                "reg_ap_trib_sn": int(_tax.get("reg_ap_trib_sn") or 1),
            }
            resultado = _emitir_sefin_registro(_reg, _cfg)
            app_logger.info(f"[{idx+1}] Emissão concluída: {resultado.get('sucesso', False)}")

            # Throttling: 2 segundos entre cada emissão
            time.sleep(DELAY_ENTRE_EMISSOES)

            if resultado['sucesso']:
                sucessos += 1
                chave = str(resultado.get('chave_acesso') or 'N/A')
                logs.append(f"  ✅ Sucesso! Chave: {chave[:20]}...")
                log_text.code("\n".join(logs[-20:]))

                nfse_data = {
                    'chave_acesso': chave,
                    'numero': resultado.get('numero', 'N/A'),
                    'data_emissao': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    'tomador_nome': record.get('nome', 'N/A'),
                    'tomador_cpf': record.get('cpf', 'N/A'),
                    'tomador_bairro': record.get('bairro', 'NI'),
                    'tomador_cep': record.get('cep', 'NI'),
                    'tomador_logradouro': record.get('logradouro', 'NI'),
                    'valor': float(valor_nota),
                    'iss': float(valor_nota) * (aliquota_iss / 100),
                    'aliquota_iss': aliquota_iss,
                    'descricao': descricao_com_hash,
                    'codigo_servico': (item_lista or '40303').replace('.', ''),
                    'xml_path': None,
                    'pdf_path': None,
                    'link_nfse': resultado.get('link_nfse'),
                }

                st.session_state.emitted_nfse.append(nfse_data)
                save_emitted_nfse()

                resultados.append({
                    'nome': record.get('nome'),
                    'cpf': record.get('cpf'),
                    'status': '✅ Sucesso',
                    'chave': chave,
                })
            else:
                falhas += 1
                logs.append(f"  ❌ Falha: {resultado.get('mensagem', 'Erro desconhecido')[:50]}")
                log_text.code("\n".join(logs[-20:]))
                resultados.append({
                    'nome': record.get('nome'),
                    'cpf': record.get('cpf'),
                    'status': '❌ Falha',
                    'erro': resultado.get('mensagem', 'Erro desconhecido')
                })

        except Exception as e:
            falhas += 1
            erro_msg = str(e)
            app_logger.error(f"[{idx+1}] ERRO COMPLETO: {erro_msg}", exc_info=True)

            logs.append(f"  ❌ ERRO: {erro_msg[:80]}")
            log_text.code("\n".join(logs[-20:]))

            resultados.append({
                'nome': record.get('nome', 'N/A'),
                'cpf': record.get('cpf', 'N/A'),
                'status': '❌ Erro',
                'erro': erro_msg[:100],
            })
            status_text.text(f"❌ Erro no registro {idx+1}: {erro_msg[:50]}...")

        # Atualizar progresso
        progress = (idx + 1) / len(records_to_process)
        progress_bar.progress(progress)

    # Finalizar
    status_text.text("✅ Processamento concluído!")

    st.markdown("### 5️⃣ Resultado do Processamento")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Processado", len(records_to_process))

    with col2:
        st.metric("✅ Sucessos", sucessos)

    with col3:
        st.metric("❌ Falhas", falhas)

    # Tabela de resultados
    st.markdown("### 📊 Detalhamento")

    import pandas as pd
    df_result = pd.DataFrame(resultados)
    st.dataframe(df_result, use_container_width=True)

    # Gerar ZIP com PDFs baixados dos links IPM
    if sucessos > 0:
        st.success(f"🎉 {sucessos} NFS-e emitidas com sucesso!")

        try:
            with st.spinner("📦 Gerando PDFs e criando ZIP..."):
                notas_recentes = st.session_state.emitted_nfse[-sucessos:]
                zip_buffer, baixados, erros_dl = _gerar_zip_pdfs_ipm(notas_recentes)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                zip_filename = f"nfse_lote_{timestamp}.zip"

            if baixados > 0:
                st.success(f"✅ {baixados}/{sucessos} PDFs prontos para download!")
                st.download_button(
                    label=f"📥 Baixar {baixados} PDFs (ZIP)",
                    data=zip_buffer,
                    file_name=zip_filename,
                    mime="application/zip",
                    use_container_width=True,
                    type="primary",
                )
            else:
                st.warning("⚠️ PDFs ainda não disponíveis nos links da Prefeitura.")
                st.info("💡 Use os links individuais em 'NFS-e Emitidas' para baixar depois.")

            if erros_dl:
                with st.expander(f"⚠️ {len(erros_dl)} PDFs não baixados"):
                    for err in erros_dl:
                        st.text(err)

        except Exception as e:
            st.error(f"❌ Erro ao preparar ZIP: {e}")
            app_logger.error(f"Erro ao gerar ZIP de PDFs IPM: {e}", exc_info=True)


def render_batch_emission():
    """Renderiza página de emissão em lote."""
    st.title("📋 Emissão em Lote de NFS-e")
    st.markdown("Processe múltiplas NFS-e a partir de um arquivo PDF")
    st.markdown("---")
    
    # Upload do PDF
    st.markdown("### 1️⃣ Upload do Arquivo PDF")
    
    uploaded_file = st.file_uploader(
        "Selecione o arquivo PDF com os registros",
        type=['pdf'],
        help="PDF contendo CPF, Nome e Hash das transações"
    )
    
    if uploaded_file is not None:
        # Salvar arquivo temporariamente
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.read())
            pdf_path = tmp_file.name
        
        st.success(f"✅ Arquivo carregado: {uploaded_file.name}")
        
        # Extrair dados do PDF
        st.markdown("### 2️⃣ Extração de Dados")
        
        with st.spinner("⏳ Extraindo dados do PDF..."):
            try:
                records = pdf_extractor.extract_from_file(Path(pdf_path))
                
                if records:
                    st.success(f"✅ {len(records)} registros encontrados!")
                    
                    # Estatísticas
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Total de Registros", len(records))
                    
                    with col2:
                        valid_records = [r for r in records if r.get('cpf') and r.get('nome')]
                        st.metric("Registros Válidos", len(valid_records))
                    
                    with col3:
                        taxa = (len(valid_records) / len(records) * 100) if records else 0
                        st.metric("Taxa de Sucesso", f"{taxa:.1f}%")
                    
                    # Preview dos dados
                    with st.expander("👁️ Visualizar Dados Extraídos"):
                        import pandas as pd
                        
                        # Preparar dataframe para exibição
                        display_data = []
                        for r in valid_records:
                            valor_pdf = r.get('valor')
                            display_data.append({
                                'Nome': r.get('nome', 'N/A'),
                                'CPF': r.get('cpf_formatado', r.get('cpf', 'N/A')),
                                'Telefone': r.get('telefone', 'Não informado'),
                                'Email': r.get('email', 'Não informado'),
                                'Data Consulta': r.get('data_consulta', 'N/A'),
                                'Valor (R$)': f"{valor_pdf:.2f}" if valor_pdf else 'Não encontrado'
                            })
                        
                        df = pd.DataFrame(display_data)
                        st.dataframe(df, use_container_width=True)
                        
                        registros_sem_valor = sum(1 for r in valid_records if not r.get('valor'))
                        if registros_sem_valor > 0:
                            st.warning(f"⚠️ **{registros_sem_valor} registro(s)** sem valor no PDF. Para esses, será usado o valor padrão configurado abaixo.")
                        else:
                            st.success("✅ Valor extraído do PDF para todos os registros. O valor do formulário abaixo será usado apenas como fallback.")
                    
                    # Configuração do serviço
                    st.markdown("### 3️⃣ Configuração do Serviço")
                    
                    with st.form("batch_config_form"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            valor_servico = st.number_input(
                                "💰 Valor Fixo (R$) — 0 = usar valor do PDF",
                                min_value=0.0,
                                value=0.0,
                                step=1.00,
                                format="%.2f",
                                help="Se preenchido (> 0), todas as notas serão emitidas com esse valor. Se deixar em 0, cada nota usará o valor extraído do PDF."
                            )
                            
                            aliquota_iss = st.number_input(
                                "Alíquota ISS (%) *",
                                min_value=0.0,
                                max_value=5.0,
                                value=2.0,
                                step=0.1,
                                format="%.2f"
                            )
                        
                        with col2:
                            item_lista = st.text_input(
                                "Item Lista LC 116/2003 *",
                                value="40303",
                                help="Código IPM do serviço (5 dígitos, sem pontos). Ex: 40303 = Análises clínicas (vinculado ao NBS 1.2301.21.00 em Santa Rosa-RS)"
                            )
                            
                            simples_nacional = st.checkbox("Optante pelo Simples Nacional", value=True)
                        
                        descricao_servico = st.text_area(
                            "Descrição do Serviço *",
                            value="Prestação de serviços conforme contrato",
                            height=100
                        )
                        
                        discriminacao = st.text_area(
                            "Discriminação Adicional (Opcional)",
                            height=80
                        )
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            limite_lote = st.number_input(
                                "Limite de NFS-e por vez",
                                min_value=1,
                                max_value=200,
                                value=min(100, len(valid_records)),
                                help="Quantidade de notas a processar neste lote"
                            )
                        
                        with col2:
                            tempo_estimado = limite_lote * 2  # ~2 segundos por nota
                            st.info(f"⏱️ Tempo estimado: ~{tempo_estimado//60} min {tempo_estimado%60} seg")
                        
                        st.markdown("---")
                        
                        # Resumo antes de processar
                        st.markdown("### 📊 Resumo do Lote")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Registros", min(limite_lote, len(valid_records)))
                        
                        with col2:
                            # Calcula valor total: se valor fixo definido usa ele; senão usa valor do PDF de cada registro
                            registros_resumo = valid_records[:min(limite_lote, len(valid_records))]
                            if valor_servico > 0:
                                valor_total = valor_servico * len(registros_resumo)
                            else:
                                valor_total = sum(r.get('valor') or 0 for r in registros_resumo)
                            st.metric("Valor Total", f"R$ {valor_total:,.2f}")

                        with col3:
                            iss_total = valor_total * (aliquota_iss / 100)
                            st.metric("ISS Total", f"R$ {iss_total:,.2f}")

                        with col4:
                            if valor_servico > 0:
                                st.metric("Fonte do valor", "Fixo (formulário)")
                            else:
                                com_valor_pdf = sum(1 for r in registros_resumo if r.get('valor'))
                                st.metric("Com valor do PDF", f"{com_valor_pdf}/{len(registros_resumo)}")
                        
                        st.markdown("---")
                        
                        submitted = st.form_submit_button(
                            "🚀 Iniciar Emissão em Lote",
                            use_container_width=True,
                            type="primary"
                        )

                    # Processamento FORA do form — evita reload/interrupção do Streamlit
                    if submitted:
                        if not valid_records:
                            st.error("❌ Nenhum registro válido encontrado!")
                        else:
                            _processar_emissao_lote(
                                records_to_process=valid_records[:limite_lote],
                                valor_servico=valor_servico,
                                aliquota_iss=aliquota_iss,
                                item_lista=item_lista,
                                descricao_servico=descricao_servico,
                                discriminacao=discriminacao,
                                simples_nacional=simples_nacional,
                            )

                else:
                    st.error("❌ Não foi possível extrair dados do PDF!")
            
            except Exception as e:
                st.error(f"❌ Erro ao processar PDF: {e}")
                app_logger.error(f"Erro no processamento do PDF: {e}", exc_info=True)


# ============================================================================
# LISTAGEM DE NFS-e EMITIDAS
# ============================================================================

def render_emitted_nfse_list():
    """Renderiza lista de NFS-e emitidas."""
    st.title("📜 NFS-e Emitidas")
    st.markdown("Consulte e baixe as NFS-e já emitidas")
    st.markdown("---")
    
    if not st.session_state.emitted_nfse:
        st.info("ℹ️ Nenhuma NFS-e emitida ainda. Use o menu 'Emissão Individual' para emitir sua primeira nota!")
        return
    
    # Filtros
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        filtro_nome = st.text_input("🔍 Filtrar por Nome", placeholder="Digite o nome...")
    
    with col2:
        filtro_cpf = st.text_input("🔍 Filtrar por CPF", placeholder="Digite o CPF...")
    
    with col3:
        # Filtro por mês (independente do ano)
        meses = {
            "Todos": "Todos",
            "01": "Janeiro",
            "02": "Fevereiro",
            "03": "Março",
            "04": "Abril",
            "05": "Maio",
            "06": "Junho",
            "07": "Julho",
            "08": "Agosto",
            "09": "Setembro",
            "10": "Outubro",
            "11": "Novembro",
            "12": "Dezembro"
        }
        filtro_mes = st.selectbox(
            "📅 Filtrar por Mês",
            list(meses.keys()),
            format_func=lambda x: meses[x],
            help="Filtrar por mês (todos os anos)"
        )
    
    with col4:
        # Extrair períodos disponíveis das notas (mês/ano)
        periodos_disponiveis = set()
        for nota in st.session_state.emitted_nfse:
            try:
                data_str = nota.get('data_emissao', '')
                if data_str:
                    # Formato: DD/MM/YYYY HH:MM:SS
                    partes = data_str.split()
                    if partes:
                        data_parte = partes[0]
                        mes_ano = '/'.join(data_parte.split('/')[-2:])
                        periodos_disponiveis.add(mes_ano)
            except:
                pass
        
        from datetime import datetime as dt
        periodos_ordenados = sorted(list(periodos_disponiveis), key=lambda x: dt.strptime(x, '%m/%Y'), reverse=True)
        filtro_periodo = st.selectbox(
            "📅 Filtrar por Período",
            ["Todos"] + periodos_ordenados,
            help="Selecione o mês/ano específico"
        )
    
    with col5:
        ordem = st.selectbox("📊 Ordenar por", ["Mais Recentes", "Mais Antigas", "Maior Valor", "Menor Valor"])

    with col6:
        # Extrair dias disponíveis, filtrados pelo período selecionado
        dias_disponiveis = set()
        for nota in st.session_state.emitted_nfse:
            try:
                data_str = nota.get('data_emissao', '')
                if data_str:
                    partes = data_str.split()
                    if partes:
                        data_parte = partes[0]  # DD/MM/YYYY
                        partes_data = data_parte.split('/')
                        if len(partes_data) == 3:
                            dia = partes_data[0]
                            mes_ano = '/'.join(partes_data[1:])
                            if filtro_periodo == "Todos" or mes_ano == filtro_periodo:
                                dias_disponiveis.add(dia)
            except:
                pass

        dias_ordenados = sorted(list(dias_disponiveis))
        filtro_dia = st.selectbox(
            "📅 Filtrar por Dia",
            ["Todos"] + dias_ordenados,
            help="Selecione o dia específico"
        )

    st.markdown("---")
    
    # Filtrar e ordenar
    nfse_list = st.session_state.emitted_nfse.copy()
    
    if filtro_nome:
        nfse_list = [n for n in nfse_list if filtro_nome.lower() in n.get('tomador_nome', '').lower()]
    
    if filtro_cpf:
        nfse_list = [n for n in nfse_list if filtro_cpf in n.get('tomador_cpf', '')]
    
    # Filtrar por mês (independente do ano)
    if filtro_mes != "Todos":
        nfse_filtradas = []
        for n in nfse_list:
            try:
                data_str = n.get('data_emissao', '')
                if data_str:
                    partes = data_str.split()
                    if partes:
                        data_parte = partes[0]
                        mes = data_parte.split('/')[1]  # Extrai o mês (MM)
                        if mes == filtro_mes:
                            nfse_filtradas.append(n)
            except:
                pass
        nfse_list = nfse_filtradas
    
    # Filtrar por período (mês/ano específico)
    if filtro_periodo != "Todos":
        nfse_filtradas = []
        for n in nfse_list:
            try:
                data_str = n.get('data_emissao', '')
                if data_str:
                    partes = data_str.split()
                    if partes:
                        data_parte = partes[0]
                        mes_ano = '/'.join(data_parte.split('/')[-2:])
                        if mes_ano == filtro_periodo:
                            nfse_filtradas.append(n)
            except:
                pass
        nfse_list = nfse_filtradas

    # Filtrar por dia
    if filtro_dia != "Todos":
        nfse_filtradas = []
        for n in nfse_list:
            try:
                data_str = n.get('data_emissao', '')
                if data_str:
                    partes = data_str.split()
                    if partes:
                        dia = partes[0].split('/')[0]
                        if dia == filtro_dia:
                            nfse_filtradas.append(n)
            except:
                pass
        nfse_list = nfse_filtradas

    if ordem == "Mais Recentes":
        nfse_list = list(reversed(nfse_list))
    elif ordem == "Maior Valor":
        nfse_list = sorted(nfse_list, key=lambda x: x.get('valor', 0), reverse=True)
    elif ordem == "Menor Valor":
        nfse_list = sorted(nfse_list, key=lambda x: x.get('valor', 0))
    
    # Exibir métricas
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total de NFS-e", len(nfse_list))
    
    with col2:
        total_valor = sum([n.get('valor', 0) for n in nfse_list])
        st.metric("Valor Total", f"R$ {total_valor:,.2f}")
    
    with col3:
        total_iss = sum([n.get('iss', 0) for n in nfse_list])
        st.metric("Total ISS", f"R$ {total_iss:,.2f}")
    
    st.markdown("---")
    
    # Botões de ação em lote
    st.markdown("### 📦 Ações em Lote")
    
    # Mostrar quantas notas estão sendo exibidas vs total
    if len(nfse_list) < len(st.session_state.emitted_nfse):
        st.info(f"📊 Exibindo {len(nfse_list)} de {len(st.session_state.emitted_nfse)} notas (filtradas)")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        label_pdf = f"📥 Baixar PDFs ({len(nfse_list)})" if len(nfse_list) < len(st.session_state.emitted_nfse) else "📥 Baixar Todos os PDFs"
        if st.button(label_pdf, type="primary", use_container_width=True, key="bulk_pdf"):
            if not nfse_list:
                st.warning("⚠️ Nenhuma nota no filtro atual")
            else:
                with st.spinner("📦 Gerando PDFs e criando ZIP..."):
                    try:
                        zip_buffer, baixados, erros_dl = _gerar_zip_pdfs_ipm(nfse_list)
                        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")

                        if baixados > 0:
                            st.download_button(
                                label=f"⬇️ Download ZIP ({baixados} PDFs)",
                                data=zip_buffer.getvalue(),
                                file_name=f"nfse_pdfs_{data_hora}.zip",
                                mime="application/zip",
                                use_container_width=True,
                                key="download_bulk_pdf"
                            )
                            st.success(f"✅ {baixados} PDF(s) prontos para download!")
                        else:
                            st.warning("⚠️ Nenhum PDF disponível nos links da Prefeitura.")

                        if erros_dl:
                            with st.expander(f"⚠️ {len(erros_dl)} PDFs não baixados"):
                                for err in erros_dl:
                                    st.text(err)

                    except Exception as e:
                        st.error(f"❌ Erro ao gerar ZIP: {e}")
    
    with col2:
        label_xml = f"📄 Baixar XMLs ({len(nfse_list)})" if len(nfse_list) < len(st.session_state.emitted_nfse) else "📄 Baixar Todos os XMLs"
        if st.button(label_xml, type="primary", use_container_width=True, key="bulk_xml"):
            if not nfse_list:
                st.warning("⚠️ Nenhuma nota no filtro atual")
            else:
                with st.spinner("📦 Gerando arquivo ZIP com os XMLs..."):
                    try:
                        
                        # Criar arquivo ZIP em memória
                        zip_buffer = BytesIO()
                        
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            xmls_encontrados = 0
                            
                            for nota in nfse_list:
                                xml_path = nota.get('xml_path')
                                if xml_path and Path(xml_path).exists():
                                    # Adicionar XML ao ZIP
                                    zip_file.write(xml_path, Path(xml_path).name)
                                    xmls_encontrados += 1
                        
                        if xmls_encontrados > 0:
                            # Preparar download
                            zip_buffer.seek(0)
                            data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
                            
                            st.download_button(
                                label=f"⬇️ Download ZIP ({xmls_encontrados} XMLs)",
                                data=zip_buffer.getvalue(),
                                file_name=f"nfse_xmls_{data_hora}.zip",
                                mime="application/zip",
                                use_container_width=True,
                                key="download_bulk_xml"
                            )
                            
                            st.success(f"✅ {xmls_encontrados} XML(s) prontos para download!")
                        else:
                            st.warning("⚠️ Nenhum arquivo XML encontrado no sistema")
                    
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar ZIP: {e}")
    
    with col3:
        # Inicializar estado de confirmação
        if 'confirmar_limpeza' not in st.session_state:
            st.session_state.confirmar_limpeza = False
        
        if not st.session_state.confirmar_limpeza:
            # Primeiro clique - pedir confirmação
            if st.button("🗑️ Limpar Histórico", type="secondary", use_container_width=True, key="clear_history", help="Remove todas as notas do histórico"):
                st.session_state.confirmar_limpeza = True
                st.rerun()
        else:
            # Segundo clique - confirmar ação
            st.warning("⚠️ **TEM CERTEZA?** Esta ação não pode ser desfeita!")
            
            col_confirm, col_cancel = st.columns(2)
            
            with col_confirm:
                if st.button("✅ Confirmar Limpeza", type="primary", use_container_width=True, key="confirm_clear"):
                    total_notas = len(st.session_state.emitted_nfse)
                    arquivos_removidos = 0
                    
                    # Remover arquivos físicos (XML e PDF)
                    for nota in st.session_state.emitted_nfse:
                        try:
                            # Remover XML
                            xml_path = nota.get('xml_path')
                            if xml_path and Path(xml_path).exists():
                                Path(xml_path).unlink()
                                arquivos_removidos += 1
                            
                            # Remover PDF
                            pdf_path = nota.get('pdf_path')
                            if pdf_path and Path(pdf_path).exists():
                                Path(pdf_path).unlink()
                                arquivos_removidos += 1
                        except Exception as e:
                            app_logger.error(f"Erro ao remover arquivos: {e}")
                    
                    # Limpar dados da sessão
                    st.session_state.emitted_nfse = []
                    st.session_state.last_emission = None
                    st.session_state.confirmar_limpeza = False
                    
                    # Salvar arquivo vazio
                    save_emitted_nfse()
                    
                    st.success(f"✅ Histórico limpo! {total_notas} nota(s) e {arquivos_removidos} arquivo(s) removidos.")
                    st.rerun()
            
            with col_cancel:
                if st.button("❌ Cancelar", type="secondary", use_container_width=True, key="cancel_clear"):
                    st.session_state.confirmar_limpeza = False
                    st.rerun()
    
    st.markdown("---")
    
    # Listar NFS-e
    for idx, nfse in enumerate(nfse_list):
        with st.expander(
            f"🧾 NFS-e #{nfse.get('numero', idx+1)} - {nfse.get('tomador_nome', 'N/A')} - "
            f"R$ {nfse.get('valor', 0):,.2f} - {nfse.get('data_emissao', 'N/A')}"
        ):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**🔑 Chave de Acesso:**")
                st.code(nfse.get('chave_acesso', 'N/A'), language=None)
                
                st.markdown(f"**👤 Tomador:** {nfse.get('tomador_nome', 'N/A')}")
                st.markdown(f"**📋 CPF/CNPJ:** {nfse.get('tomador_cpf', 'N/A')}")
                st.markdown(f"**📅 Data de Emissão:** {nfse.get('data_emissao', 'N/A')}")
            
            with col2:
                st.markdown("**💰 Valores:**")
                st.markdown(f"**Valor Total:** R$ {nfse.get('valor', 0):,.2f}")
                st.markdown(f"**ISS:** R$ {nfse.get('iss', 0):,.2f}")
            
            st.markdown("---")
            st.markdown("### 📥 Downloads")
            
            col_xml, col_pdf, col_view = st.columns(3)
            
            with col_xml:
                if nfse.get('xml_path'):
                    download_file_button(nfse['xml_path'], "📄 Baixar XML", key=f"list_xml_{idx}")
            
            with col_pdf:
                if nfse.get('pdf_path'):
                    download_file_button(nfse['pdf_path'], "📑 Baixar PDF", key=f"list_pdf_{idx}")
            
            with col_view:
                if nfse.get('xml_path'):
                    if st.button("👁️ Visualizar XML", key=f"view_{idx}"):
                        show_xml_content(nfse['xml_path'])


def show_xml_content(xml_path):
    """Exibe conteúdo do XML."""
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        st.markdown("### 📄 Conteúdo do XML")
        st.code(xml_content, language='xml')
    
    except Exception as e:
        st.error(f"Erro ao ler XML: {e}")


# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

def render_settings():
    """Renderiza página de configurações (API nacional — CNPJ + A1 por usuário)."""
    from src.users.profile import (
        DEFAULT_PRESTADOR_ADDRESS,
        UserProfile,
        cert_arquivos_ok,
        cert_identity_match,
        cert_pronto,
        clear_user_certificate,
        get_user_profile,
        read_cert_subject,
        save_user_certificate_pfx,
        save_user_profile,
    )
    from src.utils.runtime_config import (
        get_emission_backend,
        get_shared_tax_config,
        save_shared_tax_config,
        set_emission_backend,
    )
    from src.utils.logger import app_logger

    st.title("⚙️ Configurações do Sistema")
    st.caption("API Nacional NFS-e (Sefin) · certificado A1 + CNPJ por usuário")
    st.markdown("---")

    username = st.session_state.username or ""
    profile = get_user_profile(username) or UserProfile(username=username)

    st.markdown("### 🏥 Prestador deste usuário")
    st.info(
        "Cada usuário tem **CNPJ**, **endereço** e **certificado A1** próprios. "
        "Só a configuração de imposto/serviço fica compartilhada."
    )

    # Não pré-preencher endereço de outro prestador (ex.: nathalia) em usuários vazios.
    with st.form("perfil_fiscal_form"):
        st.markdown("#### Empresa")
        col1, col2 = st.columns(2)
        with col1:
            cnpj_in = st.text_input("CNPJ *", value=profile.cnpj or "", placeholder="somente números")
            im_in = st.text_input("Inscrição municipal", value=profile.inscricao_municipal or "")
            razao_in = st.text_input("Razão social", value=profile.razao_social or "")
            fantasia_in = st.text_input("Nome fantasia", value=profile.nome_fantasia or "")
        with col2:
            email_c_in = st.text_input(
                "E-mail contato",
                value=profile.email_contato or "",
                placeholder=DEFAULT_PRESTADOR_ADDRESS["email_contato"],
            )
            tel_in = st.text_input(
                "Telefone",
                value=profile.telefone or "",
                placeholder=DEFAULT_PRESTADOR_ADDRESS["telefone"],
            )
            ibge_in = st.text_input(
                "Código IBGE município",
                value=profile.codigo_municipio or "",
                placeholder=DEFAULT_PRESTADOR_ADDRESS["codigo_municipio"],
            )

        st.markdown("#### Endereço do prestador")
        a1, a2, a3 = st.columns(3)
        with a1:
            log_in = st.text_input(
                "Logradouro",
                value=profile.logradouro or "",
                placeholder=DEFAULT_PRESTADOR_ADDRESS["logradouro"],
            )
            bairro_in = st.text_input(
                "Bairro",
                value=profile.bairro or "",
                placeholder=DEFAULT_PRESTADOR_ADDRESS["bairro"],
            )
        with a2:
            num_in = st.text_input(
                "Número",
                value=profile.numero or "",
                placeholder=DEFAULT_PRESTADOR_ADDRESS["numero"],
            )
            mun_in = st.text_input(
                "Município",
                value=profile.municipio or "",
                placeholder=DEFAULT_PRESTADOR_ADDRESS["municipio"],
            )
        with a3:
            comp_in = st.text_input("Complemento", value=profile.complemento or "")
            uf_in = st.text_input(
                "UF",
                value=profile.uf or "",
                max_chars=2,
                placeholder=DEFAULT_PRESTADOR_ADDRESS["uf"],
            )
            cep_in = st.text_input(
                "CEP",
                value=profile.cep or "",
                placeholder=DEFAULT_PRESTADOR_ADDRESS["cep"],
            )

        salvar_perfil = st.form_submit_button(
            "💾 Salvar CNPJ / endereço / empresa",
            type="primary",
            use_container_width=True,
        )

    if salvar_perfil:
        try:
            profile.cnpj = cnpj_in
            profile.inscricao_municipal = im_in
            profile.razao_social = razao_in
            profile.nome_fantasia = fantasia_in
            profile.email_contato = email_c_in
            profile.telefone = tel_in
            profile.codigo_municipio = ibge_in
            profile.logradouro = log_in
            profile.numero = num_in
            profile.complemento = comp_in
            profile.bairro = bairro_in
            profile.municipio = mun_in
            profile.uf = uf_in
            profile.cep = cep_in
            save_user_profile(profile)
            st.success("✅ Perfil fiscal e endereço salvos.")
            st.rerun()
        except Exception as e:
            app_logger.exception("Falha ao salvar perfil fiscal")
            st.error(f"Falha ao salvar: {e}")

    st.markdown("---")
    st.markdown("### 🔐 Certificado Digital A1 (deste usuário)")
    cert_subj = read_cert_subject(profile)
    if cert_arquivos_ok(profile) and cert_subj.get("cn"):
        st.info(
            f"**Subject do A1 em disco:** `{cert_subj['cn']}`\n\n"
            f"Pasta: `data/certs/{username}/`"
        )
    if cert_pronto(profile):
        st.success(
            f"Certificado A1 pronto (CNPJ {profile.cnpj}) — identidade alinhada ao PEM."
        )
    elif cert_arquivos_ok(profile) and profile.cnpj and not cert_identity_match(profile):
        st.error(
            "O PEM em disco **não é deste CNPJ**. "
            f"Perfil: `{profile.cnpj}` · Certificado: `{cert_subj.get('cnpj') or '—'}`. "
            "Remova o certificado e envie o PFX correto deste prestador."
        )
    elif cert_arquivos_ok(profile):
        st.warning(
            "Arquivos PEM já estão no disco, mas falta **CNPJ** no perfil acima. "
            "Reenvie o PFX — CNPJ e razão social serão lidos do certificado."
        )
    else:
        st.warning(
            "Envie o PFX/P12 e a senha do A1. CNPJ e razão social serão preenchidos "
            "a partir do subject do certificado (somente deste usuário)."
        )

    pfx_file = st.file_uploader("Arquivo PFX / P12", type=["pfx", "p12"], key="pfx_upload")
    cert_pwd = st.text_input(
        "Senha do certificado A1",
        type="password",
        placeholder="Senha do arquivo PFX (não a senha de login)",
        key="cert_pwd_input",
    )
    col_save, col_clear = st.columns(2)
    with col_save:
        salvar_cert = st.button(
            "📤 Converter e salvar certificado",
            use_container_width=True,
            key="salvar_cert_btn",
        )
    with col_clear:
        limpar_cert = st.button(
            "🗑️ Remover certificado deste usuário",
            use_container_width=True,
            key="limpar_cert_btn",
        )

    if limpar_cert:
        try:
            clear_user_certificate(username, clear_identity=False)
            st.success("Certificado removido. Envie o PFX correto deste prestador.")
            st.rerun()
        except Exception as e:
            app_logger.exception("Falha ao remover certificado")
            st.error(f"Falha ao remover: {e}")

    if salvar_cert:
        if not pfx_file:
            st.error("Selecione o arquivo PFX/P12.")
        elif not cert_pwd:
            st.error("Informe a senha do certificado.")
        else:
            try:
                saved = save_user_certificate_pfx(username, pfx_file.getvalue(), cert_pwd)
                subj = read_cert_subject(saved)
                if cert_pronto(saved):
                    st.success(
                        f"✅ Certificado A1 salvo para **{username}**. "
                        f"CNPJ {saved.cnpj} · {saved.razao_social or subj.get('razao_social') or ''}."
                    )
                elif cert_arquivos_ok(saved):
                    st.warning(
                        "PEM salvo, mas ainda falta CNPJ legível no subject do PFX. "
                        "Preencha o CNPJ acima e clique em Salvar."
                    )
                else:
                    st.error("Processou o PFX, mas os arquivos PEM não ficaram no disco.")
                st.rerun()
            except Exception as e:
                app_logger.exception("Falha ao salvar PFX")
                st.error(f"Falha ao processar certificado: {e}")

    st.markdown("---")
    st.markdown("### 💰 Imposto / serviço (compartilhado)")
    tax = get_shared_tax_config()
    with st.form("shared_tax_form"):
        t1, t2 = st.columns(2)
        with t1:
            aliq = st.number_input("Alíquota ISS (%)", min_value=0.0, max_value=100.0, value=float(tax["aliquota_iss"]), step=0.01)
            item = st.text_input("Código serviço", value=tax["item_lista"])
            desc = st.text_input("Descrição padrão", value=tax["descricao"])
            nbs = st.text_input("NBS", value=tax["nbs"])
        with t2:
            sn = st.checkbox("Optante Simples Nacional", value=bool(tax["simples_nacional"]))
            mei = st.checkbox(
                "MEI (opSimpNac=2)",
                value=bool(tax.get("mei", False)),
                help="Marque só se o CNPJ for MEI. ME/EPP (Nathalia) deve ficar desmarcado → opSimpNac=3.",
            )
            op_labels = {
                1: "1 — Não optante",
                2: "2 — MEI",
                3: "3 — ME/EPP",
                4: "4 — Optante pendente",
            }
            current_op = int(tax.get("op_simp_nac") or (2 if mei else (3 if sn else 1)))
            op_choice = st.selectbox(
                "opSimpNac (Sefin)",
                options=[1, 2, 3, 4],
                index=[1, 2, 3, 4].index(current_op if current_op in (1, 2, 3, 4) else 3),
                format_func=lambda v: op_labels[v],
                help="Enum oficial: 2=MEI, 3=ME/EPP. Invertê-los gera E0160.",
            )
            reg_ap = st.selectbox(
                "regApTribSN (só ME/EPP)",
                options=[1, 2, 3],
                index=[1, 2, 3].index(int(tax.get("reg_ap_trib_sn") or 1)),
                help="1=federais+municipal pelo SN (padrão).",
            )
        salvar_tax = st.form_submit_button("💾 Salvar imposto compartilhado", use_container_width=True)
    if salvar_tax:
        save_shared_tax_config(
            aliquota_iss=aliq,
            item_lista=item,
            descricao=desc,
            nbs=nbs,
            simples_nacional=sn,
            mei=mei,
            op_simp_nac=op_choice,
            reg_ap_trib_sn=reg_ap,
        )
        st.success("✅ Configuração de imposto salva (vale para todos os usuários).")
        st.rerun()

    st.markdown("---")
    st.markdown("### 🌐 Integração")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Canal:** API Nacional NFS-e (Sefin)")
        st.markdown(f"**URL:** `{settings.NFSE_API_BASE_URL}`")
        st.markdown(f"**Ambiente:** `{settings.NFSE_API_AMBIENTE}`")
    with col2:
        backend = get_emission_backend()
        st.markdown(f"**Backend ativo:** `{backend}`")
        st.markdown(f"**Usuário logado:** `{username}`")
        st.markdown(f"**CNPJ emissor:** `{profile.cnpj or '—'}`")

    novo_backend = st.selectbox(
        "Backend de emissão",
        options=["sefin", "ipm"],
        index=0 if backend == "sefin" else 1,
        help="Padrão: sefin (API nacional). IPM permanece disponível só como legado.",
    )
    if st.button("Aplicar backend", use_container_width=True):
        set_emission_backend(novo_backend)
        st.success(f"Backend definido como `{novo_backend}`.")
        st.rerun()

    testar = st.button(
        "🔌 Testar API Nacional (health)",
        use_container_width=True,
        disabled=not cert_pronto(profile),
        help="Requer certificado A1 salvo para este usuário.",
    )
    if testar and cert_pronto(profile):
        with st.spinner("Consultando disponibilidade da API Nacional..."):
            try:
                ok = asyncio.run(get_nfse_service(username).consultar_status_api())
                if ok:
                    st.success("✅ API Nacional respondeu.")
                else:
                    st.warning("API Nacional não respondeu como esperado — confira certificado e ambiente.")
            except Exception as e:
                st.error(f"❌ Falha no teste: {e}")

    st.markdown("---")

    # Ações em Lote
    st.markdown("### 📦 Ações em Lote")
    st.markdown("Gerencie todas as notas fiscais emitidas de uma vez")    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Baixar Todos os PDFs", type="primary", use_container_width=True):
            if not st.session_state.emitted_nfse:
                st.warning("⚠️ Nenhuma nota fiscal emitida para baixar")
            else:
                with st.spinner("📦 Gerando arquivo ZIP com todos os PDFs..."):
                    try:
                        
                        # Criar arquivo ZIP em memória
                        zip_buffer = BytesIO()
                        
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            pdfs_encontrados = 0
                            
                            for nota in st.session_state.emitted_nfse:
                                pdf_path = nota.get('pdf_path')
                                if pdf_path and Path(pdf_path).exists():
                                    # Adicionar PDF ao ZIP
                                    zip_file.write(pdf_path, Path(pdf_path).name)
                                    pdfs_encontrados += 1
                        
                        if pdfs_encontrados > 0:
                            # Preparar download
                            zip_buffer.seek(0)
                            data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
                            
                            st.download_button(
                                label=f"⬇️ Download ZIP ({pdfs_encontrados} PDFs)",
                                data=zip_buffer.getvalue(),
                                file_name=f"nfse_pdfs_{data_hora}.zip",
                                mime="application/zip",
                                use_container_width=True
                            )
                            
                            st.success(f"✅ {pdfs_encontrados} PDF(s) prontos para download!")
                        else:
                            st.warning("⚠️ Nenhum arquivo PDF encontrado no sistema")
                    
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar ZIP: {e}")
    
    with col2:
        if st.button("📄 Baixar Todos os XMLs", type="primary", use_container_width=True):
            if not st.session_state.emitted_nfse:
                st.warning("⚠️ Nenhuma nota fiscal emitida para baixar")
            else:
                with st.spinner("📦 Gerando arquivo ZIP com todos os XMLs..."):
                    try:
                        
                        # Criar arquivo ZIP em memória
                        zip_buffer = BytesIO()
                        
                        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                            xmls_encontrados = 0
                            
                            for nota in st.session_state.emitted_nfse:
                                xml_path = nota.get('xml_path')
                                if xml_path and Path(xml_path).exists():
                                    # Adicionar XML ao ZIP
                                    zip_file.write(xml_path, Path(xml_path).name)
                                    xmls_encontrados += 1
                        
                        if xmls_encontrados > 0:
                            # Preparar download
                            zip_buffer.seek(0)
                            data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
                            
                            st.download_button(
                                label=f"⬇️ Download ZIP ({xmls_encontrados} XMLs)",
                                data=zip_buffer.getvalue(),
                                file_name=f"nfse_xmls_{data_hora}.zip",
                                mime="application/zip",
                                use_container_width=True
                            )
                            
                            st.success(f"✅ {xmls_encontrados} XML(s) prontos para download!")
                        else:
                            st.warning("⚠️ Nenhum arquivo XML encontrado no sistema")
                    
                    except Exception as e:
                        st.error(f"❌ Erro ao gerar ZIP: {e}")
    
    st.markdown("---")
    
    # Limpar sessão
    st.markdown("### 🗑️ Manutenção")
    st.warning("⚠️ **Atenção:** As ações abaixo são irreversíveis!")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Inicializar estado de confirmação
        if 'confirmar_limpeza_settings' not in st.session_state:
            st.session_state.confirmar_limpeza_settings = False
        
        if not st.session_state.confirmar_limpeza_settings:
            # Primeiro clique - pedir confirmação
            if st.button("🗑️ Limpar Histórico de Emissões", type="secondary", use_container_width=True, key="clear_history_settings", help="Remove todas as notas do histórico"):
                st.session_state.confirmar_limpeza_settings = True
                st.rerun()
        else:
            # Segundo clique - confirmar ação
            st.warning("⚠️ **TEM CERTEZA?** Esta ação não pode ser desfeita!")
            
            col_confirm, col_cancel = st.columns(2)
            
            with col_confirm:
                if st.button("✅ Confirmar", type="primary", use_container_width=True, key="confirm_clear_settings"):
                    total_notas = len(st.session_state.emitted_nfse)
                    st.session_state.emitted_nfse = []
                    st.session_state.last_emission = None
                    st.session_state.confirmar_limpeza_settings = False
                    # Salvar arquivo vazio
                    save_emitted_nfse()
                    st.success(f"✅ Histórico limpo! {total_notas} nota(s) removida(s).")
                    st.rerun()
            
            with col_cancel:
                if st.button("❌ Cancelar", type="secondary", use_container_width=True, key="cancel_clear_settings"):
                    st.session_state.confirmar_limpeza_settings = False
                    st.rerun()
    
    with col2:
        if st.button("🔄 Reiniciar Sessão", type="secondary"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.success("✅ Sessão reiniciada!")
            st.rerun()


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def download_file_button(file_path: str, label: str, key: str):
    """Cria botão de download para arquivo."""
    try:
        if not Path(file_path).exists():
            st.warning(f"⚠️ Arquivo não encontrado: {file_path}")
            return
        
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        file_name = Path(file_path).name
        
        st.download_button(
            label=label,
            data=file_data,
            file_name=file_name,
            mime='application/octet-stream',
            key=key,
            use_container_width=True
        )
    
    except Exception as e:
        st.error(f"Erro ao preparar download: {e}")


def get_file_download_link(file_path: str, link_text: str) -> str:
    """Gera link de download para arquivo."""
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        b64 = base64.b64encode(data).decode()
        file_name = Path(file_path).name
        
        return f'<a href="data:application/octet-stream;base64,{b64}" download="{file_name}">{link_text}</a>'
    
    except Exception as e:
        return f"Erro: {e}"


# ============================================================================
# APLICAÇÃO PRINCIPAL
# ============================================================================

def main():
    """Função principal da aplicação."""
    # Inicializa estado da sessão
    init_session_state()
    
    # Inicializa banco de dados (cria tabelas se não existirem)
    try:
        asyncio.run(init_database())
        app_logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        app_logger.warning(f"Aviso ao inicializar banco de dados: {e}")

    # Garante logins nathalia/guilherme (senha admin) após migrate de colunas
    try:
        from src.users.seed_login import ensure_login_users
        ensure_login_users()
    except Exception as e:
        app_logger.warning(f"Aviso ao garantir usuários de login: {e}")
    
    # Verifica autenticação
    if not st.session_state.authenticated:
        login_page()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
