"""
tests/test_nasa_power.py - Testes da Etapa 2 (nasa_power.py).

Estratégia:
- Testes de unidade: usam fixtures em /tmp com cache fake e monkeypatch
  em requests.get para simular a rede. Não dependem de internet.
- Um teste marcado como "online" (skip por padrão) faz a chamada real.

Rodar:
    pytest -v                                  # só testes offline
    pytest -v --run-online                     # inclui o teste online
"""

import json
import sys
from pathlib import Path

import pytest

# Garante que o pacote do projeto está no PYTHONPATH.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import config
from core import nasa_power


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def cache_tmp(tmp_path, monkeypatch):
    """Troca CACHE_DIR por um diretório temporário para cada teste."""
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    return config.CACHE_DIR


@pytest.fixture
def payload_t2m_fake():
    """JSON de exemplo (formato simplificado da NASA POWER)."""
    return {
        "header": {"title": "POWER Daily"},
        "parameters": {
            "T2M": {"longname": "Temperature at 2 Meters", "units": "C"}
        },
        "properties": {
            "parameter": {
                "T2M": {
                    "20240101": 25.5,
                    "20240102": 26.1,
                    "20240103": -999,   # ausente -> None
                    "20240104": 27.0,
                }
            }
        },
    }


class FakeResponse:
    """Simula requests.Response."""
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.exceptions.HTTPError(
                f"{self.status_code} error", response=self
            )


# ---------------------------------------------------------------------------
# Testes de cache (offline)
# ---------------------------------------------------------------------------
def test_cache_hit_nao_chama_rede(cache_tmp, payload_t2m_fake, monkeypatch):
    """Se o cache existe, requests.get NÃO deve ser chamado."""
    # Pré-popula o cache
    cache_file = nasa_power._nome_cache(-5.0, -42.0, 2024, 2024, "T2M")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(payload_t2m_fake), encoding="utf-8")

    chamadas = {"n": 0}

    def fake_get(url, **kwargs):
        chamadas["n"] += 1
        return FakeResponse(200, payload_t2m_fake)

    monkeypatch.setattr(nasa_power.requests, "get", fake_get)

    payload, _ = nasa_power.baixar_variavel("T2M", -5.0, -42.0, 2024, 2024)
    assert payload == payload_t2m_fake
    assert chamadas["n"] == 0, "não deveria ter chamado a rede com cache"


def test_cache_miss_sem_rede_falha_graciosamente(cache_tmp, monkeypatch):
    """Sem cache e sem rede -> NasaPowerRedeIndisponivel, não dado falso."""
    import requests

    def fake_get(url, **kwargs):
        raise requests.exceptions.ConnectionError("sem rede")

    monkeypatch.setattr(nasa_power.requests, "get", fake_get)

    with pytest.raises(nasa_power.NasaPowerRedeIndisponivel):
        nasa_power.baixar_variavel("T2M", -5.0, -42.0, 2024, 2024)


def test_cache_miss_com_rede_salva_cache(cache_tmp, payload_t2m_fake, monkeypatch):
    """Sem cache + rede OK -> baixa E salva em cache para o próximo acesso."""
    chamadas = {"n": 0}

    def fake_get(url, **kwargs):
        chamadas["n"] += 1
        return FakeResponse(200, payload_t2m_fake)

    monkeypatch.setattr(nasa_power.requests, "get", fake_get)

    # 1a chamada: baixa
    p1, c1 = nasa_power.baixar_variavel("T2M", -5.0, -42.0, 2024, 2024)
    assert p1 == payload_t2m_fake
    assert c1 is False, "primeira chamada deveria ter ido à rede"
    assert chamadas["n"] == 1

    # Cache deve existir agora
    cache_file = nasa_power._nome_cache(-5.0, -42.0, 2024, 2024, "T2M")
    assert cache_file.exists()

    # 2a chamada: lê do cache (não chama rede)
    p2, c2 = nasa_power.baixar_variavel("T2M", -5.0, -42.0, 2024, 2024)
    assert p2 == payload_t2m_fake
    assert c2 is True, "segunda chamada deveria ter vindo do cache"
    assert chamadas["n"] == 1, "segunda chamada deveria usar cache"


def test_variavel_invalida_levanta_excecao_correta(cache_tmp, monkeypatch):
    """Variável rejeitada pela API (HTTP 422) -> NasaPowerVariavelInvalida."""
    fake_payload = {"messages": ["One of your parameters is incorrect: VAR_FOO."]}
    monkeypatch.setattr(
        nasa_power.requests,
        "get",
        lambda url, **kw: FakeResponse(422, fake_payload),
    )

    with pytest.raises(nasa_power.NasaPowerVariavelInvalida):
        nasa_power.baixar_variavel("VAR_FOO", -5.0, -42.0, 2024, 2024)


