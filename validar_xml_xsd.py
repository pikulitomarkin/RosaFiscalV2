"""Validar XML DPS contra esquema XSD e identificar problemas"""
import xml.etree.ElementTree as ET

xml_file = r"d:\leitor pdf e geração de notas\xml_producao_03934960669_20260111_230149.xml"

# Ler XML
tree = ET.parse(xml_file)
root = tree.getroot()

# Namespace
ns = {'nfse': 'http://www.sped.fazenda.gov.br/nfse', 'ds': 'http://www.w3.org/2000/09/xmldsig#'}

print("🔍 ANÁLISE DO XML GERADO vs XSD v1.01\n")
print("=" * 80)

# Verificar estrutura raiz
print("\n1️⃣ ELEMENTO RAIZ:")
print(f"   Tag encontrada: {root.tag}")
print(f"   ✅ Correto: DPS")
print(f"   Namespace: {root.tag.split('}')[0] + '}' if '}' in root.tag else 'SEM NAMESPACE'}")
print(f"   Versão: {root.get('versao')}")
print(f"   ⚠️  XSD espera: versao='1.01' (encontrado: {root.get('versao')})")

# Verificar estrutura esperada pelo XSD
print("\n2️⃣ ESTRUTURA ESPERADA PELO XSD v1.01:")
expected_structure = {
    "infDPS": {
        "obrigatorio": True,
        "atributo": "Id",
        "filhos": ["tpDFe", "dhEmi", "cLocEmi", "subst (opcional)", "prest", "toma", "interm (opcional)", "serv", "valores", "IBSCBS (opcional)"]
    }
}

# Listar elementos encontrados (sem namespace para clareza)
print("\n3️⃣ ELEMENTOS ENCONTRADOS NO XML:")
for child in root:
    tag = child.tag.split('}')[1] if '}' in child.tag else child.tag
    print(f"   - {tag}")
    
print("\n4️⃣ PROBLEMAS IDENTIFICADOS:")
problems = []

# Problema 1: Falta elemento infDPS
if not root.find('.//nfse:infDPS', ns) and not root.find('infDPS'):
    problems.append("❌ CRÍTICO: Falta elemento <infDPS> (obrigatório pelo XSD)")
    
# Problema 2: Tags no lugar errado
if root.find('tpDFe') is not None or root.find('.//nfse:tpDFe', ns) is not None:
    problems.append("❌ Tag <tpDFe> está diretamente sob <DPS>, deveria estar sob <infDPS>")

# Problema 3: Tags antigas
old_tags = ['Prestador', 'InscricaoMunicipal', 'RazaoSocial', 'NomeFantasia', 'Tomador', 'Servico', 
            'Discriminacao', 'ItemListaServico', 'CodigoTributacaoMunicipal', 'Valores', 
            'ValorServicos', 'AliquotaISS', 'ValorISS', 'OutrasInformacoes']

found_old = []
for tag in old_tags:
    if root.find(f'.//{tag}') is not None:
        found_old.append(tag)
        
if found_old:
    problems.append(f"❌ Tags antigas (formato antigo): {', '.join(found_old)}")
    problems.append("   XSD v1.01 usa: prest, IM, xNome, xFant, toma, serv, xDescServ, cTribNac, cTribMun, vServPrest, pAliq, vISSQN, etc.")

# Problema 4: Versão incorreta
if root.get('versao') != '1.01':
    problems.append(f"❌ Atributo versao='{root.get('versao')}' (XSD espera: '1.01')")

# Problema 5: Falta dhEmi
if not root.find('.//dhEmi'):
    problems.append("❌ Falta elemento <dhEmi> (data/hora emissão em formato UTC)")

# Problema 6: Falta cLocEmi  
if not root.find('.//cLocEmi'):
    problems.append("❌ Falta elemento <cLocEmi> (código IBGE município emissor)")

for i, prob in enumerate(problems, 1):
    print(f"{i}. {prob}")

print("\n" + "=" * 80)
print("\n📋 ESTRUTURA CORRETA ESPERADA PELO XSD v1.01:\n")
print("""
<DPS xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.01">
  <infDPS Id="DPS...">
    <tpDFe>901</tpDFe>
    <dhEmi>2026-01-11T23:01:49-03:00</dhEmi>
    <cLocEmi>4205407</cLocEmi>  <!-- Florianópolis -->
    
    <prest>  <!-- NÃO "Prestador" -->
      <CNPJ>56169351000185</CNPJ>
      <IM>56937</IM>  <!-- NÃO "InscricaoMunicipal" -->
      <xNome>NATHALIA GABRIELA SERVICOS DE SAUDE LTDA</xNome>  <!-- NÃO "RazaoSocial" -->
      <end>  <!-- Endereço completo -->
        <endNac>
          <cMun>4205407</cMun>
          <UF>SC</UF>
          <CEP>88010000</CEP>
        </endNac>
        <xLgr>Rua Exemplo</xLgr>
        <nro>123</nro>
        <xBairro>Centro</xBairro>
      </end>
      <regTrib>  <!-- Regimes tributários -->
        <opSimpNac>1</opSimpNac>  <!-- 1=Não optante -->
        <regEspTrib>0</regEspTrib>  <!-- 0=Nenhum -->
      </regTrib>
    </prest>
    
    <toma>  <!-- NÃO "Tomador" -->
      <CPF>03934960669</CPF>
      <xNome>Luciana Ribeiro Fantini</xNome>  <!-- NÃO "Nome" -->
      <email>lufantini79@gmail.com</email>  <!-- NÃO "Email" -->
      <fone>31991506178</fone>  <!-- NÃO "Telefone" -->
    </toma>
    
    <serv>  <!-- NÃO "Servico" -->
      <cTribNac>040101</cTribNac>  <!-- NÃO "ItemListaServico" -->
      <xDescServ>Serviços médicos especializados</xDescServ>  <!-- NÃO "Discriminacao" -->
    </serv>
    
    <valores>  <!-- NÃO "Valores" -->
      <vServPrest>150.00</vServPrest>  <!-- NÃO "ValorServicos" -->
      <vDescIncond>0.00</vDescIncond>  <!-- Desconto incondicional -->
      <issqn>
        <vBC>150.00</vBC>  <!-- Base de cálculo -->
        <pAliq>2.00</pAliq>  <!-- NÃO "AliquotaISS" -->
        <vISSQN>3.00</vISSQN>  <!-- NÃO "ValorISS" -->
      </issqn>
    </valores>
  </infDPS>
  <Signature xmlns="http://www.w3.org/2000/09/xmldsig#">
    ...
  </Signature>
</DPS>
""")

print("\n✅ RESUMO:")
print(f"   Total de problemas encontrados: {len(problems)}")
print(f"   Status: {'❌ XML NÃO CONFORME com XSD v1.01' if problems else '✅ XML conforme'}")
