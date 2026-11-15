import math

import numpy as np
import pytest

from app import clima


def test_radiacao_extraterrestre_exemplo_fao56():
    # FAO-56, Exemplo 8: 20°S, 3 de setembro (dia 246) -> Ra = 32,2 MJ m-2 dia-1
    ra = clima.radiacao_extraterrestre(-20.0, np.array([246]))[0]
    assert ra == pytest.approx(32.2, abs=0.2)


def test_et0_hargreaves_monotono_e_nao_negativo():
    ra = np.array([35.0, 35.0])
    a = clima.et0_hargreaves(np.array([25.0, 27.0]), np.array([32.0, 34.0]), np.array([18.0, 20.0]), ra)
    assert (a > 0).all() and a[1] > a[0]
    assert clima.et0_hargreaves(np.array([20.0]), np.array([15.0]), np.array([18.0]), np.array([30.0]))[0] == 0.0


def test_precipitacao_efetiva_usda_scs():
    pe = clima.precipitacao_efetiva_mensal(np.array([0.0, 100.0, 300.0]))
    assert pe[0] == 0
    assert pe[1] == pytest.approx(84.0)
    assert pe[2] == pytest.approx(155.0)


def test_classes():
    assert clima.classe_aridez(0.3) == "semiárido"
    assert clima.classe_aridez(0.7) == "úmido"
    assert clima.classe_fournier(100) == "moderada"


def test_carregar_serie_do_cache(serie_srn):
    s = serie_srn
    assert s.origem == "cache"
    assert len(s.anos_completos) >= 30
    for v in ["PRECTOTCORR", "T2M", "T2M_MAX", "T2M_MIN", "ET0"]:
        assert v in s.df.columns
    # nunca inventamos chuva: só temperatura é interpolada (lacunas <= 3 dias)
    assert s.df["PRECTOTCORR"].min() >= 0


def test_indicadores_srn_coerentes(serie_srn):
    ind = clima.indicadores(serie_srn)
    assert 300 < ind["precipitacao_anual_media_mm"] < 1200
    assert ind["classe_aridez"] in ("semiárido", "árido", "subúmido seco")
    assert ind["periodo"]["n_anos_completos"] >= 30
    assert 0 <= ind["cv_precipitacao_anual"] < 1
    assert set(ind["meses_chuvosos"]).issubset(set(range(1, 13)))
    assert ind["tendencia_tmax_c"]["metodo"].startswith("Theil-Sen")


def test_perturbacao_hipotetica(serie_srn):
    p = clima.perturbar(serie_srn, 2.0, -20.0)
    assert p.perturbacao["natureza"].startswith("perturbação hipotética")
    assert p.df["PRECTOTCORR"].sum() == pytest.approx(serie_srn.df["PRECTOTCORR"].sum() * 0.8, rel=1e-6)
    assert p.df["ET0"].mean() > serie_srn.df["ET0"].mean()
    assert clima.perturbar(serie_srn, 0, 0) is serie_srn


def test_coordenada_invalida():
    with pytest.raises(clima.ClimaError):
        clima.carregar(95, 0)


def test_resumo_api_tem_fonte_unidades_e_periodo(serie_srn):
    r = clima.resumo_para_api(serie_srn)
    assert "NASA POWER" in r["fonte"]["nome"]
    assert r["variaveis"]["PRECTOTCORR"]["unidade"] == "mm/dia"
    assert len(r["climatologia_mensal"]) == 12
    assert r["enso"] is not None and r["enso"]["por_classe"]
