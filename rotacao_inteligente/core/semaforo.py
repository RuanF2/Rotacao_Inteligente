"""
core/semaforo.py - Etapa 6: semáforo de confiança (verde/amarelo/vermelho).

O QUE ESTE ARQUIVO FAZ (em linguagem simples):
    Soma pontos por evidências positivas (tamanho da amostra ENSO, lacunas
    preenchidas, dados locais) e desconta por parâmetros estimados. O
    resultado é um semáforo:
        verde  >= 5 pontos
        amarelo 3 a 4 pontos
        vermelho <= 2 pontos

REGRAS DO BRIEFING (seção 6.5 + ajustes 2026-11-14):
    Pontos somados (config.SEMAFORO_PONTOS):
    +2  anos na classe ENSO >= 10
    +1  anos na classe ENSO entre 5 e 9
    +0  anos na classe ENSO < 5
    +1  série total >= 10 anos
    +1  sem lacuna essencial (agua_mm_ciclo e ciclo_dias preenchidos)
    +1  dados do solo informados pelo usuário (Etapa 7)
    +1  validação NDVI/SMAP (Fase 2)
    -1  parâmetro estimado pela equipe (agua_mm_ciclo vazio, fallback 250)
    -1  local não calibrado (fora de config.LOCAIS_VALIDADOS)
    -1  sem janela válida (cultura semeadada fora de mês-janela, revisão)

    Os limiares "anos na classe" foram recalibrados para a série de 35
    anos (aprovado pelo usuário em 2026-11-14): >=10=2pts, 5-9=1pt, <5=0.
    Rotulo: parâmetro estimado pela equipe.

O QUE O SEMÁFORO MOSTRA:
    - Cor (verde/amarelo/vermelho).
    - Pontos totais.
    - Lista de evidências (o que somou pontos).
    - Lista de lacunas (o que descontou ou faltou).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import config


# ---------------------------------------------------------------------------
# 1. Exceções
# ---------------------------------------------------------------------------
class SemaforoError(Exception):
    """Erro no cálculo do semáforo de confiança."""


# ---------------------------------------------------------------------------
# 2. Estruturas de dados
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Semaforo:
    """Resultado do semáforo de confiança.

    - `pontos`: total somado (pode ser negativo).
    - `cor`: 'verde' / 'amarelo' / 'vermelho'.
    - `evidencias`: lista de strings do que somou pontos.
    - `lacunas`: lista de strings do que descontou ou faltou.
    - `detalhes`: dicionário com cada critério e seu valor (para debug/UI).
    """
    pontos: int
    cor: str
    evidencias: List[str] = field(default_factory=list)
    lacunas: List[str] = field(default_factory=list)
    detalhes: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 3. Função principal: calcular o semáforo
# ---------------------------------------------------------------------------
def cor_do_semaforo(pontos: int) -> str:
    """Devolve a cor do semáforo para um total de pontos.

    verde >= 5 | amarelo 3..4 | vermelho <= 2 (config).

    >>> cor_do_semaforo(7)
    'verde'
    >>> cor_do_semaforo(4)
    'amarelo'
    >>> cor_do_semaforo(2)
    'vermelho'
    >>> cor_do_semaforo(5)
    'verde'
    >>> cor_do_semaforo(3)
    'amarelo'
    """
    if pontos >= config.SEMAFORO_VERDE_MIN:
        return "verde"
    if pontos >= config.SEMAFORO_AMARELO_MIN:
        return "amarelo"
    return "vermelho"


def pontos_por_amostra_classe(n_anos_classe: int) -> int:
    """Pontos pela quantidade de anos na classe ENSO.

    Regra (aprovada 2026-11-14):
        >= 10 anos -> 2 pontos
        5 a 9 anos -> 1 ponto
        < 5 anos -> 0 pontos

    >>> pontos_por_amostra_classe(12)
    2
    >>> pontos_por_amostra_classe(9)
    1
    >>> pontos_por_amostra_classe(4)
    0
    >>> pontos_por_amostra_classe(10)
    2
    """
    if n_anos_classe >= 10:
        return config.SEMAFORO_PONTOS["anos_classe_maior_igual_10"]
    if n_anos_classe >= 5:
        return config.SEMAFORO_PONTOS["anos_classe_5_a_9"]
    return config.SEMAFORO_PONTOS["anos_classe_menor_5"]


def calcular_semaforo(n_anos_total: int,
                     n_anos_por_classe: Dict[str, int],
                     lacunas_essenciais: List[str],
                     usa_agua_estimada: bool = False,
                     local_calibrado: bool = True,
                     tem_janela_valida: bool = True,
                     tem_dados_solo: bool = False,
                     tem_validacao_ndvi: bool = False,
                     classe_avaliada: str = "El Niño",
                     ) -> Semaforo:
    """Calcula o semáforo de confiança.

    Args:
        n_anos_total: total de anos agrícolas completos na série.
        n_anos_por_classe: {"El Niño": N, "La Niña": N, "neutro": N}.
        lacunas_essenciais: lacunas que afetam o cálculo (ex.: tmax_limite_c,
            protecao_erosao, valor_mercado, fixa_nitrogenio, "sem janela
            válida"). Não confundir com "lacuna essencial" que desconta
            ponto — essa é só agua_mm_ciclo/ciclo_dias vazios.
        usa_agua_estimada: True se a cultura usou fallback 250 (-1 ponto).
        local_calibrado: True se o local está em config.LOCAIS_VALIDADOS
            (False -> -1 ponto, "sem calibração local").
        tem_janela_valida: True se o mês de semeadura é mês-janela
            (passa nos critérios Etapa 5). False se caiu no fallback
            "sem janela válida" (-1 ponto, revisão 2026-11-14).
        tem_dados_solo: True se o usuário informou dados do próprio solo
            (Etapa 7 — ainda não implementado, default False).
        tem_validacao_ndvi: True se há validação NDVI/SMAP (Fase 2, default False).
        classe_avaliada: qual classe ENSO está sendo avaliada (para o
            critério de amostra — só conta a classe em uso).

    Returns:
        Semaforo com pontos, cor, evidências e lacunas.
    """
    pontos = 0
    evidencias: List[str] = []
    lacunas: List[str] = []
    detalhes: Dict[str, int] = {}

    # 1) Tamanho da amostra ENSO (classe em uso)
    n_classe = n_anos_por_classe.get(classe_avaliada, 0)
    pts_amostra = pontos_por_amostra_classe(n_classe)
    pontos += pts_amostra
    detalhes["anos_classe"] = pts_amostra
    if pts_amostra >= 2:
        evidencias.append(
            f"amostra ENSO robusta: {n_classe} anos na classe "
            f"{classe_avaliada} (>=10) = +{pts_amostra} pts")
    elif pts_amostra == 1:
        evidencias.append(
            f"amostra ENSO moderada: {n_classe} anos na classe "
            f"{classe_avaliada} (5-9) = +{pts_amostra} pt")
    else:
        lacunas.append(
            f"amostra ENSO pequena: {n_classe} anos na classe "
            f"{classe_avaliada} (<5) = +0 pts")

    # 2) Série total >= 10 anos
    if n_anos_total >= 10:
        pontos += config.SEMAFORO_PONTOS["serie_total_maior_igual_10"]
        detalhes["serie_total"] = 1
        evidencias.append(
            f"série climática longa: {n_anos_total} anos agrícolas = +1 pt")
    else:
        detalhes["serie_total"] = 0
        lacunas.append(
            f"série curta: {n_anos_total} anos agrícolas (<10)")

    # 3) Sem lacuna essencial (agua_mm_ciclo e ciclo_dias preenchidos)
    #    Se há lacunas essenciais, não soma esse ponto.
    lacunas_essenciais_verdadeiras = [
        l for l in lacunas_essenciais
        if l in ("ciclo_dias", "agua_mm_ciclo")]
    if not lacunas_essenciais_verdadeiras:
        pontos += config.SEMAFORO_PONTOS["sem_lacuna_essencial"]
        detalhes["sem_lacuna_essencial"] = 1
        evidencias.append(
            "sem lacuna essencial: ciclo_dias e agua_mm_ciclo "
            "preenchidos = +1 pt")
    else:
        detalhes["sem_lacuna_essencial"] = 0
        lacunas.append(
            f"lacuna essencial: {lacunas_essenciais_verdadeiras} "
            "— não soma ponto")

    # 4) Dados do solo informados (Etapa 7 — ainda não implementado)
    if tem_dados_solo:
        pontos += config.SEMAFORO_PONTOS["dados_solo_locais"]
        detalhes["dados_solo_locais"] = 1
        evidencias.append("dados do solo informados pelo usuário = +1 pt")
    else:
        detalhes["dados_solo_locais"] = 0
        lacunas.append(
            "dados do solo não informados (Etapa 7) — não soma ponto")

    # 5) Validação NDVI/SMAP (Fase 2)
    if tem_validacao_ndvi:
        pontos += config.SEMAFORO_PONTOS["validacao_ndvi_smap"]
        detalhes["validacao_ndvi_smap"] = 1
        evidencias.append("validação NDVI/SMAP disponível = +1 pt")
    else:
        detalhes["validacao_ndvi_smap"] = 0
        lacunas.append(
            "sem validação NDVI/SMAP (Fase 2) — não soma ponto")

    # 6) Desconto: parâmetro estimado pela equipe (agua_mm_ciclo vazio)
    if usa_agua_estimada:
        pontos += config.SEMAFORO_PONTOS["desconto_parametro_estimado"]
        detalhes["desconto_parametro_estimado"] = -1
        lacunas.append(
            f"{config.AVISO_PARAMETRO_ESTIMADO}: agua_mm_ciclo vazio, "
            f"fallback {config.CHUVA_MINIMA_CICLO_MM} mm = -1 pt")

    # 7) Desconto: local não calibrado (fora de LOCAIS_VALIDADOS)
    if not local_calibrado:
        pontos -= 1
        detalhes["desconto_local_nao_calibrado"] = -1
        lacunas.append(
            f"{config.AVISO_SEM_CALIBRACAO_LOCAL} = -1 pt")

    # 8) Desconto: sem janela válida (cultura semeadada fora de mês-janela,
    #    revisão 2026-11-14). O mês de semeadura caiu no fallback (maior
    #    chuva do ciclo, mas não é janela pelos critérios Etapa 5).
    if not tem_janela_valida:
        pontos -= 1
        detalhes["desconto_sem_janela_valida"] = -1
        lacunas.append(
            "sem janela válida: cultura semeadada em mês que não é "
            "janela (maior chuva do ciclo, mas não passa nos critérios "
            "ciclo + estabelecimento) = -1 pt")

    # Outras lacunas (não essenciais: tmax, protecao, valor_mercado, etc.)
    outras_lacunas = [
        l for l in lacunas_essenciais
        if l not in ("ciclo_dias", "agua_mm_ciclo", "sem janela válida")]
    for lac in outras_lacunas:
        if lac not in lacunas:
            lacunas.append(f"lacuna: {lac} (renormalizada no índice)")

    cor = cor_do_semaforo(pontos)
    return Semaforo(
        pontos=pontos,
        cor=cor,
        evidencias=evidencias,
        lacunas=lacunas,
        detalhes=detalhes,
    )


# ---------------------------------------------------------------------------
# 4. Função utilitária: emoji da cor
# ---------------------------------------------------------------------------
def emoji_cor(cor: str) -> str:
    """Emoji do semáforo para a interface."""
    return {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}.get(cor, "⚪")


# ---------------------------------------------------------------------------
# 5. Verificação rápida (chamada direta no terminal)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Teste do semáforo com a série real de Teresina (35 anos):")
    print(f"  ENSO: El Niño=12, La Niña=14, neutro=9")
    print()

    for classe, n in [("El Niño", 12), ("La Niña", 14), ("neutro", 9)]:
        # Cenário 1: milho (dado real, sem estimativa)
        s1 = calcular_semaforo(
            n_anos_total=35,
            n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
            lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                                "valor_mercado"],
            usa_agua_estimada=False,
            local_calibrado=True,
            classe_avaliada=classe,
        )
        # Cenário 2: crotalária (agua estimada, local calibrado)
        s2 = calcular_semaforo(
            n_anos_total=35,
            n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
            lacunas_essenciais=["agua_mm_ciclo", "tmax_limite_c",
                                "protecao_erosao", "valor_mercado"],
            usa_agua_estimada=True,
            local_calibrado=True,
            classe_avaliada=classe,
        )
        # Cenário 3: milho em local não calibrado (ex.: Nairobi)
        s3 = calcular_semaforo(
            n_anos_total=35,
            n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
            lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                                "valor_mercado"],
            usa_agua_estimada=False,
            local_calibrado=False,
            classe_avaliada=classe,
        )
        # Cenário 4: cultura sem janela válida (semeada fora de mês-janela)
        s4 = calcular_semaforo(
            n_anos_total=35,
            n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
            lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                                "valor_mercado"],
            usa_agua_estimada=False,
            local_calibrado=True,
            tem_janela_valida=False,
            classe_avaliada=classe,
        )
        print(f"  Classe {classe} (n={n}):")
        print(f"    milho (Teresina):     {emoji_cor(s1.cor)} {s1.cor} "
              f"({s1.pontos} pts)")
        print(f"    crotalaria (Teresina):{emoji_cor(s2.cor)} {s2.cor} "
              f"({s2.pontos} pts) [agua estimada -1]")
        print(f"    milho (Nairóbi):      {emoji_cor(s3.cor)} {s3.cor} "
              f"({s3.pontos} pts) [local não calibrado -1]")
        print(f"    sem janela válida:    {emoji_cor(s4.cor)} {s4.cor} "
              f"({s4.pontos} pts) [sem janela -1]")
    print()
    print("Detalhe do milho@Teresina@ElNiño:")
    s = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                            "valor_mercado"],
        usa_agua_estimada=False,
        local_calibrado=True,
        classe_avaliada="El Niño",
    )
    print(f"  Pontos: {s.pontos} -> {emoji_cor(s.cor)} {s.cor}")
    print("  Evidências:")
    for e in s.evidencias:
        print(f"    + {e}")
    print("  Lacunas:")
    for l in s.lacunas:
        print(f"    - {l}")
