"""
Baixa a lista completa de imóveis da Caixa e grava em banco local (SQLite).

Como usar (Prompt de Comando do Windows):
    pip install pandas curl_cffi
    python baixar_caixa.py

O que ele faz:
    1. Baixa o arquivo nacional (todos os estados) do site da Caixa.
    2. Guarda uma cópia crua do arquivo em /dados_brutos (auditoria).
    3. Limpa e padroniza os campos (preço vira número, desconto vira número etc.).
    4. Grava tudo em imoveis_caixa.db, com histórico de cada carga.
"""

import re
import time
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from curl_cffi import requests as requests  # imita um navegador de verdade
import pandas as pd

BASE = "https://venda-imoveis.caixa.gov.br/listaweb/Lista_imoveis_{}.csv"
UFS = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT","PA",
       "PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"]

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Referer": "https://venda-imoveis.caixa.gov.br/sistema/download-lista.asp",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

PASTA = Path(__file__).parent
BRUTOS = PASTA / "dados_brutos"
BANCO = PASTA / "imoveis_caixa.db"


class BloqueioBot(Exception):
    """O site respondeu com a página de bloqueio antibot em vez do arquivo."""


# ---------------------------------------------------------------- download

def _validar(conteudo: bytes) -> bytes:
    """Confere se veio CSV mesmo, e não a página de bloqueio ou um HTML de erro."""
    amostra = conteudo[:2000].decode("latin1", errors="ignore").lower()
    if "bot manager" in amostra or "<html" in amostra or "<head" in amostra:
        raise BloqueioBot("Site devolveu página de bloqueio antibot.")
    if "lista de imóveis da caixa" not in amostra:
        raise BloqueioBot("Arquivo recebido não tem o cabeçalho esperado da Caixa.")
    return conteudo


def baixar(chave: str, tentativas: int = 4) -> bytes:
    """Baixa um arquivo ('geral' ou uma UF), com espera crescente se levar bloqueio."""
    url = BASE.format(chave)
    espera = 5
    for n in range(1, tentativas + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=120,
                             impersonate="chrome", allow_redirects=True)
            r.raise_for_status()
            return _validar(r.content)
        except (BloqueioBot, Exception) as e:
            print(f"   tentativa {n}/{tentativas} falhou ({e}); aguardando {espera}s")
            if n == tentativas:
                raise
            time.sleep(espera)
            espera *= 2


def baixar_tudo() -> bytes:
    """Tenta o arquivo nacional. Se não der, monta juntando estado por estado."""
    print("Baixando arquivo nacional (todos os estados)...")
    try:
        return baixar("geral")
    except Exception as e:
        print(f"Arquivo nacional indisponível ({e}). Indo estado por estado.")

    partes = []
    for i, uf in enumerate(UFS, 1):
        print(f"   [{i:02d}/27] {uf}")
        try:
            partes.append(baixar(uf))
        except Exception as e:
            print(f"   !! {uf} falhou: {e}")
        time.sleep(4)  # respiro entre requisições
    if not partes:
        raise RuntimeError("Nenhum arquivo foi baixado.")

    cabecalho = b"\n".join(partes[0].split(b"\n")[:3])
    corpo = [b"\n".join(p.split(b"\n")[3:]) for p in partes]
    return cabecalho + b"\n" + b"\n".join(corpo)


# ---------------------------------------------------------------- limpeza

def _num_br(s):
    """'1.234.567,89' -> 1234567.89"""
    if pd.isna(s):
        return None
    t = str(s).strip().replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _area(desc, rotulo):
    m = re.search(rf"([\d.,]+)\s+de\s+área\s+{rotulo}", str(desc), re.I)
    return _num_br(m.group(1).replace(".", ",")) if m else None


def _area_simples(desc, rotulo):
    """Áreas na descrição vêm no formato americano: '116.12 de área total'."""
    m = re.search(rf"([\d.]+)\s+de\s+área\s+{rotulo}", str(desc), re.I)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _quartos(desc):
    m = re.search(r"(\d+)\s*qto", str(desc), re.I)
    return int(m.group(1)) if m else None


def normalizar(bruto: bytes) -> pd.DataFrame:
    caminho_tmp = BRUTOS / "_tmp.csv"
    caminho_tmp.write_bytes(bruto)

    df = pd.read_csv(caminho_tmp, sep=";", encoding="latin1", skiprows=2, dtype=str)
    caminho_tmp.unlink()

    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={
        "N° do imóvel": "id_imovel", "UF": "uf", "Cidade": "cidade",
        "Bairro": "bairro", "Endereço": "endereco", "Preço": "preco_txt",
        "Valor de avaliação": "avaliacao_txt", "Desconto": "desconto_txt",
        "Financiamento": "financiamento_txt", "Descrição": "descricao",
        "Modalidade de venda": "modalidade", "Link de acesso": "link",
    })

    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()

    df = df[df["id_imovel"].str.match(r"^\d+$", na=False)].copy()

    df["preco"] = df["preco_txt"].map(_num_br)
    df["avaliacao"] = df["avaliacao_txt"].map(_num_br)
    df["desconto_pct"] = pd.to_numeric(df["desconto_txt"], errors="coerce")
    df["aceita_financiamento"] = df["financiamento_txt"].str.lower().eq("sim")

    df["tipo_imovel"] = df["descricao"].str.split(",").str[0].str.strip()
    df["area_total"] = df["descricao"].map(lambda d: _area_simples(d, "total"))
    df["area_privativa"] = df["descricao"].map(lambda d: _area_simples(d, "privativa"))
    df["area_terreno"] = df["descricao"].map(lambda d: _area_simples(d, "do terreno"))
    df["quartos"] = df["descricao"].map(_quartos)

    base = df["area_privativa"].where(df["area_privativa"] > 0, df["area_total"])
    df["preco_m2"] = (df["preco"] / base).where(base > 0)

    # desconto recalculado, para conferir o que a Caixa informa
    df["desconto_calc"] = ((df["avaliacao"] - df["preco"]) / df["avaliacao"] * 100).round(2)

    df["coletado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return df


# ---------------------------------------------------------------- gravação

def gravar(df: pd.DataFrame):
    con = sqlite3.connect(BANCO)
    df.to_sql("imoveis", con, if_exists="replace", index=False)
    con.execute("CREATE INDEX IF NOT EXISTS ix_uf ON imoveis(uf, cidade)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_preco ON imoveis(preco)")
    con.execute("""CREATE TABLE IF NOT EXISTS cargas
                   (data TEXT, registros INTEGER)""")
    con.execute("INSERT INTO cargas VALUES (?,?)",
                (datetime.now().isoformat(timespec="seconds"), len(df)))
    con.commit()
    con.close()


def main():
    BRUTOS.mkdir(exist_ok=True)
    bruto = baixar_tudo()

    carimbo = datetime.now().strftime("%Y-%m-%d")
    arquivo_bruto = BRUTOS / f"caixa_{carimbo}.csv"
    arquivo_bruto.write_bytes(bruto)
    print(f"Cópia crua salva em {arquivo_bruto}")

    df = normalizar(bruto)
    gravar(df)

    print(f"\n{len(df):,} imóveis gravados em {BANCO}".replace(",", "."))
    print(f"Estados presentes: {df['uf'].nunique()}")
    print(f"Com financiamento: {int(df['aceita_financiamento'].sum()):,}".replace(",", "."))
    print("\nTop 5 estados:")
    print(df["uf"].value_counts().head().to_string())


if __name__ == "__main__":
    main()
