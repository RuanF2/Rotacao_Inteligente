"""Catálogo estruturado de culturas (com fonte e confiança por atributo)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional

from . import settings


@dataclass(frozen=True)
class Cultura:
    id: str
    nome: str
    nome_en: str
    familia: str
    tipo: str  # "comercial" | "cobertura"
    ciclo_dias: int
    kc_ini: float
    kc_mid: float
    kc_end: float
    ky: Optional[float]
    tmax_critica_c: float
    fixa_nitrogenio: bool
    protecao_solo: int  # 1..3 (qualitativo)
    agua_ref_mm_ciclo: Optional[float]
    tbase_c: float = 10.0
    tolera_geada: bool = False
    fontes: Dict[str, str] = field(default_factory=dict)
    confianca: Dict[str, str] = field(default_factory=dict)

    @property
    def meses_ocupados(self) -> int:
        """Número de meses de calendário que o ciclo ocupa (arredonda p/ cima)."""
        import math

        return max(1, math.ceil(self.ciclo_dias / 30.4))

    @property
    def alta_biomassa(self) -> bool:
        return self.protecao_solo >= 3

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nome": self.nome,
            "nome_en": self.nome_en,
            "familia": self.familia,
            "tipo": self.tipo,
            "ciclo_dias": self.ciclo_dias,
            "meses_ocupados": self.meses_ocupados,
            "kc": {"ini": self.kc_ini, "mid": self.kc_mid, "end": self.kc_end},
            "ky": self.ky,
            "tmax_critica_c": self.tmax_critica_c,
            "fixa_nitrogenio": self.fixa_nitrogenio,
            "protecao_solo": self.protecao_solo,
            "agua_ref_mm_ciclo": self.agua_ref_mm_ciclo,
            "tbase_c": self.tbase_c,
            "tolera_geada": self.tolera_geada,
            "fontes": self.fontes,
            "confianca": self.confianca,
        }


class CatalogoError(Exception):
    pass


def _validar(item: dict) -> None:
    obrig = ["id", "nome", "familia", "tipo", "ciclo_dias", "kc", "tmax_critica_c",
             "fixa_nitrogenio", "protecao_solo"]
    falta = [k for k in obrig if item.get(k) is None]
    if falta:
        raise CatalogoError(f"Cultura {item.get('id')}: campos ausentes {falta}")
    if item["tipo"] not in ("comercial", "cobertura"):
        raise CatalogoError(f"Cultura {item['id']}: tipo inválido {item['tipo']}")
    if not (30 <= int(item["ciclo_dias"]) <= 240):
        raise CatalogoError(f"Cultura {item['id']}: ciclo_dias fora da faixa")
    if not (1 <= int(item["protecao_solo"]) <= 3):
        raise CatalogoError(f"Cultura {item['id']}: protecao_solo deve ser 1..3")
    for k in ("ini", "mid", "end"):
        v = item["kc"].get(k)
        if v is None or not (0.1 <= float(v) <= 1.5):
            raise CatalogoError(f"Cultura {item['id']}: kc.{k} inválido")


@lru_cache(maxsize=1)
def carregar() -> Dict[str, Cultura]:
    with settings.CATALOGO_JSON.open(encoding="utf-8") as f:
        dados = json.load(f)
    out: Dict[str, Cultura] = {}
    for item in dados["culturas"]:
        _validar(item)
        if item["id"] in out:
            raise CatalogoError(f"id duplicado: {item['id']}")
        out[item["id"]] = Cultura(
            id=item["id"], nome=item["nome"], nome_en=item.get("nome_en", ""),
            familia=item["familia"], tipo=item["tipo"], ciclo_dias=int(item["ciclo_dias"]),
            kc_ini=float(item["kc"]["ini"]), kc_mid=float(item["kc"]["mid"]),
            kc_end=float(item["kc"]["end"]),
            ky=None if item.get("ky") is None else float(item["ky"]),
            tmax_critica_c=float(item["tmax_critica_c"]),
            fixa_nitrogenio=bool(item["fixa_nitrogenio"]),
            protecao_solo=int(item["protecao_solo"]),
            agua_ref_mm_ciclo=item.get("agua_ref_mm_ciclo"),
            tbase_c=float(item.get("tbase_c", 10.0)), tolera_geada=bool(item.get("tolera_geada", False)),
            fontes=item.get("fontes", {}), confianca=item.get("confianca", {}),
        )
    return out


def metadados() -> dict:
    with settings.CATALOGO_JSON.open(encoding="utf-8") as f:
        return json.load(f)["_sobre"]


def listar() -> List[Cultura]:
    return list(carregar().values())


def obter(cid: str) -> Cultura:
    try:
        return carregar()[cid]
    except KeyError as e:
        raise CatalogoError(f"Cultura desconhecida: {cid}") from e
