"""
Gera o mapa interativo de São Paulo a partir do banco local.

Rode sempre que quiser atualizar — ele usa tudo que já foi localizado
pelo geocodificar.py até o momento.

    python gerar_mapa.py

Sai o arquivo mapa_sp.html, que abre no navegador com clique duplo.
"""

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd

from regioes import classificar, ARQ_IBGE

PASTA = Path(__file__).parent
BANCO = PASTA / "imoveis_caixa.db"
SAIDA = PASTA / "mapa_sp.html"
ARQ_DISTRITOS = PASTA / "distritos_sp.geojson"
ARQ_MUNICIPIOS = PASTA / "mun_sp_raw.geojson"


def _limpo(v):
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, str) and v.strip().lower() in ("", "nan", "none"):
        return None
    return v


def _titulo(t):
    miudas = {"de", "da", "do", "das", "dos", "e"}
    saida = []
    for i, p in enumerate(str(t).lower().split()):
        saida.append(p if (p in miudas and i > 0) else p.capitalize())
    return " ".join(saida)


def carregar():
    con = sqlite3.connect(BANCO, timeout=60)
    df = pd.read_sql("""
        SELECT i.*, c.lat, c.lon, c.precisao
        FROM imoveis i JOIN coordenadas c ON c.id_imovel = i.id_imovel
        WHERE i.uf = 'SP' AND c.lat IS NOT NULL""", con)
    total_sp = pd.read_sql("SELECT COUNT(*) n FROM imoveis WHERE uf='SP'", con).n[0]
    try:
        data = pd.read_sql("SELECT data FROM cargas ORDER BY data DESC LIMIT 1",
                           con).data[0][:10]
    except Exception:
        data = ""
    con.close()

    reg = pd.DataFrame([classificar(c, la, lo)
                        for c, la, lo in zip(df.cidade, df.lat, df.lon)])
    df = pd.concat([df.reset_index(drop=True), reg], axis=1)

    recs = []
    for x in df.itertuples():
        area = x.area_privativa if x.area_privativa and x.area_privativa > 0 else None
        if not area and x.area_total and x.area_total > 0:
            area = x.area_total
        cidade = _titulo(x.cidade)
        bairro = _titulo(x.bairro)
        # Unidade de comparação. Na capital uso o distrito OFICIAL, calculado pela
        # coordenada — o campo "bairro" da Caixa é texto livre e tem 185 variações
        # para 96 distritos ("Dist Itaquera" e "Distrito de Itaquera" viravam duas
        # regiões diferentes). Fora da capital, a unidade é a cidade.
        if cidade == "Sao Paulo":
            area_nome = _limpo(x.distrito) or bairro
        else:
            area_nome = cidade
        recs.append({
            "lat": round(x.lat, 6), "lon": round(x.lon, 6),
            "ci": cidade, "ba": bairro, "en": x.endereco,
            "pr": int(round(x.preco)), "av": int(round(x.avaliacao)),
            "ar": round(float(area), 1) if area else None,
            "qt": int(x.quartos) if not pd.isna(x.quartos) else None,
            "ti": x.tipo_imovel, "fi": int(x.aceita_financiamento),
            "mo": x.modalidade, "px": x.precisao,
            "rm": _limpo(x.regiao_metropolitana) or "Interior de SP",
            "sr": _limpo(x.sub_regiao), "zc": _limpo(x.zona_capital),
            "reg": area_nome, "lk": x.link,
        })
    return recs, int(total_sp), data


# Chave da CARTO, se houver. Sem ela o mapa usa a Esri, que não pede chave.
# Atenção: esta chave NÃO é secreta — o navegador de quem abrir o mapa precisa
# dela para pedir as imagens, então ela sempre aparece no HTML publicado.
# É assim com qualquer chave de mapa de fundo. O que protege é o limite de uso,
# não o sigilo.
CARTO_KEY = os.environ.get("CARTO_KEY", "").strip()

CAMADAS_CARTO = """const K='__CARTO_KEY__';
const cartoAttr='&copy; OpenStreetMap &copy; CARTO';
const BASES={
  'Claro':      L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png?key='+K,
                  {attribution:cartoAttr,subdomains:'abcd',maxZoom:19}),
  'Escuro':     L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png?key='+K,
                  {attribution:cartoAttr,subdomains:'abcd',maxZoom:19}),
  'Detalhado':  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key='+K,
                  {attribution:cartoAttr,subdomains:'abcd',maxZoom:19}),
  'Ruas':       L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  {attribution:'&copy; OpenStreetMap',maxZoom:19}),
  'Satélite':   L.layerGroup([
                  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                    {attribution:'Esri, Maxar, Earthstar Geographics',maxZoom:19}),
                  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png?key='+K,
                    {subdomains:'abcd',maxZoom:19})]),
};
const BASE_INICIAL='Claro';"""

