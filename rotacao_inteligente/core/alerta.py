"""
core/alerta.py - Etapa 7: alerta simulado de plantio (briefing 6.8).

O QUE ESTE ARQUIVO FAZ (em linguagem simples):
    Responde, para uma data específica, se está na hora de plantar uma
    cultura. Combina três sinais:
        1. A data está dentro de uma janela de oportunidade (Etapa 5)?
        2. A chuva dos últimos 7 dias atingiu o limiar de germinação?
        3. A umidade do solo está suficiente para a semeadura?
    Se todos os três sinais estão OK -> "PLANTE AGORA" (verde).
    Se a janela está aberta mas os outros sinais não -> "AGUARDE" (amarelo).
    Se a data está fora da janela -> "NÃO PLANTE" (vermelho).

REGRAS DO BRIEFING (seção 6.8):
    Gatilho: chuva_7d >= limiar_chuva_mm E umidade_solo >= limiar_umidade.
    Os limiares ainda precisam ser definidos pela equipe (config está None).
    Como regra "não invente dado", se os limiares são None, o alerta
    só usa o critério de janela (Etapa 5) e registra que faltam os
    limiares de chuva/umidade.

LACUNAS:
    - Sem limiar_chuva_7d_mm: alerta só por janela, registra lacuna.
    - Sem limiar_umidade_solo: mesmo.
    - Sem dado de chuva 7d ou umidade na data: alerta só por janela,
      registra lacuna.

ENTRADA DE DADOS DE SOLO (Etapa 7, briefing 6.5):
    O usuário pode informar dados do próprio solo (textura, profundidade,
    matéria orgânica). Isso sobe 1 ponto no semáforo. Aqui só registramos
    que o usuário informou; o semáforo.py usa a flag `tem_dados_solo`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import config


# ---------------------------------------------------------------------------
# 1. Exceções
# ---------------------------------------------------------------------------
class AlertaError(Exception):
    """Erro no cálculo do alerta de plantio."""


# ---------------------------------------------------------------------------
# 2. Estruturas de dados
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Alerta:
    """Resultado do alerta de plantio para uma data e cultura.

    - `data`: data avaliada.
    - `cultura`: nome da cultura.
    - `status`: 'PLANTE AGORA' / 'AGUARDE' / 'NÃO PLANTE'.
    - `cor`: 'verde' / 'amarelo' / 'vermelho' (paralelo ao semáforo).
    - `na_janela`: True se a data está num mês-janela da cultura.
    - `mes_janela`: nome do mês-janela (ou None se não houver).
    - `chuva_7d_mm`: chuva dos últimos 7 dias (mm). None se sem dado.
    - `umidade_solo`: umidade do solo na data (0..1 ou %). None se sem dado.
    - `limiares_usados`: dict com limiares aplicados (chuva/umidade).
    - `lacunas`: lista de lacunas (sem limiares, sem dados, etc.).
    - `motivos`: lista de motivos que levaram ao status (informativo).
    """
    data: pd.Timestamp
    cultura: str
    status: str
    cor: str
    na_janela: bool
    mes_janela: Optional[str]
    chuva_7d_mm: Optional[float]
    umidade_solo: Optional[float]
    limiares_usados: Dict[str, Optional[float]] = field(default_factory=dict)
    lacunas: List[str] = field(default_factory=list)
    motivos: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. Função principal: calcular o alerta
# ---------------------------------------------------------------------------
def chuva_ultimos_7d(df_clima: pd.DataFrame,
                    data: pd.Timestamp) -> Optional[float]:
    """Soma a chuva dos 7 dias anteriores (inclusive a data).

    Args:
        df_clima: DataFrame com coluna PRECTOTCORR e index de datas.
        data: data de referência (inclusive).

    Returns:
        Soma em mm, ou None se não houver dado suficiente (todos os 7
        dias NaN ou fora da série).
    """
    if "PRECTOTCORR" not in df_clima.columns:
        return None
    if not isinstance(data, pd.Timestamp):
        data = pd.Timestamp(data)
    fim = data
    inicio = data - pd.Timedelta(days=6)   # 7 dias inclusive
    sub = df_clima["PRECTOTCORR"].loc[(df_clima.index >= inicio)
                                     & (df_clima.index <= fim)]
    if sub.empty:
        return None
    # Se mais da metade dos 7 dias está NaN, não confiar.
    if sub.isna().sum() > 3:
        return None
    return float(sub.sum(min_count=1))


def umidade_solo_na_data(df_clima: pd.DataFrame,
                        data: pd.Timestamp) -> Optional[float]:
    """Pega a umidade do solo na zona de raízes (GWETROOT) na data.

    O GWETROOT da NASA POWER é fração 0..1 (0 = seco, 1 = saturado).

    Returns:
        Umidade em fração 0..1, ou None se sem dado.
    """
    if "GWETROOT" not in df_clima.columns:
        return None
    if not isinstance(data, pd.Timestamp):
        data = pd.Timestamp(data)
    try:
        v = df_clima["GWETROOT"].loc[data]
    except KeyError:
        # Tenta o dia mais próximo (a data pode não estar no index exato).
        sub = df_clima["GWETROOT"].loc[data - pd.Timedelta(days=1):
                                   data + pd.Timedelta(days=1)]
        if sub.empty:
            return None
        v = sub.iloc[-1]
    if pd.isna(v):
        return None
    return float(v)


def calcular_alerta(df_clima: pd.DataFrame,
                   cultura,
                   resultado_janelas,    # core.janelas.ResultadoJanelas
                   data: pd.Timestamp,
                   limiar_chuva_7d_mm: Optional[float] = config.LIMIAR_CHUVA_7D_MM,
                   limiar_umidade: Optional[float] = config.LIMIAR_UMIDADE_SOLO,
                   ) -> Alerta:
    """Calcula o alerta de plantio para uma data e cultura.

    Combina três sinais:
        1. A data está num mês-janela da cultura (resultado_janelas)?
        2. A chuva dos últimos 7 dias >= limiar_chuva_7d_mm?
        3. A umidade do solo (GWETROOT) >= limiar_umidade?

    Status:
        - 'PLANTE AGORA' (verde): na janela E (chuva OK ou sem limiar) E
          (umidade OK ou sem limiar). Os limiares None não bloqueiam —
          só registram a lacuna.
        - 'AGUARDE' (amarelo): na janela, mas chuva ou umidade abaixo do
          limiar.
        - 'NÃO PLANTE' (vermelho): fora da janela (não faz sentido plantar
          fora da janela de oportunidade).

    Args:
        df_clima: DataFrame da NASA POWER com PRECTOTCORR e GWETROOT.
        cultura: cultura a avaliar (para nome).
        resultado_janelas: ResultadoJanelas da cultura (Etapa 5).
        data: data da simulação.
        limiar_chuva_7d_mm: limiar de chuva 7d (mm). None = usa config.
        limiar_umidade: limiar de umidade do solo (fração 0..1). None = config.

    Returns:
        Alerta com status, cor, sinais e lacunas.
    """
    if not isinstance(data, pd.Timestamp):
        data = pd.Timestamp(data)

    lacunas: List[str] = []
    motivos: List[str] = []

    # 1) Está num mês-janela?
    mes = data.month
    jm = next((jm for jm in resultado_janelas.janelas
               if jm.mes == mes), None)
    na_janela = bool(jm and jm.e_janela)
    mes_janela_nome = jm.mes if jm and jm.e_janela else None

    # Se não há janelas calculadas, registra a lacuna.
    if not resultado_janelas.janelas:
        lacunas.append("sem janelas calculadas para a cultura")
        na_janela = False

    if not na_janela:
        motivos.append(
            f"fora da janela de oportunidade (mês {data.month} não é "
            "mês-janela)")
    else:
        motivos.append(
            f"na janela de oportunidade (mês {data.month} é mês-janela)")

    # 2) Chuva dos últimos 7 dias
    chuva_7d = chuva_ultimos_7d(df_clima, data)
    # Usa limiar do parâmetro, senão config.
    lim_chuva = (limiar_chuva_7d_mm
                 if limiar_chuva_7d_mm is not None
                 else config.LIMIAR_CHUVA_7D_MM)
    sinais_calibrados_chuva = lim_chuva is not None
    if lim_chuva is None:
        lacunas.append("limiar_chuva_7d_mm não definido (config None)")
        chuva_ok = True   # não bloqueia
        if chuva_7d is not None:
            motivos.append(
                f"chuva 7d = {chuva_7d:.1f} mm (sem limiar para comparar)")
    else:
        if chuva_7d is None:
            lacunas.append("sem dado de chuva nos últimos 7 dias")
            chuva_ok = True   # não bloqueia por falta de dado
        else:
            chuva_ok = chuva_7d >= lim_chuva
            verb = "OK" if chuva_ok else "abaixo"
            motivos.append(
                f"chuva 7d = {chuva_7d:.1f} mm vs limiar "
                f"{lim_chuva:.1f} mm ({verb})")

    # 3) Umidade do solo
    umidade = umidade_solo_na_data(df_clima, data)
    lim_umid = (limiar_umidade
                if limiar_umidade is not None
                else config.LIMIAR_UMIDADE_SOLO)
    sinais_calibrados_umidade = lim_umid is not None
    if lim_umid is None:
        lacunas.append("limiar_umidade_solo não definido (config None)")
        umidade_ok = True
        if umidade is not None:
            motivos.append(
                f"umidade solo = {umidade:.2f} (sem limiar para comparar)")
    else:
        if umidade is None:
            lacunas.append("sem dado de umidade do solo na data")
            umidade_ok = True
        else:
            umidade_ok = umidade >= lim_umid
            verb = "OK" if umidade_ok else "abaixo"
            motivos.append(
                f"umidade solo = {umidade:.2f} vs limiar "
                f"{lim_umid:.2f} ({verb})")

    # Os sinais estão calibrados? Se algum limiar é None, não podemos dar
    # "PLANTE AGORA" (verde) — só "JANELA ABERTA (sinais não calibrados)"
    # em amarelo (revisão 2026-11-14). A regra "não invente dado" impede
    # de recomendar plantio verde sem saber se a chuva/umidade são
    # suficientes.
    sinais_calibrados = sinais_calibrados_chuva and sinais_calibrados_umidade

    # Status final
    if not na_janela:
        status, cor = "NÃO PLANTE", "vermelho"
    elif not sinais_calibrados:
        # Janela aberta mas sem limiares calibrados -> não pode recomendar.
        status = "JANELA ABERTA (sinais não calibrados)"
        cor = "amarelo"
    elif chuva_ok and umidade_ok:
        status, cor = "PLANTE AGORA", "verde"
    else:
        status, cor = "AGUARDE", "amarelo"

    return Alerta(
        data=data,
        cultura=getattr(cultura, "nome", str(cultura)),
        status=status,
        cor=cor,
        na_janela=na_janela,
        mes_janela=nome_mes_breve(mes_janela_nome) if mes_janela_nome else None,
        chuva_7d_mm=chuva_7d,
        umidade_solo=umidade,
        limiares_usados={
            "limiar_chuva_7d_mm": lim_chuva,
            "limiar_umidade_solo": lim_umid,
        },
        lacunas=lacunas,
        motivos=motivos,
    )


def nome_mes_breve(mes: int) -> str:
    """Abreviação pt-BR do mês (1 -> 'Jan'). Import local para evitar ciclo."""
    from core.janelas import nome_mes
    return nome_mes(mes)


# ---------------------------------------------------------------------------
# 4. Verificação rápida (chamada direta no terminal)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from core.nasa_power import carregar_series
    from core.culturas import carregar_banco
    from core.janelas import calcular_janelas
    from core.enso import anos_agricolas_completos

    print("Carregando clima (Teresina)...")
    df, _, _ = carregar_series()
    completos, _ = anos_agricolas_completos(df)
    banco = carregar_banco()
    milho = banco["milho"]
    r_jan = calcular_janelas(df, milho, anos_agricolas_completos=completos)
    print(f"Meses-janela do milho: {r_jan.meses_janela}")
    print()

    # Simula alerta em 4 datas diferentes (janeiro = janela, junho = seca)
    print("Alerta simulado (limiares do config = None):")
    for data in ["2025-01-15", "2025-06-15", "2025-02-15", "2025-11-15"]:
        a = calcular_alerta(df, milho, r_jan, pd.Timestamp(data))
        emoji = {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}[a.cor]
        chuva_str = (f"{a.chuva_7d_mm:.1f}" if a.chuva_7d_mm is not None
                     else "—")
        umid_str = (f"{a.umidade_solo:.2f}" if a.umidade_solo is not None
                    else "—")
        print(f"  {data} ({a.cultura}): {emoji} {a.status}")
        print(f"    na_janela={a.na_janela}, chuva_7d={chuva_str} mm, "
              f"umidade={umid_str}")
        for m in a.motivos:
            print(f"    · {m}")
        if a.lacunas:
            print(f"    lacunas: {a.lacunas}")
        print()
