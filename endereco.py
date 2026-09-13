"""
Separa o endereço da Caixa em partes utilizáveis num mapa.

Entra:  'RUA DALVA RAPOSO, N. 260, Apto 407, BL 06'
Sai:    tipo=RUA | logradouro=DALVA RAPOSO | numero=260 | complemento=Apto 407, BL 06

E monta a linha de busca que o mapa entende:
        'Rua Dalva Raposo, 260, Campo Grande, Rio de Janeiro, RJ, Brasil'
"""

import re
import unicodedata

# --- abreviações que aparecem na base, traduzidas para o nome cheio ----------
TIPOS = {
    "R": "RUA", "RUA": "RUA",
    "AV": "AVENIDA", "AVE": "AVENIDA", "AVENIDA": "AVENIDA",
    "TV": "TRAVESSA", "TRAV": "TRAVESSA", "TRAVESSA": "TRAVESSA",
    "AL": "ALAMEDA", "ALAMEDA": "ALAMEDA",
    "PC": "PRACA", "PR": "PRACA", "PRACA": "PRACA", "PÇ": "PRACA",
    "ROD": "RODOVIA", "RODOVIA": "RODOVIA",
    "EST": "ESTRADA", "ESTRADA": "ESTRADA",
    "QD": "QUADRA", "QUADRA": "QUADRA", "QUAD": "QUADRA",
    "VL": "VILA", "VILA": "VILA",
    "JD": "JARDIM", "JARDIM": "JARDIM",
    "LT": "LOTE", "LOTE": "LOTE",
    "CJ": "CONJUNTO", "CONJUNTO": "CONJUNTO",
    "VIA": "VIA", "LARGO": "LARGO", "LADEIRA": "LADEIRA",
    "SETOR": "SETOR", "LOTEAMENTO": "LOTEAMENTO", "CHACARA": "CHACARA",
    "COLONIA": "COLONIA", "NUCLEO": "NUCLEO", "PARQUE": "PARQUE",
    "SITIO": "SITIO", "FAZENDA": "FAZENDA", "MARGINAL": "MARGINAL",
    "ACESSO": "ACESSO", "ALTO": "ALTO", "AREA": "AREA",
}

# valores que significam "não tem número"
SEM_NUMERO = {"", "SN", "S/N", "S/N.", "SN.", "S N", "0", "00", "000", "-", "."}

# tipos que não são logradouro de verdade — quem cai aqui não vira ponto exato
NAO_LOGRADOURO = {"QUADRA", "LOTE", "CHACARA", "SETOR", "AREA", "GLEBA"}


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if unicodedata.category(c) != "Mn")


def _titulo(t: str) -> str:
    """'RUA DALVA RAPOSO' -> 'Rua Dalva Raposo' (mantém siglas curtas em caixa alta)."""
    miudas = {"de", "da", "do", "das", "dos", "e", "a", "o"}
    palavras = []
    for i, p in enumerate(t.lower().split()):
        if re.fullmatch(r"[a-z]{1,2}\d*|\d+[a-z]?", p) and p not in miudas:
            palavras.append(p.upper())
        elif p in miudas and i > 0:
            palavras.append(p)
        else:
            palavras.append(p.capitalize())
    return " ".join(palavras)


def separar(endereco: str) -> dict:
    """Quebra o endereço bruto nas suas partes."""
    vazio = {"tipo_logradouro": None, "logradouro": None, "numero": None,
             "complemento": None, "quadra": None, "lote": None,
             "endereco_normalizado": None}
    if not endereco or not str(endereco).strip():
        return vazio

    bruto = re.sub(r"\s+", " ", str(endereco).strip()).strip(" ,")
    partes = [p.strip() for p in bruto.split(",")]

    # --- localizar o pedaço que carrega o número ---------------------------
    idx_num, numero = None, None
    for i, p in enumerate(partes):
        m = re.match(r"^N\.?\s*(.*)$", p, re.I)
        if m:
            idx_num = i
            valor = m.group(1).strip().upper().rstrip(".")
            if valor not in SEM_NUMERO:
                mn = re.match(r"^(\d+)", valor)
                if mn:
                    numero = mn.group(1).lstrip("0") or None
            break

    if idx_num is not None:
        trecho_log = ", ".join(partes[:idx_num])
        complemento = ", ".join(partes[idx_num + 1:]).strip(" ,")
    else:
        # 0,2% dos casos: endereço só com quadra/lote, sem marcador "N."
        trecho_log = partes[0]
        complemento = ", ".join(partes[1:]).strip(" ,")
        m = re.search(r"\bN[º°\.]?\s*(\d+)", bruto, re.I)
        if m:
            numero = m.group(1).lstrip("0") or None

    # --- separar tipo do nome do logradouro --------------------------------
    trecho_log = trecho_log.strip(" ,-")
    tokens = trecho_log.split()
    tipo, nome = None, trecho_log
    if tokens:
        chave = _sem_acento(tokens[0]).upper().rstrip(".")
        if chave in TIPOS:
            tipo = TIPOS[chave]
            nome = " ".join(tokens[1:]).strip()
            # "QUADRA QUADRA 34" -> tira a repetição
            if nome.split() and _sem_acento(nome.split()[0]).upper() in TIPOS \
               and TIPOS[_sem_acento(nome.split()[0]).upper()] == tipo:
                nome = " ".join(nome.split()[1:]).strip()
    if not nome:
        nome = trecho_log or None

    # --- quadra e lote, que aparecem soltos no complemento ------------------
    todo = f"{trecho_log}, {complemento}"
    mq = re.search(r"\b(?:QD|QUADRA|QUAD)\.?\s+(?!QUADRA|QD\b)([A-Z0-9\-]{1,6})\b", todo, re.I)
    ml = re.search(r"\b(?:LT|LOTE)\.?\s+(?!LOTE|LT\b)([A-Z0-9\-]{1,6})\b", todo, re.I)

    return {
        "tipo_logradouro": tipo,
        "logradouro": nome,
        "numero": numero,
        "complemento": complemento or None,
        "quadra": mq.group(1).upper() if mq else None,
        "lote": ml.group(1).upper() if ml else None,
        "endereco_normalizado": _titulo(f"{tipo} {nome}" if tipo else (nome or "")) or None,
    }