CAMADAS_ESRI = """const ESRI='https://server.arcgisonline.com/ArcGIS/rest/services/';
const BASES={
  'Claro': L.layerGroup([
      L.tileLayer(ESRI+'Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
        {attribution:'Esri, HERE, Garmin, &copy; OpenStreetMap',maxZoom:16}),
      L.tileLayer(ESRI+'Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
        {maxZoom:16})]),
  'Ruas': L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      {attribution:'&copy; OpenStreetMap',maxZoom:19}),
  'Satélite': L.layerGroup([
      L.tileLayer(ESRI+'World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {attribution:'Esri, Maxar, Earthstar Geographics',maxZoom:19}),
      L.tileLayer(ESRI+'Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
        {maxZoom:19})]),
};
const BASE_INICIAL='Claro';"""


def contornos(recs):
    """Monta os limites das regiões que aparecem no mapa.

    Só entram as que têm imóvel — desenhar os 645 municípios do estado
    deixaria a página pesada sem servir para nada. Os contornos são
    simplificados: perdem alguns metros de precisão e ganham megabytes.
    """
    import re
    from shapely.geometry import shape, mapping

    presentes = {r["reg"] for r in recs}
    capital = {r["reg"] for r in recs if r["ci"] == "Sao Paulo"}
    feats = []

    if ARQ_DISTRITOS.exists():
        g = json.loads(ARQ_DISTRITOS.read_text(encoding="utf-8"))
        for f in g["features"]:
            nome = f["properties"]["ds_nome"].title()
            if nome in capital:
                geo = shape(f["geometry"]).simplify(0.0002, preserve_topology=True)
                feats.append({"type": "Feature", "properties": {"d": nome},
                              "geometry": mapping(geo)})

    if ARQ_MUNICIPIOS.exists():
        nomes = {m["id"]: _titulo(m["nome"])
                 for m in json.loads(ARQ_IBGE.read_text(encoding="utf-8"))}
        g = json.loads(ARQ_MUNICIPIOS.read_text(encoding="utf-8"))
        for f in g["features"]:
            nome = nomes.get(int(f["properties"]["codarea"]))
            if nome and nome in presentes and nome not in capital:
                geo = shape(f["geometry"]).simplify(0.002, preserve_topology=True)
                feats.append({"type": "Feature", "properties": {"d": nome},
                              "geometry": mapping(geo)})

    txt = json.dumps({"type": "FeatureCollection", "features": feats},
                     ensure_ascii=False)
    # 4 casas decimais bastam (~10 m) e cortam o arquivo pela metade
    txt = re.sub(r"(\d+\.\d{4})\d+", r"\1", txt)
    print(f"Contornos: {len(feats)} regiões, {round(len(txt)/1024)} KB")
    return txt


def gerar():
    recs, total_sp, data = carregar()
    camadas = (CAMADAS_CARTO.replace("__CARTO_KEY__", CARTO_KEY)
               if CARTO_KEY else CAMADAS_ESRI)
    print("Mapa de fundo: " + ("CARTO (chave presente)" if CARTO_KEY
                               else "Esri (sem chave da CARTO)"))
    html = (TEMPLATE
            .replace("__DADOS__", json.dumps(recs, ensure_ascii=False, allow_nan=False))
            .replace("__TOTAL_SP__", str(total_sp))
            .replace("__NO_MAPA__", str(len(recs)))
            .replace("__DATA__", data)
            .replace("__CAMADAS_MAPA__", camadas)
            .replace("__CONTORNOS__", contornos(recs)))
    SAIDA.write_text(html, encoding="utf-8")
    print(f"{len(recs)} de {total_sp} imóveis de SP no mapa -> {SAIDA}")
    if len(recs) < total_sp:
        print(f"Faltam {total_sp - len(recs)}. Rode 'python geocodificar.py --uf SP' "
              f"e gere o mapa de novo.")


TEMPLATE = r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Leilões da Caixa · São Paulo</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Inter+Tight:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{
  --papel:#E4E7E0; --painel:#F6F7F3; --tinta:#16232A; --tinta2:#5A6A6E;
  --traco:#C2C9BE; --acao:#1F5D50;
  --r1:#CBD6CF; --r2:#9BBBAF; --r3:#5F9583; --r4:#1F5D50;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:'Inter Tight',system-ui,sans-serif;background:var(--papel);color:var(--tinta);
     overflow:hidden;font-variant-numeric:tabular-nums}
.app{display:flex;height:100vh}

.rail{width:376px;flex:0 0 376px;background:var(--painel);border-right:1px solid var(--traco);
      display:flex;flex-direction:column;overflow:hidden}
.topo{padding:22px 24px 0}
h1{font-family:'Bricolage Grotesque',sans-serif;font-size:27px;font-weight:800;
   letter-spacing:-.03em;line-height:1.05}
.fonte{font-size:12px;color:var(--tinta2);margin-top:8px;line-height:1.5}

