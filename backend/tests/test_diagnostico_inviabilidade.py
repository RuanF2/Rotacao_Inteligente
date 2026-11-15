"""O diagnóstico usa verificações reais sem apresentar hipóteses como causas provadas."""
from types import SimpleNamespace

import numpy as np

from app import catalogo, rotacao
from app.main import _erro


def _tab_sintetica(frio=0.0, chuva=30.0):
    culturas = [catalogo.obter("milho")]
    return SimpleNamespace(
        culturas=culturas, idx={"milho": 0},
        frio_mediana=np.full((1, 12), frio),
        estab_mediana=np.full((1, 12), chuva),
    )


def test_diagnostico_identifica_ausencia_de_janelas_por_frio():
    d = rotacao.diagnosticar_inviabilidade(_tab_sintetica(frio=0.8), 0)
    assert d["tipo"] == "sem_estrategia_viavel"
    assert any(v["codigo"] == "janela_termica" and v["resultado"] == "bloqueio_confirmado" for v in d["verificacoes"])
    assert any(v["codigo"] == "sem_janelas" for v in d["verificacoes"])


def test_diagnostico_nao_atribui_causa_ao_frio_quando_ha_janelas():
    d = rotacao.diagnosticar_inviabilidade(_tab_sintetica(), 0)
    assert any(v["codigo"] == "calendario_completo" and v["resultado"] == "nao_conclusivo" for v in d["verificacoes"])
    assert not any(v["resultado"] == "bloqueio_confirmado" for v in d["verificacoes"])


def test_diagnostico_chuva_e_irrigacao():
    d = rotacao.diagnosticar_inviabilidade(_tab_sintetica(chuva=0), 0)
    assert any(v["codigo"] == "estabelecimento" and v["resultado"] == "bloqueio_confirmado" for v in d["verificacoes"])
    irrigado = rotacao.diagnosticar_inviabilidade(_tab_sintetica(chuva=0), 200)
    assert any(v["codigo"] == "irrigacao" for v in irrigado["verificacoes"])
    assert not any(v["codigo"] == "estabelecimento" for v in irrigado["verificacoes"])


def test_sem_cultura_comercial_e_erro_estruturado():
    d = rotacao.diagnosticar_inviabilidade(_tab_sintetica(), 0, ["guandu"])
    assert d["verificacoes"][0]["codigo"] == "sem_comercial"
    e = _erro(rotacao.RotacaoError("Sem combinação", d))
    assert e.status_code == 422
    assert e.detail["diagnostico"]["tipo"] == "sem_estrategia_viavel"
    assert _erro(rotacao.RotacaoError("erro comum")).detail == "erro comum"


def test_endpoint_devolve_diagnostico_422(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import DEMO, app
    from app import servico
    diagnostico = rotacao.diagnosticar_inviabilidade(_tab_sintetica(frio=0.95), 0)
    def falha(_):
        raise rotacao.RotacaoError("Busca sem soluções", diagnostico)
    monkeypatch.setattr(servico, "analisar", falha)
    resposta = TestClient(app).post("/api/analise", json=DEMO)
    assert resposta.status_code == 422
    assert resposta.json()["detail"]["diagnostico"]["tipo"] == "sem_estrategia_viavel"
