"""
core/nasa_power.py - Etapa 2: download e cache de dados da NASA POWER.

O QUE ESTE ARQUIVO FAZ (em linguagem simples):
    A NASA POWER é uma API gratuita (sem chave) que dá valores diários de
    temperatura, chuva, umidade, radiação solar e umidade do solo para
    qualquer ponto do planeta. Este módulo baixa esses dados para uma
    coordenada e um período (10 a 15 anos por padrão), e guarda a resposta
    em data/cache/ para que a demo funcione offline no segundo acesso.

COMO O CACHE FUNCIONA:
    Para cada combinação (lat, lon, ano_inicio, ano_fim, variável) salvamos
    um arquivo JSON em data/cache/. Se o arquivo existe, lemos dele e não
    fazemos rede. Se não existe, baixamos, salvamos e devolvemos.

POR QUE UMA REQUISIÇÃO POR VARIÁVEL:
    Se uma variável deixar de existir na API (ou for renomeada), só ela
    falha — o restante continua funcionando. Também fica mais fácil
    identificar qual variável quebrou.

IMPORTANTE:
    - Não inventamos dados: se a API não responder, devolvemos erro.
    - Valores -999 da NASA POWER significam "dado ausente" e são
      convertidos para None (NaN) no DataFrame final.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

import config


# ---------------------------------------------------------------------------
# 1. Exceções próprias (deixam o erro claro para a interface)
# ---------------------------------------------------------------------------
class NasaPowerError(Exception):
    """Erro genérico no acesso à NASA POWER."""


class NasaPowerVariavelInvalida(NasaPowerError):
    """A variável pedida não existe na comunidade AG."""


class NasaPowerRedeIndisponivel(NasaPowerError):
    """Sem rede ou API inacessível — e não havia cache."""


# ---------------------------------------------------------------------------
# 2. Estruturas de dados simples
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VariavelInfo:
    """Metadados de uma variável retornada pela API."""
    nome: str
    longname: str
    units: str


# ---------------------------------------------------------------------------
# 3. Funções internas (não expostas para o app)
# ---------------------------------------------------------------------------
def _nome_cache(lat: float, lon: float, ano_inicio: int, ano_fim: int,
                variavel: str) -> Path:
    """Gera o caminho do arquivo de cache para uma variável."""
    # lat/lon com 2 casas decimais para evitar nomes enormes.
    lat_s = f"{lat:+.2f}".replace(".", "p").replace("+", "m").replace("-", "n")
    lon_s = f"{lon:+.2f}".replace(".", "p").replace("+", "m").replace("-", "n")
    nome = f"power_{lat_s}_{lon_s}_{ano_inicio}_{ano_fim}_{variavel}.json"
    return config.CACHE_DIR / nome


def _periodo_para_datas(ano_inicio: int, ano_fim: int) -> Tuple[str, str]:
    """Converte anos civis em YYYYMMDD inicial e final."""
    return f"{ano_inicio}0101", f"{ano_fim}1231"


def _chamar_api(variavel: str, lat: float, lon: float,
                start: str, end: str, timeout: float = 60.0) -> Dict[str, Any]:
    """Faz uma chamada HTTP à NASA POWER para UMA variável.

    Levanta NasaPowerVariavelInvalida se a API rejeitar a variável
    (status 422 com mensagem 'incorrect'), para que o chamador saiba
    distinguir 'variável não existe' de 'rede caiu'.
    """
    params = {
        "parameters": variavel,
        "community": config.NASA_POWER_COMMUNITY,
        "longitude": lon,
        "latitude": lat,
        "start": start,
        "end": end,
        "format": config.NASA_POWER_FORMAT,
    }
    try:
        resp = requests.get(config.NASA_POWER_BASE_URL, params=params, timeout=timeout)
    except requests.exceptions.RequestException as e:
        raise NasaPowerRedeIndisponivel(
            f"Sem rede para baixar '{variavel}' da NASA POWER. Erro: {e}"
        ) from e

    # HTTP 422 -> variável inválida (a API responde com messages explicando)
    if resp.status_code == 422:
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        raise NasaPowerVariavelInvalida(
            f"A variável '{variavel}' foi rejeitada pela NASA POWER "
            f"(HTTP 422). Mensagens: {payload.get('messages', [])}"
        )
    # Outros erros HTTP -> rede/servidor
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise NasaPowerRedeIndisponivel(
            f"Erro HTTP ao baixar '{variavel}': {e}"
        ) from e
    return resp.json()


def _avaliar_resposta(payload: Dict[str, Any], variavel: str) -> None:
    """Levanta exceção se a API disser que a variável é inválida.

    Mesmo com HTTP 200, a NASA POWER pode incluir `messages` alertando
    sobre problemas (observado em alguns casos). Por isso mantemos esta
    verificação extra após o download.
    """
    msgs = payload.get("messages") or []
    if not msgs:
        return
    texto = " ".join(m.lower() for m in msgs) if isinstance(msgs, list) else str(msgs).lower()
    variavel_lower = variavel.lower()
    if variavel_lower in texto and "incorrect" in texto:
        raise NasaPowerVariavelInvalida(
            f"A variável '{variavel}' não está disponível na comunidade AG "
            f"da NASA POWER. Mensagens da API: {msgs}"
        )


# ---------------------------------------------------------------------------
# 4. Funções principais (expostas para o app)
# ---------------------------------------------------------------------------
def baixar_variavel(variavel: str, lat: float, lon: float,
                    ano_inicio: int, ano_fim: int,
                    forcar_download: bool = False
                    ) -> Tuple[Dict[str, Any], bool]:
    """Baixa UMA variável da NASA POWER (com cache).

    Retorna (payload_json, veio_do_cache).
    `veio_do_cache=True` indica que NÃO houve chamada de rede — usado
    pela função de orquestração para decidir se pausa entre requisições
    (só pausamos quando bateu na API de verdade).

    Levanta NasaPowerVariavelInvalida se a API rejeitar a variável,
    ou NasaPowerRedeIndisponivel se não houver rede nem cache.

    Args:
        variavel: sigla como "T2M", "PRECTOTCORR", "GWETROOT".
        lat, lon: coordenadas.
        ano_inicio, ano_fim: anos civis (inclusive).
        forcar_download: se True, ignora o cache e baixa de novo.
    """
    cache_path = _nome_cache(lat, lon, ano_inicio, ano_fim, variavel)

    # 1) Tenta o cache primeiro (modo offline).
    if not forcar_download and cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as f:
            return json.load(f), True

    # 2) Sem cache -> vai para a rede.
    start, end = _periodo_para_datas(ano_inicio, ano_fim)
    payload = _chamar_api(variavel, lat, lon, start, end)

    # 3) Confere se a variável foi aceita (mensagens de erro mesmo com 200).
    _avaliar_resposta(payload, variavel)

    # 4) Salva o cache para o próximo acesso.
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload, False


def baixar_multiplas(variaveis: List[str], lat: float, lon: float,
                     ano_inicio: int, ano_fim: int,
                     forcar_download: bool = False,
                     intervalo_segundos: float = config.NASA_POWER_PAUSA_SEGUNDOS
                     ) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Baixa várias variáveis, uma requisição por variável.

    Uma variável inválida NÃO derruba as demais: ela é registrada em
    `falhas` e o restante é retornado normalmente.

    A pausa `intervalo_segundos` entre requisições SÓ é aplicada quando
    a variável anterior foi baixada da rede. Se veio do cache, não pausa
    (cache hit = sem custo de rede).

    Returns:
        (sucessos, falhas)
            sucessos: {variavel: payload_da_api, ...} para as que funcionaram.
            falhas:   lista de strings "variavel: motivo" para as que falharam.
    """
    sucessos: Dict[str, Dict[str, Any]] = {}
    falhas: List[str] = []

    for v in variaveis:
        houve_rede = False
        try:
            payload, veio_do_cache = baixar_variavel(
                v, lat, lon, ano_inicio, ano_fim, forcar_download=forcar_download
            )
            sucessos[v] = payload
            houve_rede = not veio_do_cache
        except NasaPowerVariavelInvalida as e:
            falhas.append(f"{v}: variável inválida ({e})")
        except NasaPowerRedeIndisponivel as e:
            falhas.append(f"{v}: sem rede/cache ({e})")
        except Exception as e:  # noqa: BLE001 - não esperado, mas isola a variável
            falhas.append(f"{v}: erro inesperado ({e})")

        # Pausa curta SÓ se houve chamada de rede (cache não precisa).
        if houve_rede:
            time.sleep(intervalo_segundos)

    return sucessos, falhas


