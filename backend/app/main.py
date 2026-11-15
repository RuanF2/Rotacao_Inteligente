"""API REST do Rotação Inteligente 2.0 (FastAPI).

Executar:  uvicorn app.main:app --reload --port 8000   (a partir da pasta backend/)
Documentação interativa: http://localhost:8000/docs
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from . import __version__, catalogo, clima, db, fontes, geocodificacao, relatorio, rotacao, servico, settings, topografia, vulnerabilidade

app = FastAPI(title="Rotação Inteligente 2.0 — Global Agricultural Intelligence", version=__version__,
              description="Apoio à decisão de rotação de culturas com dados de observação da Terra da NASA.")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


class SlotIn(BaseModel):
    cultura: str
    ano: int = Field(1, ge=1, le=2)
    mes: int = Field(..., ge=1, le=12)


class SoloIn(BaseModel):
    textura: Optional[Literal["arenosa", "media", "argilosa"]] = None
    profundidade_cm: Optional[float] = Field(None, gt=0, le=500)
    materia_organica_pct: Optional[float] = Field(None, ge=0, le=100)
    ph: Optional[float] = Field(None, ge=2, le=12)


class Prioridades(BaseModel):
    agua: float = Field(1.0, ge=0, le=5)
    solo: float = Field(1.0, ge=0, le=5)
    erosao: float = Field(1.0, ge=0, le=5)
    diversificacao: float = Field(1.0, ge=0, le=5)
    risco: float = Field(1.0, ge=0, le=5)


class Propriedade(BaseModel):
    nome: str = "Minha propriedade"
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    area_ha: Optional[float] = Field(None, gt=0)
    pais: Optional[str] = None
    regiao: Optional[str] = None
    localidade_fonte: Optional[str] = None   # ex.: "OpenStreetMap Nominatim", "informado pelo usuário"
    demonstrativa: bool = False
    solo: SoloIn = SoloIn()
    declividade_pct: Optional[float] = Field(None, ge=0, le=300)
    usar_srtm: bool = True
    irrigacao_mm_ano: float = Field(0.0, ge=0, le=3000)
    fonte_agua: Optional[str] = None
    rotacao_atual: List[SlotIn]
    historico: Optional[str] = None
    culturas_permitidas: Optional[List[str]] = None
    prioridades: Prioridades = Prioridades()


class SimulacaoIn(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    estrategias: Dict[str, List[SlotIn]]
    delta_t: float = Field(0.0, ge=-5, le=6)
    delta_p_pct: float = Field(0.0, ge=-60, le=60)
    irrigacao_mm_ano: float = Field(0.0, ge=0, le=3000)
    declividade_pct: Optional[float] = None
    base_cenario: Literal["historico", "recente"] = "historico"
    rotulo_horizonte: Optional[str] = Field(None, max_length=40)


class AvaliarIn(BaseModel):
    lat: float
    lon: float
    slots: List[SlotIn]
    irrigacao_mm_ano: float = 0.0


def _erro(e: Exception) -> HTTPException:
    if isinstance(e, rotacao.RotacaoError) and e.diagnostico:
        return HTTPException(status_code=422, detail={"mensagem": str(e), "diagnostico": e.diagnostico})
    if isinstance(e, (clima.ClimaError, rotacao.RotacaoError, catalogo.CatalogoError, ValueError)):
        return HTTPException(status_code=422, detail=str(e))
    return HTTPException(status_code=500, detail=f"Erro interno: {e}")


@app.get("/api/health")
def health():
    return {"status": "ok", "versao": __version__, "offline": settings.OFFLINE}


@app.get("/api/culturas")
def culturas():
    return {"culturas": [c.to_dict() for c in catalogo.listar()], "sobre": catalogo.metadados()}


@app.get("/api/fontes")
def listar_fontes(lat: Optional[float] = None, lon: Optional[float] = None):
    if lat is not None and lon is not None:
        return {"fontes": fontes.disponibilidade(lat, lon)}
    return {"fontes": fontes.FONTES}


@app.get("/api/locais")
def locais():
    return {"locais": fontes.locais_demo()}


@app.get("/api/camadas")
def camadas():
    return fontes.camadas_gibs()


@app.get("/api/clima")
def get_clima(lat: float, lon: float):
    try:
        return clima.resumo_para_api(clima.carregar(lat, lon))
    except Exception as e:  # noqa: BLE001
        raise _erro(e)


@app.get("/api/topografia")
def get_topografia(lat: float, lon: float):
    try:
        return topografia.obter(lat, lon)
    except topografia.TopografiaError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/geocodificar")
def geocodificar(lat: float, lon: float):
    """Município/região/país para a coordenada (OpenStreetMap Nominatim, com cache e limite de 1 req/s)."""
    try:
        return geocodificacao.reverso(lat, lon)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except geocodificacao.GeocodificacaoError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/metodologia/vulnerabilidade")
def metodologia_vulnerabilidade():
    return {"indicadores": vulnerabilidade.INDICADORES, "classes": vulnerabilidade.CLASSES,
            "minimo_indicadores": vulnerabilidade.MIN_INDICADORES}


@app.post("/api/analise")
def analise(prop: Propriedade):
    try:
        return servico.analisar(prop.model_dump())
    except Exception as e:  # noqa: BLE001
        raise _erro(e)


@app.post("/api/avaliar")
def avaliar(req: AvaliarIn):
    try:
        tab = rotacao.TabelaAvaliacao(clima.carregar(req.lat, req.lon))
        return rotacao.avaliar(rotacao.slots_de_dicts([s.model_dump() for s in req.slots]), tab, req.irrigacao_mm_ano)
    except Exception as e:  # noqa: BLE001
        raise _erro(e)


@app.post("/api/simulacao")
def simulacao(req: SimulacaoIn):
    try:
        est = {k: [s.model_dump() for s in v] for k, v in req.estrategias.items()}
        return servico.simular(req.lat, req.lon, est, req.delta_t, req.delta_p_pct, req.irrigacao_mm_ano,
                               req.declividade_pct, base_cenario=req.base_cenario,
                               rotulo_horizonte=req.rotulo_horizonte)
    except Exception as e:  # noqa: BLE001
        raise _erro(e)


@app.post("/api/relatorio", response_class=PlainTextResponse)
def gerar_relatorio(prop: Propriedade):
    try:
        return relatorio.gerar_markdown(servico.analisar(prop.model_dump()))
    except Exception as e:  # noqa: BLE001
        raise _erro(e)


@app.get("/api/mapa/pontos")
def mapa_pontos():
    return {"pontos": servico.mapa_pontos(),
            "aviso": "Indicadores calculados nos pontos com cache NASA POWER; cada ponto representa uma célula de ~50 km."}


@app.get("/api/propriedades")
def listar_props():
    return {"propriedades": db.listar_propriedades()}


@app.post("/api/propriedades")
def criar_prop(prop: Propriedade):
    return db.salvar_propriedade(prop.model_dump())


@app.get("/api/propriedades/{pid}")
def obter_prop(pid: int):
    try:
        return db.obter_propriedade(pid)
    except KeyError:
        raise HTTPException(404, "Propriedade não encontrada")


@app.put("/api/propriedades/{pid}")
def atualizar_prop(pid: int, prop: Propriedade):
    try:
        return db.salvar_propriedade(prop.model_dump(), pid)
    except KeyError:
        raise HTTPException(404, "Propriedade não encontrada")


@app.delete("/api/propriedades/{pid}")
def excluir_prop(pid: int):
    try:
        db.excluir_propriedade(pid)
        return {"ok": True}
    except KeyError:
        raise HTTPException(404, "Propriedade não encontrada")


DEMO = {
    "nome": "Sítio Demonstrativo Serra da Capivara",
    "lat": -9.015, "lon": -42.69889, "area_ha": 12.0, "pais": "Brasil", "regiao": "São Raimundo Nonato – PI (semiárido)",
    "localidade_fonte": "configuração do projeto (sede municipal, NASA1)",
    "demonstrativa": True,
    "solo": {"textura": "arenosa", "profundidade_cm": 60, "materia_organica_pct": None, "ph": None},
    "declividade_pct": None, "usar_srtm": True, "irrigacao_mm_ano": 0.0, "fonte_agua": "sequeiro (sem irrigação)",
    "rotacao_atual": [{"cultura": "milho", "ano": 1, "mes": 1}, {"cultura": "milho", "ano": 2, "mes": 1}],
    "historico": "Milho de sequeiro todo ano, semeado em janeiro, com pousio no resto do ano (exemplo demonstrativo).",
    "culturas_permitidas": None,
    "prioridades": {"agua": 3, "solo": 2, "erosao": 2, "diversificacao": 1, "risco": 3},
}


@app.get("/api/demo")
def demo():
    """Propriedade demonstrativa no semiárido (coordenadas reais da sede de São Raimundo Nonato-PI;
    área, solo e rotação são exemplos)."""
    return DEMO
