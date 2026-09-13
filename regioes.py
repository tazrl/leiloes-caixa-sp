"""
Classifica cada imóvel de SP em região metropolitana, sub-região e zona da capital.

Três níveis de filtro, do mais amplo ao mais fino:

  1. REGIÃO METROPOLITANA  -> RM de São Paulo, Baixada Santista, Campinas...
  2. SUB-REGIÃO            -> dentro da RMSP: ABC, Oeste (Barueri/Osasco), Leste...
  3. ZONA / SUBPREFEITURA  -> só na capital: Zona Sul, Zona Leste, Centro...

As listas de municípios das regiões metropolitanas vêm da lei estadual.
A lista completa dos 645 municípios e a divisão do IBGE (região imediata)
são baixadas do próprio IBGE, para o interior não ficar num balaio só.
A zona da capital é decidida pela coordenada do imóvel, cruzando com o
mapa oficial dos 96 distritos da Prefeitura de São Paulo.
"""

import json
import unicodedata
from pathlib import Path

PASTA = Path(__file__).parent
ARQ_DISTRITOS = PASTA / "distritos_sp.geojson"
ARQ_IBGE = PASTA / "municipios_sp_ibge.json"

IBGE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/35/municipios"
DISTRITOS_URL = ("https://raw.githubusercontent.com/codigourbano/"
                 "distritos-sp/master/distritos-sp.geojson")


def chave(t: str) -> str:
    """Normaliza nome de cidade: sem acento, maiúsculo, sem pontuação."""
    t = unicodedata.normalize("NFD", str(t))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = t.upper().replace("'", "").replace("-", " ").replace(".", "")
    return " ".join(t.split())


# ============================================================ regiões metropolitanas

# RM de São Paulo — 39 municípios em 5 sub-regiões (LC estadual 1.139/2011)
RMSP_SUB = {
    "Capital": ["São Paulo"],
    "Norte": ["Caieiras", "Cajamar", "Francisco Morato", "Franco da Rocha",
              "Mairiporã"],
    "Leste": ["Arujá", "Biritiba-Mirim", "Ferraz de Vasconcelos", "Guararema",
              "Guarulhos", "Itaquaquecetuba", "Mogi das Cruzes", "Poá",
              "Salesópolis", "Santa Isabel", "Suzano"],
    "Sudeste (Grande ABC)": ["Diadema", "Mauá", "Ribeirão Pires",
                             "Rio Grande da Serra", "Santo André",
                             "São Bernardo do Campo", "São Caetano do Sul"],
    "Sudoeste": ["Cotia", "Embu das Artes", "Embu", "Embu-Guaçu",
                 "Itapecerica da Serra", "Juquitiba", "São Lourenço da Serra",
                 "Taboão da Serra", "Vargem Grande Paulista"],
    "Oeste": ["Barueri", "Carapicuíba", "Itapevi", "Jandira", "Osasco",
              "Pirapora do Bom Jesus", "Santana de Parnaíba"],
}

