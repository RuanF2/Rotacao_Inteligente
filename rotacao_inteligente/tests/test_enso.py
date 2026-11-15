"""
tests/test_enso.py - Testes da Etapa 3 (core/enso.py).

Valida:
- A regra de classificação (>=+0.5 El Niño; <=-0.5 La Niña; neutro no meio).
- Anos exatamente no limite (+/- 0.5) são sinalizados.
- Leitura do CSV (cabeçalho, anos duplicados, valores vazios).
- Contagem por classe.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import config
from core import enso


# ---------------------------------------------------------------------------
# Testes da função pura classificar_oni
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("oni, esperado, limite", [
    (1.5, "El Niño", False),
    (0.6, "El Niño", False),
    (0.5, "El Niño", True),       # exatamente no limite
    (0.4, "neutro", False),
    (0.1, "neutro", False),
    (0.0, "neutro", False),
    (-0.1, "neutro", False),
    (-0.4, "neutro", False),
    (-0.5, "La Niña", True),      # exatamente no limite
    (-0.6, "La Niña", False),
    (-1.5, "La Niña", False),
    (2.5, "El Niño", False),      # El Niño muito forte (2015)
])
def test_classificar_oni(oni, esperado, limite):
    """Regra do briefing: >=+0.5 El Niño; <=-0.5 La Niña; neutro no meio."""
    classe, no_limite = enso.classificar_oni(oni)
    assert classe == esperado
    assert no_limite == limite


def test_classificar_oni_limiares_custom():
    """Permitir limiares diferentes (se a equipe mudar config.py)."""
    # Limiares mais brandos: >=+0.4 El Niño
    classe, _ = enso.classificar_oni(0.45,
                                      limiar_el_nino=0.4,
                                      limiar_la_nina=-0.4)
    assert classe == "El Niño"


# ---------------------------------------------------------------------------
# Testes da leitura do CSV
# ---------------------------------------------------------------------------
@pytest.fixture
def oni_csv_tmp(tmp_path, monkeypatch):
    """Cria um ONI CSV fake em tmp_path e aponta config.ONI_CSV para ele."""
    csv = tmp_path / "oni.csv"
    csv.write_text(
        "ano,djf_oni\n"
        "1991,1.5\n"
        "1992,-0.5\n"   # borderline La Niña
        "1993,0.5\n"    # borderline El Niño
        "1994,\n"       # dado faltante
        "1995,0.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "ONI_CSV", csv)
    return csv


def test_ler_oni_csv_cabecalho_correto(oni_csv_tmp):
    df = enso.ler_oni_csv(oni_csv_tmp)
    assert list(df.columns) == ["ano", "djf_oni"]
    assert len(df) == 5
    # Dado faltante vira NaN, não 0
    assert pd.isna(df.loc[df["ano"] == 1994, "djf_oni"].iloc[0])


def test_ler_oni_csv_ano_duplicado_erro(tmp_path):
    csv = tmp_path / "oni_dup.csv"
    csv.write_text(
        "ano,djf_oni\n2020,1.0\n2020,2.0\n",
        encoding="utf-8",
    )
    with pytest.raises(enso.EnsoError, match="duplicad"):
        enso.ler_oni_csv(csv)


def test_ler_oni_csv_cabecalho_errado(tmp_path):
    csv = tmp_path / "oni_err.csv"
    csv.write_text("ano,outro\n2020,1.0\n", encoding="utf-8")
    with pytest.raises(enso.EnsoError, match="Cabeçalho"):
        enso.ler_oni_csv(csv)


def test_ler_oni_csv_inexistente(tmp_path):
    with pytest.raises(enso.EnsoError, match="não encontrado"):
        enso.ler_oni_csv(tmp_path / "nao_existe.csv")


# ---------------------------------------------------------------------------
# Testes da classificação da série
# ---------------------------------------------------------------------------
def test_classificar_serie_dado_faltante(oni_csv_tmp):
    df = enso.ler_oni_csv(oni_csv_tmp)
    classes = enso.classificar_serie(df)

    # 1994 com djf_oni vazio -> "dado não preenchido"
    c_1994 = [c for c in classes if c.ano == 1994][0]
    assert c_1994.classe == "dado não preenchido"
    assert c_1994.no_limite is False
    assert pd.isna(c_1994.oni)


def test_classificar_serie_no_limite(oni_csv_tmp):
    df = enso.ler_oni_csv(oni_csv_tmp)
    classes = enso.classificar_serie(df)
    limite = enso.anos_no_limite(classes)
    # 1992 (-0.5) e 1993 (+0.5) estão no limite
    assert 1992 in limite
    assert 1993 in limite
    assert len(limite) == 2


def test_contar_por_classe(oni_csv_tmp):
    df = enso.ler_oni_csv(oni_csv_tmp)
    classes = enso.classificar_serie(df)
    contagem = enso.contar_por_classe(classes)
    assert contagem["El Niño"] == 2   # 1991 (1.5), 1993 (0.5 no limite)
    assert contagem["La Niña"] == 1   # 1992 (-0.5 no limite)
    assert contagem["neutro"] == 1    # 1995 (0.0)
    assert contagem["dado não preenchido"] == 1  # 1994


def test_anos_da_classe(oni_csv_tmp):
    df = enso.ler_oni_csv(oni_csv_tmp)
    classes = enso.classificar_serie(df)
    el_nino = enso.anos_da_classe(classes, "El Niño")
    assert el_nino == [1991, 1993]


# ---------------------------------------------------------------------------
# Teste integrado com o CSV real (data/oni.csv do usuário)
# ---------------------------------------------------------------------------
def test_csv_real_do_usuario():
    """Valida o CSV real fornecido pelo usuário (35 anos: 1991-2025)."""
    classes, contagem, limite = enso.carregar_classificacao()

    # 35 anos
    assert len(classes) == 35
    # Anos vão de 1991 a 2025
    assert classes[0].ano == 1991
    assert classes[-1].ano == 2025
    # Nenhum ano "dado não preenchido" (o CSV está completo)
    assert contagem["dado não preenchido"] == 0

    # Soma das classes == 35
    total = contagem["El Niño"] + contagem["La Niña"] + contagem["neutro"]
    assert total == 35

    # 2022 e 2024 estão exatamente no limite (-0.5 = La Niña borderline)
    assert 2022 in limite
    assert 2024 in limite

    # 2015 (ONI 2.5) é El Niño muito forte (sem ambiguidade)
    c_2015 = [c for c in classes if c.ano == 2015][0]
    assert c_2015.classe == "El Niño"
    assert c_2015.no_limite is False