def para_dataframe(payload: Dict[str, Any]) -> Tuple[pd.DataFrame, VariavelInfo]:
    """Converte o JSON de UMA variável em um DataFrame (index = data).

    Retorna (df, info):
        df: coluna = nome da variável; index = datas (datetime).
            Valores -999 (ausente da NASA POWER) viram None.
        info: metadados da variável (nome, longname, units).

    Estrutura esperada do payload (confirmada por chamada real à API):
        {
          "parameters": {"T2M": {"longname": "...", "units": "C"}},
          "properties": {"parameter": {"T2M": {"YYYYMMDD": valor, ...}}}
        }
    """
    try:
        props = payload["properties"]
        parametro = props["parameter"]
    except (KeyError, TypeError) as e:
        raise NasaPowerError(
            f"Resposta da NASA POWER sem estrutura esperada: {e}"
        ) from e

    if not parametro:
        raise NasaPowerError("Resposta da NASA POWER vazia (sem dados).")

    nome_var = next(iter(parametro))
    serie_dict = parametro[nome_var]

    # Conversão vetorizada (bem mais rápida que loop com pd.to_datetime).
    # - datas: array de strings "YYYYMMDD" -> DatetimeIndex
    # - valores: -999 ou None -> NaN (valores ausentes da NASA POWER)
    datas = pd.to_datetime(list(serie_dict.keys()), format="%Y%m%d")
    serie_pd = pd.Series(list(serie_dict.values()))
    serie_pd = pd.to_numeric(serie_pd, errors="coerce")
    serie_pd = serie_pd.mask(serie_pd == -999)  # -999 -> NaN

    df = pd.DataFrame({nome_var: serie_pd.to_numpy()}, index=datas)
    df.index.name = "data"

    # Metadados: lê direto de payload["parameters"][VAR] (formato oficial).
    meta = (payload.get("parameters") or {}).get(nome_var, {}) or {}
    info = VariavelInfo(
        nome=nome_var,
        longname=meta.get("longname", ""),
        units=meta.get("units", ""),
    )
    return df, info


