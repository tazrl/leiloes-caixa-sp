"""
Calcula quanto o imóvel REALMENTE custa até estar no seu nome,
e por quanto você precisa vendê-lo para não sair no prejuízo.

Por que isso importa: o "desconto" que a Caixa anuncia é sobre a avaliação DELA,
e não sobre o preço de mercado. Além disso, o desconto some rápido quando entram
comissão, ITBI e cartório. Aqui a conta é feita por inteiro.

O número mais útil que sai daqui é o PREÇO DE EQUILÍBRIO: o valor mínimo de
revenda que cobre tudo. Você compara com o que se pede na região e vê a margem.
"""

from dataclasses import dataclass, asdict

# --- comissão do leiloeiro -------------------------------------------------
# A Caixa cobra 5% do comprador SÓ em leilão e licitação aberta. Nas vendas
# feitas direto pelo site do banco, a corretagem é paga pela própria Caixa.
# Fonte: FAQ de Imóveis à venda da CAIXA.
COMISSAO_LEILOEIRO = {
    "Leilão SFI - Edital Único": 0.05,
    "Licitação Aberta": 0.05,
    "Venda Online": 0.0,
    "Venda Direta Online": 0.0,
}

# Modalidade em que dívidas antigas de IPTU e condomínio costumam passar para
# o comprador. Sempre confirmar no edital do imóvel — isto é só um sinal amarelo.
MODALIDADE_RISCO_DIVIDA = {"Leilão SFI - Edital Único"}


@dataclass
class Premissas:
    """Tudo o que dá para ajustar. Os padrões são conservadores."""
    itbi: float = 0.03              # 3% — varia por município, confira o seu
    cartorio: float = 0.01          # registro + escritura, 0,5% a 1%
    corretagem_venda: float = 0.06  # o que você paga ao vender depois
    reserva_desocupacao: float = 0.0   # R$ — se o imóvel estiver ocupado
    reserva_dividas: float = 0.0       # R$ — IPTU/condomínio atrasados
    reforma_por_m2: float = 0.0        # R$/m² de reforma prevista

    # Sinal amarelo automático: reserva sugerida quando a modalidade indica
    # que as dívidas antigas podem vir junto com o imóvel.
    reserva_dividas_sugerida: float = 15000.0


def calcular(preco, avaliacao, modalidade, area=None, p: Premissas = None) -> dict:
    """Devolve o custo completo e o ponto de equilíbrio de um imóvel."""
    p = p or Premissas()
    lance = float(preco)

    comissao = lance * COMISSAO_LEILOEIRO.get(modalidade, 0.05)
    itbi = lance * p.itbi
    cartorio = lance * p.cartorio
    reforma = (float(area) * p.reforma_por_m2) if area else 0.0

    risco_divida = modalidade in MODALIDADE_RISCO_DIVIDA
    dividas = p.reserva_dividas
    if risco_divida and dividas == 0:
        dividas = p.reserva_dividas_sugerida

    extras = comissao + itbi + cartorio + reforma + dividas + p.reserva_desocupacao
    custo_total = lance + extras

    # Para não perder dinheiro na revenda, o preço tem que cobrir o custo
    # E ainda a corretagem que você vai pagar ao vender.
    equilibrio = custo_total / (1 - p.corretagem_venda)

    return {
        "lance": round(lance),
        "comissao_leiloeiro": round(comissao),
        "itbi": round(itbi),
        "cartorio": round(cartorio),
        "reforma": round(reforma),
        "reserva_dividas": round(dividas),
        "reserva_desocupacao": round(p.reserva_desocupacao),
        "custos_extras": round(extras),
        "custo_total": round(custo_total),
        "custos_sobre_lance_pct": round(extras / lance * 100, 1) if lance else None,

        # comparações com a avaliação da Caixa (NÃO é preço de mercado)
        "desconto_bruto_pct": round((avaliacao - lance) / avaliacao * 100, 1),
        "desconto_liquido_pct": round((avaliacao - custo_total) / avaliacao * 100, 1),

        # o número que serve para decidir
        "preco_equilibrio": round(equilibrio),
        "equilibrio_m2": round(equilibrio / float(area)) if area else None,
        "margem_ate_avaliacao_pct": round((avaliacao - equilibrio) / equilibrio * 100, 1),

        "risco_divida_edital": risco_divida,
    }


def resumo_texto(c: dict) -> str:
    def r(v):
        return "R$ " + f"{v:,.0f}".replace(",", ".")
    linhas = [
        f"Lance                 {r(c['lance'])}",
        f"Comissão leiloeiro    {r(c['comissao_leiloeiro'])}",
        f"ITBI                  {r(c['itbi'])}",
        f"Cartório              {r(c['cartorio'])}",
    ]
    if c["reserva_dividas"]:
        linhas.append(f"Reserva dívidas       {r(c['reserva_dividas'])}")
    if c["reforma"]:
        linhas.append(f"Reforma               {r(c['reforma'])}")
    linhas += [
        "-" * 38,
        f"CUSTO TOTAL           {r(c['custo_total'])}  (+{c['custos_sobre_lance_pct']}% sobre o lance)",
        f"Preço de equilíbrio   {r(c['preco_equilibrio'])}"
        + (f"  ({r(c['equilibrio_m2'])}/m²)" if c["equilibrio_m2"] else ""),
        f"Desconto anunciado    {c['desconto_bruto_pct']}%",
        f"Desconto após custos  {c['desconto_liquido_pct']}%",
    ]
    return "\n".join(linhas)


if __name__ == "__main__":
    print("=== Leilão SFI (tem comissão + risco de dívida) ===")
    print(resumo_texto(calcular(226734, 370000, "Leilão SFI - Edital Único", 62)))
    print("\n=== Venda Direta Online (sem comissão) ===")
    print(resumo_texto(calcular(226734, 370000, "Venda Direta Online", 62)))
