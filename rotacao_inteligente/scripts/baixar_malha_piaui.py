"""Baixa a malha oficial do Piauí (IBGE, UF 22) e salva como GeoJSON.

Rode UMA VEZ no seu computador (com internet) antes de usar a grade
de risco do mapa:

    python scripts/baixar_malha_piaui.py

Isso cria data/piaui_uf.geojson. Quando esse arquivo existe,
gerar_pontos_grade usa ponto-em-polígono (filtro exato pela fronteira
do estado). Se o arquivo não existir, a grade usa o retângulo
config.PIAUI_BBOX como fallback (rotulado).

Fonte: API de Malhas Digitais do IBGE
  https://servicodados.ibge.gov.br/api/v2/malhas/22?formato=application/vnd.geo+json
(O IBGE retorna TopoJSON por padrão; aqui pedimos GeoJSON.)

Sem internet, o script avisa e não cria o arquivo (a grade cai no
fallback do retângulo).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que o diretório do projeto está no PYTHONPATH.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402  (após ajuste de sys.path)


URL_IBGE = (
    "https://servicodados.ibge.gov.br/api/v2/malhas/22"
    "?formato=application/vnd.geo+json&qualidade=minima"
)
DESTINO = config.PIAUI_MALHA_GEOJSON


def main() -> int:
    import urllib.request
    import urllib.error

    print(f"Baixando malha do Piauí (IBGE, UF 22)...")
    print(f"  URL: {URL_IBGE}")
    print(f"  Destino: {DESTINO}")
    try:
        req = urllib.request.Request(URL_IBGE, headers={"Accept": "application/vnd.geo+json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            dados = r.read()
    except urllib.error.URLError as e:
        print(f"\n❌ Falha no download (sem internet ou IBGE indisponível): {e}")
        print("   A grade de risco vai usar o retângulo config.PIAUI_BBOX "
              "como fallback (menos preciso).")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"\n❌ Erro inesperado: {e}")
        return 1

    # Validação mínima: começa com {" e tem "FeatureCollection" ou "features".
    texto = dados.decode("utf-8", errors="replace").lstrip()
    if not texto.startswith("{") or ("FeatureCollection" not in texto
                                     and "features" not in texto
                                     and "geometry" not in texto):
        print(f"\n❌ Resposta não parece um GeoJSON (primeiros 120 bytes):")
        print(f"   {texto[:120]!r}")
        return 1

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_bytes(dados)
    print(f"\n✅ Malha salva em {DESTINO} ({len(dados)} bytes).")
    print("   A grade de risco agora vai usar ponto-em-polígono (filtro "
          "exato pela fronteira do estado).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
