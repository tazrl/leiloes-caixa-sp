"""
Descobre a latitude/longitude de cada imóvel para plotar no mapa.

Estratégia: tenta o endereço mais específico primeiro; se o mapa não achar,
vai afrouxando até achar alguma coisa — e SEMPRE anota até onde conseguiu chegar.
Isso é o que impede você de olhar um ponto no mapa achando que é o imóvel
quando na verdade é o centro da cidade.

    1. Rua + número + cidade   -> ponto do imóvel        (precisao = numero)
    2. Rua + cidade            -> meio da rua certa      (precisao = logradouro)
    3. Bairro + cidade         -> centro do bairro       (precisao = bairro)
    4. Cidade                  -> centro da cidade       (precisao = cidade)

Tudo que já foi consultado fica guardado. Rodar de novo amanhã não repete nada.

Uso (Prompt de Comando):
    pip install pandas curl_cffi
    python geocodificar.py --uf SP --limite 500
"""

import os
import time
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

import pandas as pd
from curl_cffi import requests as cr

from endereco import (separar, classificar_precisao, _titulo, _limpar_bairro,
                      limpar_apelido)
from regioes import classificar as classificar_regiao

BANCO = Path(__file__).parent / "imoveis_caixa.db"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
HERE_URL = "https://geocode.search.hereapi.com/v1/geocode"
MAPBOX_URL = "https://api.mapbox.com/search/geocode/v6/forward"

# Provedor: 'osm' (grátis, lento) ou 'here' (chave em HERE_API_KEY).
# A escolha vem da variável de ambiente GEOCODER; o padrão é osm.
PROVEDOR = os.environ.get("GEOCODER", "osm").lower()
CHAVE_HERE = os.environ.get("HERE_API_KEY", "").strip()

# Validade do cache, em dias. Existe por motivo jurídico, não técnico:
# HERE e Google limitam a 30 dias o tempo que você pode guardar uma coordenada.
# Aqui isso quase não custa nada, porque a própria lista da Caixa se renova
# mais rápido que isso (83% dela mudou em um mês).
VALIDADE_CACHE = int(os.environ.get("CACHE_DIAS", "30"))

# O OpenStreetMap é gratuito e pede, em troca, no máximo 1 consulta por segundo
# e que você se identifique. Respeitar isso evita bloqueio.
# O serviço gratuito do OpenStreetMap pede, na política de uso, no máximo
# 1 consulta por segundo — e apenas 4 por MINUTO para scripts que rodam em
# intervalos regulares, como este. Ver:
# https://operations.osmfoundation.org/policies/nominatim/
PAUSA_OSM = float(os.environ.get("PAUSA_OSM", "15"))
PAUSA_HERE = 0.25
UA = {"User-Agent": "AppLeiloesImoveis/1.0 (uso pessoal, contato: investidor)"}

NIVEIS = ["numero", "logradouro", "bairro", "cidade"]

# Cada provedor descreve a precisão com um nome diferente.
TIPOS_EXATOS = {"houseNumber", "house_number", "address", "building",
                "ROOFTOP", "RANGE_INTERPOLATED"}

# O que costuma estar por trás de cada recusa da HERE.
DICAS_HERE = {
    401: ("A chave foi rejeitada. Duas causas comuns, nesta ordem:\n"
          "  1. O app não está ligado a um projeto com o serviço "
          "'Geocoding & Search' habilitado. No portal da HERE, abra "
          "Projects Manager, entre no seu projeto e adicione esse serviço.\n"
          "  2. A chave foi colada com espaço ou quebra de linha junto. "
          "Refaça o secret no GitHub colando sem espaços nas pontas."),
    403: ("Acesso negado. Em geral é 'Trusted Domains' configurado no app: "
          "o robô roda num servidor, sem domínio, então essa restrição "
          "precisa ficar vazia."),
    429: "Passou do limite diário do plano gratuito. Tente amanhã.",
}


# ---------------------------------------------------------------- cache

def preparar_banco():
    con = sqlite3.connect(BANCO, timeout=60)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=60000")
    con.execute("""CREATE TABLE IF NOT EXISTS geocache(
        consulta TEXT PRIMARY KEY, lat REAL, lon REAL,
        tipo_osm TEXT, encontrado INTEGER, data TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS coordenadas(
        id_imovel TEXT PRIMARY KEY, lat REAL, lon REAL,
        precisao TEXT, precisao_desejada TEXT, consulta TEXT, data TEXT)""")
    con.commit()
    return con


def _do_cache(con, consulta):
    """Devolve o resultado guardado, se ainda estiver dentro da validade."""
    r = con.execute("""SELECT lat, lon, encontrado, data FROM geocache
                       WHERE consulta=?""", (consulta,)).fetchone()
    if not r:
        return None
    if VALIDADE_CACHE > 0 and r[3]:
        try:
            idade = (datetime.now() - datetime.fromisoformat(r[3])).days
            if idade > VALIDADE_CACHE:
                return None          # venceu: consulta de novo
        except ValueError:
            pass
    return r[:3]


