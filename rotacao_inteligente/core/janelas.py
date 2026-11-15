"""
core/janelas.py - Etapa 5: detector de janelas de oportunidade.

O QUE ESTE ARQUIVO FAZ (em linguagem simples):
    Dados os valores diários de chuva da NASA POWER e uma cultura (com
    `ciclo_dias` e `agua_efetiva_mm_ciclo`), este módulo responde, para
    cada mês do ano (jan a dez), se aquele é um bom mês de SEMEADURA —
    isto é, se a chuva que vai cair ao longo do ciclo da cultura atinge
    pelo menos `agua_efetiva × FATOR_MINIMO_CHUVA` (0,6). A "linha do
    tempo" das janelas é o resultado que a interface mostra.

REGRAS DO BRIEFING (seção 6.1):
    "Meses em que o campo está livre segundo o calendário informado E
    a chuva acumulada esperada no ciclo da cultura de cobertura >=
    agua_mm_ciclo x fator_minimo (padrão 0,6)."

    - Se `agua_mm_ciclo` estiver vazio, usar `config.CHUVA_MINIMA_CICLO_MM`
      e marcar o resultado como "parâmetro estimado pela equipe"
      (desconta ponto no semáforo). Se esse parâmetro também não
      estiver definido, não calcular a janela e avisar.
    - Se `ciclo_dias` estiver vazio, não calcular a janela e avisar.
    - Na Fase 2, validar com NDVI < `config.NDVI_LIMIAR_SOLO_NU` (0,3).
      (Aqui na Fase 1 não há NDVI; registramos a lacuna.)

CONVENÇÃO DE CICLO EM COBERTURA:
    Para cobertura, `ciclo_dias` = dias até o CORTE no pico de floração
    (não colheita). A janela mede a chuva que cai da semeadura até o
    corte — suficiente para a cultura acumular biomassa. Documentado
    no README e em `core/culturas.py`.

O QUE É A "CHUVA DO CICLO":
    Para um mês de semeadura M, somamos a chuva diária dos
    `ciclo_dias` dias seguintes (a partir do dia 1 de M). Em vez de
    usar a média entre anos (que puxa a chuva para um "ano típico" e
    esconde anos secos), usamos a **mediana** entre os anos agrícolas
    completos — mais robusta a outliers (anos de seca extrema ou
    El Niño forte). O briefing (seção 6.2) pede mediana para os
    cenários ENSO; usamos a mesma estatística para a janela
    climatológica (todos os anos agrícolas completos juntos).

CRITÉRIO DE ESTABELECIMENTO (ajuste 2026-11-14):
    A janela do ciclo inteiro ignora o MOMENTO da chuva — uma
    semeadura em setembro em Teresina passa no critério do ciclo (160
    mm no ciclo de 120 dias) mesmo chovendo só ~4 mm nos primeiros 30
    dias (a semente nem germina). Por isso há um SEGUNDO critério: o
    mês só é janela se a chuva mediana dos primeiros
    `config.JANELA_ESTABELECIMENTO_DIAS` (30) dias também atingir
    `config.CHUVA_MINIMA_ESTABELECIMENTO_MM` (20). Os dois valores são
    suposição da equipe (validar com agrônomo local, briefing 6.9).
    O resultado mostra a chuva dos 30 dias ao lado da chuva do ciclo.

O QUE NÃO FAZOS AQUI (deixa para etapas futuras):
    - Separar por cenário ENSO (Etapa 6, resiliencia.py): aqui a
      janela é climatológica (todos os anos agrícolas juntos).
    - Cruzar com o calendário informado pelo agricultor ("campo
      livre"): feito nesta etapa via `meses_livres`, mas a interface
      que coleta o calendário do agricultor chega na Etapa 7.
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
class JanelasError(Exception):
    """Erro no cálculo de janelas de oportunidade."""


# ---------------------------------------------------------------------------
# 2. Estruturas de dados
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class JanelaMes:
    """Resultado da janela de oportunidade para um mês de semeadura.

    Dois critérios (briefing 6.1 + ajuste de estabelecimento 2026-11-14):
      (1) chuva do ciclo inteiro: mediana entre anos agrícolas completos
          da soma dos `ciclo_dias` dias a partir do dia 1 do mês.
      (2) chuva de estabelecimento: mediana da soma dos
          `JANELA_ESTABELECIMENTO_DIAS` (30) primeiros dias.

    O mês é janela (`e_janela=True`) só se passar NOS DOIS critérios.

    - `mes`: 1..12 (mês de semeadura avaliado).
    - `chuva_ciclo_mm`: mediana da chuva do ciclo. None se não calculável.
    - `chuva_estab_mm`: mediana da chuva dos primeiros 30 dias. None se
      não calculável.
    - `e_janela`: True se `chuva_ciclo_mm >= agua_necessaria_mm` E
      `chuva_estab_mm >= estab_necessaria_mm`.
    - `agua_necessaria_mm`: agua_efetiva × FATOR_MINIMO_CHUVA (piso do ciclo).
    - `estab_necessaria_mm`: config.CHUVA_MINIMA_ESTABELECIMENTO_MM (20).
    - `anos_usados`: quantos anos agrícolas completos entraram na
      mediana (para o semáforo conferir tamanho de amostra).
    - `aviso`: None ou mensagem de lacuna/limitação.
    """
    mes: int
    chuva_ciclo_mm: Optional[float]
    chuva_estab_mm: Optional[float]
    e_janela: bool
    agua_necessaria_mm: float
    estab_necessaria_mm: float
    anos_usados: int
    aviso: Optional[str] = None


@dataclass(frozen=True)
class ResultadoJanelas:
    """Resultado completo das janelas de uma cultura.

    - `cultura`: nome da cultura avaliada.
    - `ciclo_dias`: ciclo usado (do CSV; em cobertura = dias até corte).
    - `agua_efetiva_mm`: água usada no cálculo (do CSV ou fallback 250).
    - `agua_estimada`: True se `agua_efetiva_mm` veio do fallback da
      equipe (desconta ponto no semáforo).
    - `estab_dias`: dias de estabelecimento (config.JANELA_ESTABELECIMENTO_DIAS).
    - `estab_min_mm`: chuva mínima de estabelecimento (config.CHUVA_MINIMA_ESTABELECIMENTO_MM).
    - `janelas`: lista de 12 JanelaMes (jan..dez).
    - `meses_janela`: nomes dos meses que são janela (passam nos 2 critérios).
    - `aviso_geral`: None ou aviso se a cultura não pôde ser avaliada.
    """
    cultura: str
    ciclo_dias: Optional[int]
    agua_efetiva_mm: Optional[float]
    agua_estimada: bool
    estab_dias: int
    estab_min_mm: float
    janelas: List[JanelaMes] = field(default_factory=list)
    meses_janela: List[str] = field(default_factory=list)
    aviso_geral: Optional[str] = None


# ---------------------------------------------------------------------------
# 3. Funções auxiliares (puras, testáveis)
# ---------------------------------------------------------------------------
_MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def nome_mes(mes: int) -> str:
    """Devolve a abreviação pt-BR do mês (1 -> 'Jan')."""
    if not 1 <= mes <= 12:
        raise JanelasError(f"mês inválido: {mes}")
    return _MESES_PT[mes - 1]


def agua_necessaria(agua_efetiva_mm: float,
                    fator: float = config.FATOR_MINIMO_CHUVA) -> float:
    """Piso de chuva do ciclo para o mês ser janela.

    = agua_efetiva × FATOR_MINIMO_CHUVA (briefing 6.1).
    """
    return float(agua_efetiva_mm) * float(fator)


def chuva_do_ciclo(df_chuva: pd.Series, data_inicio: pd.Timestamp,
                   ciclo_dias: int) -> Optional[float]:
    """Soma a chuva diária ao longo do ciclo a partir de `data_inicio`.

    `df_chuva` é uma Series indexada por data (PRECTOTCORR do DataFrame
    da NASA POWER). Retorna a soma em mm, ou None se não houver dado
    suficiente (todos os dias do ciclo NaN).

    Se o ciclo ultrapassar o fim da série, soma só o que existir —
    mas marca None se mais de 20% dos dias estiverem faltando (para
    não subestimar a janela em anos incompletos).
    """
    fim = data_inicio + pd.Timedelta(days=ciclo_dias - 1)
    janela = df_chuva.loc[(df_chuva.index >= data_inicio)
                          & (df_chuva.index <= fim)]
    if janela.empty:
        return None
    # Se mais de 20% dos dias esperados estão faltando, não confiar.
    if len(janela) < ciclo_dias * 0.8:
        return None
    # min_count=1: se tudo for NaN, soma vira NaN (não 0).
    return float(janela.sum(min_count=1))


# ---------------------------------------------------------------------------
# 4. Função principal: calcular janelas de uma cultura
# ---------------------------------------------------------------------------
def calcular_janelas(df_clima: pd.DataFrame,
                    cultura: Cultura,
                    anos_agricolas_completos: Optional[List[int]] = None,
                    meses_livres: Optional[List[int]] = None
                    ) -> ResultadoJanelas:
    """Calcula a janela de oportunidade (jan..dez) para uma cultura.

    Para cada mês M de semeadura (1..12), computa DOIS critérios e o
    mês só é janela se passar nos dois (ajuste 2026-11-14):

      (1) Chuva do ciclo: mediana (entre anos agrícolas completos) da
          soma dos `ciclo_dias` dias a partir do dia 1 de M. Deve ser
          >= agua_efetiva × FATOR_MINIMO_CHUVA.
      (2) Chuva de estabelecimento: mediana da soma dos
          JANELA_ESTABELECIMENTO_DIAS (30) primeiros dias. Deve ser
          >= CHUVA_MINIMA_ESTABELECIMENTO_MM (20).

    O critério de estabelecimento evita o caso em que a chuva do ciclo
    inteiro é suficiente mas concentrada no final — a semente não
    germina nos primeiros 30 dias secos (ex.: crotalária em setembro
    em Teresina, 160 mm no ciclo de 120 dias mas só ~4 mm nos
    primeiros 30 dias).

    Args:
        df_clima: DataFrame da NASA POWER com coluna "PRECTOTCORR"
            e index de datas (datetime).
        cultura: cultura a avaliar (precisa ter ciclo_dias; se não
            tiver, devolve aviso e janelas vazias).
        anos_agricolas_completos: lista de anos agrícolas a usar.
            Se None, usa TODOS os anos do DataFrame.
        meses_livres: meses em que o campo está livre (calendário do
            agricultor). Se None, assume TODOS livres.

    Returns:
        ResultadoJanelas com 12 JanelaMes (um por mês) + avisos.

    Trata lacunas (briefing 6.1):
        - Sem ciclo_dias: não calcula, avisa.
        - Sem agua_mm_ciclo: usa config.CHUVA_MINIMA_CICLO_MM
          (marcado agua_estimada=True).
        - Sem dado de chuva no DataFrame: avisa.
    """
    estab_dias = int(config.JANELA_ESTABELECIMENTO_DIAS)
    estab_min = float(config.CHUVA_MINIMA_ESTABELECIMENTO_MM)

    # --- 1) Pré-validação: ciclo_dias é obrigatório.
    if cultura.ciclo_dias is None:
        return ResultadoJanelas(
            cultura=cultura.nome,
            ciclo_dias=None,
            agua_efetiva_mm=None,
            agua_estimada=False,
            estab_dias=estab_dias,
            estab_min_mm=estab_min,
            janelas=[],
            meses_janela=[],
            aviso_geral=(
                f"{cultura.nome}: sem ciclo_dias no CSV — não é possível "
                "calcular a janela (briefing 6.1)."
            ),
        )

    # --- 2) Água efetiva (do CSV ou fallback da equipe).
    try:
        agua_ef = cultura.agua_efetiva_mm_ciclo
    except Exception as e:
        return ResultadoJanelas(
            cultura=cultura.nome,
            ciclo_dias=cultura.ciclo_dias,
            agua_efetiva_mm=None,
            agua_estimada=False,
            estab_dias=estab_dias,
            estab_min_mm=estab_min,
            janelas=[],
            meses_janela=[],
            aviso_geral=(
                f"{cultura.nome}: {e} "
                "(briefing 6.1: sem agua_mm_ciclo e sem fallback da equipe)."
            ),
        )
    agua_estimada = cultura.usa_agua_estimada
    agua_nec = agua_necessaria(agua_ef)

    # --- 3) Confere que temos chuva no DataFrame.
    if df_clima is None or df_clima.empty or "PRECTOTCORR" not in df_clima.columns:
        return ResultadoJanelas(
            cultura=cultura.nome,
            ciclo_dias=cultura.ciclo_dias,
            agua_efetiva_mm=agua_ef,
            agua_estimada=agua_estimada,
            estab_dias=estab_dias,
            estab_min_mm=estab_min,
            janelas=[],
            meses_janela=[],
            aviso_geral="Sem dados de chuva (PRECTOTCORR) no DataFrame.",
        )
    chuva = df_clima["PRECTOTCORR"].dropna()
    if chuva.empty:
        return ResultadoJanelas(
            cultura=cultura.nome,
            ciclo_dias=cultura.ciclo_dias,
            agua_efetiva_mm=agua_ef,
            agua_estimada=agua_estimada,
            estab_dias=estab_dias,
            estab_min_mm=estab_min,
            janelas=[],
            meses_janela=[],
            aviso_geral="Coluna PRECTOTCORR está totalmente vazia.",
        )

    # --- 4) Anos a usar na mediana.
    if anos_agricolas_completos is None:
        anos_usar = sorted(set(chuva.index.year))
    else:
        anos_usar = list(anos_agricolas_completos)

    # --- 5) Para cada mês, mediana da chuva do ciclo E dos 30 dias.
    janelas: List[JanelaMes] = []
    meses_janela: List[str] = []
    for mes in range(1, 13):
        # Pula meses em que o campo não está livre (calendário).
        if meses_livres is not None and mes not in meses_livres:
            janelas.append(JanelaMes(
                mes=mes,
                chuva_ciclo_mm=None,
                chuva_estab_mm=None,
                e_janela=False,
                agua_necessaria_mm=agua_nec,
                estab_necessaria_mm=estab_min,
                anos_usados=0,
                aviso="mês não livre segundo o calendário informado",
            ))
            continue

        # Para cada ano agrícola completo, soma a chuva do ciclo e a
        # chuva dos primeiros estab_dias a partir do dia 1 do mês.
        chuvas_ciclo: List[float] = []
        chuvas_estab: List[float] = []
        for ano in anos_usar:
            data_inicio = pd.Timestamp(ano, mes, 1)
            # Critério 1: chuva do ciclo inteiro.
            soma_ciclo = chuva_do_ciclo(chuva, data_inicio, cultura.ciclo_dias)
            if soma_ciclo is not None and not np.isnan(soma_ciclo):
                chuvas_ciclo.append(soma_ciclo)
            # Critério 2: chuva de estabelecimento (primeiros 30 dias).
            # Reaproveita chuva_do_ciclo com um "ciclo" de estab_dias.
            soma_estab = chuva_do_ciclo(chuva, data_inicio, estab_dias)
            if soma_estab is not None and not np.isnan(soma_estab):
                chuvas_estab.append(soma_estab)

        if not chuvas_ciclo:
            janelas.append(JanelaMes(
                mes=mes,
                chuva_ciclo_mm=None,
                chuva_estab_mm=None,
                e_janela=False,
                agua_necessaria_mm=agua_nec,
                estab_necessaria_mm=estab_min,
                anos_usados=0,
                aviso="sem anos agrícolas completos para este mês",
            ))
            continue

        mediana_ciclo = float(np.median(chuvas_ciclo))
        # Mediana de estabelecimento: pode ter n anos diferente do ciclo
        # se alguns anos não cobrirem os 30 dias, mas em geral é igual.
        mediana_estab = (float(np.median(chuvas_estab))
                         if chuvas_estab else None)

        # O mês é janela só se passar NOS DOIS critérios.
        passou_ciclo = mediana_ciclo >= agua_nec
        passou_estab = (mediana_estab is not None
                        and mediana_estab >= estab_min)
        e_janela = passou_ciclo and passou_estab

        # Aviso por critério reprovado (informativo para a interface).
        aviso: Optional[str] = None
        if not e_janela:
            motivos = []
            if not passou_ciclo:
                motivos.append(
                    f"chuva do ciclo ({mediana_ciclo:.0f} mm < "
                    f"{agua_nec:.0f} mm)"
                )
            if not passou_estab:
                if mediana_estab is None:
                    motivos.append(
                        f"sem dado de chuva nos primeiros {estab_dias} dias"
                    )
                else:
                    motivos.append(
                        f"chuva de estabelecimento ({mediana_estab:.0f} mm < "
                        f"{estab_min:.0f} mm)"
                    )
            aviso = "reprovado: " + "; ".join(motivos)

        jm = JanelaMes(
            mes=mes,
            chuva_ciclo_mm=mediana_ciclo,
            chuva_estab_mm=mediana_estab,
            e_janela=e_janela,
            agua_necessaria_mm=agua_nec,
            estab_necessaria_mm=estab_min,
            anos_usados=len(chuvas_ciclo),
            aviso=aviso,
        )
        janelas.append(jm)
        if e_janela:
            meses_janela.append(nome_mes(mes))

    aviso_geral: Optional[str] = None
    if agua_estimada:
        aviso_geral = (
            f"{config.AVISO_PARAMETRO_ESTIMADO} — agua_mm_ciclo vazio no "
            f"CSV; janela usa config.CHUVA_MINIMA_CICLO_MM = "
            f"{config.CHUVA_MINIMA_CICLO_MM} mm "
            f"({config.CHUVA_MINIMA_CICLO_ROTULO})."
        )

    return ResultadoJanelas(
        cultura=cultura.nome,
        ciclo_dias=cultura.ciclo_dias,
        agua_efetiva_mm=agua_ef,
        agua_estimada=agua_estimada,
        estab_dias=estab_dias,
        estab_min_mm=estab_min,
        janelas=janelas,
        meses_janela=meses_janela,
        aviso_geral=aviso_geral,
    )


# ---------------------------------------------------------------------------
# 5. Função utilitária para o app: DataFrame de visualização
# ---------------------------------------------------------------------------
def janelas_para_dataframe(resultado: ResultadoJanelas) -> pd.DataFrame:
    """Converte ResultadoJanelas em DataFrame pronto para st.dataframe/plotly.

    Colunas: mes, mes_nome, chuva_ciclo_mm, chuva_estab_mm,
    agua_necessaria_mm, estab_necessaria_mm, e_janela.
    Meses sem cálculo (None) ficam com NaN em chuva_ciclo_mm/chuva_estab_mm
    e False em e_janela.
    """
    linhas = []
    for jm in resultado.janelas:
        linhas.append({
            "mes": jm.mes,
            "mes_nome": nome_mes(jm.mes),
            "chuva_ciclo_mm": jm.chuva_ciclo_mm,
            "chuva_estab_mm": jm.chuva_estab_mm,
            "agua_necessaria_mm": jm.agua_necessaria_mm,
            "estab_necessaria_mm": jm.estab_necessaria_mm,
            "e_janela": jm.e_janela,
        })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# 6. Verificação rápida (chamada direta no terminal)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from core.culturas import carregar_banco
    from core.nasa_power import carregar_series
    from core.enso import anos_agricolas_completos

    print("Carregando clima (NASA POWER)...")
    df, falhas, _ = carregar_series()
    if falhas:
        print("Falhas:", falhas)
    completos, _ = anos_agricolas_completos(df)
    print(f"Anos agrícolas completos: {len(completos)} "
          f"({completos[0]}-{completos[-1]})")

    print("\nCarregando culturas...")
    banco = carregar_banco()

    print(
        f"\nCritério de estabelecimento: primeiros "
        f"{config.JANELA_ESTABELECIMENTO_DIAS} dias precisam de "
        f"{config.CHUVA_MINIMA_ESTABELECIMENTO_MM} mm "
        f"({config.JANELA_ESTABELECIMENTO_ROTULO})."
    )

    print("\nJanelas de oportunidade por cultura "
          "(ciclo / estabelecimento, ambos mediana):")
    for nome, c in banco.items():
        r = calcular_janelas(df, c, anos_agricolas_completos=completos)
        print(f"\n  {nome} (ciclo={r.ciclo_dias}d, agua="
              f"{r.agua_efetiva_mm:.0f}mm"
              + (", estimada" if r.agua_estimada else "") + "):")
        if r.aviso_geral and not r.janelas:
            print(f"    AVISO: {r.aviso_geral}")
            continue
        for jm in r.janelas:
            if jm.chuva_ciclo_mm is None:
                marca = "—"
            else:
                marca = "✓" if jm.e_janela else "✗"
                estab_str = (f"{jm.chuva_estab_mm:.0f}"
                             if jm.chuva_estab_mm is not None else "—")
                marca += (f" ciclo={jm.chuva_ciclo_mm:.0f}mm"
                          f" (≥{jm.agua_necessaria_mm:.0f}), "
                          f"estab={estab_str}mm (≥{jm.estab_necessaria_mm:.0f})"
                          f" [{jm.anos_usados} anos]")
            print(f"    {nome_mes(jm.mes):>3}: {marca}")
            if jm.e_janela is False and jm.aviso:
                print(f"         {jm.aviso}")
        if r.aviso_geral:
            print(f"    ⚠️ {r.aviso_geral}")
