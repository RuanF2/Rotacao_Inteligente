"""
core/planejador.py - Etapa 4: calculadora kg de semente -> m² e colheita estimada.

O QUE ESTE ARQUIVO FAZ (em linguagem simples):
    Dada uma cultura (do banco culturas.csv) e uma quantidade de kg de
    semente, calcula:
      (1) a área em m² que dá para plantar com esses kg;
      (2) a colheita estimada em kg, conforme a regra de prioridade do
          briefing (seção 6.6).

REGRAS DO BRIEFING (seção 6.6):
    area_m2 = (kg_semente / taxa_semeadura_kg_ha) * 10000
    Se taxa_semeadura_kg_ha estiver vazia, NÃO calcula a área e avisa
    "taxa de semeadura não preenchida".

    Colheita estimada (linha separada, rotulada "estimativa"):
      - Se existe rendimento_regional_kg_ha -> usa ele
        (rótulo "estimativa com dado regional").
      - Senão, se existe rendimento_potencial_kg_ha -> usa ele
        (rótulo "potencial experimental, costuma ser maior que a
        colheita real").
      - Se ambos vazios -> NÃO mostra colheita.

    NUNCA usar valor padrão escondido. Célula vazia é lacuna.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import config
from core.culturas import Cultura


# ---------------------------------------------------------------------------
# 1. Exceções
# ---------------------------------------------------------------------------
class PlanejadorError(Exception):
    """Erro no planejador (ex.: kg de semente inválido)."""


# ---------------------------------------------------------------------------
# 2. Estruturas de dados
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ResultadoArea:
    """Resultado do cálculo de área.

    Se `area_m2` for None, significa que não foi possível calcular
    (taxa de semeadura ausente). `aviso` traz a mensagem de lacuna.
    """
    area_m2: Optional[float]
    area_ha: Optional[float]
    aviso: Optional[str]   # None quando calculou sem problema


@dataclass(frozen=True)
class ResultadoColheita:
    """Resultado do cálculo de colheita estimada.

    `rendimento_kg_ha_usado`: qual dos dois rendimentos foi usado
    (se for None, nenhum estava disponível e `colheita_kg` é None).
    `fonte_rendimento`: "regional" | "potencial" | None.
    `aviso`: rótulo do briefing (estimativa / potencial experimental /
             dado não preenchido).
    """
    colheita_kg: Optional[float]
    rendimento_kg_ha_usado: Optional[float]
    fonte_rendimento: Optional[str]   # "regional" | "potencial" | None
    aviso: Optional[str]


@dataclass(frozen=True)
class ResultadoPlanejamento:
    """Resultado completo: área + colheita + avisos."""
    cultura: str
    kg_semente: float
    area: ResultadoArea
    colheita: ResultadoColheita


# ---------------------------------------------------------------------------
# 3. Funções puras (testáveis)
# ---------------------------------------------------------------------------
def calcular_area(kg_semente: float, cultura: Cultura) -> ResultadoArea:
    """Calcula a área plantável (m²) com X kg de semente.

    Fórmula do briefing 6.6:
        area_m2 = (kg_semente / taxa_semeadura_kg_ha) * 10000

    Se a taxa de semeadura da cultura for None (lacuna), NÃO calcula:
    devolve area_m2=None e o aviso do config.

    Args:
        kg_semente: quantidade de semente disponível (kg). Deve ser >= 0.
        cultura: cultura escolhida (com .taxa_semeadura_kg_ha).

    Returns:
        ResultadoArea com (area_m2, area_ha, aviso).
    """
    if kg_semente < 0:
        raise PlanejadorError(
            f"kg de semente não pode ser negativo (recebido: {kg_semente})."
        )
    if not cultura.tem_taxa_semeadura:
        return ResultadoArea(
            area_m2=None, area_ha=None,
            aviso=config.AVISO_TAXA_SEMEADURA_FALTANTE,
        )
    taxa = cultura.taxa_semeadura_kg_ha
    if taxa <= 0:
        raise PlanejadorError(
            f"taxa_semeadura_kg_ha inválida para {cultura.nome}: {taxa}."
        )
    area_m2 = (kg_semente / taxa) * config.FATOR_HA_M2
    area_ha = area_m2 / config.FATOR_HA_M2
    return ResultadoArea(area_m2=area_m2, area_ha=area_ha, aviso=None)


def calcular_colheita(area_ha: Optional[float],
                      cultura: Cultura) -> ResultadoColheita:
    """Calcula a colheita estimada (kg) para uma área (ha).

    Regra de prioridade do briefing 6.6:
      1. se rendimento_regional_kg_ha existe -> usa ele
         (rótulo "estimativa com dado regional")
      2. senão, se rendimento_potencial_kg_ha existe -> usa ele
         (rótulo "potencial experimental, costuma ser maior que a
         colheita real")
      3. se ambos vazios -> não calcula (devolve None + aviso de lacuna).

    Args:
        area_ha: área em hectares (None se a área não foi calculada).
        cultura: cultura escolhida.

    Returns:
        ResultadoColheita com (colheita_kg, rendimento_usado, fonte, aviso).
    """
    # Se a área não pôde ser calculada, a colheita também não pode.
    if area_ha is None:
        return ResultadoColheita(
            colheita_kg=None, rendimento_kg_ha_usado=None,
            fonte_rendimento=None,
            aviso=config.AVISO_DADO_FALTANTE,
        )

    # 1) Preferência: rendimento regional (dado real do Piauí/IBGE).
    if cultura.tem_rendimento_regional:
        rend = cultura.rendimento_regional_kg_ha
        return ResultadoColheita(
            colheita_kg=area_ha * rend,
            rendimento_kg_ha_usado=rend,
            fonte_rendimento="regional",
            aviso="estimativa com dado regional",
        )

    # 2) Fallback: rendimento potencial experimental (com aviso).
    if cultura.tem_rendimento_potencial:
        rend = cultura.rendimento_potencial_kg_ha
        return ResultadoColheita(
            colheita_kg=area_ha * rend,
            rendimento_kg_ha_usado=rend,
            fonte_rendimento="potencial",
            aviso=config.AVISO_POTENCIAL_EXPERIMENTAL,
        )

    # 3) Ambos vazios: não mostra colheita.
    return ResultadoColheita(
        colheita_kg=None, rendimento_kg_ha_usado=None,
        fonte_rendimento=None,
        aviso=config.AVISO_DADO_FALTANTE,
    )


def planejar(kg_semente: float, cultura: Cultura) -> ResultadoPlanejamento:
    """Ponto de entrada: junta área + colheita em um resultado único.

    Args:
        kg_semente: kg de semente disponível (>= 0).
        cultura: cultura escolhida (do banco carregado por culturas.py).

    Returns:
        ResultadoPlanejamento com tudo preenchido ou avisos de lacuna.
    """
    area = calcular_area(kg_semente, cultura)
    colheita = calcular_colheita(area.area_ha, cultura)
    return ResultadoPlanejamento(
        cultura=cultura.nome,
        kg_semente=kg_semente,
        area=area,
        colheita=colheita,
    )


# ---------------------------------------------------------------------------
# 4. Verificação rápida (chamada direta no terminal)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from core.culturas import carregar_banco
    print(f"Lendo {config.CULTURAS_CSV}...")
    banco = carregar_banco()
    print("\nTeste com 10 kg de semente para cada cultura comercial:")
    for nome, c in banco.items():
        r = planejar(10.0, c)
        if r.area.area_m2 is not None:
            area_txt = f"{r.area.area_m2:.0f} m²"
        else:
            area_txt = r.area.aviso or "?"
        if r.colheita.colheita_kg is not None:
            colh_txt = f"{r.colheita.colheita_kg:.0f} kg [{r.colheita.fonte_rendimento}]"
        else:
            colh_txt = r.colheita.aviso or "?"
        print(f"  {nome:<22} área={area_txt:<28} colheita={colh_txt}")