.abas{display:flex;gap:2px;margin-top:18px;border-bottom:1px solid var(--traco)}
.abas button{flex:1;background:none;border:0;border-bottom:2px solid transparent;
             padding:11px 4px;font:600 13.5px 'Inter Tight',sans-serif;color:var(--tinta2);
             cursor:pointer;margin-bottom:-1px}
.abas button.on{color:var(--tinta);border-bottom-color:var(--acao)}
button:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--acao);outline-offset:2px}

.painel{flex:1;overflow-y:auto;padding-bottom:28px}
.painel::-webkit-scrollbar{width:8px}
.painel::-webkit-scrollbar-thumb{background:var(--traco);border-radius:4px}
.oculto{display:none}

.explica{padding:16px 24px 4px;font-size:12.5px;color:var(--tinta2);line-height:1.55}
.ordena{display:flex;gap:6px;padding:12px 24px 10px;flex-wrap:wrap}
.mini{background:none;border:1px solid var(--traco);border-radius:14px;padding:4px 11px;
      font:500 12px 'Inter Tight',sans-serif;color:var(--tinta2);cursor:pointer}
.mini.on{background:var(--tinta);color:var(--painel);border-color:var(--tinta)}

.linha{display:grid;grid-template-columns:1fr auto;gap:4px 12px;padding:11px 24px;
       border:0;border-bottom:1px solid var(--traco);cursor:pointer;width:100%;
       text-align:left;background:none;font:inherit;color:inherit}
