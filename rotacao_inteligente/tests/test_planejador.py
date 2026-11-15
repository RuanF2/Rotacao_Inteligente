"""
tests/test_planejador.py - Testes da Etapa 4 (core/planejador.py).

Valida os 4 cenários pedidos pelo usuário:
  1. cultura com taxa preenchida -> calcula área.
  2. cultura com taxa vazia -> não calcula, avisa.
  3. cultura com AMBOS rendimentos (regional + potencial) -> usa regional.
  4. cultura só com potencial -> usa potencial com aviso experimental.

Mais:
  - Cultura sem nenhum rendimento -> não mostra colheita.
  - kg de semente negativo -> erro.
  - taxa = 0 -> erro.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from core import planejador
from core.culturas import Cultura
from core.planejador import (
    calcular_area, calcular_colheita, planejar,
    PlanejadorError,
)


# ---------------------------------------------------------------------------
# Helpers: constrói uma Cultura manualmente para isolar o teste
# ---------------------------------------------------------------------------
def _cultura(nome="feijao-caupi", *,
             taxa=None, regional=None, potencial=None,
             ciclo=70, agua=325.0):
    """Cria uma Cultura só com os campos que importam para o planejador."""
    return Cultura(
        nome=nome, tipo="comercial",
        ciclo_dias=ciclo, agua_mm_ciclo=agua,
        tmax_limite_c=None,
        fixa_nitrogenio=None, protecao_erosao=None, valor_mercado=None,
        taxa_semeadura_kg_ha=taxa,
        rendimento_potencial_kg_ha=potencial,
        rendimento_regional_kg_ha=regional,
        fonte="teste",
        lacunas=[],
    )


# ---------------------------------------------------------------------------
# 1. Cálculo de ÁREA
# ---------------------------------------------------------------------------
def test_area_calcula_quando_taxa_preenchida():
    """Cenário 1: taxa preenchida -> calcula área."""
    c = _cultura(taxa=18.0)  # 18 kg/ha
    r = calcular_area(10.0, c)   # 10 kg de semente
    # area_m2 = (10 / 18) * 10000 = 5555.55...
    assert r.area_m2 is not None
    assert r.area_m2 == pytest.approx(5555.5556, rel=1e-3)
    assert r.area_ha == pytest.approx(0.55555556, rel=1e-3)
    assert r.aviso is None


def test_area_nao_calcula_quando_taxa_vazia():
    """Cenário 2: taxa vazia -> não calcula, devolve aviso do config."""
    c = _cultura(taxa=None)
    r = calcular_area(10.0, c)
    assert r.area_m2 is None
    assert r.area_ha is None
    assert r.aviso == config.AVISO_TAXA_SEMEADURA_FALTANTE


def test_area_kg_negativo_erro():
    c = _cultura(taxa=18.0)
    with pytest.raises(PlanejadorError, match="negativo"):
        calcular_area(-1.0, c)


def test_area_taxa_zero_erro():
    c = _cultura(taxa=0.0)
    with pytest.raises(PlanejadorError, match="inválida"):
        calcular_area(10.0, c)


def test_area_kg_zero_devolve_area_zero():
    """0 kg de semente -> 0 m² (não é erro, é só plantio nulo)."""
    c = _cultura(taxa=18.0)
    r = calcular_area(0.0, c)
    assert r.area_m2 == 0.0
    assert r.area_ha == 0.0
    assert r.aviso is None


# ---------------------------------------------------------------------------
# 2. Cálculo de COLHEITA
# ---------------------------------------------------------------------------
def test_colheita_usa_regional_quando_tem_ambos():
    """Cenário 3: ambos os rendimentos -> usa regional (prioridade briefing)."""
    c = _cultura(taxa=18.0, regional=800.0, potencial=2000.0)
    r = calcular_colheita(area_ha=0.5, cultura=c)
    # 0.5 ha * 800 kg/ha = 400 kg
    assert r.colheita_kg == pytest.approx(400.0)
    assert r.rendimento_kg_ha_usado == 800.0
    assert r.fonte_rendimento == "regional"
    assert r.aviso == "estimativa com dado regional"


def test_colheita_usa_potencial_quando_so_potencial():
    """Cenário 4: só potencial -> usa potencial com aviso experimental."""
    c = _cultura(taxa=18.0, regional=None, potencial=2000.0)
    r = calcular_colheita(area_ha=0.5, cultura=c)
    # 0.5 ha * 2000 kg/ha = 1000 kg
    assert r.colheita_kg == pytest.approx(1000.0)
    assert r.rendimento_kg_ha_usado == 2000.0
    assert r.fonte_rendimento == "potencial"
    assert r.aviso == config.AVISO_POTENCIAL_EXPERIMENTAL


def test_colheita_nao_calcula_quando_sem_rendimentos():
    """Sem nenhum rendimento -> não mostra colheita, avisa."""
    c = _cultura(taxa=18.0, regional=None, potencial=None)
    r = calcular_colheita(area_ha=0.5, cultura=c)
    assert r.colheita_kg is None
    assert r.rendimento_kg_ha_usado is None
    assert r.fonte_rendimento is None
    assert r.aviso == config.AVISO_DADO_FALTANTE


def test_colheita_nao_calcula_se_area_none():
    """Se a área não foi calculada (sem taxa), colheita também não."""
    c = _cultura(taxa=None, regional=800.0)
    r = calcular_colheita(area_ha=None, cultura=c)
    assert r.colheita_kg is None
    assert r.aviso == config.AVISO_DADO_FALTANTE


def test_colheita_regional_prevalece_sobre_potencial():
    """Mesmo se o potencial for maior, o regional é preferido (briefing)."""
    c = _cultura(taxa=18.0, regional=500.0, potencial=5000.0)
    r = calcular_colheita(area_ha=1.0, cultura=c)
    assert r.rendimento_kg_ha_usado == 500.0  # regional, não 5000
    assert r.colheita_kg == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# 3. planejar() - integração
# ---------------------------------------------------------------------------
def test_planejar_cenario1_taxa_preenchida_potencial():
    """Cenário completo: taxa + potencial -> área + colheita potencial."""
    c = _cultura(taxa=18.0, regional=None, potencial=2000.0)
    r = planejar(10.0, c)
    assert r.cultura == "feijao-caupi"
    assert r.kg_semente == 10.0
    assert r.area.area_m2 == pytest.approx(5555.5556, rel=1e-3)
    assert r.colheita.colheita_kg == pytest.approx(1111.1111, rel=1e-3)
    assert r.colheita.fonte_rendimento == "potencial"


def test_planejar_cenario2_taxa_vazia():
    """Sem taxa -> sem área e sem colheita, com avisos."""
    c = _cultura(taxa=None, regional=800.0, potencial=2000.0)
    r = planejar(10.0, c)
    assert r.area.area_m2 is None
    assert r.area.aviso == config.AVISO_TAXA_SEMEADURA_FALTANTE
    assert r.colheita.colheita_kg is None


def test_planejar_cenario3_ambos_rendimentos():
    """Ambos os rendimentos -> usa regional no cálculo final."""
    c = _cultura(taxa=18.0, regional=800.0, potencial=2000.0)
    r = planejar(10.0, c)
    assert r.area.area_m2 is not None
    assert r.colheita.fonte_rendimento == "regional"
    # 0.555... ha * 800 = ~444.44 kg
    assert r.colheita.colheita_kg == pytest.approx(444.4444, rel=1e-3)


def test_planejar_cenario4_so_potencial():
    """Só potencial -> usa potencial com aviso experimental."""
    c = _cultura(taxa=18.0, regional=None, potencial=2000.0)
    r = planejar(10.0, c)
    assert r.colheita.fonte_rendimento == "potencial"
    assert r.colheita.aviso == config.AVISO_POTENCIAL_EXPERIMENTAL


def test_planejar_cenario5_sem_rendimentos():
    """Com taxa mas sem rendimentos -> área calculada, colheita não."""
    c = _cultura(taxa=18.0, regional=None, potencial=None)
    r = planejar(10.0, c)
    assert r.area.area_m2 is not None  # área calcula (tem taxa)
    assert r.colheita.colheita_kg is None  # colheita não (sem rendimento)
    assert r.colheita.aviso == config.AVISO_DADO_FALTANTE
