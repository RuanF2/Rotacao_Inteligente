"""Persistência mínima em SQLite (propriedades e cache de topografia)."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, List, Optional

from . import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS propriedades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    dados TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cache_topografia (
    chave TEXT PRIMARY KEY,
    dados TEXT NOT NULL,
    obtido_em TEXT NOT NULL
);
"""


@contextmanager
def conectar() -> Iterator[sqlite3.Connection]:
    settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def salvar_propriedade(dados: dict, pid: Optional[int] = None) -> dict:
    nome = dados.get("nome") or "Propriedade sem nome"
    with conectar() as con:
        if pid is None:
            cur = con.execute("INSERT INTO propriedades (nome, dados, criado_em, atualizado_em) VALUES (?,?,?,?)",
                              (nome, json.dumps(dados, ensure_ascii=False), _agora(), _agora()))
            pid = cur.lastrowid
        else:
            cur = con.execute("UPDATE propriedades SET nome=?, dados=?, atualizado_em=? WHERE id=?",
                              (nome, json.dumps(dados, ensure_ascii=False), _agora(), pid))
            if cur.rowcount == 0:
                raise KeyError(pid)
    return obter_propriedade(pid)


def obter_propriedade(pid: int) -> dict:
    with conectar() as con:
        row = con.execute("SELECT * FROM propriedades WHERE id=?", (pid,)).fetchone()
    if row is None:
        raise KeyError(pid)
    return {"id": row["id"], "nome": row["nome"], "dados": json.loads(row["dados"]),
            "criado_em": row["criado_em"], "atualizado_em": row["atualizado_em"]}


def listar_propriedades() -> List[dict]:
    with conectar() as con:
        rows = con.execute("SELECT id, nome, atualizado_em FROM propriedades ORDER BY atualizado_em DESC").fetchall()
    return [dict(r) for r in rows]


def excluir_propriedade(pid: int) -> None:
    with conectar() as con:
        cur = con.execute("DELETE FROM propriedades WHERE id=?", (pid,))
        if cur.rowcount == 0:
            raise KeyError(pid)


def cache_topo_get(chave: str) -> Optional[dict]:
    with conectar() as con:
        row = con.execute("SELECT dados FROM cache_topografia WHERE chave=?", (chave,)).fetchone()
    return json.loads(row["dados"]) if row else None


def cache_topo_set(chave: str, dados: dict) -> None:
    with conectar() as con:
        con.execute("INSERT OR REPLACE INTO cache_topografia (chave, dados, obtido_em) VALUES (?,?,?)",
                    (chave, json.dumps(dados), _agora()))
