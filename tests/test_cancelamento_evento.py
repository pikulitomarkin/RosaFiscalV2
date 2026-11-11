"""Testes unitários do XML pedRegEvento (cancelamento e101101)."""
from src.models.schemas import TipoAmbiente
from src.utils.xml_generator import NFSeXMLGenerator


CHAVE = "43172022256169351000185000000000000426119891248643"
CNPJ = "56169351000185"


def test_gerar_xml_pedido_cancelamento_estrutura():
    gen = NFSeXMLGenerator(ambiente=TipoAmbiente.PRODUCAO)
    xml, id_ped = gen.gerar_xml_pedido_cancelamento(
        CHAVE,
        CNPJ,
        c_motivo=1,
        x_motivo="Cancelamento de emissao em lote por erro operacional.",
    )
    assert id_ped == f"PRE{CHAVE}101001"
    assert 'versao="1.00"' in xml
    assert "<e101101>" in xml
    assert "<xDesc>Cancelamento de NFS-e</xDesc>" in xml
    assert f"<chNFSe>{CHAVE}</chNFSe>" in xml
    assert f"<CNPJAutor>{CNPJ}</CNPJAutor>" in xml
    assert f'Id="{id_ped}"' in xml
    assert "<cMotivo>1</cMotivo>" in xml
    assert "Signature" not in xml


def test_gerar_xml_pedido_cancelamento_cpf_autor():
    gen = NFSeXMLGenerator(ambiente=TipoAmbiente.PRODUCAO)
    xml, id_ped = gen.gerar_xml_pedido_cancelamento(
        CHAVE,
        "12345678901",
        c_motivo=2,
        x_motivo="Servico nao prestado conforme combinado com o paciente.",
        n_ped_reg_evento=2,
    )
    assert id_ped.endswith("101002")
    assert "<CPFAutor>12345678901</CPFAutor>" in xml
    assert "<cMotivo>2</cMotivo>" in xml
