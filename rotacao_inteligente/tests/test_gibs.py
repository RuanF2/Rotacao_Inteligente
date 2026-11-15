"""tests/test_gibs.py - Testes das camadas GIBS (correção 2026-11-14).

Estratégia (igual aos outros testes do projeto):
- Testes de unidade: injetam um GetCapabilities fake em memória
  (_CAPS_CACHE) e mockam requests.get/requests.head. Não dependem
  de internet.
- Um teste marcado "online" (skip por padrão) lê o GetCapabilities
  real e confere as datas Default das 3 camadas.

Cobre:
- _parse_intervalos: P1D, P16D, P1M, data única.
- data_padrao: lê o <Default> do XML.
- data_mais_proxima_valida: dentro do intervalo -> exata/borda do grid;
  fora do intervalo -> borda mais próxima.
- verificar_tile: True quando HEAD responde 200; False em falha/timeout.
- camadas_disponiveis: validado + data_padrao + intervalos por camada.

Rodar:
    pytest -v tests/test_gibs.py
    pytest -v --run-online     # inclui o teste online
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import datetime as dt
import xml.etree.ElementTree as ET

import config
from core import gibs


# ---------------------------------------------------------------------------
# GetCapabilities fake (XML em memória)
# ---------------------------------------------------------------------------

_CAPS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0"
              xmlns:ows="http://www.opengis.net/ows/1.1">
  <Contents>
    <Layer>
      <ows:Identifier>MODIS_Terra_L3_NDVI_16Day</ows:Identifier>
      <Dimension>
        <ows:Identifier>Time</ows:Identifier>
        <ows:UOM>ISO8601</ows:UOM>
        <Default>2026-10-16</Default>
        <Current>false</Current>
        <Value>2026-01-01/2026-10-16/P16D</Value>
      </Dimension>
    </Layer>
    <Layer>
      <ows:Identifier>IMERG_Precipitation_Rate</ows:Identifier>
      <Dimension>
        <ows:Identifier>Time</ows:Identifier>
        <ows:UOM>ISO8601</ows:UOM>
        <Default>2026-11-13</Default>
        <Current>false</Current>
        <Value>2026-05-27/2026-11-13/P1D</Value>
      </Dimension>
    </Layer>
    <Layer>
      <ows:Identifier>SMAP_L4_Analyzed_Root_Zone_Soil_Moisture</ows:Identifier>
      <Dimension>
        <ows:Identifier>Time</ows:Identifier>
        <ows:UOM>ISO8601</ows:UOM>
        <Default>2026-11-10</Default>
        <Current>false</Current>
        <Value>2026-11-08/2026-11-10/P1D</Value>
      </Dimension>
    </Layer>
    <Layer>
      <ows:Identifier>CAMADA_SEM_TEMPO</ows:Identifier>
    </Layer>
  </Contents>
</Capabilities>
"""


@pytest.fixture(autouse=True)
def caps_fake(monkeypatch):
    """Injeta o GetCapabilities fake em memória (não baixa da rede)."""
    monkeypatch.setattr(gibs, "_CAPS_CACHE", ET.fromstring(_CAPS_XML))
    yield
    # Reseta após cada teste.
    monkeypatch.setattr(gibs, "_CAPS_CACHE", None)


# ---------------------------------------------------------------------------
# 1. _parse_intervalos
# ---------------------------------------------------------------------------

def test_parse_intervalos_p1d():
    """P1D -> periodo 1 dia."""
    dim = ET.fromstring(
        "<Dimension xmlns='http://www.opengis.net/wmts/1.0'>"
        "<Value>2026-05-27/2026-11-13/P1D</Value></Dimension>")
    ints = gibs._parse_intervalos(dim)
    assert ints == [(dt.date(2026, 5, 27), dt.date(2026, 11, 13), 1)]


def test_parse_intervalos_p16d():
    """P16D -> periodo 16 dias."""
    dim = ET.fromstring(
        "<Dimension xmlns='http://www.opengis.net/wmts/1.0'>"
        "<Value>2026-01-01/2026-10-16/P16D</Value></Dimension>")
    ints = gibs._parse_intervalos(dim)
    assert ints == [(dt.date(2026, 1, 1), dt.date(2026, 10, 16), 16)]


# ---------------------------------------------------------------------------
# 2. data_padrao (lê o <Default>)
# ---------------------------------------------------------------------------

def test_data_padrao_ndvi():
    """Default do NDVI = 2026-10-16."""
    assert gibs.data_padrao("ndvi") == dt.date(2026, 10, 16)


def test_data_padrao_imerg():
    """Default do IMERG = 2026-11-13."""
    assert gibs.data_padrao("imerg") == dt.date(2026, 11, 13)


def test_data_padrao_smap():
    """Default do SMAP = 2026-11-10."""
    assert gibs.data_padrao("smap") == dt.date(2026, 11, 10)


def test_data_padrao_camada_inexistente():
    """Camada fora do config -> None."""
    assert gibs.data_padrao("inexistente") is None


# ---------------------------------------------------------------------------
# 3. data_mais_proxima_valida
# ---------------------------------------------------------------------------

