"""
tests/test_etapa7.py - Testes da Etapa 7 (alerta + dados de solo).

Valida:
- core/alerta.py: alerta simulado de plantio.
  - Em mês-janela com chuva/umidade OK (ou sem limiar) -> PLANTE AGORA.
  - Em mês-janela com chuva/umidade abaixo do limiar -> AGUARDE.
  - Fora da janela -> NÃO PLANTE.
  - Sem limiares (config None) -> só usa janela, registra lacuna.
- core/solo.py: dados de solo informados pelo usuário.
  - DadosSolo.informado = True se pelo menos 1 campo preenchido.
  - Valores inválidos viram None (não bloqueiam o app).
  - Semáforo soma +1 se DadosSolo.informado (testado via calcular_semaforo).
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from core import alerta, solo
from core.alerta import Alerta, calcular_alerta, chuva_ultimos_7d
from core.solo import DadosSolo, criar_dados_solo
from core.semaforo import calcular_semaforo


# ===========================================================================
# 1. solo.DadosSolo / criar_dados_solo
# ===========================================================================
def test_solo_vazio_nao_informado():
    s = criar_dados_solo()
    assert s.informado is False


def test_solo_com_dados_informado():
    s = criar_dados_solo(textura="arenoza", profundidade_cm=30,
                         materia_organica_pct=1.5, ph=5.8)
    assert s.informado is True
    assert s.textura == "arenoza"
    assert s.profundidade_cm == 30
    assert s.materia_organica_pct == 1.5
    assert s.ph == 5.8


def test_solo_um_campo_nao_basta():
    """Só 1 campo estruturado NÃO conta (exige >= 2, revisão 2026-11-14)."""
    s = criar_dados_solo(textura="argilosa")
    assert s.informado is False


def test_solo_dois_campos_basta():
    """2 campos estruturados preenchidos contam como informado."""
    s = criar_dados_solo(textura="argilosa", profundidade_cm=30)
    assert s.informado is True


def test_solo_observacao_nao_conta():
    """Só observações (texto livre) NÃO conta (revisão 2026-11-14)."""
    s = criar_dados_solo(observacoes="solo vermelho, bem drenado")
    assert s.informado is False


def test_solo_observacao_mais_um_campo_nao_basta():
    """Observações + 1 campo estruturado NÃO conta (precisa de 2
    estruturados; observações não contam)."""
    s = criar_dados_solo(textura="arenoza",
                         observacoes="solo vermelho, bem drenado")
    assert s.informado is False


def test_solo_observacao_mais_dois_campos_basta():
    """Observações + 2 campos estruturados conta (os 2 estruturados
    já bastam; observações são só complemento)."""
    s = criar_dados_solo(textura="arenoza", profundidade_cm=30,
                         observacoes="solo vermelho")
    assert s.informado is True


def test_solo_textura_invalida_vira_none():
    """Textura fora de arenoza/media/argilosa vira None (não bloqueia)."""
    s = criar_dados_solo(textura="outra")
    assert s.textura is None
    assert s.informado is False


def test_solo_profundidade_negativa_vira_none():
    s = criar_dados_solo(profundidade_cm=-10)
    assert s.profundidade_cm is None
    assert s.informado is False


def test_solo_ph_fora_0_14_vira_none():
    s = criar_dados_solo(ph=20)
    assert s.ph is None
    assert s.informado is False


def test_solo_umidade_fora_0_1_vira_none():
    s = criar_dados_solo(umidade_inicial=1.5)
    assert s.umidade_inicial is None
    assert s.informado is False


# ===========================================================================
# 2. Semáforo com dados de solo (Etapa 7: +1 ponto)
# ===========================================================================
def test_semaforo_soma_ponto_com_dados_solo():
    """Sem dados de solo: 4 pts (milho Teresina). Com dados: 5 pts (verde)."""
    s_sem = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                            "valor_mercado"],
        usa_agua_estimada=False,
        local_calibrado=True,
        tem_dados_solo=False,
        classe_avaliada="El Niño",
    )
    s_com = calcular_semaforo(
        n_anos_total=35,
        n_anos_por_classe={"El Niño": 12, "La Niña": 14, "neutro": 9},
        lacunas_essenciais=["tmax_limite_c", "protecao_erosao",
                            "valor_mercado"],
        usa_agua_estimada=False,
        local_calibrado=True,
        tem_dados_solo=True,    # <- Etapa 7
        classe_avaliada="El Niño",
    )
    assert s_sem.pontos == 4
    assert s_sem.cor == "amarelo"
    assert s_com.pontos == 5
    assert s_com.cor == "verde"   # +1 do solo


# ===========================================================================
# 3. alerta.chuva_ultimos_7d
# ===========================================================================
def test_chuva_7d_soma_7_dias():
    idx = pd.date_range("2025-01-01", "2025-01-20", freq="D")
    valores = [5.0] * len(idx)
    df = pd.DataFrame({"PRECTOTCORR": valores}, index=idx)
    # 15/jan: últimos 7 dias (9 a 15) = 7 × 5 = 35 mm
    assert chuva_ultimos_7d(df, pd.Timestamp("2025-01-15")) == pytest.approx(35.0)


def test_chuva_7d_none_se_sem_coluna():
    df = pd.DataFrame({"outra": [1.0]}, index=pd.to_datetime(["2025-01-01"]))
    assert chuva_ultimos_7d(df, pd.Timestamp("2025-01-01")) is None


def test_chuva_7d_none_se_muitos_nan():
    idx = pd.date_range("2025-01-01", "2025-01-15", freq="D")
    valores = [float("nan")] * len(idx)
    df = pd.DataFrame({"PRECTOTCORR": valores}, index=idx)
    assert chuva_ultimos_7d(df, pd.Timestamp("2025-01-15")) is None


# ===========================================================================
# 4. alerta.calcular_alerta (sem limiares — só janela)
# ===========================================================================
def _df_clima_sintetico():
    """DataFrame sintético com chuva 10 mm/dia em jan-fev-nov-dez,
    0 mm/dia em jun-jul (simula Teresina)."""
    idx = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    valores = []
    for d in idx:
        if d.month in (1, 2, 3, 11, 12):
            valores.append(10.0)
        else:
            valores.append(0.0)
    return pd.DataFrame({"PRECTOTCORR": valores, "GWETROOT": 0.4},
                       index=idx)


def _resultado_janelas_mock(meses_janela=(1, 2, 3, 11, 12)):
    """ResultadoJanelas mockado: meses_janela são janela, outros não."""
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
        cultura="milho", ciclo_dias=120, agua_efetiva_mm=600.0,
        agua_estimada=False, estab_dias=30, estab_min_mm=20.0,
        janelas=janelas, meses_janela=["Jan", "Fev", "Mar", "Nov", "Dez"],
    )


class _CulturaMock:
    nome = "milho"


def test_alerta_janela_sem_limiar_janela_aberta():
    """Sem limiares (config None): na janela -> JANELA ABERTA (amarelo),
    NÃO 'PLANTE AGORA' (revisão 2026-11-14). Sem sinais calibrados, não
    podemos recomendar plantio verde."""
    df = _df_clima_sintetico()
    r = _resultado_janelas_mock()
    a = calcular_alerta(df, _CulturaMock(), r, pd.Timestamp("2025-01-15"))
    assert a.status == "JANELA ABERTA (sinais não calibrados)"
    assert a.cor == "amarelo"
    assert a.na_janela is True
    # Lacunas: os 2 limiares não definidos
    assert any("limiar_chuva_7d_mm" in l for l in a.lacunas)
    assert any("limiar_umidade" in l for l in a.lacunas)


def test_alerta_fora_janela_nao_plante():
    """Fora da janela -> NÃO PLANTE."""
    df = _df_clima_sintetico()
    r = _resultado_janelas_mock()
    a = calcular_alerta(df, _CulturaMock(), r, pd.Timestamp("2025-06-15"))
    assert a.status == "NÃO PLANTE"
    assert a.cor == "vermelho"
    assert a.na_janela is False


def test_alerta_com_limiares_chuva_ok_plante_agora():
    """Com limiares, na janela e chuva OK -> PLANTE AGORA."""
    df = _df_clima_sintetico()   # 10 mm/dia -> chuva 7d = 70 mm
    r = _resultado_janelas_mock()
    a = calcular_alerta(df, _CulturaMock(), r, pd.Timestamp("2025-01-15"),
                        limiar_chuva_7d_mm=30.0, limiar_umidade=0.3)
    assert a.status == "PLANTE AGORA"
    assert a.cor == "verde"
    # chuva 7d = 70 mm >= 30 mm OK; umidade 0.4 >= 0.3 OK
    assert a.chuva_7d_mm == pytest.approx(70.0)
    assert a.umidade_solo == pytest.approx(0.4)


def test_alerta_com_limiares_chuva_baixa_aguarde():
    """Na janela mas chuva abaixo do limiar -> AGUARDE."""
    # Série com chuva 2 mm/dia em janeiro -> chuva 7d = 14 mm
    idx = pd.date_range("2025-01-01", "2025-01-31", freq="D")
    df = pd.DataFrame({"PRECTOTCORR": [2.0] * len(idx),
                        "GWETROOT": [0.4] * len(idx)}, index=idx)
    r = _resultado_janelas_mock()
    a = calcular_alerta(df, _CulturaMock(), r, pd.Timestamp("2025-01-15"),
                        limiar_chuva_7d_mm=30.0, limiar_umidade=0.3)
    assert a.status == "AGUARDE"
    assert a.cor == "amarelo"
    assert a.na_janela is True
    # chuva 14 mm < 30 mm -> abaixo
    assert a.chuva_7d_mm == pytest.approx(14.0)


def test_alerta_sem_janelas_calculadas():
    """ResultadoJanelas vazio -> NÃO PLANTE + lacuna."""
    from core.janelas import ResultadoJanelas
    df = _df_clima_sintetico()
    r_vazio = ResultadoJanelas(
        cultura="x", ciclo_dias=None, agua_efetiva_mm=None,
        agua_estimada=False, estab_dias=30, estab_min_mm=20.0,
        janelas=[], meses_janela=[],
        aviso_geral="sem ciclo_dias")
    a = calcular_alerta(df, _CulturaMock(), r_vazio,
                        pd.Timestamp("2025-01-15"))
    assert a.status == "NÃO PLANTE"
    assert any("sem janelas calculadas" in l for l in a.lacunas)


def test_alerta_motivos_preenchidos():
    """O alerta lista motivos (informativo para a interface)."""
    df = _df_clima_sintetico()
    r = _resultado_janelas_mock()
    a = calcular_alerta(df, _CulturaMock(), r, pd.Timestamp("2025-01-15"))
    assert len(a.motivos) >= 2   # janela + chuva + umidade
    assert any("janela" in m.lower() for m in a.motivos)


# ===========================================================================
# 5. Integração com o cache real (Teresina)
# ===========================================================================
def test_integracao_alerta_teresina():
    """Carrega cache de Teresina, calcula alerta em janeiro e junho."""
    from core.nasa_power import carregar_series
    from core.culturas import carregar_banco
    from core.janelas import calcular_janelas
    from core.enso import anos_agricolas_completos

    df, _, _ = carregar_series()
    completos, _ = anos_agricolas_completos(df)
    banco = carregar_banco()
    milho = banco["milho"]
    r = calcular_janelas(df, milho, anos_agricolas_completos=completos)

    # Janeiro (mês-janela) -> JANELA ABERTA (sinais não calibrados), amarelo,
    # porque config.LIMIAR_CHUVA_7D_MM e LIMIAR_UMIDADE_SOLO são None
    # (revisão 2026-11-14: sem sinais calibrados, não pode ser PLANTE AGORA).
    a_jan = calcular_alerta(df, milho, r, pd.Timestamp("2025-01-15"))
    assert a_jan.status == "JANELA ABERTA (sinais não calibrados)"
    assert a_jan.cor == "amarelo"
    assert a_jan.na_janela is True

    # Janeiro com limiares definidos manualmente -> PLANTE AGORA (verde)
    a_jan_cal = calcular_alerta(df, milho, r, pd.Timestamp("2025-01-15"),
                                limiar_chuva_7d_mm=30.0, limiar_umidade=0.3)
    assert a_jan_cal.status == "PLANTE AGORA"
    assert a_jan_cal.cor == "verde"

    # Junho (seca, não janela) -> NÃO PLANTE
    a_jun = calcular_alerta(df, milho, r, pd.Timestamp("2025-06-15"))
    assert a_jun.status == "NÃO PLANTE"
    assert a_jun.na_janela is False


# ===========================================================================
# 6. Alerta: sinais não calibrados (revisão 2026-11-14)
# ===========================================================================
def test_alerta_sinais_nao_calibrados_amarelo():
    """Sem limiares (config None), na janela -> amarelo 'JANELA ABERTA',
    NÃO verde 'PLANTE AGORA' (não podemos recomendar sem sinais calibrados).
    """
    df = _df_clima_sintetico()
    r = _resultado_janelas_mock()
    a = calcular_alerta(df, _CulturaMock(), r, pd.Timestamp("2025-01-15"))
    assert a.cor == "amarelo"
    assert "sinais não calibrados" in a.status
    assert "PLANTE AGORA" not in a.status


def test_alerta_sinais_calibrados_verde():
    """Com os 2 limiares definidos e na janela, sinais OK -> PLANTE AGORA verde."""
    df = _df_clima_sintetico()
    r = _resultado_janelas_mock()
    a = calcular_alerta(df, _CulturaMock(), r, pd.Timestamp("2025-01-15"),
                        limiar_chuva_7d_mm=30.0, limiar_umidade=0.3)
    assert a.status == "PLANTE AGORA"
    assert a.cor == "verde"


def test_alerta_soh_limiar_chuva_calibrado_amarelo():
    """Se só o limiar de chuva está calibrado (umidade None), ainda é
    'JANELA ABERTA (sinais não calibrados)' — faltou 1 sinal."""
    df = _df_clima_sintetico()
    r = _resultado_janelas_mock()
    a = calcular_alerta(df, _CulturaMock(), r, pd.Timestamp("2025-01-15"),
                        limiar_chuva_7d_mm=30.0)  # umidade fica None
    assert a.cor == "amarelo"
    assert "sinais não calibrados" in a.status
