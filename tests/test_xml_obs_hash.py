"""Garante que o hash do paciente vai para observação (xInfComp) no DPS."""
from decimal import Decimal
from datetime import datetime, date

from src.models.schemas import (
    NFSeRequest,
    PrestadorServico,
    TomadorServico,
    Servico,
    TipoAmbiente,
)
from src.utils.xml_generator import NFSeXMLGenerator


def _req(*, hash_tx: str, descricao: str, discriminacao: str | None = None) -> NFSeRequest:
    return NFSeRequest(
        data_emissao=datetime.now(),
        competencia=date.today(),
        prestador=PrestadorServico(
            cnpj="20586334000160",
            inscricao_municipal="1",
            razao_social="TESTE SERVICOS LTDA",
            logradouro="Rua Teste",
            numero="100",
            bairro="Centro",
            municipio="Santa Rosa",
            uf="RS",
            cep="98900000",
            codigo_municipio="4317202",
        ),
        tomador=TomadorServico(cpf="12345678901", nome="Tomador Teste Silva"),
        servico=Servico(
            descricao=descricao,
            valor_servico=Decimal("50.00"),
            aliquota_iss=Decimal("2.00"),
            item_lista_servico="040301",
            discriminacao=discriminacao,
        ),
        hash_transacao=hash_tx or None,
        outras_informacoes=f"Hash do Paciente: {hash_tx}" if hash_tx else None,
        optante_simples_nacional=True,
        op_simp_nac=3,
        reg_ap_trib_sn=1,
    )


def test_xinfcomp_contem_hash_paciente():
    hash_tx = "PACIENTEBLIS35474857_"
    gen = NFSeXMLGenerator(ambiente=TipoAmbiente.PRODUCAO)
    xml = gen.gerar_xml_nfse(
        _req(
            hash_tx=hash_tx,
            descricao=f"Prestação de serviços conforme contrato | {hash_tx}",
            discriminacao=f"Hash do Paciente: {hash_tx}",
        )
    )
    assert "<xDescServ>" in xml
    assert hash_tx in xml
    assert "<infoCompl>" in xml
    assert "<xInfComp>" in xml
    assert f"Hash do Paciente: {hash_tx}" in xml
    # Sem quebra de linha dentro de xInfComp
    start = xml.index("<xInfComp>") + len("<xInfComp>")
    end = xml.index("</xInfComp>")
    assert "\n" not in xml[start:end]


def test_sem_hash_nao_emite_infocompl_vazio():
    gen = NFSeXMLGenerator(ambiente=TipoAmbiente.PRODUCAO)
    xml = gen.gerar_xml_nfse(
        _req(hash_tx="", descricao="Prestação de serviços conforme contrato", discriminacao=None)
    )
    # outras_informacoes None e sem hash → sem infoCompl
    assert "<infoCompl>" not in xml
    assert "<xInfComp>" not in xml


def test_compose_info_comp_dedup():
    gen = NFSeXMLGenerator(ambiente=TipoAmbiente.PRODUCAO)
    req = _req(
        hash_tx="PACIENTEBLIS999_",
        descricao="Consulta medica",
        discriminacao="Hash do Paciente: PACIENTEBLIS999_",
    )
    text = gen._compose_info_comp(req)
    assert text is not None
    assert text.count("PACIENTEBLIS999_") == 1
    assert "\n" not in text
