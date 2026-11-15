from app import vulnerabilidade as v


def test_notas_por_faixa():
    assert v.nota("aridez", 0.1) == 1.0
    assert v.nota("aridez", 0.8) == 0.0
    assert v.nota("estresse_termico", 150) == 1.0
    assert v.nota("declividade", 2) == 0.0
    assert v.nota("solo_descoberto", 0.4) == 0.4
    assert v.nota("aridez", None) is None


def test_classificacao():
    assert v.classificar(0.1) == "baixa"
    assert v.classificar(0.3) == "moderada"
    assert v.classificar(0.6) == "alta"
    assert v.classificar(0.9) == "crítica"


def test_dados_insuficientes_nao_classifica():
    r = v.avaliar({"indice_aridez": 0.3, "dias_calor_ano_medio": 50})
    assert r["indice"] is None and r["classe"] == "dados insuficientes"


def test_indice_e_media_simples():
    ind = {"indice_aridez": 0.1, "cv_precipitacao_anual": 0.4, "cdd_estacao_chuvosa_medio_dias": 30,
           "gwetroot_medio": 0.2, "dias_calor_ano_medio": 200, "indice_fournier_modificado": 200}
    r = v.avaliar(ind, declividade_pct=1.0, fracao_solo_descoberto=0.0)
    assert r["indice"] == round(6 / 8, 3)
    assert r["classe"] == "crítica"
    assert all(i["base_faixas"] for i in r["indicadores"])
