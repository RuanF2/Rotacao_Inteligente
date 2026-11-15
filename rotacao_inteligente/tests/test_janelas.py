"""
tests/test_janelas.py - Testes da Etapa 5 (core/janelas.py).

Valida:
- Detecção de janela: mês é janela se passar em DOIS critérios
  (ajuste 2026-11-14):
  (1) mediana da chuva do ciclo >= agua_efetiva × FATOR_MINIMO_CHUVA
  (2) mediana da chuva dos primeiros JANELA_ESTABELECIMENTO_DIAS (30)
      dias >= CHUVA_MINIMA_ESTABELECIMENTO_MM (20)
- Tratamento de lacunas (briefing 6.1):
  - Sem ciclo_dias: não calcula, avisa.
  - Sem agua_mm_ciclo: usa config.CHUVA_MINIMA_CICLO_MM e marca
    "parâmetro estimado pela equipe" (agua_estimada=True).
  - Sem chuva no DataFrame: avisa.
- Funções puras auxiliares (agua_necessaria, chuva_do_ciclo, nome_mes).
- meses_livres (calendário) filtra os meses que o agricultor informou.
- Caso problemático: chuva no ciclo mas seca na germinação -> NÃO janela.
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
from core import janelas
from core.janelas import (JanelaMes, ResultadoJanelas, calcular_janelas,
                          janelas_para_dataframe, agua_necessaria,
                          chuva_do_ciclo, nome_mes)
from core.culturas import Cultura


# ---------------------------------------------------------------------------
# Helpers para construir Culturas e DataFrames de teste
# ---------------------------------------------------------------------------
def cultura(nome="feijao-caupi", tipo="comercial", ciclo_dias=70,
            agua_mm_ciclo=325.0, **kwargs) -> Cultura:
    """Cria uma Cultura para teste (todos os outros campos None)."""
    return Cultura(
        nome=nome, tipo=tipo, ciclo_dias=ciclo_dias,
        agua_mm_ciclo=agua_mm_ciclo, tmax_limite_c=None,
        fixa_nitrogenio=None, protecao_erosao=None, valor_mercado=None,
        taxa_semeadura_kg_ha=None, rendimento_potencial_kg_ha=None,
        rendimento_regional_kg_ha=None, fonte="", lacunas=[],
    )


def serie_chuva(ano_inicio, ano_fim, chuva_diaria_mm=5.0):
    """Cria uma Series diária de chuva (todos os dias com o mesmo valor).

    Período: 1/jan/ano_inicio a 31/dez/ano_fim. Cada dia recebe
    `chuva_diaria_mm` (mm/dia), o que dá chuva_diaria × 30 ≈ 150 mm/mês.
    """
    idx = pd.date_range(f"{ano_inicio}-01-01", f"{ano_fim}-12-31", freq="D")
    return pd.Series(chuva_diaria_mm, index=idx, name="PRECTOTCORR")


def df_chuva(ano_inicio, ano_fim, chuva_diaria_mm=5.0) -> pd.DataFrame:
    """DataFrame com coluna PRECTOTCORR, pronto para calcular_janelas."""
    s = serie_chuva(ano_inicio, ano_fim, chuva_diaria_mm)
    return s.to_frame()


def serie_chuva_estacional(ano_inicio, ano_fim):
    """Série com chuva sazonal: 10 mm/dia nov-abr, 0 mm/dia mai-out.

    Simula o regime do semiárido piauiense (chuvosa nov-abr, seco mai-out).
    Usado para testar que só os meses da chuvosa viram janela.
    """
    idx = pd.date_range(f"{ano_inicio}-01-01", f"{ano_fim}-12-31", freq="D")
    valores = []
    for d in idx:
        if d.month in (11, 12, 1, 2, 3, 4):
            valores.append(10.0)   # 10 mm/dia = ~300 mm/mês
        else:
            valores.append(0.0)    # seca
    return pd.Series(valores, index=idx, name="PRECTOTCORR")


# ---------------------------------------------------------------------------
# 1. Funções auxiliares puras
# ---------------------------------------------------------------------------
def test_nome_mes():
    assert nome_mes(1) == "Jan"
    assert nome_mes(12) == "Dez"
    assert nome_mes(7) == "Jul"


def test_nome_mes_invalido():
    with pytest.raises(janelas.JanelasError, match="mês inválido"):
        nome_mes(0)
    with pytest.raises(janelas.JanelasError, match="mês inválido"):
        nome_mes(13)


def test_agua_necessaria_usa_fator_do_config():
    # 325 × 0.6 = 195
    assert agua_necessaria(325.0) == pytest.approx(195.0)
    assert agua_necessaria(250.0) == pytest.approx(150.0)
    assert agua_necessaria(600.0) == pytest.approx(360.0)


def test_agua_necessaria_respeita_fator_alternativo():
    # Se alguém mudar o fator no config, a função acompanha.
    assert agua_necessaria(100.0, fator=0.5) == 50.0
    assert agua_necessaria(100.0, fator=1.0) == 100.0


def test_chuva_do_ciclo_soma_dias():
    # 5 mm/dia × 10 dias = 50 mm
    s = serie_chuva(2000, 2000, chuva_diaria_mm=5.0)
    soma = chuva_do_ciclo(s, pd.Timestamp(2000, 6, 1), ciclo_dias=10)
    assert soma == pytest.approx(50.0)


def test_chuva_do_ciclo_respeita_limite_do_ciclo():
    # 5 mm/dia × 30 dias = 150 mm (não soma mais que o ciclo)
    s = serie_chuva(2000, 2000, chuva_diaria_mm=5.0)
    soma_30 = chuva_do_ciclo(s, pd.Timestamp(2000, 6, 1), ciclo_dias=30)
    soma_60 = chuva_do_ciclo(s, pd.Timestamp(2000, 6, 1), ciclo_dias=60)
    assert soma_30 == pytest.approx(150.0)
    assert soma_60 == pytest.approx(300.0)


def test_chuva_do_ciclo_none_se_faltar_mais_de_20_porcento():
    # Série curta demais para o ciclo pedido.
    s = serie_chuva(2000, 2000, chuva_diaria_mm=5.0)
    # Ciclo de 365 dias a partir de 1/dez sobra poucos dias no ano.
    soma = chuva_do_ciclo(s, pd.Timestamp(2000, 12, 1), ciclo_dias=365)
    assert soma is None


# ---------------------------------------------------------------------------
# 2. Cultura sem ciclo_dias -> não calcula, avisa
# ---------------------------------------------------------------------------
def test_sem_ciclo_dias_nao_calcula():
    """Sem ciclo_dias, devolve aviso e janelas vazias (briefing 6.1)."""
    c = cultura(ciclo_dias=None, agua_mm_ciclo=325.0)
    df = df_chuva(2000, 2002)
    r = calcular_janelas(df, c)
    assert r.ciclo_dias is None
    assert r.agua_efetiva_mm is None
    assert r.janelas == []
    assert r.meses_janela == []
    assert r.aviso_geral is not None
    assert "sem ciclo_dias" in r.aviso_geral


# ---------------------------------------------------------------------------
# 3. Cultura sem agua_mm_ciclo -> usa fallback (estimada)
# ---------------------------------------------------------------------------
def test_sem_agua_mm_ciclo_usa_fallback_estimada():
    """Sem agua_mm_ciclo, usa config.CHUVA_MINIMA_CICLO_MM e marca estimada."""
    c = cultura(ciclo_dias=70, agua_mm_ciclo=None)
    df = df_chuva(2000, 2002, chuva_diaria_mm=10.0)  # 300 mm/mês
    r = calcular_janelas(df, c)
    assert r.ciclo_dias == 70
    assert r.agua_efetiva_mm == config.CHUVA_MINIMA_CICLO_MM
    assert r.agua_efetiva_mm == 250
    assert r.agua_estimada is True
    # Aviso geral menciona "parâmetro estimado pela equipe"
    assert r.aviso_geral is not None
    assert config.AVISO_PARAMETRO_ESTIMADO in r.aviso_geral
    # Água necessária = 250 × 0.6 = 150
    assert r.janelas[0].agua_necessaria_mm == pytest.approx(150.0)


def test_com_agua_mm_ciclo_nao_e_estimada():
    """Com agua_mm_ciclo no CSV, agua_estimada=False e aviso_geral=None."""
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)
    df = df_chuva(2000, 2002, chuva_diaria_mm=10.0)
    r = calcular_janelas(df, c)
    assert r.agua_efetiva_mm == 325.0
    assert r.agua_estimada is False
    # Sem aviso de estimativa (pode haver outros avisos, mas não de estimativa)
    if r.aviso_geral:
        assert config.AVISO_PARAMETRO_ESTIMADO not in r.aviso_geral


# ---------------------------------------------------------------------------
# 4. Sem dado de chuva -> avisa
# ---------------------------------------------------------------------------
def test_sem_dataframe_avisa():
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)
    r = calcular_janelas(pd.DataFrame(), c)
    assert r.janelas == []
    assert r.aviso_geral is not None
    assert "chuva" in r.aviso_geral.lower() or "PRECTOTCORR" in r.aviso_geral


def test_sem_coluna_prectotcorr_avisa():
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)
    df = pd.DataFrame({"T2M": [25.0]}, index=pd.date_range("2000-01-01",
                                                            periods=1))
    r = calcular_janelas(df, c)
    assert r.janelas == []
    assert r.aviso_geral is not None


def test_coluna_prectotcorr_toda_nan_avisa():
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)
    idx = pd.date_range("2000-01-01", "2000-12-31", freq="D")
    df = pd.DataFrame({"PRECTOTCORR": [np.nan] * len(idx)}, index=idx)
    r = calcular_janelas(df, c)
    assert r.janelas == []
    assert r.aviso_geral is not None


# ---------------------------------------------------------------------------
# 5. Detecção de janela: mês é janela se mediana >= agua × 0.6
# ---------------------------------------------------------------------------
def test_chuva_alta_todos_meses_sao_janela():
    """10 mm/dia × 70 dias = 700 mm; precisa 195 mm -> todos os 12 são janela.

    Para a maioria dos meses, todos os 6 anos (2000-2005) têm o ciclo
    completo dentro da série. EXCEÇÃO: dezembro — o ciclo de 70 dias
    a partir de 1/dez/2005 ultrapassa o fim da série (sem 2006), então
    esse ano é descartado pela regra de "menos de 80% dos dias" e
    ficam só 5 anos. Isso é o comportamento correto (não subestimar a
    janela com ciclos incompletos).
    """
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)  # precisa 195 mm
    df = df_chuva(2000, 2005, chuva_diaria_mm=10.0)  # 700 mm no ciclo
    r = calcular_janelas(df, c)
    assert len(r.janelas) == 12
    assert all(jm.e_janela for jm in r.janelas)
    assert len(r.meses_janela) == 12
    # A mediana de cada mês deve ser 700 mm
    for jm in r.janelas:
        assert jm.chuva_ciclo_mm == pytest.approx(700.0, rel=0.01)
    # Janeiro a novembro: 6 anos. Dezembro: 5 anos (ciclo não cabe em 2005).
    for jm in r.janelas:
        if jm.mes == 12:
            assert jm.anos_usados == 5
        else:
            assert jm.anos_usados == 6


def test_chuva_baixa_nenhum_mes_e_janela():
    """1 mm/dia × 70 dias = 70 mm; precisa 195 mm -> nenhum é janela."""
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)  # precisa 195 mm
    df = df_chuva(2000, 2005, chuva_diaria_mm=1.0)  # 70 mm no ciclo
    r = calcular_janelas(df, c)
    assert len(r.janelas) == 12
    assert not any(jm.e_janela for jm in r.janelas)
    assert r.meses_janela == []


def test_chuva_sazonal_so_meses_chuvosos_sao_janela():
    """Série sazonal (10 mm/dia nov-abr, 0 mai-out) com ciclo 90 dias.

    Para uma cultura de 90 dias e agua_efetiva=250 (precisa 150 mm):
    - Semeadura em out/dez/jan/fev/mar: o ciclo pega pelo menos parte da
      chuvosa -> soma >= 150 mm -> JANELA.
    - Semeadura em mai/jun/jul/ago: ciclo inteiro na seca -> 0 mm -> NÃO.
    - Abr e set são borda: dependem do mês exato.
    """
    c = cultura(ciclo_dias=90, agua_mm_ciclo=None)  # usa 250 (estimada)
    s = serie_chuva_estacional(2000, 2010)
    df = s.to_frame()
    r = calcular_janelas(df, c)
    assert len(r.janelas) == 12
    # Meses que certamente são janela (chuvosa forte no ciclo)
    meses_pt = {jm.mes: jm.e_janela for jm in r.janelas}
    for mes in (11, 12, 1, 2):  # nov, dez, jan, fev
        assert meses_pt[mes] is True, f"mês {mes} deveria ser janela"
    # Meses que certamente NÃO são (ciclo inteiro na seca)
    for mes in (5, 6, 7):  # mai, jun, jul
        assert meses_pt[mes] is False, f"mês {mes} NÃO deveria ser janela"


# ---------------------------------------------------------------------------
# 6. Usa mediana entre anos (robusta a outliers)
# ---------------------------------------------------------------------------
def test_usa_mediana_entre_anos_nao_media():
    """Se 1 ano é outlier (muita chuva) e 4 são normais, a mediana
    acompanha os 4 normais — não o outlier.

    4 anos com 100 mm no ciclo + 1 ano com 2000 mm. Mediana = 100 mm.
    Se estivesse usando média, seria (4×100 + 2000)/5 = 480 mm.
    """
    c = cultura(ciclo_dias=30, agua_mm_ciclo=200.0)  # precisa 120 mm
    # 5 anos: 4 secos (3.33 mm/dia × 30 = 100 mm), 1 molhado (66 mm/dia)
    idx = pd.date_range("2000-01-01", "2004-12-31", freq="D")
    valores = []
    for d in idx:
        if d.year == 2002:
            valores.append(66.67)  # outlier
        else:
            valores.append(3.33)   # normal
    df = pd.DataFrame({"PRECTOTCORR": valores}, index=idx)
    r = calcular_janelas(df, c, anos_agricolas_completos=[2000, 2001, 2002,
                                                          2003, 2004])
    # Todos os meses: mediana ≈ 100 mm (4 anos normais) < 120 mm -> não janela
    for jm in r.janelas:
        # Mediana entre 5 valores: 100 (4 normais) ou 100 (a mediana pega
        # o 3º de 5 valores ordenados, que é 100).
        assert jm.chuva_ciclo_mm == pytest.approx(100.0, abs=5.0)
        assert jm.e_janela is False  # 100 < 120


# ---------------------------------------------------------------------------
# 7. Filtro por anos agrícolas completos
# ---------------------------------------------------------------------------
def test_filtra_anos_agricolas_completos():
    """Se passar só alguns anos, só esses entram na mediana."""
    c = cultura(ciclo_dias=30, agua_mm_ciclo=100.0)  # precisa 60 mm
    df = df_chuva(2000, 2005, chuva_diaria_mm=5.0)  # 150 mm no ciclo
    # Passa só 2 anos
    r = calcular_janelas(df, c, anos_agricolas_completos=[2000, 2001])
    for jm in r.janelas:
        assert jm.anos_usados == 2


# ---------------------------------------------------------------------------
# 8. meses_livres (calendário do agricultor) — Etapa 7 vai usar
# ---------------------------------------------------------------------------
def test_meses_livres_filtra_meses_nao_informados():
    """Se o agricultor disse que o campo está livre em [11, 12, 1], os
    outros meses ficam com aviso 'não livre' e e_janela=False."""
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)
    df = df_chuva(2000, 2002, chuva_diaria_mm=10.0)  # tudo é janela
    r = calcular_janelas(df, c, meses_livres=[11, 12, 1])
    # Meses livres: 1, 11, 12 -> e_janela=True
    meses_livres_resultado = {jm.mes for jm in r.janelas if jm.e_janela}
    assert meses_livres_resultado == {1, 11, 12}
    # Os outros: aviso de "não livre"
    for jm in r.janelas:
        if jm.mes not in (1, 11, 12):
            assert jm.e_janela is False
            assert jm.aviso is not None
            assert "não livre" in jm.aviso


def test_meses_livres_none_nao_filtra():
    """Se meses_livres=None (default), todos os meses são avaliados."""
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)
    df = df_chuva(2000, 2002, chuva_diaria_mm=10.0)
    r = calcular_janelas(df, c, meses_livres=None)
    # Nenhum mês tem aviso de "não livre"
    for jm in r.janelas:
        if jm.aviso:
            assert "não livre" not in jm.aviso


# ---------------------------------------------------------------------------
# 9. janelas_para_dataframe()
# ---------------------------------------------------------------------------
def test_janelas_para_dataframe_tem_12_linhas():
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)
    df = df_chuva(2000, 2002, chuva_diaria_mm=10.0)
    r = calcular_janelas(df, c)
    df_out = janelas_para_dataframe(r)
    assert len(df_out) == 12
    # Colunas novas incluem chuva_estab_mm e estab_necessaria_mm
    assert set(df_out.columns) == {
        "mes", "mes_nome", "chuva_ciclo_mm", "chuva_estab_mm",
        "agua_necessaria_mm", "estab_necessaria_mm", "e_janela",
    }
    assert df_out["mes_nome"].tolist()[0] == "Jan"
    assert df_out["mes_nome"].tolist()[-1] == "Dez"
    # A coluna de chuva de estabelecimento deve ter valores (não NaN)
    # quando há dado de chuva suficiente.
    assert df_out["chuva_estab_mm"].notna().any()


def test_janelas_para_dataframe_cultura_sem_dados():
    """Cultura sem ciclo_dias -> DataFrame vazio."""
    c = cultura(ciclo_dias=None, agua_mm_ciclo=325.0)
    df = df_chuva(2000, 2002)
    r = calcular_janelas(df, c)
    df_out = janelas_para_dataframe(r)
    assert df_out.empty


# ---------------------------------------------------------------------------
# 9.b. Critério de ESTABELECIMENTO (ajuste 2026-11-14)
# ---------------------------------------------------------------------------
def test_estabelecimento_reprova_chuva_no_ciclo_mas_seca_na_germinacao():
    """Caso problemático do briefing: chuva suficiente no ciclo inteiro,
    mas seca nos primeiros 30 dias (semente não germina) -> NÃO janela.

    Construímos uma série em que a semeadura em setembro tem:
      - primeiros 30 dias (setembro inteiro): 0 mm (seca — germinação falha)
      - restantes do ciclo de 120 dias (out-dez): 6 mm/dia = ~540 mm,
        suficiente para o ciclo inteiro (~540 mm >= 150 mm)

    A mediana da chuva do ciclo passa, mas a de estabelecimento
    (0 mm) reprova. O mês NÃO é janela.
    """
    c = cultura(ciclo_dias=120, agua_mm_ciclo=250.0)  # precisa 150 mm no ciclo
    # 3 anos; cada ano: setembro seco, outubro-dezembro chuvoso.
    idx = pd.date_range("2000-01-01", "2002-12-31", freq="D")
    valores = []
    for d in idx:
        if d.month == 9:
            valores.append(0.0)     # seca na germinação (primeiros 30 dias)
        elif d.month in (10, 11, 12):
            valores.append(6.0)      # 6 mm/dia = ~180 mm/mês depois do estab.
        else:
            valores.append(0.0)
    df = pd.DataFrame({"PRECTOTCORR": valores}, index=idx)
    r = calcular_janelas(df, c, anos_agricolas_completos=[2000, 2001, 2002])
    # Localiza setembro (mês 9)
    jm_set = next(jm for jm in r.janelas if jm.mes == 9)
    # Chuva do ciclo: primeiros 30 dias (set) = 0 + restante (out-dez) = ~540 mm
    assert jm_set.chuva_ciclo_mm is not None
    assert jm_set.chuva_ciclo_mm >= 150.0  # ciclo passa
    # Chuva de estabelecimento: primeiros 30 dias de setembro = 0 mm
    assert jm_set.chuva_estab_mm == pytest.approx(0.0)
    # O mês NÃO é janela (estabelecimento falhou)
    assert jm_set.e_janela is False
    assert jm_set.aviso is not None
    assert "estabelecimento" in jm_set.aviso


def test_estabelecimento_aprovado_quando_chuva_na_germinacao():
    """Se os primeiros 30 dias têm >= 20 mm e o ciclo passa, é janela."""
    # 6 mm/dia = 180 mm nos 30 dias (>= 20 mm OK); ciclo 70 dias = 420 mm
    # (>= 195 mm para caupi OK).
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)
    df = df_chuva(2000, 2005, chuva_diaria_mm=6.0)
    r = calcular_janelas(df, c)
    assert len(r.janelas) == 12
    # Todos os meses com ciclo completo passam nos dois critérios.
    for jm in r.janelas:
        if jm.chuva_ciclo_mm is not None:
            assert jm.chuva_estab_mm == pytest.approx(180.0, rel=0.05)
            assert jm.e_janela is True


def test_estab_min_e_dias_do_config():
    """O resultado carrega estab_dias e estab_min_mm do config."""
    c = cultura(ciclo_dias=70, agua_mm_ciclo=325.0)
    df = df_chuva(2000, 2002, chuva_diaria_mm=10.0)
    r = calcular_janelas(df, c)
    assert r.estab_dias == config.JANELA_ESTABELECIMENTO_DIAS
    assert r.estab_dias == 30
    assert r.estab_min_mm == config.CHUVA_MINIMA_ESTABELECIMENTO_MM
    assert r.estab_min_mm == 20.0
    for jm in r.janelas:
        assert jm.estab_necessaria_mm == 20.0


# ---------------------------------------------------------------------------
# 10. Integração com o cache real (offline) — usa Teresina
# ---------------------------------------------------------------------------
def test_integracao_cache_real_teresina():
    """Carrega o cache da NASA POWER para Teresina e calcula janelas do
    feijão-caupi. Apenas confere que roda e devolve 12 janelas — sem
    afirmar valores específicos (o cache pode mudar de versão da API).
    """
    from core.nasa_power import carregar_series
    from core.enso import anos_agricolas_completos
    from core.culturas import carregar_banco

    df, falhas, _ = carregar_series()
    assert "PRECTOTCORR" in df.columns
    assert not falhas
    completos, _ = anos_agricolas_completos(df)
    assert len(completos) > 0

    banco = carregar_banco()
    c = banco["feijao-caupi"]
    r = calcular_janelas(df, c, anos_agricolas_completos=completos)
    assert r.cultura == "feijao-caupi"
    assert r.ciclo_dias == 70
    assert r.agua_efetiva_mm == 325.0
    assert r.agua_estimada is False
    assert len(r.janelas) == 12
    # No semiárido piauiense, DEZ-JAN-FEV-MAR devem ser janela (chuvosa)
    # e MAI-JUN-JUL-AGO não (seca). Confirma o padrão sazonal.
    meses = {jm.mes: jm.e_janela for jm in r.janelas}
    assert meses[12] is True     # dezembro
    assert meses[1] is True      # janeiro
    assert meses[2] is True       # fevereiro
    assert meses[6] is False      # junho (seca)
    assert meses[7] is False      # julho (seca)


def test_integracao_cache_real_cobertura_estimada():
    """Cobertura sem agua_mm_ciclo: usa fallback 250 e marca estimada."""
    from core.nasa_power import carregar_series
    from core.enso import anos_agricolas_completos
    from core.culturas import carregar_banco

    df, _, _ = carregar_series()
    completos, _ = anos_agricolas_completos(df)
    banco = carregar_banco()
    c = banco["crotalaria-juncea"]
    r = calcular_janelas(df, c, anos_agricolas_completos=completos)
    assert r.ciclo_dias == 120
    assert r.agua_efetiva_mm == 250
    assert r.agua_estimada is True
    assert r.aviso_geral is not None
    assert config.AVISO_PARAMETRO_ESTIMADO in r.aviso_geral
    assert len(r.janelas) == 12


def test_integracao_cache_real_crotalaria_setembro_reprovada_por_estab():
    """Caso problemático do briefing: crotalária em setembro em Teresina
    passa no critério do ciclo (160 mm) mas REPROVA no de estabelecimento
    (4 mm nos primeiros 30 dias < 20 mm). Isso é o ajuste 2026-11-14.
    """
    from core.nasa_power import carregar_series
    from core.enso import anos_agricolas_completos
    from core.culturas import carregar_banco

    df, _, _ = carregar_series()
    completos, _ = anos_agricolas_completos(df)
    banco = carregar_banco()
    c = banco["crotalaria-juncea"]
    r = calcular_janelas(df, c, anos_agricolas_completos=completos)
    jm_set = next(jm for jm in r.janelas if jm.mes == 9)
    # Ciclo passa (160 mm >= 150 mm), estabelecimento reprova (4 mm < 20 mm)
    assert jm_set.chuva_ciclo_mm >= 150.0
    assert jm_set.chuva_estab_mm < 20.0
    assert jm_set.e_janela is False
    assert "estabelecimento" in jm_set.aviso


# ---------------------------------------------------------------------------
# 11. Integração multi-município (Teresina, Picos, São Raimundo Nonato)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nome_local,lat,lon", [
    ("Teresina-PI", -5.09, -42.81),
    ("Picos-PI", -7.07694, -41.46694),
    ("São Raimundo Nonato-PI", -9.015, -42.69889),
])
def test_janelas_caupi_milho_crotalaria_nos_3_municipios(nome_local, lat, lon):
    """Para cada um dos 3 municípios validados, calcula as janelas de
    feijao-caupi, milho e crotalaria-juncea. Confirma que:

    - Devolve 12 janelas (jan..dez) para cada cultura.
    - caupi e milho usam agua_efetiva do CSV (não estimada).
    - crotalaria usa agua_efetiva=250 (estimada).
    - Pelo menos UM mês é janela (chuvosa existe em todos os 3).
    - Os meses de seca (jun-ago) NÃO são janela.

    Este teste documenta o comportamento; a lista final de meses-janela
    é impressa no relatório (não afirmamos valores exatos, pois o cache
    pode mudar entre versões da API).
    """
    from core.nasa_power import carregar_series
    from core.enso import anos_agricolas_completos
    from core.culturas import carregar_banco

    df, falhas, _ = carregar_series(lat=lat, lon=lon,
                                     ano_inicio=config.ANO_INICIO_SERIE,
                                     ano_fim=config.ANO_FIM_SERIE)
    assert not falhas, f"{nome_local}: falhas ao carregar clima: {falhas}"
    assert "PRECTOTCORR" in df.columns
    completos, _ = anos_agricolas_completos(df)
    assert len(completos) > 0, f"{nome_local}: sem anos agrícolas completos"

    banco = carregar_banco()
    for nome_cultura in ("feijao-caupi", "milho", "crotalaria-juncea"):
        c = banco[nome_cultura]
        r = calcular_janelas(df, c, anos_agricolas_completos=completos)
        assert r.cultura == nome_cultura
        assert len(r.janelas) == 12, f"{nome_local}/{nome_cultura}: 12 janelas"
        # caupi e milho: agua do CSV (não estimada)
        if nome_cultura in ("feijao-caupi", "milho"):
            assert r.agua_estimada is False
        # crotalaria: agua estimada (250 mm)
        if nome_cultura == "crotalaria-juncea":
            assert r.agua_estimada is True
            assert r.agua_efetiva_mm == 250
        # Em todos os 3 municípios do semiárido piauiense, junho/julho
        # são meses secos (sem janela). Janeiro/dezembro são chuvosos.
        meses = {jm.mes: jm.e_janela for jm in r.janelas}
        assert meses[6] is False, f"{nome_local}/{nome_cultura}: jun não é seca?"
        assert meses[7] is False, f"{nome_local}/{nome_cultura}: jul não é seca?"
        assert meses[1] is True, f"{nome_local}/{nome_cultura}: jan não é janela?"
        # Pelo menos um mês é janela
        assert any(jm.e_janela for jm in r.janelas), \
            f"{nome_local}/{nome_cultura}: nenhuma janela"
