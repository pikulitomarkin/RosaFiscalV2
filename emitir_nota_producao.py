"""
Script para emissão de NFS-e em PRODUÇÃO - Cliente Real
URL: https://adn.nfse.gov.br/adn/DFe
Ambiente: PRODUCAO
"""
import asyncio
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent))

from src.models.schemas import (
    NFSeRequest, PrestadorServico, TomadorServico, 
    Servico, TipoAmbiente
)
from src.utils.xml_generator import NFSeXMLGenerator
from src.api.client import NFSeAPIClient
from src.utils.logger import app_logger
from config.settings import settings


async def emitir_nota_cliente():
    """Emite uma nota fiscal para um cliente em PRODUÇÃO."""
    
    print("\n" + "="*80)
    print("🚀 EMISSÃO DE NFS-e EM PRODUÇÃO - CLIENTE REAL")
    print("="*80)
    print(f"🌐 URL: https://adn.nfse.gov.br/adn/DFe")
    print(f"🔐 Ambiente: PRODUCAO")
    print(f"📜 Prestador: NATHALIA GABRIELA SERVICOS DE SAUDE LTDA")
    print("="*80 + "\n")
    
    # ========== DADOS DO CLIENTE - PREENCHA AQUI ==========
    print("📋 Coletando dados do cliente...")
    print("\n--- DADOS DO TOMADOR (CLIENTE) ---")
    
    cpf_cliente = input("CPF do cliente (apenas números): ").strip()
    nome_cliente = input("Nome completo do cliente: ").strip()
    email_cliente = input("Email do cliente: ").strip()
    telefone_cliente = input("Telefone do cliente (com DDD): ").strip()
    
    print("\n--- DADOS DO SERVIÇO ---")
    valor_servico = input("Valor do serviço (ex: 150.00): ").strip()
    descricao_servico = input("Descrição do serviço: ").strip()
    
    # Validações básicas
    if not cpf_cliente or not nome_cliente or not valor_servico:
        print("\n❌ Dados obrigatórios não preenchidos!")
        return 1
    
    try:
        valor_decimal = Decimal(valor_servico)
    except:
        print("\n❌ Valor do serviço inválido!")
        return 1
    
    # ========== CONFIGURAÇÃO DO PRESTADOR ==========
    prestador = PrestadorServico(
        cnpj="56169351000185",
        inscricao_municipal="56937",
        razao_social="NATHALIA GABRIELA SERVICOS DE SAUDE LTDA",
        nome_fantasia="NATHALIA GABRIELA",
        logradouro="RUA TARQUINIO DE OLIVEIRA",
        numero="249",
        bairro="CRUZEIRO",
        municipio="SANTA ROSA",
        uf="RS",
        cep="98789104"
    )
    
    # ========== DADOS DO TOMADOR (CLIENTE) ==========
    tomador = TomadorServico(
        cpf=cpf_cliente,
        nome=nome_cliente,
        email=email_cliente if email_cliente else None,
        telefone=telefone_cliente if telefone_cliente else None,
        logradouro="",
        numero="",
        municipio="SAO PAULO",
        uf="SP"
    )
    
    # ========== DADOS DO SERVIÇO ==========
    aliquota_iss = Decimal("5.00")  # 5%
    valor_iss = valor_decimal * (aliquota_iss / 100)
    
    servico = Servico(
        descricao=descricao_servico or "Serviços médicos especializados",
        item_lista_servico="04.01",  # Serviços de saúde
        codigo_tributacao_municipio="0401",
        valor_servico=valor_decimal,
        aliquota_iss=aliquota_iss,
        valor_iss=valor_iss
    )
    
    # ========== CRIAR REQUEST NFS-e ==========
    nfse_request = NFSeRequest(
        prestador=prestador,
        tomador=tomador,
        servico=servico,
        outras_informacoes=f"Nota emitida em {datetime.now().strftime('%d/%m/%Y às %H:%M')}"
    )
    
    # ========== PREVIEW DOS DADOS ==========
    print("\n" + "="*80)
    print("📄 PREVIEW DA NOTA FISCAL")
    print("="*80)
    print(f"\n👤 TOMADOR: {nome_cliente}")
    print(f"📝 CPF: {cpf_cliente}")
    print(f"📧 Email: {email_cliente or 'Não informado'}")
    print(f"📞 Telefone: {telefone_cliente or 'Não informado'}")
    print(f"\n💰 SERVIÇO: {descricao_servico}")
    print(f"💵 Valor: R$ {valor_decimal:.2f}")
    print(f"📊 ISS ({aliquota_iss}%): R$ {valor_iss:.2f}")
    print(f"💳 Total: R$ {valor_decimal:.2f}")
    print("\n" + "="*80)
    
    # ========== CONFIRMAÇÃO ==========
    print("\n⚠️  ATENÇÃO: VOCÊ ESTÁ PRESTES A EMITIR UMA NOTA FISCAL REAL EM PRODUÇÃO ⚠️")
    confirmacao = input("\nDigite 'CONFIRMAR' para prosseguir: ").strip().upper()
    
    if confirmacao != "CONFIRMAR":
        print("\n❌ Operação cancelada pelo usuário")
        return 0
    
    # ========== GERAÇÃO DO XML ==========
    print("\n🔧 Gerando XML NFS-e...")
    try:
        # Caminhos dos certificados
        cert_path = Path("certificados/cert.pem")
        key_path = Path("certificados/key.pem")
        
        if not cert_path.exists() or not key_path.exists():
            print(f"❌ Certificados não encontrados!")
            print(f"   Cert: {cert_path.absolute()}")
            print(f"   Key: {key_path.absolute()}")
            return 1
        
        # Gerar XML com assinatura
        generator = NFSeXMLGenerator(
            ambiente=TipoAmbiente.PRODUCAO,
            cert_path=str(cert_path.absolute()),
            key_path=str(key_path.absolute())
        )
        
        xml_assinado = generator.gerar_xml_assinado(nfse_request)
        print("✅ XML gerado e assinado digitalmente")
        
        # Salvar XML para auditoria
        xml_file = Path(f"xml_producao_{cpf_cliente}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml")
        xml_file.write_text(xml_assinado, encoding='utf-8')
        print(f"💾 XML salvo em: {xml_file.name}")
        
        # Comprimir e codificar
        xml_comprimido = generator.comprimir_e_codificar(xml_assinado)
        print(f"📦 XML comprimido: {len(xml_comprimido)} caracteres")
        
    except Exception as e:
        print(f"❌ Erro ao gerar XML: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # ========== ENVIO PARA API ==========
    print("\n🚀 Enviando para API ADN em PRODUÇÃO...")
    try:
        # Inicializar cliente API
        client = NFSeAPIClient()
        
        # Preparar payload
        payload = {
            f"Lote{datetime.now().strftime('%Y%m%d%H%M%S')}": [xml_comprimido],
            "TipoAmbiente": "PRODUCAO",
            "VersaoAplicativo": "2.0.0",
            "DataHoraProcessamento": datetime.now().isoformat()
        }
        
        # Enviar para API
        response = await client.recepcionar_lote(payload)
        
        print("\n" + "="*80)
        print("✅ RESPOSTA DA API")
        print("="*80)
        print(f"Status: {response.get('status', 'N/A')}")
        
        if "Lote" in response:
            lote = response["Lote"]
            if isinstance(lote, list) and len(lote) > 0:
                doc = lote[0]
                print(f"📋 Número do Lote: {doc.get('NumeroLote', 'N/A')}")
                print(f"🔑 Chave de Acesso: {doc.get('ChaveAcesso', 'N/A')}")
                print(f"📊 Status: {doc.get('Status', 'N/A')}")
                
                if "Mensagem" in doc:
                    print(f"📝 Mensagem: {doc['Mensagem']}")
        
        print("\n📄 Resposta completa:")
        import json
        print(json.dumps(response, indent=2, ensure_ascii=False))
        
        print("\n" + "="*80)
        print("✅ NOTA FISCAL EMITIDA COM SUCESSO!")
        print("="*80)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Erro ao enviar para API: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    print("\n" + "⚠️ "*20)
    print("   AMBIENTE DE PRODUÇÃO - EMISSÕES REAIS")
    print("⚠️ "*20 + "\n")
    
    try:
        exit_code = asyncio.run(emitir_nota_cliente())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Operação cancelada pelo usuário (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
