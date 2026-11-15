"""Baixa os caches da NASA POWER (1991-2026) para Picos-PI e São Raimundo Nonato-PI.

Coordenadas confirmadas pelo usuário (sede municipal, Wikipédia — IBGE fora do ar):
  - Picos-PI:                  lat=-7.07694, lon=-41.46694
  - São Raimundo Nonato-PI:    lat=-9.015,   lon=-42.69889
"""
import sys
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "rotacao_inteligente"))

from core.nasa_power import carregar_series

MUNICIPIOS = [
    ("Picos-PI", -7.07694, -41.46694),
    ("São Raimundo Nonato-PI", -9.015, -42.69889),
]

ANO_INICIO = 1991
ANO_FIM = 2026

if __name__ == "__main__":
    for nome, lat, lon in MUNICIPIOS:
        t0 = time.perf_counter()
        print(f"\n=== Baixando {nome} (lat={lat}, lon={lon}) ===")
        df, falhas, infos = carregar_series(
            lat=lat, lon=lon, ano_inicio=ANO_INICIO, ano_fim=ANO_FIM,
        )
        dt = time.perf_counter() - t0
        print(f"  {nome}: {len(df)} linhas, {len(df.columns)} vars, "
              f"{len(falhas)} falhas, período {df.index.min()} a "
              f"{df.index.max()} ({dt:.1f}s)")
        if falhas:
            for f in falhas:
                print(f"    FALHA: {f}")
    print("\nConcluído.")
