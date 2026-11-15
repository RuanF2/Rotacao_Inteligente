"""tests/conftest.py - Configurações e hooks do pytest.

Hooks do pytest (pytest_addoption, pytest_collection_modifyitems) precisam
ficar em conftest.py para serem carregados automaticamente.
"""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-online",
        action="store_true",
        default=False,
        help="Roda também testes que dependem de internet (marcados com @pytest.mark.online)",
    )


def pytest_collection_modifyitems(config, items):
    """Pula testes marcados com 'online' a menos que --run-online seja passado."""
    if not config.getoption("--run-online"):
        skip_marker = pytest.mark.skip(reason="precisa de --run-online")
        for item in items:
            if "online" in item.keywords:
                item.add_marker(skip_marker)
