"""
tests/test_etapa6.py - Testes da Etapa 6 (resiliencia.py + semaforo.py + enso.ano_agricola_da_semeadura).

Valida:
- enso.ano_agricola_da_semeadura: semeadura jan-out ano Y -> AA Y-1;
  nov/dez ano Y -> AA Y. Teste jan/2016 -> AA 2015 -> El Niño.
- resiliencia.py: score_agua (min(100, chuva/agua×100)), penalidade de
  calor (tmax vazio = 0 e registra lacuna), índice de resiliência
  (média ponderada com renormalização quando critério vazio).
- semaforo.py: verde/amarelo/vermelho, pontos por amostra ENSO
  (>=10=2, 5-9=1, <5=0), descontos (agua estimada -1, local não
  calibrado -1).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from core import enso, resiliencia, semaforo
from core.resiliencia import (ScoreCultura, ScoreRotacaoCenario,
                              calcular_score_agua, calcular_penalidade_calor,
                              pontuar_cultura_cenario, pontuar_rotacao_cenario,
                              chuva_ciclo_por_classe, pior_cenario,
                              _escalar_1_3_para_0_100, _fixa_n_para_score)
from core.semaforo import (Semaforo, calcular_semaforo, cor_do_semaforo,
                            pontos_por_amostra_classe, emoji_cor)
from core.culturas import Cultura


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def cultura(nome="milho", tipo="comercial", ciclo_dias=120,
            agua_mm_ciclo=600.0, tmax_limite_c=None,
            fixa_nitrogenio="nao", protecao_erosao=None,
            valor_mercado=None, **kw) -> Cultura:
    return Cultura(
        nome=nome, tipo=tipo, ciclo_dias=ciclo_dias,
        agua_mm_ciclo=agua_mm_ciclo, tmax_limite_c=tmax_limite_c,
        fixa_nitrogenio=fixa_nitrogenio, protecao_erosao=protecao_erosao,
        valor_mercado=valor_mercado,
        taxa_semeadura_kg_ha=None, rendimento_potencial_kg_ha=None,
        rendimento_regional_kg_ha=None, fonte="", lacunas=[],
    )


# ===========================================================================
# 1. enso.ano_agricola_da_semeadura (Etapa 6, briefing 6.7)
# ===========================================================================
def test_semeadura_janeiro_volta_ano_anterior():
    """Semeação em jan/2016 pertence ao ano agrícola 2015 (nov/15-out/16)."""
    assert enso.ano_agricola_da_semeadura(pd.Timestamp(2016, 1, 15)) == 2015


def test_semeadura_outubro_volta_ano_anterior():
    """Semeação em 31/out/2016 -> AA 2015 (out/16 ainda é AA 2015)."""
    assert enso.ano_agricola_da_semeadura(pd.Timestamp(2016, 10, 31)) == 2015


def test_semeadura_novembro_mesmo_ano():
    """Semeação em nov/2016 -> AA 2016 (nov/16 inicia AA 2016)."""
    assert enso.ano_agricola_da_semeadura(pd.Timestamp(2016, 11, 1)) == 2016


def test_semeadura_dezembro_mesmo_ano():
    """Semeação em dez/2016 -> AA 2016."""
    assert enso.ano_agricola_da_semeadura(pd.Timestamp(2016, 12, 31)) == 2016


def test_semeadura_jan_2016_aa_2015_el_nino():
    """Teste pedido pelo briefing: jan/2016 -> AA 2015 -> El Niño.

    Carrega a classificação real do oni.csv e confere que a semeadura
    em jan/2016 cai no ano agrícola 2015 e que 2015 foi El Niño.
    """
    classes, _, _ = enso.carregar_classificacao()
    classe = enso.classe_da_semeadura(pd.Timestamp(2016, 1, 15), classes)
    aa = enso.ano_agricola_da_semeadura(pd.Timestamp(2016, 1, 15))
    assert aa == 2015
    # 2015 foi El Niño na tabela ONI (DJF 2016 = +0.6 a +1.0)
    # Aceitamos também "neutro" se a tabela mudar, mas NÃO La Niña.
    assert classe in ("El Niño", "neutro"), \
        f"2015 deveria ser El Niño ou neutro, veio: {classe}"


def test_semeadura_dez_2015_aa_2015():
    """Teste pedido na revisão 2026-11-14: dez/2015 -> AA 2015.

    Novembro e dezembro do ano civil Y pertencem ao ano agrícola Y.
    Logo, semeadura em dez/2015 -> AA 2015 (mesmo AA da semeadura em
    jan/2016, que é AA 2015). Confirma a simetria: o ano agrícola 2015
    vai de nov/2015 a out/2016.
    """
    assert enso.ano_agricola_da_semeadura(pd.Timestamp(2015, 12, 1)) == 2015
    assert enso.ano_agricola_da_semeadura(pd.Timestamp(2015, 12, 31)) == 2015
    # E a classe deve ser a mesma do ano agrícola 2015 (El Niño na série real)
    classes, _, _ = enso.carregar_classificacao()
    classe_dez = enso.classe_da_semeadura(pd.Timestamp(2015, 12, 15), classes)
    classe_jan = enso.classe_da_semeadura(pd.Timestamp(2016, 1, 15), classes)
    # Ambas pertencem ao AA 2015 -> mesma classe.
    assert classe_dez == classe_jan, (
        f"dez/2015 e jan/2016 deveriam ter a mesma classe (AA 2015), "
        f"veio dez={classe_dez}, jan={classe_jan}")


def test_semeadura_jul_2010_aa_2009():
    """Semeação em jul/2010 -> AA 2009 (jul/10 ainda é AA 2009)."""
    assert enso.ano_agricola_da_semeadura(pd.Timestamp(2010, 7, 1)) == 2009


def test_semeadura_nov_2010_aa_2010():
    """Semeação em nov/2010 -> AA 2010 (nov/10 inicia AA 2010)."""
    assert enso.ano_agricola_da_semeadura(pd.Timestamp(2010, 11, 1)) == 2010


# ===========================================================================
# 2. resiliencia.calcular_score_agua
# ===========================================================================
def test_score_agua_proporcional():
    assert calcular_score_agua(300, 300) == pytest.approx(100.0)
    assert calcular_score_agua(150, 300) == pytest.approx(50.0)
    assert calcular_score_agua(0, 300) == 0.0


def test_score_agua_cap_em_100():
    """Chuva maior que demanda -> cap em 100."""
    assert calcular_score_agua(600, 300) == 100.0
    assert calcular_score_agua(1000, 300) == 100.0


def test_score_agua_erro_se_agua_zero():
    with pytest.raises(resiliencia.ResilienciaError):
        calcular_score_agua(100, 0)


# ===========================================================================
# 3. resiliencia.calcular_penalidade_calor
# ===========================================================================
def test_penalidade_zero_se_tmax_limite_vazio():
    """tmax_limite_c vazio -> penalidade 0 e registra lacuna."""
    pen, lacuna = calcular_penalidade_calor(35.0, None)
    assert pen == 0.0
    assert lacuna is True


def test_penalidade_zero_se_tmax_ciclo_none():
    """Sem dado de tmax_ciclo -> penalidade 0 e registra lacuna."""
    pen, lacuna = calcular_penalidade_calor(None, 38.0)
    assert pen == 0.0
    assert lacuna is True


def test_penalidade_zero_se_dentro_limite():
    """tmax dentro do limite -> 0 penalidade."""
    pen, lacuna = calcular_penalidade_calor(35.0, 38.0)
    assert pen == 0.0
    assert lacuna is False


def test_penalidade_positiva_se_acima_limite():
    """tmax acima do limite -> 5 pts por °C de excesso."""
    # 40 - 38 = 2°C acima -> 10 pts
    pen, lacuna = calcular_penalidade_calor(40.0, 38.0)
    assert pen == pytest.approx(10.0)
    assert lacuna is False


# ===========================================================================
# 4. resiliencia helpers de critérios agronômicos
# ===========================================================================
def test_escalar_1_3_para_0_100():
    assert _escalar_1_3_para_0_100(1) == 0.0
    assert _escalar_1_3_para_0_100(2) == 50.0
    assert _escalar_1_3_para_0_100(3) == 100.0
    assert _escalar_1_3_para_0_100(None) is None
    assert _escalar_1_3_para_0_100(5) is None  # fora da escala


def test_fixa_n_para_score():
    assert _fixa_n_para_score("sim") == 100.0
    assert _fixa_n_para_score("nao") == 0.0
    assert _fixa_n_para_score(None) is None
    assert _fixa_n_para_score("talvez") is None  # valor inesperado


# ===========================================================================
# 5. resiliencia.pontuar_cultura_cenario
# ===========================================================================
def test_pontuar_cultura_com_dados_completos():
    """Cultura com todos os critérios preenchidos -> score completo."""
    c = cultura(ciclo_dias=120, agua_mm_ciclo=600.0,
                tmax_limite_c=38.0, fixa_nitrogenio="sim",
                protecao_erosao=3, valor_mercado=2)
    sc = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=c, classe="La Niña",
        chuva_ciclo_mm=600.0, anos_usados=14,
        tmax_ciclo=35.0,   # dentro do limite -> sem penalidade
    )
    assert sc.score_agua == pytest.approx(100.0)
    assert sc.penalidade_calor == 0.0
    assert sc.score_cultura == pytest.approx(100.0)
    assert sc.fixa_nitrogenio == 100.0
    assert sc.protecao_erosao == 100.0
    assert sc.valor_mercado == 50.0
    assert sc.lacunas == []
    assert sc.anos_usados == 14


def test_pontuar_cultura_com_lacunas():
    """Cultura com lacunas (tmax, protecao, valor) -> critérios None."""
    c = cultura(ciclo_dias=120, agua_mm_ciclo=600.0,
                tmax_limite_c=None, fixa_nitrogenio="nao",
                protecao_erosao=None, valor_mercado=None)
    sc = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=c, classe="El Niño",
        chuva_ciclo_mm=480.0, anos_usados=12,
    )
    # score_agua = 480/600×100 = 80
    assert sc.score_agua == pytest.approx(80.0)
    # Sem tmax_limite -> penalidade 0
    assert sc.penalidade_calor == 0.0
    assert sc.score_cultura == pytest.approx(80.0)
    # Critérios vazios -> None
    assert sc.protecao_erosao is None
    assert sc.valor_mercado is None
    # fixa_n "nao" -> 0 (não lacuna)
    assert sc.fixa_nitrogenio == 0.0
    # Lacunas registradas
    assert "tmax_limite_c" in sc.lacunas
    assert "protecao_erosao" in sc.lacunas
    assert "valor_mercado" in sc.lacunas


def test_pontuar_cultura_sem_chuva_na_classe():
    """Sem anos na classe ENSO -> score_agua None."""
    c = cultura()
    sc = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=c, classe="neutro",
        chuva_ciclo_mm=None, anos_usados=0,
    )
    assert sc.score_agua is None
    assert sc.score_cultura is None
    assert "sem anos da classe ENSO" in sc.lacunas


def test_pontuar_cultura_agua_estimada():
    """Cultura com agua estimada (crotalaria) -> agua_estimada=True."""
    c = cultura(nome="crotalaria-juncea", ciclo_dias=120,
                agua_mm_ciclo=None)   # usa fallback 250
    sc = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=c, classe="La Niña",
        chuva_ciclo_mm=400.0, anos_usados=14,
    )
    assert sc.agua_estimada is True
    assert sc.agua_efetiva_mm == 250.0
    # score = 400/250×100 = 160 -> cap 100
    assert sc.score_agua == 100.0


# ===========================================================================
# 6. resiliencia.pontuar_rotacao_cenario (média ponderada com renormalização)
# ===========================================================================
def test_indice_rotacao_uma_cultura():
    """Rotação com uma cultura: índice = índice ponderado dela."""
    c = cultura(ciclo_dias=120, agua_mm_ciclo=600.0,
                tmax_limite_c=38.0, fixa_nitrogenio="sim",
                protecao_erosao=3, valor_mercado=3)
    sc = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=c, classe="La Niña",
        chuva_ciclo_mm=600.0, anos_usados=14, tmax_ciclo=35.0)
    sr = pontuar_rotacao_cenario([sc], "solo", "La Niña", "solo")
    # Com prioridade=solo: pesos solo = {agua:0.25, fixa:0.3, prot:0.3, valor:0.15}
    # score_agua=100, fixa=100, prot=100, valor=100 -> índice = 100
    assert sr.indice == pytest.approx(100.0)
    assert sr.rotacao == "solo"
    assert sr.classe == "La Niña"
    assert sr.prioridade == "solo"


def test_indice_rotacao_renormaliza_quando_criterio_vazio():
    """Se protecao_erosao e valor_mercado vazios, pesos renormalizam."""
    c = cultura(ciclo_dias=120, agua_mm_ciclo=600.0,
                tmax_limite_c=38.0, fixa_nitrogenio="sim",
                protecao_erosao=None, valor_mercado=None)
    sc = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=c, classe="El Niño",
        chuva_ciclo_mm=600.0, anos_usados=12, tmax_ciclo=35.0)
    # prioridade=agua: pesos = {agua:0.6, fixa:0.15, prot:0.15, valor:0.1}
    # Sem prot e valor: pesos usados = {agua:0.6, fixa:0.15} = 0.75 total
    # Renormalizado: agua=0.8, fixa=0.2
    # índice = 100×0.8 + 100×0.2 = 100
    sr = pontuar_rotacao_cenario([sc], "atual", "El Niño", "agua")
    assert sr.indice == pytest.approx(100.0)
    # Pesos usados devem ter só 2 chaves (agua + fixa_nitrogenio)
    assert set(sr.pesos_usados.keys()) == {"score_agua", "fixa_nitrogenio"}
    # Soma dos pesos = 1 (renormalizado)
    assert sum(sr.pesos_usados.values()) == pytest.approx(1.0)


def test_indice_rotacao_multiplas_culturas_media():
    """Rotação com 2 culturas: índice = média dos índices."""
    c1 = cultura(nome="milho", ciclo_dias=120, agua_mm_ciclo=600.0,
                 tmax_limite_c=None, fixa_nitrogenio="nao",
                 protecao_erosao=None, valor_mercado=None)
    c2 = cultura(nome="feijao-caupi", ciclo_dias=70, agua_mm_ciclo=325.0,
                 tmax_limite_c=None, fixa_nitrogenio="sim",
                 protecao_erosao=None, valor_mercado=None)
    sc1 = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=c1, classe="La Niña",
        chuva_ciclo_mm=600.0, anos_usados=14)
    sc2 = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=c2, classe="La Niña",
        chuva_ciclo_mm=325.0, anos_usados=14)
    # c1: score_agua=100, fixa=0 -> com prioridade=agua e só esses 2
    # critérios: pesos agua=0.6, fixa=0.15 -> renorm 0.8/0.2 -> 100×0.8+0×0.2=80
    # c2: score_agua=100, fixa=100 -> 100×0.8+100×0.2=100
    sr = pontuar_rotacao_cenario([sc1, sc2], "solo", "La Niña", "agua")
    # Média = (80 + 100)/2 = 90
    assert sr.indice == pytest.approx(90.0)


def test_indice_rotacao_none_se_todas_sem_score():
    """Se nenhuma cultura tem score_cultura, índice=None."""
    c = cultura()
    sc = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=c, classe="neutro",
        chuva_ciclo_mm=None, anos_usados=0)
    sr = pontuar_rotacao_cenario([sc], "atual", "neutro", "agua")
    assert sr.indice is None


def test_pior_cenario():
    """pior_cenario devolve a classe com menor índice."""
    c = cultura(ciclo_dias=120, agua_mm_ciclo=600.0, tmax_limite_c=None,
                fixa_nitrogenio="nao", protecao_erosao=None,
                valor_mercado=None)
    scores_por_classe = {}
    for classe, chuva in [("El Niño", 480), ("La Niña", 600), ("neutro", 400)]:
        sc = pontuar_cultura_cenario(
            df_clima=pd.DataFrame(), cultura=c, classe=classe,
            chuva_ciclo_mm=chuva, anos_usados=10)
        scores_por_classe[classe] = pontuar_rotacao_cenario(
            [sc], "atual", classe, "agua")
    # neutro tem chuva 400 (score_agua 66) -> menor índice
    pior_classe, pior_ind = pior_cenario(scores_por_classe)
    assert pior_classe == "neutro"
    assert pior_ind == scores_por_classe["neutro"].indice


# ===========================================================================
# 7. semaforo.cor_do_semaforo
# ===========================================================================
def test_cor_verde():
    assert cor_do_semaforo(5) == "verde"
    assert cor_do_semaforo(10) == "verde"


def test_cor_amarelo():
    assert cor_do_semaforo(3) == "amarelo"
    assert cor_do_semaforo(4) == "amarelo"


def test_cor_vermelho():
    assert cor_do_semaforo(2) == "vermelho"
    assert cor_do_semaforo(0) == "vermelho"
    assert cor_do_semaforo(-1) == "vermelho"


# ===========================================================================
# 8. semaforo.pontos_por_amostra_classe
# ===========================================================================
def test_pontos_amostra_grande():
    assert pontos_por_amostra_classe(12) == 2
    assert pontos_por_amostra_classe(10) == 2


def test_pontos_amostra_media():
    assert pontos_por_amostra_classe(9) == 1
    assert pontos_por_amostra_classe(5) == 1


def test_pontos_amostra_pequena():
    assert pontos_por_amostra_classe(4) == 0
    assert pontos_por_amostra_classe(0) == 0


# ===========================================================================
# 9. semaforo.calcular_semaforo
# ===========================================================================
def test_semaforo_milho_teresina_amarelo():
    """Milho em Teresina (El Niño, 12 anos): amostra +2, série +1,
    sem lacuna essencial +1, sem solo/NDVI = 4 pts -> amarelo.
    """
    s = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                            "valor_mercado"],
        usa_agua_estimada=False,
        local_calibrado=True,
        classe_avaliada="El Niño",
    )
    assert s.pontos == 4
    assert s.cor == "amarelo"
    # Evidências: 3 itens (amostra, série, sem lacuna essencial)
    assert len(s.evidencias) == 3


def test_semaforo_crotalaria_agua_estimada_desconta():
    """Crotalária (agua estimada) desconta 1 ponto."""
    s = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=["agua_mm_ciclo", "tmax_limite_c",
                            "protecao_erosao", "valor_mercado"],
        usa_agua_estimada=True,
        local_calibrado=True,
        classe_avaliada="El Niño",
    )
    # 4 (base) - 1 (agua estimada) = 3 -> amarelo
    # mas agua_mm_ciclo em lacunas_essenciais -> não soma ponto de
    # "sem lacuna essencial": -1. Fica: 2+1-1 = 2 -> vermelho
    assert s.pontos == 2
    assert s.cor == "vermelho"
    # A lacuna de agua_mm_ciclo está registrada
    assert any("agua_mm_ciclo" in l for l in s.lacunas)


def test_semaforo_local_nao_calibrado_desconta():
    """Milho em local fora de LOCAIS_VALIDADOS desconta 1 ponto."""
    s = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                            "valor_mercado"],
        usa_agua_estimada=False,
        local_calibrado=False,
        classe_avaliada="El Niño",
    )
    # 4 - 1 = 3 -> amarelo
    assert s.pontos == 3
    assert s.cor == "amarelo"
    assert config.AVISO_SEM_CALIBRACAO_LOCAL in " ".join(s.lacunas)


def test_semaforo_neutro_amostra_pequena():
    """Neutro tem 9 anos na série real -> +1 pt (5-9) em vez de +2."""
    s = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                            "valor_mercado"],
        usa_agua_estimada=False,
        local_calibrado=True,
        classe_avaliada="neutro",
    )
    # amostra 9 -> +1 (em vez de +2 para El Niño)
    # série +1, sem lacuna essencial +1 -> 3 pts -> amarelo
    assert s.pontos == 3
    assert s.cor == "amarelo"


def test_semaforo_verde_com_tudo_preenchido():
    """Com dados de solo + NDVI, sem lacunas, amostra grande -> verde."""
    s = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=[],   # sem lacunas
        usa_agua_estimada=False,
        local_calibrado=True,
        tem_dados_solo=True,
        tem_validacao_ndvi=True,
        classe_avaliada="El Niño",
    )
    # 2 (amostra) + 1 (série) + 1 (sem lacuna essencial) + 1 (solo) + 1 (NDVI) = 6
    assert s.pontos == 6
    assert s.cor == "verde"


def test_semaforo_vermelho_se_serie_curta_e_amostra_pequena():
    """Série <10 anos e classe <5 -> vermelho."""
    s = calcular_semaforo(
        n_anos_total=8,
        n_anos_por_classe={"El Niño": 3, "La Niña": 3, "neutro": 2},
        lacunas_essenciais=["agua_mm_ciclo"],
        usa_agua_estimada=True,
        local_calibrado=False,
        classe_avaliada="El Niño",
    )
    # 0 (amostra <5) + 0 (série <10) + 0 (lacuna essencial) - 1 (agua) - 1 (local) = -2
    assert s.pontos == -2
    assert s.cor == "vermelho"


def test_emoji_cor():
    assert emoji_cor("verde") == "🟢"
    assert emoji_cor("amarelo") == "🟡"
    assert emoji_cor("vermelho") == "🔴"


# ===========================================================================
# 9.b. Sem janela válida (revisão 2026-11-14) — desconto no semáforo
# ===========================================================================
def test_semaforo_sem_janela_valida_desconta():
    """Sem janela válida (False) desconta 1 ponto no semáforo."""
    s = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                            "valor_mercado"],
        usa_agua_estimada=False,
        local_calibrado=True,
        tem_janela_valida=False,    # <- sem janela
        classe_avaliada="El Niño",
    )
    # 4 (base) - 1 (sem janela) = 3 -> amarelo
    assert s.pontos == 3
    assert s.cor == "amarelo"
    assert any("sem janela" in l for l in s.lacunas)


def test_semaforo_com_janela_valida_nao_desconta():
    """Com janela válida (True, default) NÃO desconta."""
    s = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                            "valor_mercado"],
        usa_agua_estimada=False,
        local_calibrado=True,
        tem_janela_valida=True,     # <- janela válida
        classe_avaliada="El Niño",
    )
    assert s.pontos == 4
    assert s.cor == "amarelo"
    assert not any("sem janela" in l for l in s.lacunas)


def test_semaforo_sem_janela_e_local_nao_calibrado_desconta_2():
    """Combinação: sem janela (-1) + local não calibrado (-1) = -2."""
    s = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                            "valor_mercado"],
        usa_agua_estimada=False,
        local_calibrado=False,
        tem_janela_valida=False,
        classe_avaliada="El Niño",
    )
    # 4 - 1 (sem janela) - 1 (local) = 2 -> vermelho
    assert s.pontos == 2
    assert s.cor == "vermelho"


# ===========================================================================
# 9.c. melhor_mes_semeadura (revisão 2026-11-14)
# ===========================================================================
def test_melhor_mes_semeadura_sem_ciclo_dias_devolve_none():
    """Cultura sem ciclo_dias -> (None, False, None)."""
    c = cultura(ciclo_dias=None, agua_mm_ciclo=600.0)
    mes, tem_janela, chuva = resiliencia.melhor_mes_semeadura(
        df_clima=pd.DataFrame({"PRECTOTCORR": []}), cultura=c)
    assert mes is None
    assert tem_janela is False
    assert chuva is None


def test_melhor_mes_semeadura_escolhe_mes_janela_maior_chuva():
    """Com série sazonal (chuvosa nov-abr), o mês de semeadura deve ser
    um dos meses da chuvosa com maior chuva — e deve ser janela válida.
    """
    # Série: 10 mm/dia nov-abr (300 mm/mês), 0 mm/dia mai-out.
    idx = pd.date_range("2000-01-01", "2005-12-31", freq="D")
    valores = []
    for d in idx:
        valores.append(10.0 if d.month in (11, 12, 1, 2, 3, 4) else 0.0)
    df = pd.DataFrame({"PRECTOTCORR": valores}, index=idx)
    # Cultura com ciclo 70d, agua 325 mm (precisa 195 mm no ciclo).
    # Todos os meses da chuvosa passam. O de maior chuva deve ser o
    # escolhido (geralmente janeiro ou fevereiro, com chuva de 3 meses
    # dentro do ciclo).
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)
    mes, tem_janela, chuva = resiliencia.melhor_mes_semeadura(df, c)
    assert mes is not None
    assert 1 <= mes <= 12
    assert tem_janela is True
    assert chuva is not None and chuva > 0


def test_melhor_mes_semeadura_fallback_sem_janela_valida():
    """Se nenhum mês é janela (chuva baixa), usa o de maior chuva e marca
    'sem janela válida' (tem_janela_valida=False).
    """
    # Série com chuva uniforme baixa: 2 mm/dia = ~60 mm/mês.
    # Cultura com ciclo 120d, agua 600 mm (precisa 360 mm no ciclo).
    # Ciclo de 120 dias = ~240 mm (2×120) < 360 -> nenhum mês é janela.
    idx = pd.date_range("2000-01-01", "2005-12-31", freq="D")
    valores = [2.0] * len(idx)
    df = pd.DataFrame({"PRECTOTCORR": valores}, index=idx)
    c = cultura(ciclo_dias=120, agua_mm_ciclo=600.0)
    mes, tem_janela, chuva = resiliencia.melhor_mes_semeadura(df, c)
    # Mesmo sem janela, devolve um mês (o de maior chuva) com fallback.
    assert mes is not None
    assert tem_janela is False   # <- sem janela válida
    assert chuva is not None


def test_chuva_ciclo_por_classe_usa_mes_semeadura():
    """chuva_ciclo_por_classe com mes_semeadura=2 (fevereiro) deve
    classificar as semeaduras pelo ano agrícola correto (fev/Y -> AA Y-1).
    """
    # Série: chuva só em fevereiro (15 mm/dia = 420 mm/mês).
    idx = pd.date_range("2000-01-01", "2010-12-31", freq="D")
    valores = [15.0 if d.month == 2 else 0.0 for d in idx]
    df = pd.DataFrame({"PRECTOTCORR": valores}, index=idx)
    # Classificação mock: todos os anos El Niño.
    from core.enso import ClassificacaoAno
    classes_mock = [
        ClassificacaoAno(ano=y, oni=1.0, classe="El Niño", no_limite=False)
        for y in range(2000, 2010)]
    c = cultura(ciclo_dias=30, agua_mm_ciclo=100.0)  # ciclo curto
    # Semeio em fevereiro: fev/Y -> AA Y-1.
    chuvas = chuva_ciclo_por_classe(df, c, classes_mock, 2000, 2009,
                                     mes_semeadura=2)
    # Todos os anos mock são El Niño; as semeaduras fev/2001..fev/2010
    # caem em AA 2000..2009. Deve haver chuva em El Niño.
    med, n = chuvas["El Niño"]
    assert med is not None
    assert n > 0
    # La Niña e neutro não têm anos -> None
    assert chuvas["La Niña"][0] is None
    assert chuvas["neutro"][0] is None


# ===========================================================================
# 9.d. Risco hídrico + desempate do pior cenário (revisão 2026-11-14)
# ===========================================================================
def test_risco_hidrico_por_classe_basico():
    """Risco hídrico = % de anos com chuva < agua_efetiva."""
    # Série: 10 mm/dia em fevereiro (420 mm/mês), 0 nos outros.
    # Cultura: ciclo 30d, agua 200 mm (precisa 120 mm no ciclo).
    # Cada semeadura em fev dá 300 mm (10×30) > 200 -> 0% de risco.
    idx = pd.date_range("2000-01-01", "2010-12-31", freq="D")
    valores = [10.0 if d.month == 2 else 0.0 for d in idx]
    df = pd.DataFrame({"PRECTOTCORR": valores}, index=idx)
    from core.enso import ClassificacaoAno
    classes_mock = [
        ClassificacaoAno(ano=y, oni=1.0, classe="El Niño", no_limite=False)
        for y in range(2000, 2010)]
    c = cultura(ciclo_dias=30, agua_mm_ciclo=200.0)
    riscos = resiliencia.risco_hidrico_por_classe(
        df, c, classes_mock, 2000, 2009, mes_semeadura=2)
    # Semeio em fev -> 300 mm > 200 -> 0% de risco em todos os anos El Niño
    assert riscos["El Niño"] == 0.0
    assert riscos["La Niña"] is None
    assert riscos["neutro"] is None


def test_risco_hidrico_por_classe_alto():
    """Risco alto: chuva do ciclo sempre abaixo do limiar -> 100%."""
    # Série: 1 mm/dia (30 mm/mês), cultura ciclo 60d agua 500 mm
    # (precisa 300 mm no ciclo; ciclo 60d com 1mm/dia = 60 mm << 500).
    idx = pd.date_range("2000-01-01", "2005-12-31", freq="D")
    valores = [1.0] * len(idx)
    df = pd.DataFrame({"PRECTOTCORR": valores}, index=idx)
    from core.enso import ClassificacaoAno
    classes_mock = [
        ClassificacaoAno(ano=y, oni=1.0, classe="El Niño", no_limite=False)
        for y in range(2000, 2005)]
    c = cultura(ciclo_dias=60, agua_mm_ciclo=500.0)
    riscos = resiliencia.risco_hidrico_por_classe(
        df, c, classes_mock, 2000, 2004, mes_semeadura=6)
    # Todas as semeaduras têm chuva 60 mm < 500 -> 100% de risco
    assert riscos["El Niño"] == 100.0


def test_risco_hidrico_limiar_custom():
    """Risco com limiar custom (agua_mm_ciclo) sobrepõe agua_efetiva."""
    idx = pd.date_range("2000-01-01", "2005-12-31", freq="D")
    valores = [5.0] * len(idx)   # 150 mm/mês
    df = pd.DataFrame({"PRECTOTCORR": valores}, index=idx)
    from core.enso import ClassificacaoAno
    classes_mock = [
        ClassificacaoAno(ano=y, oni=1.0, classe="El Niño", no_limite=False)
        for y in range(2000, 2005)]
    c = cultura(ciclo_dias=30, agua_mm_ciclo=100.0)   # 150 mm > 100 -> 0%
    # Mas com limiar custom 200 mm: 150 < 200 -> 100%
    riscos = resiliencia.risco_hidrico_por_classe(
        df, c, classes_mock, 2000, 2004, mes_semeadura=6,
        agua_mm_ciclo=200.0)
    assert riscos["El Niño"] == 100.0


def test_pior_cenario_desempata_por_risco_hidrico():
    """Empate de índice: maior risco hídrico vence (pior cenário)."""
    # 3 cenários com mesmo índice (100) mas risco diferente.
    def _sc(classe, risco):
        return pontuar_cultura_cenario(
            df_clima=pd.DataFrame(), cultura=cultura(nome="x"),
            classe=classe, chuva_ciclo_mm=600.0, anos_usados=10,
            mes_semeadura=1, risco_hidrico_pct=risco)
    srs = {
        "El Niño": pontuar_rotacao_cenario(
            [_sc("El Niño", 8.0)], "atual", "El Niño", "agua"),
        "La Niña": pontuar_rotacao_cenario(
            [_sc("La Niña", 7.0)], "atual", "La Niña", "agua"),
        "neutro": pontuar_rotacao_cenario(
            [_sc("neutro", 11.0)], "atual", "neutro", "agua"),
    }
    # Todos têm índice 100 -> desempate pelo risco: neutro (11%) é pior.
    pior_classe, _ = pior_cenario(srs)
    assert pior_classe == "neutro"


def test_pior_cenario_menor_indice_vence_sem_desempate():
    """Se os índices diferem, o menor índice vence (não usa o risco)."""
    def _sc(classe, chuva, risco):
        return pontuar_cultura_cenario(
            df_clima=pd.DataFrame(), cultura=cultura(nome="x"),
            classe=classe, chuva_ciclo_mm=chuva, anos_usados=10,
            mes_semeadura=1, risco_hidrico_pct=risco)
    srs = {
        "El Niño": pontuar_rotacao_cenario(
            [_sc("El Niño", 600.0, 5.0)], "atual", "El Niño", "agua"),
        "La Niña": pontuar_rotacao_cenario(
            [_sc("La Niña", 300.0, 0.0)], "atual", "La Niña", "agua"),
        "neutro": pontuar_rotacao_cenario(
            [_sc("neutro", 600.0, 20.0)], "atual", "neutro", "agua"),
    }
    # La Niña tem índice menor (chuva 300 vs 600) -> pior, mesmo com risco 0.
    # El Niño e neutro têm o mesmo índice (maior); La Niña é o menor.
    pior_classe = pior_cenario(srs)[0]
    assert pior_classe == "La Niña"
    # Confirma que La Niña tem o menor índice
    assert srs["La Niña"].indice < srs["El Niño"].indice
    assert srs["La Niña"].indice < srs["neutro"].indice


def test_score_cultura_tem_risco_hidrico():
    """ScoreCultura tem o campo risco_hidrico_pct (default None)."""
    sc = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=cultura(),
        classe="El Niño", chuva_ciclo_mm=600.0, anos_usados=10)
    assert hasattr(sc, "risco_hidrico_pct")
    assert sc.risco_hidrico_pct is None  # default


def test_score_rotacao_tem_risco_hidrico_medio():
    """ScoreRotacaoCenario tem risco_hidrico_pct = média das culturas."""
    sc1 = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=cultura(nome="a"),
        classe="El Niño", chuva_ciclo_mm=600.0, anos_usados=10,
        risco_hidrico_pct=10.0)
    sc2 = pontuar_cultura_cenario(
        df_clima=pd.DataFrame(), cultura=cultura(nome="b"),
        classe="El Niño", chuva_ciclo_mm=600.0, anos_usados=10,
        risco_hidrico_pct=20.0)
    sr = pontuar_rotacao_cenario([sc1, sc2], "atual", "El Niño", "agua")
    assert sr.risco_hidrico_pct == 15.0   # (10+20)/2


# ===========================================================================
# 9.e. Safra 1 / Safra 2 (alternância) + janela pós-colheita (revisão 2026-11-14)
# ===========================================================================
def test_mes_da_colheita_basico():
    """Mês da colheita = semeadura + ceil(ciclo_dias/30) meses (mod 12)."""
    from core.resiliencia import mes_da_colheita
    # jan(1) + ceil(120/30)=4 meses -> mai(5)
    assert mes_da_colheita(1, 120) == 5
    # fev(2) + ceil(75/30)=3 meses -> mai(5)
    assert mes_da_colheita(2, 75) == 5
    # nov(11) + ceil(60/30)=2 meses -> jan(1) do ano seguinte
    assert mes_da_colheita(11, 60) == 1
    # jun(6) + ceil(30/30)=1 mês -> jul(7)
    assert mes_da_colheita(6, 30) == 7


def test_janela_pos_colheita_com_janela():
    """Se a cobertura tem janela no mês da colheita da safra 1, OK."""
    from core.resiliencia import janela_pos_colheita, mes_da_colheita
    # Mock: cobertura tem janela em jan-mai e nov-dez.
    r_cob = _resultado_janelas_mock_cobertura(
        meses_janela=(1, 2, 3, 4, 5, 11, 12))
    # Safra 1: milho semeado em jan, ciclo 120 -> colheita em maio (5).
    mes_colh = mes_da_colheita(1, 120)
    assert mes_colh == 5
    jpc = janela_pos_colheita(r_cob, mes_colh)
    assert jpc.tem_janela_pos_colheita is True
    assert jpc.aviso is None
    assert "Mai" in jpc.meses_disponiveis


def test_janela_pos_colheita_sem_janela_aviso():
    """Se a cobertura NÃO tem janela pós-colheita, aviso 'sem janela'."""
    from core.resiliencia import janela_pos_colheita, mes_da_colheita
    # Mock: cobertura só tem janela em nov-dez.
    r_cob = _resultado_janelas_mock_cobertura(meses_janela=(11, 12))
    # Safra 1: semeado em jan, colheita em maio (5) -> cobertura precisa
    # de janela em mai/jun/jul, mas cobertura só tem em nov-dez -> sem.
    jpc = janela_pos_colheita(r_cob, mes_da_colheita(1, 120))
    assert jpc.tem_janela_pos_colheita is False
    assert jpc.aviso is not None
    assert "sem janela" in jpc.aviso.lower()


def test_janela_pos_colheita_sem_data_colheita():
    """Sem mês de colheita (ciclo_dias vazio) -> aviso."""
    from core.resiliencia import janela_pos_colheita
    r_cob = _resultado_janelas_mock_cobertura()
    jpc = janela_pos_colheita(r_cob, None)
    assert jpc.tem_janela_pos_colheita is False
    assert "sem data de colheita" in jpc.aviso.lower()


def _resultado_janelas_mock_cobertura(meses_janela=(1, 2, 3, 11, 12)):
    """Mock de ResultadoJanelas para uma cultura de cobertura."""
    from core.janelas import ResultadoJanelas, JanelaMes
    janelas = []
    for m in range(1, 13):
        e_jan = m in meses_janela
        janelas.append(JanelaMes(
            mes=m, chuva_ciclo_mm=100.0 if e_jan else 50.0,
            chuva_estab_mm=50.0 if e_jan else 10.0,
            e_janela=e_jan,
            agua_necessaria_mm=60.0, estab_necessaria_mm=20.0,
            anos_usados=10,
        ))
    return ResultadoJanelas(
        cultura="crotalaria-juncea", ciclo_dias=90, agua_efetiva_mm=400.0,
        agua_estimada=False, estab_dias=30, estab_min_mm=20.0,
        janelas=janelas,
        meses_janela=[nome_mes_pt(m) for m in meses_janela],
    )


def nome_mes_pt(mes):
    nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    return nomes[mes - 1]


# ===========================================================================
# 10. Integração com o cache real (Teresina)
# ===========================================================================
def test_integracao_resiliencia_milho_teresina():
    """Carrega cache de Teresina, calcula índice do milho nos 3 cenários."""
    from core.nasa_power import carregar_series
    from core.enso import anos_agricolas_completos, carregar_classificacao
    from core.culturas import carregar_banco

    df, falhas, _ = carregar_series()
    assert not falhas
    completos, _ = anos_agricolas_completos(df)
    classes, _, _ = carregar_classificacao()
    banco = carregar_banco()
    milho = banco["milho"]

    chuvas = chuva_ciclo_por_classe(df, milho, classes,
                                    completos[0], completos[-1])
    indices = {}
    for classe in ("El Niño", "La Niña", "neutro"):
        med, n = chuvas[classe]
        if med is None:
            continue
        sc = pontuar_cultura_cenario(df, milho, classe, med, n)
        sr = pontuar_rotacao_cenario([sc], "atual", classe, "agua")
        indices[classe] = sr.indice
    # Todos os cenários têm índice (35 anos, 12/14/9 por classe)
    assert all(v is not None for v in indices.values())
    # La Niña tende a ser melhor em Teresina (mais chuva)
    # Não afirmamos ordem exata, mas pelo menos todos > 0
    assert all(v > 0 for v in indices.values())


def test_integracao_semaforo_real():
    """Semáforo real do milho em Teresina nos 3 cenários."""
    from core.enso import carregar_classificacao

    classes, contagem, _ = carregar_classificacao()
    for classe in ("El Niño", "La Niña", "neutro"):
        s = calcular_semaforo(
            n_anos_total=35,
            n_anos_por_classe=contagem,
            lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                                "valor_mercado"],
            usa_agua_estimada=False,
            local_calibrado=True,
            classe_avaliada=classe,
        )
        # Sem solo/NDVI -> no máximo amarelo (não verde)
        assert s.cor in ("amarelo", "vermelho")
        assert s.pontos >= 0   # milho com dados não fica negativo
