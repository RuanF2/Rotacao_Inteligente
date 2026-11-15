import pytest

from app import explicabilidade, topografia


def test_horn_plano_inclinado():
    # superfície com aumento de 9 m a cada 90 m para leste => 10 %
    z = [0, 9, 18, 0, 9, 18, 0, 9, 18]
    assert topografia.declividade_horn(z, 90, 90) == pytest.approx(10.0)
    assert topografia.declividade_horn([5] * 9, 90, 90) == 0


def test_srtm_fora_de_cobertura():
    with pytest.raises(topografia.TopografiaError):
        topografia.obter(70.0, 10.0)


def test_srtm_com_resposta_simulada(monkeypatch):
    monkeypatch.setattr(topografia.settings, "OFFLINE", False)

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": [{"elevation": v} for v in [100, 104.5, 109, 100, 104.5, 109, 100, 104.5, 109]]}

    class Sessao:
        def get(self, url, params, timeout):
            assert params["locations"].count("|") == 8
            return Resp()

    r = topografia.obter(-9.5, -42.5, sessao=Sessao())
    assert r["declividade_pct"] == pytest.approx(5.0)
    assert r["origem"] == "rede"
    assert topografia.obter(-9.5, -42.5)["origem"] == "cache"


def test_srtm_offline_informa_limitacao():
    with pytest.raises(topografia.TopografiaError):
        topografia.obter(-1.234, 2.345)


def test_confianca_nao_e_probabilidade():
    c = explicabilidade.confianca(["milho", "guandu"], 35, False, False, True)
    assert 0 <= c["valor"] <= 100
    assert "NÃO é probabilidade" in c["nota"]
    assert c["componentes"]["observacao_satelite_numerica"] == 0.0
    c2 = explicabilidade.confianca(["milho"], 35, True, True, True)
    assert c2["valor"] > c["valor"]
