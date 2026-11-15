"""Ponte para o núcleo científico do NASA1 (pasta ``rotacao_inteligente``).

A migração é incremental: o backend NÃO copia nem reescreve os módulos
``core/`` já validados (NASA POWER com cache, ENSO/ONI, janelas, etc.).
Ele apenas coloca a pasta legada no ``sys.path`` e importa de lá. Assim o
app Streamlit original continua funcionando e as duas interfaces usam a
mesma lógica e o mesmo cache de dados.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

LEGACY_DIR = Path(
    os.environ.get(
        "ROTACAO_LEGACY_DIR",
        Path(__file__).resolve().parents[2] / "rotacao_inteligente",
    )
).resolve()

if not LEGACY_DIR.exists():  # pragma: no cover - erro de instalação
    raise RuntimeError(
        f"Pasta do núcleo legado não encontrada: {LEGACY_DIR}. "
        "Defina ROTACAO_LEGACY_DIR ou mantenha a estrutura do repositório."
    )

if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))

import config as legacy_config  # noqa: E402
from core import enso, nasa_power  # noqa: E402

__all__ = ["LEGACY_DIR", "legacy_config", "nasa_power", "enso"]
