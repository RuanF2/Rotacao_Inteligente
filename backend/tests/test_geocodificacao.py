import pytest
from fastapi.testclient import TestClient

from app import geocodificacao as geo
from app.main import DEMO, app

client = TestClient(app)

RESP_FRANCA = {"display_name": "Dijon, Côte-d'Or, Bourgogne-Franche-Comté, France métropolitaine, França",
               "address": {"city": "Dijon", "state": "Bourgogne-Franche-Comté", "country": "França", "country_code": "fr"}}


class Resp:
    def __init__(self, status=200, payload=None, json_err=False):
        self.status_code, self._p, self._e = status, payload, json_err

    def json(self):
        if self._e:
            raise ValueError("json inválido")
        return self._p


class Sessao:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc, self.chamadas = resp, exc, []

    def get(self, url, params, headers, timeout):
        self.chamadas.append((url, params, headers))
        if self.exc:
            raise self.exc
        return self.resp


@pytest.fixture
def online(monkeypatch):
    monkeypatch.setattr(geo.settings, "OFFLINE", False)
    monkeypatch.setattr(geo.time, "sleep", lambda s: None)


def test_reverso_sucesso_usa_user_agent_e_cache(online):
    s = Sessao(Resp(200, RESP_FRANCA))
    r = geo.reverso(47.0101, 5.7681, sessao=s)
    assert r["identificado"] and r["municipio"] == "Dijon" and r["pais"] == "França" and r["codigo_pais"] == "FR"
    assert r["fonte"] == "OpenStreetMap Nominatim" and r["origem"] == "rede"
    assert "RotacaoInteligente" in s.chamadas[0][2]["User-Agent"]
    assert geo.reverso(47.0101, 5.7681, sessao=Sessao(exc=AssertionError("não deveria chamar")))["origem"] == "cache"


def test_ponto_sem_endereco_nao_inventa_localidade(online):
    r = geo.reverso(-30.0, -20.0, sessao=Sessao(Resp(200, {"error": "Unable to geocode"})))
    assert r["identificado"] is False and r["municipio"] is None and r["pais"] is None


def test_falha_de_rede(online):
    import requests
    with pytest.raises(geo.GeocodificacaoError, match="indisponível"):
        geo.reverso(10.0, 10.0, sessao=Sessao(exc=requests.ConnectionError("x")))


def test_limite_de_requisicoes_429(online):
    with pytest.raises(geo.GeocodificacaoError, match="Limite"):
        geo.reverso(11.0, 11.0, sessao=Sessao(Resp(429)))


def test_resposta_invalida(online):
    with pytest.raises(geo.GeocodificacaoError, match="inválida"):
        geo.reverso(12.0, 12.0, sessao=Sessao(Resp(200, json_err=True)))


def test_intervalo_minimo_entre_requisicoes(monkeypatch):
    monkeypatch.setattr(geo.settings, "OFFLINE", False)
    esperas = []
    monkeypatch.setattr(geo.time, "sleep", lambda s: esperas.append(s))
    geo.reverso(20.0, 20.0, sessao=Sessao(Resp(200, RESP_FRANCA)))
    geo.reverso(21.0, 21.0, sessao=Sessao(Resp(200, RESP_FRANCA)))
    assert esperas and max(esperas) > 0.5   # a 2ª chamada esperou para respeitar 1 req/s


def test_offline_e_endpoint():
    # conftest liga o modo offline: ponto sem cache => 503 com mensagem clara
    r = client.get("/api/geocodificar", params={"lat": 33.3, "lon": 44.4})
    assert r.status_code == 503 and "offline" in r.json()["detail"].lower()
    assert client.get("/api/geocodificar", params={"lat": 100, "lon": 0}).status_code == 422


def test_persistencia_da_troca_de_localizacao():
    nova = dict(DEMO, nome="Fazenda na Borgonha", lat=47.01, lon=5.768, regiao=None, pais=None,
                localidade_fonte=None, demonstrativa=False)
    pid = client.post("/api/propriedades", json=nova).json()["id"]
    lida = client.get(f"/api/propriedades/{pid}").json()["dados"]
    assert (lida["lat"], lida["lon"]) == (47.01, 5.768)
    assert lida["regiao"] is None and lida["pais"] is None and lida["demonstrativa"] is False
    upd = dict(nova, regiao="Dijon – Bourgogne-Franche-Comté", pais="França", localidade_fonte="OpenStreetMap Nominatim")
    lida = client.put(f"/api/propriedades/{pid}", json=upd).json()["dados"]
    assert lida["pais"] == "França" and lida["localidade_fonte"] == "OpenStreetMap Nominatim"


def test_relatorio_sem_localidade_identificada():
    # usa ponto com cache (Iowa) sem metadados geográficos: o relatório não pode herdar o local anterior
    p = dict(DEMO, nome="Teste", lat=41.6, lon=-93.6, regiao=None, pais=None, localidade_fonte=None, demonstrativa=False,
             rotacao_atual=[{"cultura": "milho", "ano": 1, "mes": 5}, {"cultura": "soja", "ano": 2, "mes": 5}])
    t = client.post("/api/relatorio", json=p).text
    assert "Localização não identificada" in t
    assert "São Raimundo Nonato" not in t and "Brasil" not in t


def test_analise_devolve_a_propriedade_e_coordenadas_pedidas():
    p = dict(DEMO, nome="Teste Iowa", lat=41.6, lon=-93.6, regiao=None, pais=None, demonstrativa=False,
             rotacao_atual=[{"cultura": "milho", "ano": 1, "mes": 5}, {"cultura": "soja", "ano": 2, "mes": 5}])
    a = client.post("/api/analise", json=p).json()
    assert a["propriedade"]["lat"] == 41.6 and a["propriedade"]["regiao"] is None
    assert a["clima"]["local"] == {"lat": 41.6, "lon": -93.6}
