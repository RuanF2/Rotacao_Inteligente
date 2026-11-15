import pytest
from fastapi.testclient import TestClient

from app.main import DEMO, app

client = TestClient(app)


@pytest.fixture(scope="module")
def analise():
    r = client.post("/api/analise", json=DEMO)
    assert r.status_code == 200, r.text
    return r.json()


def test_health_e_catalogo():
    assert client.get("/api/health").json()["status"] == "ok"
    cs = client.get("/api/culturas").json()["culturas"]
    assert len(cs) >= 10


def test_fontes_por_local():
    f = client.get("/api/fontes", params={"lat": 70, "lon": 10}).json()["fontes"]
    srtm = next(x for x in f if x["id"] == "srtm")
    assert srtm["cobre_local"] is False
    power = next(x for x in f if x["id"] == "nasa_power")
    assert power["usado_nos_calculos"] is True


def test_clima_endpoint():
    r = client.get("/api/clima", params={"lat": DEMO["lat"], "lon": DEMO["lon"]})
    assert r.status_code == 200
    assert r.json()["indicadores"]["periodo"]["n_anos_completos"] >= 30


def test_analise_tres_estrategias_comparaveis(analise):
    chaves = [e["chave"] for e in analise["estrategias"]]
    assert chaves[:3] == ["A", "B", "C"]
    hor = {e["avaliacao"]["indicadores"]["pares_de_anos_avaliados"] for e in analise["estrategias"]}
    assert len(hor) == 1  # mesmo horizonte/mesma série para todas
    for e in analise["estrategias"]:
        ex = e["explicacao"]
        for campo in ["por_que", "evidencias", "beneficios", "riscos", "confianca", "informacoes_ausentes"]:
            assert campo in ex
    assert analise["vulnerabilidade"]["classe"] in ("baixa", "moderada", "alta", "crítica")
    # offline: SRTM indisponível deve aparecer como limitação, não como valor inventado
    assert analise["topografia"]["declividade_pct"] is None and analise["topografia"]["erro"]
    assert any("Declividade" in a for a in analise["vulnerabilidade"]["ausentes"])


def test_coerencia_resultado_exibido(analise):
    # o objetivo exibido de A é o mesmo recalculado pelo endpoint /api/avaliar
    a = analise["estrategias"][0]
    r = client.post("/api/avaliar", json={"lat": DEMO["lat"], "lon": DEMO["lon"], "slots": a["slots"],
                                          "irrigacao_mm_ano": 0}).json()
    assert r["objetivos"] == a["avaliacao"]["objetivos"]


def test_simulacao(analise):
    est = {e["chave"]: e["slots"] for e in analise["estrategias"]}
    r = client.post("/api/simulacao", json={"lat": DEMO["lat"], "lon": DEMO["lon"], "estrategias": est,
                                            "delta_t": 2, "delta_p_pct": -20})
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j["cenarios"]) == {"historico", "recente", "hipotetico"}
    assert "NÃO é projeção" in j["cenarios"]["hipotetico"]["natureza"]
    h, s = j["cenarios"]["historico"]["estrategias"]["A"], j["cenarios"]["hipotetico"]["estrategias"]["A"]
    assert s["objetivos"]["vulnerabilidade_climatica"] > h["objetivos"]["vulnerabilidade_climatica"]
    assert len(j["sensibilidade_temperatura"]) == 5


def test_simulacao_fora_da_faixa():
    r = client.post("/api/simulacao", json={"lat": DEMO["lat"], "lon": DEMO["lon"],
                                            "estrategias": {"A": DEMO["rotacao_atual"]}, "delta_t": 9})
    assert r.status_code == 422


def test_relatorio_markdown():
    r = client.post("/api/relatorio", json=DEMO)
    assert r.status_code == 200
    t = r.text
    for trecho in ["## 2. Fontes de dados", "NASA POWER", "Estratégia A", "Estratégia B", "Estratégia C", "## 5. Limitações"]:
        assert trecho in t


def test_entrada_invalida():
    bad = dict(DEMO, lat=120)
    assert client.post("/api/analise", json=bad).status_code == 422
    bad = dict(DEMO, rotacao_atual=[{"cultura": "inexistente", "ano": 1, "mes": 1}])
    assert client.post("/api/analise", json=bad).status_code == 422


def test_crud_propriedades():
    r = client.post("/api/propriedades", json=DEMO).json()
    pid = r["id"]
    assert client.get(f"/api/propriedades/{pid}").json()["nome"] == DEMO["nome"]
    upd = dict(DEMO, nome="Outro nome")
    assert client.put(f"/api/propriedades/{pid}", json=upd).json()["nome"] == "Outro nome"
    assert any(p["id"] == pid for p in client.get("/api/propriedades").json()["propriedades"])
    assert client.delete(f"/api/propriedades/{pid}").status_code == 200
    assert client.get(f"/api/propriedades/{pid}").status_code == 404


def test_mapa_pontos():
    pts = client.get("/api/mapa/pontos").json()["pontos"]
    assert len(pts) >= 6
    assert all("vulnerabilidade" in p for p in pts if "erro" not in p)


def test_relatorio_distingue_perda_hidrica_de_risco_termico():
    r = client.post("/api/relatorio", json=DEMO)
    assert r.status_code == 200, r.text
    texto = r.text
    assert "perda potencial por falta de água" in texto.lower()
    assert "0% não significa produção garantida" in texto
    assert "frio/geada" in texto