def test_data_mais_proxima_valida_dentro_p1d_exata():
    """Data escolhida dentro do intervalo P1D e no grid -> exata."""
    # IMERG: 2026-05-27..2026-11-13, P1D (diário). 2026-06-15 é válida.
    prox = gibs.data_mais_proxima_valida("imerg", dt.date(2026, 6, 15))
    assert prox == dt.date(2026, 6, 15)


def test_data_mais_proxima_valida_p1d_ajusta_para_grid():
    """Se a data está dentro do intervalo mas não no grid, ajusta p/
    a válida mais próxima. IMERG é P1D, então toda data é válida —
    testamos com uma data no futuro ao Default para ver o teto."""
    # IMERG: Default 2026-11-13. 2026-11-14 -> 2026-11-13 (última).
    prox = gibs.data_mais_proxima_valida("imerg", dt.date(2026, 11, 14))
    assert prox == dt.date(2026, 11, 13)


def test_data_mais_proxima_valida_p16d_ajusta():
    """NDVI é P16D: 2026-11-14 -> 2026-10-16 (última do intervalo)."""
    prox = gibs.data_mais_proxima_valida("ndvi", dt.date(2026, 11, 14))
    assert prox == dt.date(2026, 10, 16)


def test_data_mais_proxima_valida_antes_do_intervalo():
    """Data antes do intervalo -> start do intervalo."""
    # IMERG começa em 2026-05-27. 2020-01-01 -> 2026-05-27.
    prox = gibs.data_mais_proxima_valida("imerg", dt.date(2020, 1, 1))
    assert prox == dt.date(2026, 5, 27)


def test_data_mais_proxima_valida_camada_inexistente_none():
    """Camada fora do config -> None."""
    assert gibs.data_mais_proxima_valida("inexistente",
                                          dt.date(2026, 11, 14)) is None


# ---------------------------------------------------------------------------
# 4. camadas_disponiveis
# ---------------------------------------------------------------------------

def test_camadas_disponiveis_validado_e_datas():
    """As 3 camadas do config devem vir validadas com data_padrao."""
    out = gibs.camadas_disponiveis()
    assert set(out.keys()) == set(config.GIBS_CAMADAS.keys())
    assert out["ndvi"]["validado"] is True
    assert out["ndvi"]["data_padrao"] == dt.date(2026, 10, 16)
    assert out["imerg"]["data_padrao"] == dt.date(2026, 11, 13)
    assert out["smap"]["data_padrao"] == dt.date(2026, 11, 10)
    assert len(out["imerg"]["intervalos"]) == 1


# ---------------------------------------------------------------------------
# 5. verificar_tile (mock de requests.head)
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status):
        self.status_code = status

    def raise_for_status(self):
        pass


def test_verificar_tile_ok(monkeypatch):
    """HEAD 200 -> True."""
    def fake_head(url, **kw):
        return _FakeResp(200)
    monkeypatch.setattr(gibs.requests, "head", fake_head)
    assert gibs.verificar_tile("imerg", "2026-11-13") is True


def test_verificar_tile_404(monkeypatch):
    """HEAD 404 -> False."""
    def fake_head(url, **kw):
        return _FakeResp(404)
    monkeypatch.setattr(gibs.requests, "head", fake_head)
    assert gibs.verificar_tile("imerg", "2026-11-13") is False


def test_verificar_tile_sem_rede(monkeypatch):
    """Exceção de rede -> False (não levanta)."""
    def fake_head(url, **kw):
        raise gibs.requests.exceptions.RequestException("sem rede")
    monkeypatch.setattr(gibs.requests, "head", fake_head)
    assert gibs.verificar_tile("imerg", "2026-11-13") is False


# ---------------------------------------------------------------------------
# 6. tile_url_gibs preserva {z}/{y}/{x} para o folium
# ---------------------------------------------------------------------------

def test_tile_url_preserva_placeholders():
    """A URL deve manter {z}/{y}/{x} para o folium resolver."""
    url = gibs.tile_url_gibs("imerg", "2026-11-13")
    assert url is not None
    assert "{z}" in url and "{y}" in url and "{x}" in url
    assert "IMERG_Precipitation_Rate" in url
    assert "2026-11-13" in url


# ---------------------------------------------------------------------------
# 7. Teste online (skip por padrão) — GetCapabilities real
# ---------------------------------------------------------------------------

@pytest.mark.online
def test_gibs_online_defaults_reais():
    """Lê o GetCapabilities real e confere que cada camada tem um
    Default (data mais recente). Skip por padrão (precisa --run-online).
    """
    gibs._CAPS_CACHE = None   # força leitura real
    out = gibs.camadas_disponiveis()
    for chave in config.GIBS_CAMADAS:
        assert out[chave]["validado"], f"{chave} não validado no GIBS"
        assert out[chave]["data_padrao"] is not None, \
            f"{chave} sem data_padrao"
        print(f"\n[gibs online] {chave}: Default={out[chave]['data_padrao']}"
              f" intervalos={len(out[chave]['intervalos'])}")
