"""
core/resiliencia.py - Etapa 6: índice de resiliência de rotações por cenário.

O QUE ESTE ARQUIVO FAZ (em linguagem simples):
    Para cada uma das 3 estratégias de rotação (atual, solo, agua) e cada
    cenário ENSO (El Niño, La Niña, neutro), calcula um índice de
    resiliência (0..100) que combina o score de água das culturas com
    critérios agronômicos (fixação de N, proteção contra erosão, valor de
    mercado), ponderados pela prioridade do agricultor.

REGRAS DO BRIEFING:
    Seção 6.3 — Score de uma cultura num cenário:
        score_agua = min(100, chuva_ciclo_mm / agua_efetiva_mm × 100)
        score_cultura = score_agua - penalidade_calor   (limitado 0..100)

    Seção 6.4 — Índice de resiliência da rotação:
        Média ponderada dos scores das culturas da sequência. Pesos por
        prioridade do agricultor (agua/solo/renda) em config.PESOS_PRIORIDADE.
        Se um critério (fixa_nitrogenio, protecao_erosao, valor_mercado)
        estiver vazio, ele SAI da média e os pesos renormalizam (entra
        como lacuna no semáforo).

    Seção 6.7 (ano agrícola):
        Uma semeadura em janeiro-outubro do ano civil Y pertence ao ano
        agrícola Y-1 (nov Y-1 a out Y); só novembro e dezembro de Y
        pertencem ao ano agrícola Y. O ano agrícola N usa o DJF de N+1
        (dez/N a fev/N+1). Implementado em enso.ano_agricola_da_semeadura
        e USADO DE FATO em chuva_ciclo_por_classe (revisão 2026-11-14):
        cada semeadura é ligada ao ano agrícola pela sua DATA REAL (mês
        de semeadura da cultura), não por uma data fixa de novembro.

MÊS DE SEMEADURA POR CULTURA (revisão 2026-11-14):
    Antes, todas as culturas eram "semeadas" em 1/nov — isso avaliava o
    caupi fora da sua janela (jan-abr) e fazia o "pior cenário = neutro"
    ser artefato da data fixa. Agora cada cultura é avaliada no seu mês
    de semeadura:
        - padrão: o mês-janela (pelos critérios da Etapa 5: ciclo +
          estabelecimento) com a MAIOR chuva mediana do ciclo.
        - se não houver mês-janela: usa o mês de maior chuva do ciclo e
          marca "sem janela válida" (desconta 1 ponto no semáforo).
        - o usuário pode trocar o mês de semeadura de cada cultura no
          app (seletor com o padrão pré-selecionado).

LACUNAS (briefing 5.1 + ajustes 2026-11-14):
    - tmax_limite_c vazio: penalidade_calor = 0 e registra a lacuna.
    - fixa_nitrogenio / protecao_erosao / valor_mercado vazios: o
      critério sai da média, pesos renormalizam, registra lacuna.
    - agua estimada pela equipe (agua_mm_ciclo vazio, fallback 250):
      score_agua calculado normalmente, mas a cultura é marcada e o
      semáforo desconta 1 ponto.

PONDERAÇÃO:
    Para cada cultura da rotação, calculamos:
        score_agua (0..100)
      + contribuição de fixa_nitrogenio (0 se "nao"/vazio, 100 se "sim")
      + contribuição de protecao_erosao (0..100, escala 1..3 do CSV)
      + contribuição de valor_mercado (0..100, escala 1..3 do CSV)
    O índice da rotação é a MÉDIA PONDERADA desses (pelos pesos da
    prioridade). Critérios vazios saem e os pesos renormalizam.

    Os pesos são PARÂMETROS AJUSTÁVEIS (config.PESOS_PRIORIDADE), não
    vieram do briefing — são suposição da equipe (calibrar com agrônomo).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import config
from core.culturas import Cultura


# ---------------------------------------------------------------------------
# 1. Exceções
# ---------------------------------------------------------------------------
class ResilienciaError(Exception):
    """Erro no cálculo do índice de resiliência."""


# ---------------------------------------------------------------------------
# 2. Estruturas de dados
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScoreCultura:
    """Score de uma cultura num cenário específico.

    - `cultura`: nome da cultura.
    - `classe`: cenário ENSO ('El Niño'/'La Niña'/'neutro').
    - `mes_semeadura`: mês (1..12) usado como data de semeadura. Cada
      cultura é avaliada no seu próprio mês (revisão 2026-11-14), não
      em 1/nov fixo. None se não foi possível determinar.
    - `tem_janela_valida`: True se `mes_semeadura` é um mês-janela (passa
      nos critérios ciclo + estabelecimento da Etapa 5). False se caiu
      no fallback "sem janela válida" (maior chuva do ciclo, mas não é
      janela — desconta 1 ponto no semáforo).
    - `chuva_ciclo_mm`: mediana da chuva do ciclo nos anos da classe,
      calculada a partir de `mes_semeadura`.
    - `agua_efetiva_mm`: demanda hídrica usada (do CSV ou fallback 250).
    - `agua_estimada`: True se usou fallback da equipe.
    - `score_agua`: min(100, chuva/agua × 100).
    - `penalidade_calor`: pontos descontados por calor (0 se tmax vazio).
    - `score_cultura`: score_agua - penalidade_calor, limitado 0..100.
    - `fixa_nitrogenio`: 100 se "sim", 0 se "nao"/vazio.
    - `protecao_erosao`: 0..100 (escala 1..3 do CSV). None se vazio.
    - `valor_mercado`: 0..100 (escala 1..3 do CSV). None se vazio.
    - `lacunas`: lista de campos que afetaram o cálculo.
    - `anos_usados`: nº de anos da classe usados na mediana da chuva.
    - `risco_hidrico_pct`: % dos anos da classe com chuva do ciclo ABAIXO
      de agua_efetiva_mm (revisão 2026-11-14). 0 = nenhum ano teve
      déficit, 100 = todos os anos tiveram déficit. None se nenhum ano.
      Diferencia cenários quando o índice satura em 100 (todos iguais).
    """
    cultura: str
    classe: str
    mes_semeadura: Optional[int]
    tem_janela_valida: bool
    chuva_ciclo_mm: Optional[float]
    agua_efetiva_mm: Optional[float]
    agua_estimada: bool
    score_agua: Optional[float]
    penalidade_calor: float
    score_cultura: Optional[float]
    fixa_nitrogenio: Optional[float]
    protecao_erosao: Optional[float]
    valor_mercado: Optional[float]
    lacunas: List[str] = field(default_factory=list)
    anos_usados: int = 0
    risco_hidrico_pct: Optional[float] = None


@dataclass(frozen=True)
class ScoreRotacaoCenario:
    """Índice de resiliência de uma rotação num cenário ENSO.

    - `rotacao`: nome da rotação ('atual'/'solo'/'agua').
    - `classe`: cenário ENSO.
    - `scores`: lista de ScoreCultura (um por cultura da sequência).
    - `indice`: média ponderada dos scores (0..100). None se nenhuma
      cultura pôde ser pontuada.
    - `prioridade`: 'agua'/'solo'/'renda' (define os pesos).
    - `lacunas`: consolidação das lacunas de todas as culturas.
    - `pesos_usados`: os pesos efetivamente usados (após renormalização).
    - `risco_hidrico_pct`: média do risco hídrico das culturas pontuadas
      (% de anos com chuva do ciclo < agua_efetiva). None se nenhuma
      cultura tem risco. Usado para desempatar o pior cenário quando o
      índice satura em 100 (revisão 2026-11-14).
    """
    rotacao: str
    classe: str
    scores: List[ScoreCultura] = field(default_factory=list)
    indice: Optional[float] = None
    prioridade: str = "agua"
    lacunas: List[str] = field(default_factory=list)
    pesos_usados: Dict[str, float] = field(default_factory=dict)
    risco_hidrico_pct: Optional[float] = None


# ---------------------------------------------------------------------------
# 3. Funções auxiliares (puras, testáveis)
# ---------------------------------------------------------------------------
def calcular_score_agua(chuva_ciclo_mm: float,
                        agua_efetiva_mm: float) -> float:
    """score_agua = min(100, chuva/agua × 100), limitado em 0.

    >>> calcular_score_agua(300, 300)
    100.0
    >>> calcular_score_agua(150, 300)
    50.0
    >>> calcular_score_agua(0, 300)
    0.0
    >>> calcular_score_agua(600, 300)   # cap em 100
    100.0
    """
    if agua_efetiva_mm <= 0:
        raise ResilienciaError("agua_efetiva_mm deve ser > 0")
    score = (float(chuva_ciclo_mm) / float(agua_efetiva_mm)) * 100.0
    return float(max(config.SCORE_MIN, min(config.SCORE_MAX, score)))


def calcular_penalidade_calor(tmax_ciclo: Optional[float],
                             tmax_limite_c: Optional[float]) -> Tuple[float, bool]:
    """Penalidade de calor (pontos descontados do score_agua).

    Regra (briefing 6.3): se a temperatura MÁXIMA média do ciclo excede
    `tmax_limite_c`, desconta pontos. Aqui usamos uma escala simples:
    cada °C acima do limite desconta 5 pontos (parâmetro ajustável).

    - Se `tmax_limite_c` for vazio (lacuna): penalidade = 0 e
      registra_lacuna=True (briefing: "tmax_limite_c vazio -> penalidade
      de calor = 0 e registrar a lacuna").
    - Se `tmax_ciclo` for None (sem dado de temperatura): penalidade = 0
      e registra_lacuna=True.

    Returns: (penalidade, registra_lacuna)
    """
    if tmax_limite_c is None or tmax_ciclo is None:
        return 0.0, True
    excesso = float(tmax_ciclo) - float(tmax_limite_c)
    if excesso <= 0:
        return 0.0, False
    # 5 pontos por °C acima do limite (parâmetro ajustável, suposição).
    return float(excesso * 5.0), False


def _escalar_1_3_para_0_100(valor: Optional[int]) -> Optional[float]:
    """Converte escala 1..3 do CSV para 0..100.

    1 -> 0, 2 -> 50, 3 -> 100. None -> None (lacuna).
    """
    if valor is None:
        return None
    v = int(valor)
    if not 1 <= v <= 3:
        return None
    return float((v - 1) * 50.0)


def _fixa_n_para_score(fixa_n: Optional[str]) -> Optional[float]:
    """Converte 'sim'/'nao'/None em 100/0/None.

    'sim' -> 100 (fixa N), 'nao' -> 0 (não fixa), None -> None (lacuna).
    """
    if fixa_n is None:
        return None
    if fixa_n == "sim":
        return 100.0
    if fixa_n == "nao":
        return 0.0
    return None  # valor inesperado -> lacuna


# ---------------------------------------------------------------------------
# 4. Mês de semeadura da cultura + mediana da chuva por classe ENSO
# ---------------------------------------------------------------------------
def melhor_mes_semeadura(df_clima: pd.DataFrame,
                         cultura: Cultura,
                         anos_agricolas_completos: Optional[List[int]] = None,
                         meses_livres: Optional[List[int]] = None,
                         ) -> Tuple[Optional[int], bool, Optional[float]]:
    """Escolhe o mês de semeadura da cultura (revisão 2026-11-14).

    Cada cultura deve ser avaliada no seu próprio mês de semeadura, não
    em 1/nov fixo. Esta função:

    1. Calcula as janelas da Etapa 5 (ciclo + estabelecimento) para a
       cultura.
    2. Entre os meses-janela, escolhe o de MAIOR chuva mediana do ciclo.
    3. Se NÃO houver mês-janela, usa o mês de maior chuva do ciclo e
       marca `tem_janela_valida=False` (sem janela válida — desconta 1
       ponto no semáforo).

    Args:
        df_clima: DataFrame da NASA POWER com PRECTOTCORR.
        cultura: cultura a avaliar.
        anos_agricolas_completos: anos a usar (None = todos).
        meses_livres: meses em que o campo está livre (None = todos).

    Returns:
        (mes, tem_janela_valida, chuva_mediana_ciclo_mm)
            mes: 1..12 ou None se não foi possível (sem ciclo_dias, etc.).
            tem_janela_valida: True se mes é janela; False se fallback.
            chuva_mediana_ciclo_mm: mediana da chuva do ciclo no mes
                escolhido (entre os anos agrícolas completos). None se
                sem dado.
    """
    from core.janelas import calcular_janelas, nome_mes

    # Sem ciclo_dias, não há como escolher mês.
    if cultura.ciclo_dias is None:
        return None, False, None
    if df_clima is None or df_clima.empty or "PRECTOTCORR" not in df_clima.columns:
        return None, False, None

    # Calcula as janelas (Etapa 5: ciclo + estabelecimento).
    r = calcular_janelas(df_clima, cultura,
                         anos_agricolas_completos=anos_agricolas_completos,
                         meses_livres=meses_livres)
    if not r.janelas:
        return None, False, None

    # Candidatos: meses com chuva_ciclo_mm calculada.
    candidatos = [jm for jm in r.janelas if jm.chuva_ciclo_mm is not None]
    if not candidatos:
        return None, False, None

    # 1) Meses-janela (passam nos 2 critérios): escolhe o de maior chuva.
    janelas_validas = [jm for jm in candidatos if jm.e_janela]
    if janelas_validas:
        melhor = max(janelas_validas, key=lambda jm: jm.chuva_ciclo_mm)
        return melhor.mes, True, melhor.chuva_ciclo_mm

    # 2) Fallback: nenhum mês-janela. Usa o de maior chuva do ciclo,
    #    marca "sem janela válida".
    melhor = max(candidatos, key=lambda jm: jm.chuva_ciclo_mm)
    return melhor.mes, False, melhor.chuva_ciclo_mm


def chuva_ciclo_por_classe(df_clima: pd.DataFrame,
                          cultura: Cultura,
                          classificacoes,
                          ano_agr_inicio: int,
                          ano_agr_fim: int,
                          mes_semeadura: Optional[int] = None,
                          anos_agricolas_completos: Optional[List[int]] = None,
                          meses_livres: Optional[List[int]] = None,
                          ) -> Dict[str, Tuple[Optional[float], int]]:
    """Para cada classe ENSO, mediana da chuva do ciclo da cultura,
    calculada a partir do MÊS DE SEMEADURA da cultura (revisão 2026-11-14).

    Cada semeadura em M/ano_civil é ligada ao ano agrícola correto por
    `enso.ano_agricola_da_semeadura`:
        - M em jan..out  -> ano agrícola = ano_civil - 1
        - M em nov..dez  -> ano agrícola = ano_civil

    A chuva do ciclo (ciclo_dias a partir de 1/M) é somada em cada ano
    civil em que a semeadura cai, e classificada pelo ano agrícola
    correspondente. Depois tira-se a mediana por classe ENSO.

    Args:
        df_clima: DataFrame da NASA POWER com PRECTOTCORR.
        cultura: cultura a avaliar.
        classificacoes: lista de ClassificacaoAno (de enso.carregar_classificacao).
        ano_agr_inicio, ano_agr_fim: intervalo de anos agrícolas a considerar.
        mes_semeadura: mês (1..12) da semeadura. Se None, escolhe
            automaticamente via melhor_mes_semeadura.
        anos_agricolas_completos: anos agrícolas com série climática
            completa (para melhor_mes_semeadura).
        meses_livres: meses em que o campo está livre (para
            melhor_mes_semeadura).

    Returns:
        {classe: (mediana_chuva_mm, n_anos)} para El Niño/La Niña/neutro.
        Mediana None se nenhum ano da classe. Os anos contados são os
        ANOS AGRÍCOLAS (não civis) que caíram na classe e tiveram chuva
        calculável a partir do mês de semeadura.
    """
    por_classe = _chuvas_por_classe(df_clima, cultura, classificacoes,
                                     ano_agr_inicio, ano_agr_fim,
                                     mes_semeadura, anos_agricolas_completos,
                                     meses_livres)
    resultado: Dict[str, Tuple[Optional[float], int]] = {}
    for classe, vals in por_classe.items():
        if vals:
            resultado[classe] = (float(np.median(vals)), len(vals))
        else:
            resultado[classe] = (None, 0)
    return resultado


# ---------------------------------------------------------------------------
# 4.b. Rotação como alternância safra 1 / safra 2 (revisão 2026-11-14)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SafraInfo:
    """Informação de uma safra (semeadura) dentro da rotação.

    - `cultura`: nome da cultura.
    - `mes_semeadura`: mês (1..12) da semeadura, escolhido pelo usuário
      ou pelo padrão melhor_mes_semeadura.
    - `tem_janela_valida`: True se `mes_semeadura` é mês-janela.
    - `mes_colheita`: mês (1..12) da colheita = semeadura + ciclo_dias.
      None se ciclo_dias for None.
    - `posicao`: 'safra 1' ou 'safra 2' (alternância entre safras).
    """
    cultura: str
    mes_semeadura: Optional[int]
    tem_janela_valida: bool
    mes_colheita: Optional[int]
    posicao: str


@dataclass(frozen=True)
class JanelaPosColheita:
    """Janela de uma cultura de COBERTURA logo após a colheita da safra 1.

    - `cultura_cobertura`: nome da cultura de cobertura.
    - `mes_colheita_safra1`: mês de colheita da safra 1.
    - `tem_janela_pos_colheita`: True se há mês-janela para a cultura de
      cobertura no mês da colheita da safra 1 ou nos 2 meses seguintes.
    - `meses_disponiveis`: lista de meses (nomes) que seriam janela para a
      cobertura dentro da janela pós-colheita.
    - `aviso`: None, ou "sem janela" se não houver janela válida para a
      cobertura logo após a colheita da safra 1.
    """
    cultura_cobertura: str
    mes_colheita_safra1: Optional[int]
    tem_janela_pos_colheita: bool
    meses_disponiveis: List[str] = field(default_factory=list)
    aviso: Optional[str] = None


def mes_da_colheita(mes_semeadura: int, ciclo_dias: int) -> int:
    """Mês da colheita = mês de semeadura + ciclo_dias (módulo 12).

    >>> mes_da_colheita(1, 120)   # jan + 120 dias (~4 meses) -> maio
    5
    >>> mes_da_colheita(2, 75)    # fev + 75 dias (~2.5 meses) -> abr/mai
    4
    """
    if ciclo_dias <= 0:
        return mes_semeadura
    # Aproximação: ~30,44 dias por mês. ceil para não subestimar.
    meses_add = -(-ciclo_dias // 30)   # divisão teto (ceil) inteira
    return ((mes_semeadura - 1 + meses_add) % 12) + 1


def janela_pos_colheita(resultado_janelas_cobertura,    # ResultadoJanelas
                        mes_colheita_safra1: Optional[int],
                        janela_meses: int = 2,
                        ) -> JanelaPosColheita:
    """Verifica se há janela para a cultura de cobertura logo após a
    colheita da safra 1 (revisão 2026-11-14).

    Para rotações com cultura de cobertura (ex.: solo = milho +
    crotalária), a cobertura deve ser semeada DEPOIS da colheita da
    safra 1. Esta função confere se o mês da colheita da safra 1 (ou os
    `janela_meses` meses seguintes) é janela válida para a cobertura.

    Args:
        resultado_janelas_cobertura: ResultadoJanelas da cultura de
            cobertura (Etapa 5).
        mes_colheita_safra1: mês (1..12) da colheita da safra 1.
        janela_meses: quantos meses após a colheita considerar (default 2).

    Returns:
        JanelaPosColheita com tem_janela_pos_colheita, meses_disponiveis
        e aviso (None se há janela, "sem janela pós-colheita" se não).
    """
    from core.janelas import nome_mes
    nome_cob = resultado_janelas_cobertura.cultura
    if mes_colheita_safra1 is None:
        return JanelaPosColheita(
            cultura_cobertura=nome_cob,
            mes_colheita_safra1=None,
            tem_janela_pos_colheita=False,
            aviso="sem data de colheita da safra 1 (ciclo_dias vazio?)")
    # Meses a conferir: colheita + janela_meses seguintes.
    meses_a_ver = []
    for k in range(janela_meses + 1):
        m = ((mes_colheita_safra1 - 1 + k) % 12) + 1
        meses_a_ver.append(m)
    janelas_ok = [jm for jm in resultado_janelas_cobertura.janelas
                  if jm.mes in meses_a_ver and jm.e_janela]
    meses_disp = [nome_mes(jm.mes) for jm in janelas_ok]
    tem = bool(janelas_ok)
    aviso = (None if tem
             else f"sem janela pós-colheita: a cobertura não tem "
                  f"janela em {nome_mes(mes_colheita_safra1)} "
                  f"nem nos {janela_meses} meses seguintes")
    return JanelaPosColheita(
        cultura_cobertura=nome_cob,
        mes_colheita_safra1=mes_colheita_safra1,
        tem_janela_pos_colheita=tem,
        meses_disponiveis=meses_disp,
        aviso=aviso,
    )


def _chuvas_por_classe(df_clima: pd.DataFrame,
                       cultura: Cultura,
                       classificacoes,
                       ano_agr_inicio: int,
                       ano_agr_fim: int,
                       mes_semeadura: Optional[int],
                       anos_agricolas_completos: Optional[List[int]],
                       meses_livres: Optional[List[int]],
                       ) -> Dict[str, List[float]]:
    """Interno: devolve as LISTAS de chuva do ciclo por classe ENSO.

    Reutilizada por chuva_ciclo_por_classe (mediana) e
    risco_hidrico_por_classe (% abaixo do limiar), para não iterar nos
    anos duas vezes.
    """
    from core.enso import ano_agricola_da_semeadura
    from core.janelas import chuva_do_ciclo

    vazio: Dict[str, List[float]] = {
        "El Niño": [], "La Niña": [], "neutro": []}
    if cultura.ciclo_dias is None:
        return vazio
    if "PRECTOTCORR" not in df_clima.columns:
        return vazio

    if mes_semeadura is None:
        mes_semeadura, _, _ = melhor_mes_semeadura(
            df_clima, cultura,
            anos_agricolas_completos=anos_agricolas_completos,
            meses_livres=meses_livres)
    if mes_semeadura is None:
        return vazio

    chuva = df_clima["PRECTOTCORR"].dropna()
    classes_map = {c.ano: c.classe for c in classificacoes}
    por_classe: Dict[str, List[float]] = {
        "El Niño": [], "La Niña": [], "neutro": []}

    for y_civil in range(ano_agr_inicio, ano_agr_fim + 2):
        data_inicio = pd.Timestamp(y_civil, mes_semeadura, 1)
        aa = ano_agricola_da_semeadura(data_inicio)
        if aa not in classes_map:
            continue
        classe = classes_map[aa]
        if classe not in por_classe:
            continue
        if not (ano_agr_inicio <= aa <= ano_agr_fim):
            continue
        soma = chuva_do_ciclo(chuva, data_inicio, cultura.ciclo_dias)
        if soma is not None and not np.isnan(soma):
            por_classe[classe].append(soma)
    return por_classe


def risco_hidrico_por_classe(df_clima: pd.DataFrame,
                             cultura: Cultura,
                             classificacoes,
                             ano_agr_inicio: int,
                             ano_agr_fim: int,
                             mes_semeadura: Optional[int] = None,
                             agua_mm_ciclo: Optional[float] = None,
                             anos_agricolas_completos: Optional[List[int]] = None,
                             meses_livres: Optional[List[int]] = None,
                             ) -> Dict[str, Optional[float]]:
    """Para cada classe ENSO, % dos anos com chuva do ciclo ABAIXO do
    limiar hídrico (revisão 2026-11-14).

    O "risco hídrico" responde: em quantos anos da classe a chuva do
    ciclo não atingiu a demanda da cultura? Diferentemente do índice
    (que satura em 100 quando chuva >= agua), o risco distingue cenários
    mesmo quando o índice está no teto. Ex.: índice 100 em todos os
    cenários, mas risco 8% em La Niña vs 25% em El Niño -> El Niño é o
    pior (mais anos com déficit).

    Args:
        df_clima, cultura, classificacoes, ano_agr_inicio, ano_agr_fim,
        mes_semeadura, anos_agricolas_completos, meses_livres: mesmos
            de chuva_ciclo_por_classe.
        agua_mm_ciclo: limiar hídrico (mm). Se None, usa
            cultura.agua_efetiva_mm_ciclo (do CSV ou fallback 250).

    Returns:
        {classe: risco_pct (0..100)} para El Niño/La Niña/neutro.
        None se nenhum ano da classe teve chuva calculável.
    """
    por_classe = _chuvas_por_classe(df_clima, cultura, classificacoes,
                                     ano_agr_inicio, ano_agr_fim,
                                     mes_semeadura, anos_agricolas_completos,
                                     meses_livres)
    limiar = (agua_mm_ciclo if agua_mm_ciclo is not None
              else cultura.agua_efetiva_mm_ciclo)
    resultado: Dict[str, Optional[float]] = {}
    for classe, vals in por_classe.items():
        if not vals or limiar is None:
            resultado[classe] = None
            continue
        abaixo = sum(1 for v in vals if v < limiar)
        resultado[classe] = 100.0 * abaixo / len(vals)
    return resultado


# ---------------------------------------------------------------------------
# 5. Score de uma cultura num cenário
# ---------------------------------------------------------------------------
def pontuar_cultura_cenario(df_clima: pd.DataFrame,
                            cultura: Cultura,
                            classe: str,
                            chuva_ciclo_mm: Optional[float],
                            anos_usados: int,
                            mes_semeadura: Optional[int] = None,
                            tem_janela_valida: bool = True,
                            risco_hidrico_pct: Optional[float] = None,
                            tmax_ciclo: Optional[float] = None,
                            ) -> ScoreCultura:
    """Calcula o ScoreCultura de uma cultura num cenário ENSO.

    Args:
        df_clima: DataFrame (não usado diretamente aqui, mas mantido
            para consistência de assinatura).
        cultura: a cultura a pontuar.
        classe: 'El Niño'/'La Niña'/'neutro'.
        chuva_ciclo_mm: mediana da chuva do ciclo nos anos da classe,
            calculada a partir de `mes_semeadura`. None se nenhum ano.
        anos_usados: nº de anos da classe usados na mediana.
        mes_semeadura: mês (1..12) da semeadura (revisão 2026-11-14).
            None se não foi possível determinar.
        tem_janela_valida: True se `mes_semeadura` é mês-janela; False se
            fallback "sem janela válida" (desconta 1 no semáforo).
        risco_hidrico_pct: % dos anos da classe com chuva do ciclo
            abaixo de agua_efetiva_mm (revisão 2026-11-14). None se
            nenhum ano. Usado para desempatar o pior cenário quando o
            índice satura em 100.
        tmax_ciclo: temperatura máxima média do ciclo (None se sem dado).

    Returns:
        ScoreCultura com mes_semeadura, tem_janela_valida, score_agua,
        penalidade_calor, score_cultura, critérios agronômicos,
        risco_hidrico_pct e lacunas.
    """
    lacunas: List[str] = []

    # Sem janela válida -> registra lacuna (desconta no semáforo).
    if not tem_janela_valida:
        lacunas.append("sem janela válida (mês de maior chuva, não janela)")

    # Score de água
    if chuva_ciclo_mm is None or cultura.agua_efetiva_mm_ciclo is None:
        score_agua = None
        if chuva_ciclo_mm is None:
            lacunas.append("sem anos da classe ENSO")
    else:
        score_agua = calcular_score_agua(chuva_ciclo_mm,
                                          cultura.agua_efetiva_mm_ciclo)

    # Penalidade de calor
    if cultura.tmax_limite_c is None:
        lacunas.append("tmax_limite_c")
    penalidade, lacuna_tmax = calcular_penalidade_calor(
        tmax_ciclo, cultura.tmax_limite_c)
    if lacuna_tmax and "tmax_limite_c" not in lacunas:
        lacunas.append("tmax_ciclo (sem dado ou sem limite)")

    # Score da cultura = score_agua - penalidade, limitado 0..100
    if score_agua is None:
        score_cultura = None
    else:
        sc = score_agua - penalidade
        score_cultura = float(max(config.SCORE_MIN, min(config.SCORE_MAX, sc)))

    # Critérios agronômicos
    fixa_n = _fixa_n_para_score(cultura.fixa_nitrogenio)
    if fixa_n is None and cultura.fixa_nitrogenio is not None:
        lacunas.append("fixa_nitrogenio (valor inesperado)")
    elif cultura.fixa_nitrogenio is None:
        lacunas.append("fixa_nitrogenio")

    protecao = _escalar_1_3_para_0_100(cultura.protecao_erosao)
    if protecao is None and cultura.protecao_erosao is not None:
        lacunas.append("protecao_erosao (fora de 1..3)")
    elif cultura.protecao_erosao is None:
        lacunas.append("protecao_erosao")

    mercado = _escalar_1_3_para_0_100(cultura.valor_mercado)
    if mercado is None and cultura.valor_mercado is not None:
        lacunas.append("valor_mercado (fora de 1..3)")
    elif cultura.valor_mercado is None:
        lacunas.append("valor_mercado")

    return ScoreCultura(
        cultura=cultura.nome,
        classe=classe,
        mes_semeadura=mes_semeadura,
        tem_janela_valida=tem_janela_valida,
        chuva_ciclo_mm=chuva_ciclo_mm,
        agua_efetiva_mm=cultura.agua_efetiva_mm_ciclo,
        agua_estimada=cultura.usa_agua_estimada,
        score_agua=score_agua,
        penalidade_calor=penalidade,
        score_cultura=score_cultura,
        fixa_nitrogenio=fixa_n,
        protecao_erosao=protecao,
        valor_mercado=mercado,
        lacunas=lacunas,
        anos_usados=anos_usados,
        risco_hidrico_pct=risco_hidrico_pct,
    )


# ---------------------------------------------------------------------------
# 6. Índice de resiliência da rotação (média ponderada com renormalização)
# ---------------------------------------------------------------------------
def _pesos_da_prioridade(prioridade: str) -> Dict[str, float]:
    """Pega os pesos da prioridade do config (agua/solo/renda)."""
    if prioridade not in config.PESOS_PRIORIDADE:
        raise ResilienciaError(
            f"prioridade inválida: {prioridade}. "
            f"Use: {list(config.PESOS_PRIORIDADE)}")
    return dict(config.PESOS_PRIORIDADE[prioridade])


def _calcular_indice_ponderado(score: ScoreCultura,
                               pesos: Dict[str, float]
                               ) -> Tuple[Optional[float], Dict[str, float]]:
    """Calcula a média ponderada do score_cultura com os critérios
    agronômicos, renormalizando pesos quando um critério é None.

    Returns: (indice, pesos_usados)
        indice: 0..100 ou None se score_cultura for None.
        pesos_usados: pesos efetivamente usados (após renormalização).
    """
    if score.score_cultura is None:
        return None, {}

    # Componentes disponíveis (não-None)
    componentes = {
        "score_agua": score.score_cultura,
        "fixa_nitrogenio": score.fixa_nitrogenio,
        "protecao_erosao": score.protecao_erosao,
        "valor_mercado": score.valor_mercado,
    }
    # Filtra None e renormaliza pesos
    usados: Dict[str, float] = {}
    for k, v in componentes.items():
        if v is not None and k in pesos:
            usados[k] = pesos[k]
    soma_pesos = sum(usados.values())
    if soma_pesos <= 0:
        # Sem pesos: devolve o score_agua puro
        return score.score_cultura, {"score_agua": 1.0}

    # Renormaliza
    pesos_norm = {k: v / soma_pesos for k, v in usados.items()}
    indice = sum(componentes[k] * pesos_norm[k] for k in pesos_norm)
    return float(indice), pesos_norm


def pontuar_rotacao_cenario(scores_culturas: List[ScoreCultura],
                            rotacao: str,
                            classe: str,
                            prioridade: str = "agua"
                            ) -> ScoreRotacaoCenario:
    """Calcula o índice de resiliência de uma rotação num cenário.

    O índice é a MÉDIA dos índices ponderados de cada cultura da
    sequência. Culturas sem score (score_cultura=None) não entram na
    média (mas ficam listadas com suas lacunas).

    Args:
        scores_culturas: lista de ScoreCultura (um por cultura da rotação).
        rotacao: nome da rotação ('atual'/'solo'/'agua').
        classe: 'El Niño'/'La Niña'/'neutro'.
        prioridade: 'agua'/'solo'/'renda' (define os pesos).

    Returns:
        ScoreRotacaoCenario com índice, scores, lacunas consolidadas,
        pesos usados.
    """
    pesos = _pesos_da_prioridade(prioridade)
    indices: List[float] = []
    lacunas_todas: List[str] = []
    pesos_amostra: Dict[str, float] = {}
    riscos: List[float] = []   # risco hídrico por cultura (para média)

    for sc in scores_culturas:
        lacunas_todas.extend(sc.lacunas)
        indice, pesos_usados = _calcular_indice_ponderado(sc, pesos)
        if indice is not None:
            indices.append(indice)
            pesos_amostra = pesos_usados   # última amostra (são as mesmas)
        if sc.risco_hidrico_pct is not None:
            riscos.append(sc.risco_hidrico_pct)

    if not indices:
        indice_final = None
    else:
        indice_final = float(np.mean(indices))

    # Risco hídrico médio da rotação (média simples das culturas com risco)
    risco_medio = float(np.mean(riscos)) if riscos else None

    # Deduplica lacunas preservando ordem
    lacunas_unicas = list(dict.fromkeys(lacunas_todas))

    return ScoreRotacaoCenario(
        rotacao=rotacao,
        classe=classe,
        scores=scores_culturas,
        indice=indice_final,
        prioridade=prioridade,
        lacunas=lacunas_unicas,
        pesos_usados=pesos_amostra,
        risco_hidrico_pct=risco_medio,
    )


# ---------------------------------------------------------------------------
# 7. Pior cenário de uma rotação
# ---------------------------------------------------------------------------
def pior_cenario(scores_por_classe: Dict[str, ScoreRotacaoCenario]
                 ) -> Tuple[Optional[str], Optional[float]]:
    """Devolve (classe, índice) do pior cenário.

    Critério (revisão 2026-11-14):
        1. Menor índice vence (pior).
        2. EMPATE de índice -> maior RISCO HÍDRICO vence (pior). Antes,
           o desempate era arbitrário (El Niño por ordem de iteração),
           o que mascarava o artefato de todos os cenários saírem iguais.
           Agora, quando o índice satura em 100, o risco hídrico (% de
           anos com chuva < agua) discrimina qual cenário teve mais
           anos deficitários.
        3. EMPATE de índice E de risco -> ordem alfabética estável
           (determinística) como fallback.

    Se algum cenário tem índice None (sem dados), ele é o pior.
    """
    # Cenários com índice None são piores que qualquer índice numérico.
    for classe, sr in scores_por_classe.items():
        if sr.indice is None:
            return classe, None

    pior_classe = None
    pior_indice = None
    pior_risco = None   # para desempate
    for classe, sr in scores_por_classe.items():
        if pior_indice is None:
            pior_indice = sr.indice
            pior_risco = sr.risco_hidrico_pct
            pior_classe = classe
            continue
        # Critério 1: menor índice
        if sr.indice < pior_indice:
            pior_indice = sr.indice
            pior_risco = sr.risco_hidrico_pct
            pior_classe = classe
        elif sr.indice == pior_indice:
            # Critério 2 (empate de índice): maior risco hídrico vence
            risco_sr = sr.risco_hidrico_pct
            risco_atual = pior_risco
            # None é "pior" que 0 (não sabemos o risco -> mais incerto)
            if risco_sr is None and risco_atual is not None:
                # Manter o atual (não trocar para incerto). Decisão
                # conservadora: o que tem risco conhecido fica como pior.
                pass
            elif risco_atual is None and risco_sr is not None:
                pior_risco = risco_sr
                pior_classe = classe
            elif (risco_sr is not None and risco_atual is not None
                  and risco_sr > risco_atual):
                pior_risco = risco_sr
                pior_classe = classe
            # Critério 3 (empate total): mantém o atual (determinístico)
    return pior_classe, pior_indice


# ---------------------------------------------------------------------------
# 8. Verificação rápida (chamada direta no terminal)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from core.nasa_power import carregar_series
    from core.enso import anos_agricolas_completos, carregar_classificacao
    from core.culturas import carregar_banco
    from core.janelas import nome_mes

    print("Carregando clima (Teresina)...")
    df, falhas, _ = carregar_series()
    if falhas:
        print("Falhas:", falhas)
    completos, _ = anos_agricolas_completos(df)
    classes, contagem, _ = carregar_classificacao()
    print(f"Anos agrícolas completos: {len(completos)}")
    print(f"ENSO: {contagem}")

    banco = carregar_banco()

    print("\nMês de semeadura por cultura (revisão 2026-11-14):")
    for nome in ("milho", "feijao-caupi", "crotalaria-juncea", "sorgo"):
        if nome not in banco:
            continue
        c = banco[nome]
        mes, tem_janela, chuva = melhor_mes_semeadura(
            df, c, anos_agricolas_completos=completos)
        marca = "✓ janela" if tem_janela else "✗ sem janela válida"
        if mes is None:
            print(f"  {nome}: sem mês (sem ciclo_dias?)")
        else:
            print(f"  {nome}: {nome_mes(mes)} ({marca}, "
                  f"chuva mediana ciclo = {chuva:.0f} mm)")

    print("\nTeste: score do MILHO por cenário (prioridade=agua):")
    milho = banco["milho"]
    mes_milho, _, _ = melhor_mes_semeadura(
        df, milho, anos_agricolas_completos=completos)
    chuvas = chuva_ciclo_por_classe(
        df, milho, classes, completos[0], completos[-1],
        mes_semeadura=mes_milho)
    riscos = risco_hidrico_por_classe(
        df, milho, classes, completos[0], completos[-1],
        mes_semeadura=mes_milho)
    for classe in ("El Niño", "La Niña", "neutro"):
        med, n = chuvas[classe]
        if med is None:
            print(f"  {classe}: sem anos")
            continue
        risco = riscos[classe]
        sc = pontuar_cultura_cenario(
            df, milho, classe, med, n, mes_semeadura=mes_milho,
            risco_hidrico_pct=risco)
        risco_str = (f"{risco:.0f}%" if risco is not None else "—")
        print(f"  {classe}: semeio em {nome_mes(mes_milho)}, "
              f"chuva={med:.0f}mm (n={n}), "
              f"score_agua={sc.score_agua:.0f}, "
              f"risco_hídrico={risco_str}, "
              f"score={sc.score_cultura:.0f}, "
              f"janela_valida={sc.tem_janela_valida}")
        sr = pontuar_rotacao_cenario([sc], "atual", classe, "agua")
        print(f"    -> índice rotação 'atual': {sr.indice:.1f}, "
              f"risco médio: "
              f"{sr.risco_hidrico_pct:.0f}%" if sr.indice
              else "    -> índice: None")
