"""Configurações do backend (lidas de variáveis de ambiente quando existirem)."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CATALOGO_JSON = DATA_DIR / "catalogo_culturas.json"

# Banco SQLite do MVP (propriedades salvas + cache de topografia).
DB_PATH = Path(os.environ.get("ROTACAO_DB_PATH", BASE_DIR.parent / "rotacao.db"))

# Origem permitida para o frontend (CORS). Vários valores separados por vírgula.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ROTACAO_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# Permite desligar chamadas de rede (útil em testes e demonstrações offline).
OFFLINE = os.environ.get("ROTACAO_OFFLINE", "0") == "1"

# Serviço público de elevação SRTM (sem chave). Pode ser trocado por outro
# servidor OpenTopoData (inclusive auto-hospedado) via variável de ambiente.
OPENTOPODATA_URL = os.environ.get(
    "ROTACAO_OPENTOPODATA_URL", "https://api.opentopodata.org/v1/srtm90m"
)

# Otimização (NSGA-II). Semente fixa = resultados reprodutíveis.
NSGA_POP = int(os.environ.get("ROTACAO_NSGA_POP", "120"))
NSGA_GEN = int(os.environ.get("ROTACAO_NSGA_GEN", "120"))
NSGA_SEED = int(os.environ.get("ROTACAO_NSGA_SEED", "42"))
