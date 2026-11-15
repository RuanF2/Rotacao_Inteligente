import os
import sys
import tempfile
from pathlib import Path

# Configuração ANTES de importar o app: banco temporário, modo offline e NSGA-II menor (testes rápidos).
os.environ.setdefault("ROTACAO_DB_PATH", str(Path(tempfile.mkdtemp()) / "teste.db"))
os.environ.setdefault("ROTACAO_OFFLINE", "1")
os.environ.setdefault("ROTACAO_NSGA_POP", "40")
os.environ.setdefault("ROTACAO_NSGA_GEN", "30")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

SRN = (-9.015, -42.69889)    # São Raimundo Nonato-PI (cache do NASA1)
IOWA = (41.6, -93.6)          # demo global (cache do NASA1)


@pytest.fixture(scope="session")
def serie_srn():
    from app import clima
    return clima.carregar(*SRN)


@pytest.fixture(scope="session")
def tab_srn(serie_srn):
    from app import rotacao
    return rotacao.TabelaAvaliacao(serie_srn)