def _consultar_mapa(con, consulta):
    """Pergunta ao OpenStreetMap. Guarda a resposta (inclusive 'não achei')."""
    cache = _do_cache(con, consulta)
    if cache is not None:
        lat, lon, achou = cache
        return (lat, lon) if achou else None

    achado = None
    try:
        if PROVEDOR == "here" and CHAVE_HERE:
            d = cr.get(HERE_URL,
                       params={"q": consulta, "in": "countryCode:BRA",
                               "limit": 1, "apiKey": CHAVE_HERE},
                       headers=UA, timeout=30).json()
            itens = d.get("items") or []
            if itens:
                pos = itens[0]["position"]
                achado = (pos["lat"], pos["lng"], itens[0].get("resultType"))
        else:
            d = cr.get(NOMINATIM,
                       params={"q": consulta, "format": "json", "limit": 1,
                               "countrycodes": "br"},
                       headers=UA, timeout=30).json()
            if d:
                achado = (float(d[0]["lat"]), float(d[0]["lon"]),
                          d[0].get("addresstype"))
    except Exception:
        achado = None
    time.sleep(PAUSA_HERE if (PROVEDOR == "here" and CHAVE_HERE) else PAUSA_OSM)

    if achado:
        lat, lon, tipo = achado
        con.execute("INSERT OR REPLACE INTO geocache VALUES (?,?,?,?,1,?)",
                    (consulta, lat, lon, tipo, datetime.now().isoformat(timespec="seconds")))
        con.commit()
        return lat, lon

    con.execute("INSERT OR REPLACE INTO geocache VALUES (?,NULL,NULL,NULL,0,?)",
                (consulta, datetime.now().isoformat(timespec="seconds")))
    con.commit()
    return None


# ---------------------------------------------------------------- consultas

def montar_consultas(p: dict, bairro, cidade, uf) -> list:
    """Monta a escada de tentativas, da mais precisa para a mais grosseira.

    O bairro fica FORA das duas primeiras tentativas de propósito: em teste,
    incluir o bairro derrubou o acerto de 90% para 35%, porque o nome do bairro
    na planilha da Caixa quase nunca bate com o nome no mapa.
    """
    cidade_t = _titulo(str(cidade).strip())
    uf = str(uf).strip().upper()
    fim = f"{cidade_t}, {uf}, Brasil"

    log = p.get("endereco_normalizado")
    prec = classificar_precisao(p)
    escada = []

    if prec in ("numero", "logradouro") and log:
        # o nome como veio, e depois o nome sem apelido/erro de digitação
        nomes = [log]
        limpo = limpar_apelido(log)
        if limpo and limpo != log:
            nomes.append(limpo)

        if prec == "numero" and p.get("numero"):
            for n in nomes:
                escada.append(("numero", f"{n}, {p['numero']}, {fim}"))
        for n in nomes:
            escada.append(("logradouro", f"{n}, {fim}"))

    if bairro and str(bairro).strip():
        escada.append(("bairro", f"{_limpar_bairro(str(bairro).strip())}, {fim}"))

    escada.append(("cidade", fim))
    return escada


def localizar(con, p, bairro, cidade, uf):
    for nivel, consulta in montar_consultas(p, bairro, cidade, uf):
        achou = _consultar_mapa(con, consulta)
        if achou:
            return achou[0], achou[1], nivel, consulta
    return None, None, "nao_encontrado", None