def carregar_series(lat: float = config.LAT_DEFAULT,
                    lon: float = config.LON_DEFAULT,
                    ano_inicio: int = config.ANO_INICIO_SERIE,
                    ano_fim: int = config.ANO_FIM_SERIE,
                    forcar_download: bool = False
                    ) -> Tuple[pd.DataFrame, List[str], List[VariavelInfo]]:
    """Carrega TODAS as variáveis do config como um único DataFrame.

    Usa o período fixo definido em config.ANO_INICIO_SERIE/ANO_FIM_SERIE
    (1991-2025 por padrão). O nome do arquivo de cache depende desses
    anos, então fica estável entre execuções (a demo offline funciona).

    Args:
        lat, lon: coordenadas (default: Teresina-PI).
        ano_inicio, ano_fim: anos civis (inclusive). Defaults do config.
        forcar_download: ignora o cache.

    Returns:
        (df, falhas, infos)
            df: DataFrame com index=data e uma coluna por variável.
            falhas: lista de strings "variavel: motivo".
            infos: metadados de cada variável carregada com sucesso.
    """
    sucessos, falhas = baixar_multiplas(
        config.NASA_POWER_VARS, lat, lon, ano_inicio, ano_fim,
        forcar_download=forcar_download,
    )

    frames: List[pd.DataFrame] = []
    infos: List[VariavelInfo] = []
    for var, payload in sucessos.items():
        try:
            df_v, info = para_dataframe(payload)
            frames.append(df_v)
            infos.append(info)
        except NasaPowerError as e:
            falhas.append(f"{var}: erro ao parsear ({e})")

    if frames:
        df = pd.concat(frames, axis=1).sort_index()
    else:
        # Sem nenhuma variável: devolve DataFrame vazio (interface avisa).
        df = pd.DataFrame()

    return df, falhas, infos


def resumo_mensal(df: pd.DataFrame, var: str) -> pd.DataFrame:
    """Agrega uma variável diária para média/suma mensal.

    - PRECTOTCORR: soma mensal (mm/mês). Usa min_count=1 em .sum() para
      que meses totalmente vazios viram NaN (não 0).
    - Demais: média mensal. Meses sem dado viram NaN naturalmente.
    """
    if var not in df.columns:
        raise NasaPowerError(f"Variável '{var}' não está no DataFrame.")
    if df.empty:
        return pd.DataFrame()

    sub = df[[var]].dropna()
    if sub.empty:
        return pd.DataFrame()

    if var == "PRECTOTCORR":
        # min_count só é aceito por .sum(), não por .mean().
        mensal = sub.resample("MS").sum(min_count=1)
        mensal.columns = [f"{var}_soma_mm"]
    else:
        mensal = sub.resample("MS").mean()
        mensal.columns = [f"{var}_media"]
    return mensal


# ---------------------------------------------------------------------------
# 5. Verificação rápida (chamada direta no terminal)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Baixando {len(config.NASA_POWER_VARS)} variáveis para "
          f"({config.LAT_DEFAULT}, {config.LON_DEFAULT}) "
          f"({config.ANO_INICIO_SERIE}-{config.ANO_FIM_SERIE})...")
    df, falhas, infos = carregar_series()
    print(f"\nVariáveis carregadas: {list(df.columns)}")
    print(f"Período: {df.index.min()} a {df.index.max()}")
    print(f"Linhas: {len(df)}")
    if falhas:
        print("\nFalhas:")
        for f in falhas:
            print(f"  - {f}")
    if infos:
        print("\nMetadados:")
        for i in infos:
            print(f"  - {i.nome}: {i.longname} ({i.units})")