def test_baixar_multiplas_isola_variavel_invalida(cache_tmp, monkeypatch):
    """Uma variável inválida não derruba as demais."""
    payloads = {
        "T2M": {
            "parameters": {"T2M": {"longname": "T", "units": "C"}},
            "properties": {"parameter": {"T2M": {"20240101": 25.0}}},
        },
        "VAR_FOO": {"messages": ["One of your parameters is incorrect: VAR_FOO."]},
        "PRECTOTCORR": {
            "parameters": {"PRECTOTCORR": {"longname": "P", "units": "mm"}},
            "properties": {"parameter": {"PRECTOTCORR": {"20240101": 5.0}}},
        },
    }

    def fake_get(url, params=None, **kw):
        var = params["parameters"]
        if var == "VAR_FOO":
            return FakeResponse(422, payloads[var])
        return FakeResponse(200, payloads[var])

    monkeypatch.setattr(nasa_power.requests, "get", fake_get)
    monkeypatch.setattr(nasa_power.time, "sleep", lambda s: None)  # acelera testes

    sucessos, falhas = nasa_power.baixar_multiplas(
        ["T2M", "VAR_FOO", "PRECTOTCORR"], -5.0, -42.0, 2024, 2024,
        intervalo_segundos=0,
    )
    assert set(sucessos.keys()) == {"T2M", "PRECTOTCORR"}
    assert len(falhas) == 1
    assert "VAR_FOO" in falhas[0]


# ---------------------------------------------------------------------------
# Testes de parsing
# ---------------------------------------------------------------------------
def test_para_dataframe_converte_menos999_para_none(payload_t2m_fake):
    """Valor -999 (ausente) deve virar None no DataFrame."""
    df, info = nasa_power.para_dataframe(payload_t2m_fake)
    assert list(df.columns) == ["T2M"]
    assert df.index.name == "data"
    # 4 datas
    assert len(df) == 4
    # -999 -> None
    linha_ausente = df.loc[df.index[2], "T2M"]
    assert linha_ausente is None or pd.isna(linha_ausente)
    # Demantes valores preservados
    assert df.loc[df.index[0], "T2M"] == 25.5


def test_para_dataframe_extrai_metadados(payload_t2m_fake):
    """A função deve expor longname e units da variável."""
    _, info = nasa_power.para_dataframe(payload_t2m_fake)
    assert info.nome == "T2M"
    assert info.longname == "Temperature at 2 Meters"
    assert info.units == "C"


def test_resumo_mensal_chuva_soma_demais_media():
    """PRECTOTCORR -> soma mensal; demais -> média mensal."""
    import pandas as pd
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    valores = [1.0] * 60
    df = pd.DataFrame({"PRECTOTCORR": valores, "T2M": [20.0 + i * 0.1 for i in range(60)]}, index=idx)

    chuva = nasa_power.resumo_mensal(df, "PRECTOTCORR")
    t2m = nasa_power.resumo_mensal(df, "T2M")

    # Janeiro tem 31 dias -> chuva soma 31; fevereiro tem 29 -> soma 29
    assert "PRECTOTCORR_soma_mm" in chuva.columns
    assert chuva.loc[chuva.index[0], "PRECTOTCORR_soma_mm"] == 31.0
    assert "T2M_media" in t2m.columns


# ---------------------------------------------------------------------------
# Teste online (skip por padrão; ativar com --run-online)
# ---------------------------------------------------------------------------
@pytest.mark.online
def test_online_carrega_todas_as_variaveis(cache_tmp):
    """Teste de integração real com a NASA POWER.

    Skip por padrão. Para rodar:
        pytest -v --run-online

    A lógica que pula este teste quando --run-online não é passado
    está em tests/conftest.py (hooks do pytest precisam ficar lá).
    """
    df, falhas, infos = nasa_power.carregar_series(
        lat=-5.09, lon=-42.81, ano_inicio=2024, ano_fim=2025,
    )
    # Pelo menos as 8 variáveis do config deveriam carregar
    assert len(df.columns) >= 7, f"variáveis: {list(df.columns)}"
    assert len(df) > 0, "DataFrame vazio"
    # Sem falhas
    assert falhas == [], f"falhas: {falhas}"
    # GWETROOT e GWETTOP devem estar presentes (confirmamos disponibilidade)
    assert "GWETROOT" in df.columns
    assert "GWETTOP" in df.columns