RM = {
    "RM de São Paulo": [c for lista in RMSP_SUB.values() for c in lista],

    "RM da Baixada Santista": [
        "Bertioga", "Cubatão", "Guarujá", "Itanhaém", "Mongaguá", "Peruíbe",
        "Praia Grande", "Santos", "São Vicente"],

    "RM de Campinas": [
        "Americana", "Artur Nogueira", "Campinas", "Cosmópolis",
        "Engenheiro Coelho", "Holambra", "Hortolândia", "Indaiatuba",
        "Itatiba", "Jaguariúna", "Monte Mor", "Morungaba", "Nova Odessa",
        "Paulínia", "Pedreira", "Santa Bárbara d'Oeste",
        "Santo Antônio de Posse", "Sumaré", "Valinhos", "Vinhedo"],

    "RM de Jundiaí": [
        "Cabreúva", "Campo Limpo Paulista", "Itupeva", "Jarinu", "Jundiaí",
        "Louveira", "Várzea Paulista"],

    "RM de Sorocaba": [
        "Alambari", "Alumínio", "Araçariguama", "Araçoiaba da Serra",
        "Boituva", "Capela do Alto", "Cerquilho", "Cesário Lange", "Ibiúna",
        "Iperó", "Itapetininga", "Itu", "Jumirim", "Mairinque", "Piedade",
        "Pilar do Sul", "Porto Feliz", "Salto", "Salto de Pirapora",
        "São Miguel Arcanjo", "São Roque", "Sarapuí", "Sorocaba", "Tapiraí",
        "Tatuí", "Tietê", "Votorantim"],

    "RM do Vale do Paraíba e Litoral Norte": [
        "Aparecida", "Arapeí", "Areias", "Bananal", "Caçapava",
        "Cachoeira Paulista", "Campos do Jordão", "Canas", "Caraguatatuba",
        "Cruzeiro", "Cunha", "Guaratinguetá", "Igaratá", "Ilhabela",
        "Jacareí", "Jambeiro", "Lagoinha", "Lavrinhas", "Lorena",
        "Monteiro Lobato", "Natividade da Serra", "Paraibuna",
        "Pindamonhangaba", "Piquete", "Potim", "Queluz", "Redenção da Serra",
        "Roseira", "Santa Branca", "Santo Antônio do Pinhal",
        "São Bento do Sapucaí", "São José do Barreiro", "São José dos Campos",
        "São Luiz do Paraitinga", "São Sebastião", "Silveiras", "Taubaté",
        "Tremembé", "Ubatuba"],

    "RM de Ribeirão Preto": [
        "Barrinha", "Batatais", "Brodowski", "Cajuru", "Cássia dos Coqueiros",
        "Cravinhos", "Dumont", "Guariba", "Guatapará", "Jaboticabal",
        "Jardinópolis", "Luís Antônio", "Mococa", "Monte Alto", "Morro Agudo",
        "Nuporanga", "Orlândia", "Pitangueiras", "Pontal", "Pradópolis",
        "Ribeirão Preto", "Sales Oliveira", "Santa Cruz da Esperança",
        "Santa Rita do Passa Quatro", "Santa Rosa de Viterbo",
        "Santo Antônio da Alegria", "São Simão", "Serra Azul", "Serrana",
        "Sertãozinho", "Tambaú", "Taquaral", "Taquaritinga", "Viradouro"],

    "RM de Piracicaba": [
        "Águas de São Pedro", "Analândia", "Araras", "Capivari", "Charqueada",
        "Conchal", "Cordeirópolis", "Corumbataí", "Elias Fausto", "Ipeúna",
        "Iracemápolis", "Itirapina", "Leme", "Limeira", "Mombuca",
        "Piracicaba", "Rafard", "Rio Claro", "Rio das Pedras", "Saltinho",
        "Santa Cruz da Conceição", "Santa Gertrudes", "Santa Maria da Serra",
        "São Pedro", "Torrinha"],
}

_MAPA_RM, _MAPA_SUB = {}, {}
for nome_rm, cidades in RM.items():
    for c in cidades:
        _MAPA_RM[chave(c)] = nome_rm
for nome_sub, cidades in RMSP_SUB.items():
    for c in cidades:
        _MAPA_SUB[chave(c)] = nome_sub


# ============================================================ zonas da capital

