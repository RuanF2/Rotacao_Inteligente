"""Verificação independente — São Raimundo Nonato-PI (cenário demonstrativo).

Recalcula, DIRETO dos JSON brutos da NASA POWER e SEM importar nenhuma função do backend:
  * tendências de Tmax, dias de calor e chuva (Theil-Sen + Mann-Kendall);
  * balanço hídrico, perda potencial (FAO-33), anos-safra com perda > 50 % e déficit hídrico de:
      - Estratégia A (rotação atual): milho semeado em 1º/jan nos anos 1 e 2;
      - Estratégia C (resiliência hídrica): sorgo em 1º/jan do ano 1 e milheto em 1º/jan do ano 2.

O modelo é reescrito aqui a partir da METHODOLOGY.md (seções 1 e 4.3):
  ET0 Hargreaves-Samani (FAO-56 Eq. 52, Ra Eqs. 21-25); curva de Kc em 4 estádios (20/30/30/20 %);
  chuva efetiva USDA-SCS sobre o total mensal, aplicada a cada dia pelo fator Pe/P do mês;
  ETa = min(ETc, Pe) (sequeiro); d = 1 - ETa/ETc; perda = min(1, Ky·d).

Parâmetros (documentados no catálogo; NÃO ajustados para coincidir com o backend):
  milho   120 d, Kc 0,30/1,20/0,35, Ky 1,25 (FAO-33)
  sorgo   100 d, Kc 0,30/1,05/0,55, Ky 0,90 (FAO-33)
  milheto  90 d, Kc 0,30/1,00/0,30, Ky NÃO TABELADO na FAO-33 -> ASSUMIDO 1,0 (mesma convenção do backend)

Duas formas de contar os anos-safra são reportadas (ver METHODOLOGY.md, seção 4.4.1):
  (1) PARES DESLIZANTES — a do backend: pares (y, y+1), y = 1991..2024 => 34 pares sobrepostos, 68 observações;
  (2) ANOS ÚNICOS — cada ano histórico usado uma única vez, nas duas "fases" possíveis da rotação.

Uso:
    python scripts/verificacao_independente_srn.py                 # só o recálculo
    python scripts/verificacao_independente_srn.py --api http://localhost:8000   # compara com a API em execução
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import urllib.request
from pathlib import Path

import numpy as np
from scipy import stats

RAIZ = Path(__file__).resolve().parents[1]
CACHE = RAIZ / "rotacao_inteligente" / "data" / "cache"
PREF = "power_n9p02_n42p70_1991_2026_"
LAT = -9.015
ANOS = list(range(1991, 2026))          # anos civis completos usados
PARES = list(range(1991, 2025))         # y da par (y, y+1)
LIMIAR_QUEBRA = 0.5
FRACOES = (0.20, 0.30, 0.30, 0.20)

CULTURAS = {
    "milho":   {"ciclo": 120, "kc": (0.30, 1.20, 0.35), "ky": 1.25, "ky_fonte": "FAO-33"},
    "sorgo":   {"ciclo": 100, "kc": (0.30, 1.05, 0.55), "ky": 0.90, "ky_fonte": "FAO-33"},
    "milheto": {"ciclo": 90,  "kc": (0.30, 1.00, 0.30), "ky": 1.00, "ky_fonte": "ASSUMIDO (não tabelado na FAO-33)"},
}
ESTRATEGIAS = {
    "A": {"nome": "Rotação atual", "slots": [("milho", 1), ("milho", 2)]},       # (cultura, ano no ciclo de 2 anos)
    "C": {"nome": "Resiliência hídrica", "slots": [("sorgo", 1), ("milheto", 2)]},
}
MES_SEMEADURA = 1   # todas as semeaduras destas estratégias em 1º de janeiro


# ---------------------------------------------------------------------------
# Dados brutos
# ---------------------------------------------------------------------------
def serie(var: str) -> dict:
    d = json.loads((CACHE / f"{PREF}{var}.json").read_text(encoding="utf-8"))
    return {k: (None if v == -999 else v) for k, v in d["properties"]["parameter"][var].items()}


TMAX, TMED, TMIN, P = serie("T2M_MAX"), serie("T2M"), serie("T2M_MIN"), serie("PRECTOTCORR")
AUSENTES_USADOS: set[str] = set()


def val(s: dict, k: str):
    v = s.get(k)
    if v is None:
        AUSENTES_USADOS.add(k)
    return v


# ---------------------------------------------------------------------------
# Modelo (reimplementação própria)
# ---------------------------------------------------------------------------
def ra(doy: int) -> float:
    phi = math.radians(LAT)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    de = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(de))))
    return 24 * 60 / math.pi * 0.082 * dr * (ws * math.sin(phi) * math.sin(de) + math.cos(phi) * math.cos(de) * math.sin(ws))


def et0(d: dt.date) -> float:
    k = d.strftime("%Y%m%d")
    amp = max(0.0, val(TMAX, k) - val(TMIN, k))
    return max(0.0, 0.0023 * (val(TMED, k) + 17.8) * math.sqrt(amp) * 0.408 * ra(d.timetuple().tm_yday))


def kc(i: int, L: int, k3) -> float:
    ini, mid, end = k3
    l1, l2, l3 = max(1, round(L * FRACOES[0])), max(1, round(L * FRACOES[1])), max(1, round(L * FRACOES[2]))
    l4 = max(1, L - l1 - l2 - l3)
    if i < l1:
        return ini
    if i < l1 + l2:
        return ini + (mid - ini) * (i - l1) / l2
    if i < l1 + l2 + l3:
        return mid
    return mid + (end - mid) * (i - l1 - l2 - l3) / (l4 - 1) if l4 > 1 else end


_FATOR = {}


def fator_pe(y: int, m: int) -> float:
    if (y, m) not in _FATOR:
        tot = sum(v for k, v in P.items() if k.startswith(f"{y}{m:02d}") and v is not None)
        pe = tot * (125 - 0.2 * tot) / 125 if tot <= 250 else 125 + 0.1 * tot
        _FATOR[(y, m)] = pe / tot if tot > 0 else 0.0
    return _FATOR[(y, m)]


def ciclo(cultura: str, ano: int) -> dict:
    c = CULTURAS[cultura]
    d0 = dt.date(ano, MES_SEMEADURA, 1)
    etc = pe = 0.0
    for i in range(c["ciclo"]):
        d = d0 + dt.timedelta(days=i)
        k = d.strftime("%Y%m%d")
        etc += kc(i, c["ciclo"], c["kc"]) * et0(d)
        pe += (val(P, k) or 0.0) * fator_pe(d.year, d.month)
    deficit = max(0.0, etc - pe)
    d_rel = 1 - min(etc, pe) / etc
    return {"etc": etc, "pe": pe, "deficit": deficit, "perda": min(1.0, c["ky"] * d_rel)}


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def por_ano(cultura: str) -> dict[int, dict]:
    return {a: ciclo(cultura, a) for a in ANOS}


def metricas_pares(estr: dict, tab: dict) -> dict:
    """Reproduz a contagem do backend: 34 pares sobrepostos (y, y+1) -> 68 observações de ano-safra."""
    obs_perda, obs_quebra, deficit_par = [], [], []
    for y in PARES:
        soma = 0.0
        for cultura, ano in estr["slots"]:
            r = tab[cultura][y + ano - 1]
            obs_perda.append(r["perda"])
            obs_quebra.append(r["perda"] > LIMIAR_QUEBRA)
            soma += r["deficit"]
        deficit_par.append(soma / 2)       # mm por ano
    por_slot = {}
    for cultura, ano in estr["slots"]:
        rs = [tab[cultura][y + ano - 1] for y in PARES]
        por_slot[f"{cultura} (ano {ano})"] = {
            "anos_usados": f"{PARES[0] + ano - 1}–{PARES[-1] + ano - 1}",
            "perda_media": float(np.mean([r["perda"] for r in rs])),
            "etc_medio": float(np.mean([r["etc"] for r in rs])),
            "pe_media": float(np.mean([r["pe"] for r in rs])),
        }
    return {"n_observacoes": len(obs_quebra), "freq_quebra": float(np.mean(obs_quebra)),
            "perda_media": float(np.mean(obs_perda)), "deficit_mm_ano": float(np.mean(deficit_par)),
            "por_slot": por_slot}


def metricas_anos_unicos(estr: dict, tab: dict) -> dict:
    """Cada ano histórico 1991–2025 entra UMA vez. Como a rotação tem 2 fases, há 2 alinhamentos possíveis:
    'fase par'   — slot do ano 1 nos anos ímpares (1991, 1993, ...) e slot do ano 2 nos pares;
    'fase ímpar' — o contrário. Também se reporta a frequência de cada cultura em todos os 35 anos."""
    (c1, _), (c2, _) = estr["slots"]
    out = {}
    for nome, primeiro in (("alinhamento 1 (ano 1 da rotação em 1991, 1993, …)", c1),
                           ("alinhamento 2 (ano 1 da rotação em 1992, 1994, …)", c2)):
        segundo = c2 if primeiro == c1 else c1
        q = [tab[primeiro if (a - 1991) % 2 == 0 else segundo][a]["perda"] > LIMIAR_QUEBRA for a in ANOS]
        out[nome] = {"n_anos_unicos": len(q), "anos_com_quebra": int(sum(q)), "freq_quebra": float(np.mean(q))}
    for c in dict.fromkeys([c1, c2]):
        q = [tab[c][a]["perda"] > LIMIAR_QUEBRA for a in ANOS]
        out[f"{c} em todos os anos 1991–2025"] = {"n_anos_unicos": len(q), "anos_com_quebra": int(sum(q)),
                                                  "freq_quebra": float(np.mean(q))}
    return out


def tendencias() -> dict:
    tmax_anual = [np.mean([v for k, v in TMAX.items() if k.startswith(str(a)) and v is not None]) for a in ANOS]
    dias35 = [sum(1 for k, v in TMAX.items() if k.startswith(str(a)) and v is not None and v >= 35) for a in ANOS]
    pa = [sum(v for k, v in P.items() if k.startswith(str(a)) and v is not None) for a in ANOS]
    t = lambda y: (stats.theilslopes(y, ANOS)[0] * 10, stats.kendalltau(ANOS, y)[1])  # noqa: E731
    return {"tmax": t(tmax_anual), "dias35": t(dias35), "chuva": t(pa), "chuva_media": float(np.mean(pa))}


def comparar_api(url: str, res: dict) -> None:
    def post(path, body=None):
        req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST" if body else "GET")
        return json.loads(urllib.request.urlopen(req, timeout=600).read())
    an = post("/api/analise", post("/api/demo"))
    print("\n== Comparação com a API em execução (" + url + ") ==")
    print(f"{'item':48} {'independente':>13} {'backend':>10} {'dif':>8}")
    for e in an["estrategias"]:
        if e["chave"] not in res:
            continue
        av, r = e["avaliacao"], res[e["chave"]]["pares"]
        slots_back = [(s["cultura"], s["ano"], s["mes"]) for s in av["slots"]]
        slots_ind = [(c, a, MES_SEMEADURA) for c, a in ESTRATEGIAS[e["chave"]]["slots"]]
        if sorted(slots_back) != sorted(slots_ind):
            print(f"  {e['chave']}: o backend selecionou outra sequência {slots_back}; comparação não aplicável.")
            continue
        linhas = [(f"{e['chave']} anos-safra com perda > 50 %", r["freq_quebra"], av["indicadores"]["risco_quebra_anos"]),
                  (f"{e['chave']} déficit hídrico (mm/ano)", r["deficit_mm_ano"], av["objetivos"]["demanda_irrigacao_mm_ano"])]
        for s in av["slots"]:
            k = f"{s['cultura']} (ano {s['ano']})"
            linhas.append((f"{e['chave']} perda média {k}", r["por_slot"][k]["perda_media"], s["perda_rendimento_media"]))
            linhas.append((f"{e['chave']} ETc média {k} (mm)", r["por_slot"][k]["etc_medio"], s["etc_mm"]))
            linhas.append((f"{e['chave']} chuva efetiva média {k} (mm)", r["por_slot"][k]["pe_media"], s["chuva_efetiva_mm"]))
        for nome, a, b in linhas:
            print(f"  {nome:46} {a:13.3f} {b:10.3f} {a - b:+8.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", help="URL da API em execução para comparar (ex.: http://localhost:8000)")
    args = ap.parse_args()

    t = tendencias()
    print("== Tendências (1991–2025, NASA POWER bruto) ==")
    print(f"Tmax: {t['tmax'][0]:+.3f} °C/década, Mann-Kendall p = {t['tmax'][1]:.5f}")
    print(f"Dias Tmax ≥ 35 °C: {t['dias35'][0]:+.2f} dias/década, p = {t['dias35'][1]:.5f}")
    print(f"Chuva anual: média {t['chuva_media']:.1f} mm; {t['chuva'][0]:+.1f} mm/década, p = {t['chuva'][1]:.3f}")

    tab = {c: por_ano(c) for c in CULTURAS}
    res = {}
    for k, estr in ESTRATEGIAS.items():
        pares = metricas_pares(estr, tab)
        unicos = metricas_anos_unicos(estr, tab)
        res[k] = {"pares": pares, "anos_unicos": unicos}
        print(f"\n== Estratégia {k} — {estr['nome']}: " + " → ".join(f"{c} (jan, ano {a})" for c, a in estr["slots"]) + " ==")
        for c, _ in estr["slots"]:
            print(f"  Ky {c}: {CULTURAS[c]['ky']} — {CULTURAS[c]['ky_fonte']}")
        print(f"  [pares deslizantes] {len(PARES)} pares sobrepostos = {pares['n_observacoes']} observações de ano-safra")
        print(f"    anos-safra com perda > 50 %: {pares['freq_quebra'] * 100:.1f} %")
        print(f"    perda potencial média: {pares['perda_media'] * 100:.1f} %   déficit hídrico médio: {pares['deficit_mm_ano']:.1f} mm/ano")
        for nome, s in pares["por_slot"].items():
            print(f"    {nome:18} anos {s['anos_usados']}: perda média {s['perda_media'] * 100:.1f} %, "
                  f"ETc {s['etc_medio']:.1f} mm, chuva efetiva {s['pe_media']:.1f} mm")
        print("  [anos históricos únicos 1991–2025, sem sobreposição]")
        for nome, u in unicos.items():
            print(f"    {nome:52} {u['anos_com_quebra']:2d}/{u['n_anos_unicos']} = {u['freq_quebra'] * 100:.1f} %")

    print("\n== Anos históricos com perda > 50 % (cultura semeada em 1º/jan daquele ano) ==")
    for c in CULTURAS:
        anos_q = [a for a in ANOS if tab[c][a]["perda"] > LIMIAR_QUEBRA]
        print(f"  {c:8} {len(anos_q):2d}/35: {anos_q}")
    print("  Nos pares, o slot do ano 1 só usa 1991–2024 e o do ano 2 só usa 1992–2025: as quebras de 2025 no slot do\n"
          "  ano 1 e de 1991 no slot do ano 2 ficam fora; os anos 1992–2024 aparecem em duas observações (uma por fase).")
    dentro = sorted(k for k in AUSENTES_USADOS if k <= "20251231")
    print(f"\nDias sem dado dentro dos ciclos avaliados: {len(dentro)}" + (f" ({dentro[:5]}…)" if dentro else ""))
    (RAIZ / "scripts" / "verificacao_independente_srn.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.api:
        comparar_api(args.api.rstrip("/"), res)


if __name__ == "__main__":
    main()