.linha:hover{background:#EDEFE9}
.linha.sel{background:#E2EBE6;box-shadow:inset 3px 0 0 var(--acao)}
.nome{font-weight:600;font-size:14px;letter-spacing:-.01em}
.qtd{font-size:12px;color:var(--tinta2);white-space:nowrap}
.medidas{grid-column:1/-1;display:flex;align-items:center;gap:10px;margin-top:3px}
.bar{flex:1;height:7px;background:#DCE0D8;border-radius:4px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--acao)}
.val{font-size:12.5px;font-weight:600;white-space:nowrap;min-width:44px;text-align:right}
.sub{grid-column:1/-1;font-size:11.5px;color:var(--tinta2);margin-top:2px}
.frag{display:block;font-style:normal;color:#8E3B26;margin-top:2px}
.vazio{padding:28px 24px;color:var(--tinta2);font-size:13.5px;line-height:1.6}

.bloco{padding:16px 24px;border-bottom:1px solid var(--traco)}
.rot{font-size:12.5px;font-weight:600;color:var(--tinta2);margin-bottom:10px;
     display:flex;justify-content:space-between;gap:8px;align-items:baseline}
.rot b{color:var(--tinta);font-weight:600}
select{width:100%;background:#fff;color:var(--tinta);border:1px solid var(--traco);
       border-radius:6px;padding:9px 10px;font:500 13.5px 'Inter Tight',sans-serif;cursor:pointer}
select:disabled{opacity:.4;cursor:not-allowed}
select+select{margin-top:8px}
input[type=range]{width:100%;accent-color:var(--acao);cursor:pointer}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{background:#fff;border:1px solid var(--traco);color:var(--tinta2);border-radius:16px;
      padding:5px 12px;font:500 12.5px 'Inter Tight',sans-serif;cursor:pointer}
.chip:hover{border-color:var(--tinta2)}
.chip.on{background:var(--tinta);color:var(--painel);border-color:var(--tinta)}
.par{display:flex;justify-content:space-between;font-size:13px;color:var(--tinta2);margin:12px 0 3px}
.par b{color:var(--tinta);font-weight:600}
.limpar{width:100%;background:none;border:1px solid var(--traco);color:var(--tinta2);
        border-radius:6px;padding:10px;font:500 13px 'Inter Tight',sans-serif;cursor:pointer}
.limpar:hover{border-color:var(--tinta);color:var(--tinta)}
.aviso{font-size:12px;line-height:1.55;color:var(--tinta2);padding:16px 24px}
.aviso b{color:var(--tinta);font-weight:600}

.mapa{flex:1;position:relative}
#map{position:absolute;inset:0;background:#DDE0DA}
.leaflet-popup-content-wrapper{border-radius:8px;box-shadow:0 8px 30px rgba(22,35,42,.24)}
.leaflet-popup-content{margin:0;width:290px!important;font-family:'Inter Tight',sans-serif}
.pp{color:#16232A}
.pp .cab{padding:13px 16px 11px;border-bottom:1px solid #E3E6DF}
.pp .tt{font-weight:700;font-size:14.5px;letter-spacing:-.01em}
.pp .ed{font-size:12px;color:#5A6A6E;margin-top:4px;line-height:1.45}
.pp .conta{padding:11px 16px;font-size:12.5px;line-height:1.85;border-bottom:1px solid #E3E6DF}
.pp .li{display:flex;justify-content:space-between;gap:12px}
.pp .li span{color:#5A6A6E}
.pp .li b{font-weight:600}
.pp .tot{border-top:1px solid #E3E6DF;margin-top:6px;padding-top:6px}
.pp .tot span,.pp .tot b{color:#16232A;font-weight:700}
.pp .eq{padding:12px 16px;background:#EDF1EC;border-bottom:1px solid #E3E6DF}
.pp .eq .v{font-family:'Bricolage Grotesque',sans-serif;font-size:19px;font-weight:700;letter-spacing:-.02em}
.pp .eq .k{font-size:11.5px;color:#5A6A6E;margin-top:4px;line-height:1.45}
.pp .rod{padding:11px 16px;display:flex;justify-content:space-between;align-items:center;gap:10px}
.pp .cf{font-size:11px;color:#5A6A6E;line-height:1.4}
.pp .cf .al{color:#8E3B26;font-weight:600}
.pp a{background:#16232A;color:#F6F7F3;text-decoration:none;border-radius:6px;
      padding:8px 13px;font-size:12px;font-weight:600;white-space:nowrap}
.pp .lista{max-height:150px;overflow-y:auto;padding:6px 16px 12px;font-size:12.5px}
.pp .lista button{display:block;width:100%;text-align:left;background:none;border:0;
      border-bottom:1px solid #EDEFE9;padding:7px 0;cursor:pointer;font:inherit;color:#16232A}
.pp .lista button:hover{color:#1F5D50}

.chave{position:absolute;bottom:18px;right:18px;z-index:500;background:rgba(246,247,243,.95);
       border:1px solid var(--traco);border-radius:8px;padding:12px 14px;font-size:11.5px;
       line-height:1.55;max-width:216px}
.chave strong{display:block;font-size:12.5px;margin-bottom:7px;font-weight:600}
.rampa{display:flex;height:9px;border-radius:5px;overflow:hidden;margin:2px 0 4px}
.rampa i{flex:1}
.extremos{display:flex;justify-content:space-between;color:var(--tinta2);font-size:10.5px}
.chave hr{border:0;border-top:1px solid var(--traco);margin:10px 0}
.pino{display:inline-block;width:11px;height:11px;border-radius:50%;vertical-align:-1px;
      margin-right:6px;border:1.5px solid var(--tinta)}
.pino.aprox{background:transparent;border-style:dashed}
.pino.exato{background:var(--r3)}

@media(max-width:860px){
  .app{flex-direction:column}
  .rail{width:100%;flex:0 0 auto;max-height:54vh;border-right:0;border-bottom:1px solid var(--traco)}
  .mapa{flex:1;min-height:46vh}
  .chave{display:none}
}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>
<div class="app">
<aside class="rail">
  <div class="topo">
    <h1>Onde comprar em São Paulo</h1>
    <div class="fonte" id="fonte"></div>
    <div class="abas">
      <button id="aba-reg" class="on">Comparar regiões</button>
      <button id="aba-fil">Filtros</button>
    </div>
  </div>

  <div class="painel" id="p-reg">
    <div class="explica" id="explica"></div>
    <div class="ordena">
      <button class="mini on" data-ord="desc">Maior desconto</button>
      <button class="mini" data-ord="m2">Menor R$/m²</button>
      <button class="mini" data-ord="qtd">Mais imóveis</button>
    </div>
    <div id="ranking"></div>
  </div>

  <div class="painel oculto" id="p-fil">
    <div class="bloco">
      <div class="rot">A cor dos pontos mostra</div>
      <div class="chips">
        <button class="chip on" id="m-liq">Desconto após custos</button>
        <button class="chip" id="m-bruto">Desconto anunciado</button>
      </div>
    </div>

    <div class="bloco">
      <div class="rot">Região</div>
      <select id="f-rm"><option value="">Todo o estado de São Paulo</option></select>
      <select id="f-sub" disabled><option value="">Toda a RM de São Paulo</option></select>
      <select id="f-zona" disabled><option value="">Toda a capital</option></select>
    </div>

    <div class="bloco">
      <div class="rot">Tipo de imóvel</div>
      <div class="chips" id="f-tipo"></div>
    </div>

    <div class="bloco">
      <div class="rot">Modalidade de venda</div>
      <div class="chips" id="f-moda"></div>
    </div>

    <div class="bloco">
      <div class="rot">Preço máximo <b id="v-preco"></b></div>
      <input type="range" id="f-preco" min="50000" max="2000000" step="25000" value="2000000">
    </div>

    <div class="bloco">
      <div class="rot">Outros</div>
      <div class="chips">
        <button class="chip" id="f-fin">Só os que financiam</button>
        <button class="chip" id="f-exato">Só posição exata</button>
      </div>
    </div>

    <div class="bloco">
      <div class="rot">Premissas de custo</div>
      <div class="par"><span>ITBI</span><b id="v-itbi"></b></div>
      <input type="range" id="p-itbi" min="0" max="5" step="0.1" value="3">
      <div class="par"><span>Cartório e registro</span><b id="v-cart"></b></div>
      <input type="range" id="p-cart" min="0" max="2" step="0.1" value="1">
      <div class="par"><span>Reserva para desocupação</span><b id="v-deso"></b></div>
      <input type="range" id="p-deso" min="0" max="60000" step="1000" value="0">
      <div class="par"><span>Reforma por m²</span><b id="v-ref"></b></div>
      <input type="range" id="p-ref" min="0" max="4000" step="50" value="0">
      <div class="par"><span>Corretagem na revenda</span><b id="v-corr"></b></div>
      <input type="range" id="p-corr" min="0" max="8" step="0.5" value="6">
    </div>

    <div class="bloco"><button class="limpar" id="limpar">Limpar filtros</button></div>

    <div class="aviso">
      <b>A comissão de 5% do leiloeiro só existe em Leilão SFI e Licitação Aberta.</b>
      Nas vendas feitas direto pelo site da Caixa, quem paga a corretagem é o banco.
      A mesma placa de desconto pode valer coisas bem diferentes.
    </div>
    <div class="aviso">
      O <b>preço de equilíbrio</b> é o mínimo que a revenda precisa render para você não
      perder dinheiro. O valor de avaliação da Caixa não é preço de mercado, então
      compare o equilíbrio com o que se pede na região.
    </div>
  </div>
</aside>

<div class="mapa">
  <div id="map"></div>
  <div class="chave">
    <strong>Desconto</strong>
    <div class="rampa"><i style="background:var(--r1)"></i><i style="background:var(--r2)"></i><i style="background:var(--r3)"></i><i style="background:var(--r4)"></i></div>
    <div class="extremos"><span>menor</span><span>maior</span></div>
    <hr>
    <strong>Confiança da posição</strong>
    <span class="pino exato"></span>número exato<br>
    <span class="pino aprox"></span>aproximado
  </div>
</div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const DADOS = __DADOS__;
const TOTAL_SP = __TOTAL_SP__, NO_MAPA = __NO_MAPA__, DATA = "__DATA__";

/* A Caixa só cobra a comissão do leiloeiro em duas das quatro modalidades. */
const COMISSAO = {'Leilão SFI - Edital Único':.05,'Licitação Aberta':.05,
                  'Venda Online':0,'Venda Direta Online':0};
const RISCO = new Set(['Leilão SFI - Edital Único']);
const RESERVA_DIVIDA = 15000;
const MIN_REGIAO = 3;   /* abaixo disso a mediana é ruído, não sinal */

const P = {itbi:.03, cart:.01, deso:0, ref:0, corr:.06};
const est = {rm:'',sub:'',zona:'',tipos:new Set(),modas:new Set(),preco:2000000,
             fin:false,exato:false,metrica:'liq',ord:'desc',regiao:null};

const brl = n => Math.round(n).toLocaleString('pt-BR');
const med = a => { if(!a.length) return null; const s=[...a].sort((x,y)=>x-y),m=s.length>>1;
  return s.length%2 ? s[m] : (s[m-1]+s[m])/2; };

function conta(d){
  const com=d.pr*(COMISSAO[d.mo]??.05), itbi=d.pr*P.itbi, cart=d.pr*P.cart;
  const ref=d.ar?d.ar*P.ref:0, div=RISCO.has(d.mo)?RESERVA_DIVIDA:0;
  const extras=com+itbi+cart+ref+div+P.deso, total=d.pr+extras, eq=total/(1-P.corr);
  return {com,itbi,cart,ref,div,deso:P.deso,extras,total,eq,
    eqM2:d.ar?eq/d.ar:null,
    bruto:(d.av-d.pr)/d.av*100, liq:(d.av-total)/d.av*100, extrasPct:extras/d.pr*100};
}
const metrica = d => est.metrica==='bruto' ? conta(d).bruto : conta(d).liq;

/* rampa sequencial de uma cor só: mostra intensidade, não julgamento */
const RAMPA=['#CBD6CF','#9BBBAF','#5F9583','#1F5D50'];
const cor = v => v>=45?RAMPA[3] : v>=32?RAMPA[2] : v>=18?RAMPA[1] : RAMPA[0];

const map=L.map('map',{zoomControl:false}).setView([-22.6,-48.4],7);
L.control.zoom({position:'topright'}).addTo(map);
__CAMADAS_MAPA__
BASES[BASE_INICIAL].addTo(map);

const camada=L.layerGroup().addTo(map);

/* Limites das regiões. Ficam abaixo dos pontos, num plano próprio. */
const CONTORNOS = __CONTORNOS__;
map.createPane('regioes');
map.getPane('regioes').style.zIndex = 350;

let camadaRegioes = null, medianasRegiao = {};

const contornoLayer = L.geoJSON(CONTORNOS, {
  pane:'regioes',
  style: f => estiloRegiao(f.properties.d),
  onEachFeature: (f, l) => {
    const nome = f.properties.d;
    l.on('mouseover', () => {
      const m = medianasRegiao[nome];
      l.bindTooltip(nome + (m===undefined ? ' · sem imóveis no filtro'
                    : ' · ' + m.toFixed(0) + '% de desconto'),
                    {sticky:true}).openTooltip();
      l.setStyle({weight:2.5, opacity:.9});
    });
    l.on('mouseout', () => l.setStyle(estiloRegiao(nome)));
    /* clicar na região é o mesmo que clicar na linha do ranking */
    l.on('click', () => {
      est.regiao = est.regiao === nome ? null : nome;
      pintar(true);
    });
  }
}).addTo(map);

function estiloRegiao(nome){
  const m = medianasRegiao[nome];
  const escolhida = est.regiao === nome;
  if(m === undefined)
    return {color:'#7A8A80', weight:1, opacity:.45, fill:false};
  return {color: escolhida ? '#1F5D50' : '#16232A',
          weight: escolhida ? 3 : 1,
          opacity: escolhida ? 1 : .5,
          fill:true, fillColor:cor(m),
          fillOpacity: escolhida ? .62 : .38};
}
const el=id=>document.getElementById(id);

[...new Set(DADOS.map(d=>d.rm))].sort().forEach(r=>
  el('f-rm').add(new Option(r+' ('+DADOS.filter(d=>d.rm===r).length+')',r)));
[...new Set(DADOS.filter(d=>d.sr).map(d=>d.sr))].sort().forEach(s=>el('f-sub').add(new Option(s,s)));
[...new Set(DADOS.filter(d=>d.zc).map(d=>d.zc))].sort().forEach(z=>el('f-zona').add(new Option(z,z)));

function chips(alvo,campo,conj){
  [...new Set(DADOS.map(d=>d[campo]))]
    .sort((a,b)=>DADOS.filter(d=>d[campo]===b).length-DADOS.filter(d=>d[campo]===a).length)
    .forEach(t=>{
      const b=document.createElement('button'); b.className='chip'; b.textContent=t;
      b.onclick=()=>{conj.has(t)?conj.delete(t):conj.add(t); b.classList.toggle('on'); pintar();};
      el(alvo).appendChild(b);
    });
}
chips('f-tipo','ti',est.tipos);
chips('f-moda','mo',est.modas);

el('aba-reg').onclick=()=>troca(true);
el('aba-fil').onclick=()=>troca(false);
function troca(reg){
  el('aba-reg').classList.toggle('on',reg); el('aba-fil').classList.toggle('on',!reg);
  el('p-reg').classList.toggle('oculto',!reg); el('p-fil').classList.toggle('oculto',reg);
}

document.querySelectorAll('.mini').forEach(b=>b.onclick=()=>{
  est.ord=b.dataset.ord;
  document.querySelectorAll('.mini').forEach(x=>x.classList.toggle('on',x===b));
  pintar();
});

el('m-liq').onclick=()=>{est.metrica='liq';el('m-liq').classList.add('on');
  el('m-bruto').classList.remove('on');pintar();};
el('m-bruto').onclick=()=>{est.metrica='bruto';el('m-bruto').classList.add('on');
  el('m-liq').classList.remove('on');pintar();};

el('f-rm').onchange=e=>{est.rm=e.target.value;est.sub='';est.zona='';est.regiao=null;
  const rmsp=est.rm==='RM de São Paulo'||est.rm==='';
  el('f-sub').disabled=!rmsp; el('f-sub').value='';
  el('f-zona').disabled=true; el('f-zona').value=''; pintar(true);};
el('f-sub').onchange=e=>{est.sub=e.target.value;est.zona='';est.regiao=null;
  el('f-zona').disabled=e.target.value!=='Capital'; el('f-zona').value=''; pintar(true);};
el('f-zona').onchange=e=>{est.zona=e.target.value;est.regiao=null;pintar(true);};
el('f-preco').oninput=e=>{est.preco=+e.target.value;pintar();};
el('f-fin').onclick=e=>{est.fin=!est.fin;e.target.classList.toggle('on');pintar();};
el('f-exato').onclick=e=>{est.exato=!est.exato;e.target.classList.toggle('on');pintar();};

const liga=(id,c,f)=>el(id).oninput=e=>{P[c]=+e.target.value*f;pintar();};
liga('p-itbi','itbi',.01); liga('p-cart','cart',.01); liga('p-deso','deso',1);
liga('p-ref','ref',1);     liga('p-corr','corr',.01);

el('limpar').onclick=()=>{
  Object.assign(est,{rm:'',sub:'',zona:'',tipos:new Set(),modas:new Set(),
                     preco:2000000,fin:false,exato:false,regiao:null});
  el('f-rm').value='';el('f-sub').value='';el('f-zona').value='';
  el('f-sub').disabled=false;el('f-zona').disabled=true;el('f-preco').value=2000000;
  ['f-fin','f-exato'].forEach(i=>el(i).classList.remove('on'));
  document.querySelectorAll('#f-tipo .chip,#f-moda .chip').forEach(c=>c.classList.remove('on'));
  pintar(true);
};

function filtrados(comRegiao){
  return DADOS.filter(d=>
    (!est.rm||d.rm===est.rm) && (!est.sub||d.sr===est.sub) && (!est.zona||d.zc===est.zona) &&
    (!est.tipos.size||est.tipos.has(d.ti)) && (!est.modas.size||est.modas.has(d.mo)) &&
    d.pr<=est.preco && (!est.fin||d.fi===1) && (!est.exato||d.px==='numero') &&
    (!comRegiao||!est.regiao||d.reg===est.regiao));
}

function ranking(base){
  const grupos={};
  base.forEach(d=>{ (grupos[d.reg]=grupos[d.reg]||[]).push(d); });
  return Object.entries(grupos).map(function(par){
    const nome=par[0], itens=par[1];
    const m2=itens.map(d=>conta(d).eqM2).filter(x=>x);
    return {nome:nome, n:itens.length,
            desc:med(itens.map(metrica)),
            m2:med(m2),
            exatos:itens.filter(d=>d.px==='numero').length,
            cidade:itens[0].ci};
  }).filter(r=>r.n>=MIN_REGIAO);
}

function desenharRanking(base){
  const rs=ranking(base), cx=el('ranking');
  if(!rs.length){
    cx.innerHTML='<div class="vazio">Nenhuma região tem ao menos '+MIN_REGIAO+
      ' imóveis com os filtros atuais. Abaixo disso a mediana vira ruído, então '+
      'prefiro não mostrar um número em que você não deveria confiar.</div>';
    return;
  }
  if(est.ord==='desc')     rs.sort((a,b)=>b.desc-a.desc);
  else if(est.ord==='qtd') rs.sort((a,b)=>b.n-a.n);
  else                     rs.sort((a,b)=>(a.m2==null?Infinity:a.m2)-(b.m2==null?Infinity:b.m2));

  const maior=Math.max.apply(null,rs.map(r=>r.desc).concat([1]));
  cx.innerHTML=rs.map(function(r){
    const pct=Math.max(2,(r.desc/maior)*100);
    const exatoPct=Math.round(r.exatos/r.n*100);
    return '<button class="linha'+(est.regiao===r.nome?' sel':'')+
      '" data-reg="'+r.nome.replace(/"/g,'&quot;')+'">'+
      '<div class="nome">'+r.nome+'</div>'+
      '<div class="qtd">'+r.n+(r.n===1?' imóvel':' imóveis')+'</div>'+
      '<div class="medidas"><div class="bar"><i style="width:'+pct+'%;opacity:'+(r.n<5?'.45':'1')+'"></i></div>'+
      '<div class="val">'+r.desc.toFixed(0)+'%</div></div>'+
      '<div class="sub">'+(r.m2?'equilíbrio R$ '+brl(r.m2)+'/m²':'sem área informada')+
      ' · '+exatoPct+'% com posição exata'+
      (r.cidade!==r.nome?' · '+r.cidade:'')+
      (r.n<5?'<em class="frag">amostra pequena, a mediana oscila muito</em>':'')+
      '</div></button>';
  }).join('');

  cx.querySelectorAll('.linha').forEach(b=>b.onclick=()=>{
    est.regiao = est.regiao===b.dataset.reg ? null : b.dataset.reg;
    pintar(true);
  });
}

function fichaImovel(d){
  const c=conta(d);
  const cf = d.px==='numero'?'Posição exata do imóvel'
    : d.px==='logradouro'?'Rua certa, ponto aproximado'
    : d.px==='bairro'?'Aproximado: só o bairro foi localizado'
    : 'Aproximado: só a cidade foi localizada';
  const li=(k,v)=>'<div class="li"><span>'+k+'</span><b>'+v+'</b></div>';
  let corpo=li('Lance','R$ '+brl(d.pr));
  if(c.com)  corpo+=li('Comissão do leiloeiro','R$ '+brl(c.com));
  corpo+=li('ITBI','R$ '+brl(c.itbi))+li('Cartório','R$ '+brl(c.cart));
  if(c.div)  corpo+=li('Reserva para dívidas','R$ '+brl(c.div));
  if(c.deso) corpo+=li('Desocupação','R$ '+brl(c.deso));
  if(c.ref)  corpo+=li('Reforma','R$ '+brl(c.ref));
  corpo+='<div class="li tot"><span>Custo total</span><b>R$ '+brl(c.total)+
         ' (+'+c.extrasPct.toFixed(1)+'%)</b></div>';

  return '<div class="pp"><div class="cab"><div class="tt">'+d.ti+
    (d.qt?' · '+d.qt+(d.qt>1?' quartos':' quarto'):'')+(d.ar?' · '+d.ar+' m²':'')+
    '</div><div class="ed">'+d.en+'<br>'+d.ba+', '+d.ci+'</div></div>'+
    '<div class="conta">'+corpo+'</div>'+
    '<div class="eq"><div class="v">R$ '+brl(c.eq)+
      (c.eqM2?' <span style="font-size:12.5px;font-weight:500;color:#5A6A6E">· R$ '+
      brl(c.eqM2)+'/m²</span>':'')+'</div>'+
      '<div class="k">preço mínimo de revenda para não perder dinheiro<br>'+
      'anunciado '+c.bruto.toFixed(1)+'% → após custos <b>'+c.liq.toFixed(1)+'%</b></div></div>'+
    '<div class="rod"><div class="cf">'+cf+'<br>'+d.mo+
      (RISCO.has(d.mo)?'<br><span class="al">Confira IPTU e condomínio no edital</span>':'')+
      '</div><a href="'+d.lk+'" target="_blank" rel="noopener">Ver na Caixa</a></div></div>';
}

/* vários imóveis no mesmo endereço viram um pino só, com a lista dentro */
function fichaGrupo(g){
  const linhas=g.map(function(d,i){
    const c=conta(d);
    return '<button data-i="'+i+'"><b>R$ '+brl(d.pr)+'</b> · '+c.liq.toFixed(0)+
           '% após custos'+(d.ar?' · '+d.ar+' m²':'')+(d.qt?' · '+d.qt+'q':'')+'</button>';
  }).join('');
  return '<div class="pp"><div class="cab"><div class="tt">'+g.length+
    ' imóveis neste endereço</div><div class="ed">'+g[0].en+'<br>'+
    g[0].ba+', '+g[0].ci+'</div></div><div class="lista">'+linhas+'</div></div>';
}

function pintar(reenquadrar){
  const base=filtrados(false);   /* o ranking ignora a região escolhida */
  const v=filtrados(true);       /* o mapa respeita */
  desenharRanking(base);

  /* a cor de cada região acompanha os filtros, igual ao ranking */
  medianasRegiao = {};
  ranking(base).forEach(r => { medianasRegiao[r.nome] = r.desc; });
  if(contornoLayer) contornoLayer.setStyle(f => estiloRegiao(f.properties.d));

  camada.clearLayers();

  const grupos=new Map();
  v.forEach(function(d){
    const k=d.lat+','+d.lon;
    if(!grupos.has(k)) grupos.set(k,[]);
    grupos.get(k).push(d);
  });

  const pts=[];
  grupos.forEach(function(g){
    const vals=g.map(metrica), melhor=Math.max.apply(null,vals);
    const d0=g[0], exato=d0.px==='numero';
    const raio = g.length>1 ? Math.min(7+Math.sqrt(g.length)*2.2,17) : 6.5;
    const m=L.circleMarker([d0.lat,d0.lon],{
      radius:raio, fillColor:cor(melhor), fillOpacity:exato?.85:.35,
      color:'#16232A', weight:1.3, dashArray:exato?null:'3,3'});
    if(g.length===1){
      m.bindPopup(fichaImovel(d0));
      m.bindTooltip(d0.ba+' · R$ '+brl(d0.pr)+' · '+vals[0].toFixed(0)+'%',{direction:'top'});
    }else{
      m.bindPopup(fichaGrupo(g));
      m.bindTooltip(g.length+' imóveis · '+d0.ba+' · a partir de R$ '+
        brl(Math.min.apply(null,g.map(x=>x.pr))),{direction:'top'});
      m.on('popupopen',function(ev){
        ev.popup.getElement().querySelectorAll('.lista button').forEach(function(b){
          b.onclick=function(){ m.setPopupContent(fichaImovel(g[+b.dataset.i])); };
        });
      });
    }
    camada.addLayer(m); pts.push([d0.lat,d0.lon]);
  });

  el('explica').textContent = base.length
    ? 'Cada linha é um bairro da capital ou uma cidade do interior, com pelo menos '+
      MIN_REGIAO+' imóveis. A barra mostra o desconto mediano '+
      (est.metrica==='liq'?'depois dos custos':'anunciado')+
      '. Toque numa linha para ver só aquela região no mapa.'
    : 'Nenhum imóvel com os filtros atuais.';

  el('v-preco').textContent='R$ '+brl(est.preco);
  el('v-itbi').textContent=(P.itbi*100).toFixed(1)+'%';
  el('v-cart').textContent=(P.cart*100).toFixed(1)+'%';
  el('v-deso').textContent='R$ '+brl(P.deso);
  el('v-ref').textContent='R$ '+brl(P.ref);
  el('v-corr').textContent=(P.corr*100).toFixed(1)+'%';

  if(pts.length && (reenquadrar||est.regiao)) map.fitBounds(pts,{padding:[46,46],maxZoom:15});
}

L.control.layers(BASES, {'Limites das regiões': contornoLayer},
                 {position:'topright', collapsed:true}).addTo(map);

el('fonte').textContent = NO_MAPA+' de '+TOTAL_SP+' imóveis localizados'+
  (DATA?' · lista da Caixa de '+DATA.split('-').reverse().join('/'):'');
pintar(true);
</script>
</body></html>'''


if __name__ == "__main__":
    gerar()