SUBPREF_ZONA = {
    "SE": "Centro",

    "CASA VERDE-CACHOEIRINHA": "Zona Norte", "FREGUESIA-BRASILANDIA": "Zona Norte",
    "JACANA-TREMEMBE": "Zona Norte", "PERUS": "Zona Norte",
    "PIRITUBA-JARAGUA": "Zona Norte", "SANTANA-TUCURUVI": "Zona Norte",
    "VILA MARIA-VILA GUILHERME": "Zona Norte",

    "ARICANDUVA-FORMOSA-CARRAO": "Zona Leste", "CIDADE TIRADENTES": "Zona Leste",
    "ERMELINO MATARAZZO": "Zona Leste", "GUAIANASES": "Zona Leste",
    "ITAIM PAULISTA": "Zona Leste", "ITAQUERA": "Zona Leste",
    "MOOCA": "Zona Leste", "PENHA": "Zona Leste", "SAO MATEUS": "Zona Leste",
    "SAO MIGUEL": "Zona Leste", "SAPOPEMBA": "Zona Leste",
    "VILA PRUDENTE": "Zona Leste",

    "BUTANTA": "Zona Oeste", "LAPA": "Zona Oeste", "PINHEIROS": "Zona Oeste",

    "CAMPO LIMPO": "Zona Sul", "CAPELA DO SOCORRO": "Zona Sul",
    "CIDADE ADEMAR": "Zona Sul", "IPIRANGA": "Zona Sul",
    "JABAQUARA": "Zona Sul", "M'BOI MIRIM": "Zona Sul",
    "PARELHEIROS": "Zona Sul", "SANTO AMARO": "Zona Sul",
    "VILA MARIANA": "Zona Sul",
}

_distritos = None


def _carregar_distritos():
    """Carrega os 96 distritos da capital uma única vez."""
    global _distritos
    if _distritos is not None:
        return _distritos
    from shapely.geometry import shape
    from shapely.strtree import STRtree

    g = json.loads(ARQ_DISTRITOS.read_text(encoding="utf-8"))
    geos, meta = [], []
    for f in g["features"]:
        geos.append(shape(f["geometry"]))
        p = f["properties"]
        meta.append((p["ds_nome"].title(), p["ds_subpref"]))
    _distritos = (STRtree(geos), geos, meta)
    return _distritos


def zona_da_capital(lat, lon):
    """Dada a coordenada, devolve (distrito, subprefeitura, zona)."""
    if lat is None or lon is None:
        return None, None, None
    from shapely.geometry import Point
    arvore, geos, meta = _carregar_distritos()
    p = Point(lon, lat)
    for i in arvore.query(p):
        if geos[i].contains(p):
            distrito, subpref = meta[i]
            return distrito, subpref.title(), SUBPREF_ZONA.get(subpref)
    return None, None, None


# ============================================================ IBGE (interior)

_ibge = None


def _carregar_ibge():
    global _ibge
    if _ibge is not None:
        return _ibge
    dados = json.loads(ARQ_IBGE.read_text(encoding="utf-8"))
    _ibge = {chave(m["nome"]): m["regiao-imediata"]["nome"] for m in dados}
    return _ibge


def classificar(cidade, lat=None, lon=None) -> dict:
    """Devolve os rótulos de região de um imóvel."""
    k = chave(cidade)
    rm = _MAPA_RM.get(k)
    sub = _MAPA_SUB.get(k) if rm == "RM de São Paulo" else None

    if rm:
        grupo = rm
    else:
        imediata = _carregar_ibge().get(k)
        grupo = f"Interior — {imediata}" if imediata else "Interior"

    distrito = subpref = zona = None
    if k == "SAO PAULO":
        distrito, subpref, zona = zona_da_capital(lat, lon)

    return {"regiao_metropolitana": rm, "sub_regiao": sub, "grupo_regiao": grupo,
            "distrito": distrito, "subprefeitura": subpref, "zona_capital": zona}


def baixar_bases():
    """Baixa os dois arquivos de apoio. Rodar uma vez só."""
    from curl_cffi import requests as cr
    if not ARQ_IBGE.exists():
        ARQ_IBGE.write_text(json.dumps(cr.get(IBGE_URL, timeout=90).json(),
                                       ensure_ascii=False), encoding="utf-8")
        print(f"IBGE salvo em {ARQ_IBGE}")
    if not ARQ_DISTRITOS.exists():
        ARQ_DISTRITOS.write_bytes(cr.get(DISTRITOS_URL, timeout=180).content)
        print(f"Distritos salvos em {ARQ_DISTRITOS}")


if __name__ == "__main__":
    baixar_bases()
    print(classificar("SAO PAULO", -23.5614, -46.6559))
    print(classificar("SANTO ANDRE"))
    print(classificar("RIBEIRAO PRETO"))
    print(classificar("MARILIA"))
