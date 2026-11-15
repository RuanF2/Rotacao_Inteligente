"""
tests/test_smoke.py - Teste de fumaça da Etapa 1.

Garante que config.py importa e que os caminhos básicos existem.
Quando as próximas etapas forem implementadas, adicionamos testes reais
(cálculo de sementes, classificação ENSO, janelas, etc.).
"""

from pathlib import Path

import config


def test_config_carrega():
    """config.py deve importar sem erro e expor os símbolos básicos."""
    assert config.RODAPE.startswith("Ferramenta de apoio")
    assert config.AVISO_DADO_FALTANTE == "dado não preenchido"
    assert config.FATOR_MINIMO_CHUVA == 0.6
    assert config.FATOR_HA_M2 == 10000


def test_caminhos_existem():
    """As pastas e o CSV de culturas precisam existir desde a Etapa 1."""
    assert config.DATA_DIR.exists()
    assert config.CACHE_DIR.exists()
    assert config.CULTURAS_CSV.exists()
    assert config.CULTURAS_CSV.read_text(encoding="utf-8").startswith("nome,")


def test_headers_dos_arquivos_manuais():
    """oni.csv e produtividade.csv devem existir e começar com o cabeçalho esperado.

    Não exigimos que tenham só o cabeçalho: quando o usuário preencher dados
    reais da NOAA/IBGE, o teste continua passando.
    """
    assert config.ONI_CSV.exists()
    assert config.PRODUTIVIDADE_CSV.exists()

    # Lê só a primeira linha (cabeçalho) e normaliza para comparar.
    oni_header = config.ONI_CSV.read_text(encoding="utf-8").splitlines()[0].strip()
    prod_header = (
        config.PRODUTIVIDADE_CSV.read_text(encoding="utf-8").splitlines()[0].strip()
    )
    assert oni_header == "ano,djf_oni"
    assert prod_header == "municipio,ano,cultura,rendimento_kg_ha,fonte"