def classificar_precisao(p: dict) -> str:
    """
    Diz até onde dá para confiar neste endereço num mapa.
      numero     -> ponto exato do imóvel
      logradouro -> a rua certa, mas ponto no meio dela
      bairro     -> só o bairro (quadra/lote sem rua nomeada)
    """
    log = p.get("logradouro")
    if not isinstance(log, str) or not log.strip():
        return "bairro"
    if p.get("tipo_logradouro") in NAO_LOGRADOURO:
        return "bairro"
    # nome de rua que é só um código curto ('M', '05', 'II') raramente existe no mapa
    if re.fullmatch(r"[A-Z0-9\-]{1,3}", log.upper()):
        return "bairro" if not p.get("numero") else "logradouro"
    return "numero" if p.get("numero") else "logradouro"


ABREV_BAIRRO = {"JD": "Jardim", "JDM": "Jardim", "VL": "Vila", "PQ": "Parque",
                "CJ": "Conjunto", "CJTO": "Conjunto", "CH": "Chacara",
                "STO": "Santo", "STA": "Santa", "S": "Sao", "N SRA": "Nossa Senhora",
                "RES": "Residencial", "LOT": "Loteamento", "DIST": "Distrito",
                "PRQ": "Parque", "SET": "Setor", "NUC": "Nucleo"}


def _limpar_bairro(b: str) -> str:
    saida = []
    for tok in _titulo(b).split():
        saida.append(ABREV_BAIRRO.get(tok.upper(), tok))
    return " ".join(saida)


def linha_de_busca(p: dict, bairro: str, cidade: str, uf: str) -> str:
    """Monta o texto que vai ser jogado no serviço de mapa."""
    prec = classificar_precisao(p)
    pedacos = []
    if prec in ("numero", "logradouro") and p.get("endereco_normalizado"):
        pedacos.append(p["endereco_normalizado"])
        if prec == "numero":
            pedacos.append(str(p["numero"]))
    if bairro and str(bairro).strip():
        pedacos.append(_limpar_bairro(str(bairro).strip()))
    pedacos += [_titulo(str(cidade).strip()), str(uf).strip().upper(), "Brasil"]
    return ", ".join(x for x in pedacos if x)


# ---------------------------------------------------------------- limpeza de apelidos
# A Caixa às vezes escreve o apelido da rua junto do nome oficial, ou anota
# o nome antigo. O mapa não reconhece nada disso. Estas regras tiram só o que
# é seguro tirar — nunca cortam nome composto tipo "Rua Vice-Prefeito Fulano".
_ERROS_CAIXA = {"vivinal": "Vicinal", "avienida": "Avenida", "estarda": "Estrada"}


def limpar_apelido(nome: str) -> str:
    """'Rua Jose Antonio Rodrigues - Ze Pulga' -> 'Rua Jose Antonio Rodrigues'"""
    if not isinstance(nome, str) or not nome.strip():
        return nome
    t = nome
    t = re.sub(r"\s+-\s+.*$", "", t)            # hífen COM espaço dos dois lados
    t = re.sub(r"\(.*?\)", " ", t)              # trecho entre parênteses
    t = re.sub(r"\b(Antiga|Antigo)\s+", "", t, flags=re.I)
    # "Rua Antiga Rua Futura" virava "Rua Rua Futura": tira o tipo repetido
    t = re.sub(r"^(\w+)\s+\1\b", r"\1", t, flags=re.I)
    t = re.sub(r"\s*,\s*(vulgo|conhecida como|ex)\b.*$", "", t, flags=re.I)
    palavras = [_ERROS_CAIXA.get(p.lower(), p) for p in t.split()]
    t = " ".join(palavras).strip(" ,-")
    # se sobrou quase nada, é sinal de que a limpeza exagerou: devolve o original
    return t if len(t.split()) >= 2 else nome