# ---------------------------------------------------------------- execução

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uf", help="Só um estado, ex: SP")
    ap.add_argument("--cidade", help="Só uma cidade")
    ap.add_argument("--preco-max", type=float, help="Teto de preço")
    ap.add_argument("--tipo", help="Ex: Apartamento")
    ap.add_argument("--regiao", help="Ex: 'RM de São Paulo'")
    ap.add_argument("--limite", type=int, help="Máximo de imóveis nesta rodada")
    ap.add_argument("--refazer-imprecisos", action="store_true",
                    help="Tenta de novo os que só acharam bairro ou cidade")
    ap.add_argument("--testar-chave", action="store_true",
                    help="Faz uma consulta de teste e diz qual serviço respondeu")
    args = ap.parse_args()

    # Deixa claro, no log, qual serviço está em uso. Sem isso não dá para
    # saber se a chave da HERE pegou ou não.
    if PROVEDOR == "here" and CHAVE_HERE:
        print(f"Serviço de mapas: HERE (chave com {len(CHAVE_HERE)} caracteres), "
              f"{PAUSA_HERE}s entre consultas")
    elif PROVEDOR == "here":
        print("ATENÇÃO: pedi HERE, mas a chave HERE_API_KEY chegou vazia. "
              "Vou usar o OpenStreetMap.")
    else:
        print(f"Serviço de mapas: OpenStreetMap gratuito, "
              f"{PAUSA_OSM}s entre consultas")

    con = preparar_banco()

    if args.testar_chave:
        # Aqui a consulta é feita "na mão", sem cache e sem engolir erro,
        # justamente para mostrar a mensagem exata do serviço.
        alvo = "Avenida Paulista, 1578, Sao Paulo, SP, Brasil"
        print(f"Consulta de teste: {alvo}")
        try:
            if PROVEDOR == "here" and CHAVE_HERE:
                r = cr.get(HERE_URL,
                           params={"q": alvo, "in": "countryCode:BRA",
                                   "limit": 1, "apiKey": CHAVE_HERE},
                           headers=UA, timeout=30)
                print(f"HTTP {r.status_code}")
                if r.status_code == 200:
                    itens = (r.json().get("items") or [])
                    if itens:
                        p_ = itens[0]["position"]
                        print(f"OK: {p_['lat']}, {p_['lng']} "
                              f"({itens[0].get('resultType')})")
                    else:
                        print("Respondeu 200 mas sem resultado. "
                              "Endereço não encontrado — a chave está boa.")
                else:
                    print(f"Recusado. Resposta do serviço: {r.text[:300]}")
                    print(DICAS_HERE.get(r.status_code, ""))
            else:
                # apaga do cache primeiro, senão o teste lê resposta velha
                con.execute("DELETE FROM geocache WHERE consulta=?", (alvo,))
                con.commit()
                r = _consultar_mapa(con, alvo)
                print(f"OK: {r[0]}, {r[1]}" if r
                      else "Sem resultado pelo OpenStreetMap.")
        except Exception as e:
            print(f"Falha na conexão: {e}")
        con.close()
        return

    sql = "SELECT * FROM imoveis WHERE 1=1"
    par = []
    if args.uf:
        sql += " AND uf=?"; par.append(args.uf.upper())
    if args.cidade:
        sql += " AND cidade LIKE ?"; par.append(f"%{args.cidade.upper()}%")
    if args.preco_max:
        sql += " AND preco<=?"; par.append(args.preco_max)
    if args.tipo:
        sql += " AND tipo_imovel=?"; par.append(args.tipo)

    df = pd.read_sql(sql, con, params=par)

    if args.regiao:
        alvo = df.cidade.map(lambda c: classificar_regiao(c)["regiao_metropolitana"])
        df = df[alvo == args.regiao]

    if args.refazer_imprecisos:
        n = con.execute("""DELETE FROM coordenadas
                           WHERE precisao IN ('bairro','cidade','nao_encontrado')""").rowcount
        con.commit()
        print(f"Vou tentar de novo {n} imóveis que tinham posição imprecisa.\n")

    ja = pd.read_sql("SELECT id_imovel FROM coordenadas", con)["id_imovel"].tolist()
    df = df[~df.id_imovel.isin(ja)]
    if args.limite:
        df = df.head(args.limite)

    if df.empty:
        print("Nada novo para localizar. Tudo já está no mapa.")
        return

    print(f"{len(df)} imóveis a localizar. "
          f"Como o mapa gratuito aceita 1 consulta por segundo, "
          f"isso leva no máximo ~{len(df)*PAUSA/60:.0f} min "
          f"(bem menos, porque endereços repetidos já ficam no cache).\n")

    contagem = dict.fromkeys(NIVEIS + ["nao_encontrado"], 0)
    for i, (_, r) in enumerate(df.iterrows(), 1):
        p = separar(r.endereco)
        lat, lon, nivel, consulta = localizar(con, p, r.bairro, r.cidade, r.uf)
        contagem[nivel] += 1
        con.execute("INSERT OR REPLACE INTO coordenadas VALUES (?,?,?,?,?,?,?)",
                    (r.id_imovel, lat, lon, nivel, classificar_precisao(p),
                     consulta, datetime.now().isoformat(timespec="seconds")))
        if i % 25 == 0:
            con.commit()
            print(f"   {i}/{len(df)}  exatos:{contagem['numero']} "
                  f"rua:{contagem['logradouro']} bairro:{contagem['bairro']} "
                  f"cidade:{contagem['cidade']} falhou:{contagem['nao_encontrado']}")
    con.commit()

    print("\n--- resultado ---")
    for k in NIVEIS + ["nao_encontrado"]:
        if contagem[k]:
            print(f"   {k:15s} {contagem[k]:5d}  ({contagem[k]/len(df)*100:.1f}%)")
    con.close()


if __name__ == "__main__":
    main()
