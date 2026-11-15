"""Gera a nova tabela 3x3 de Teresina (revisão 2026-11-14) com o método
corrigido: cada cultura é avaliada no seu mês de semeadura (não 1/nov)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent / "download" / "rotacao_inteligente"
sys.path.insert(0, str(ROOT))

import pandas as pd
from core.nasa_power import carregar_series
from core.enso import anos_agricolas_completos, carregar_classificacao
from core.culturas import carregar_banco
from core.resiliencia import (chuva_ciclo_por_classe, pontuar_cultura_cenario,
                              pontuar_rotacao_cenario, pior_cenario,
                              melhor_mes_semeadura)
from core.semaforo import calcular_semaforo, emoji_cor
from core.janelas import nome_mes

df, _, _ = carregar_series()
completos, _ = anos_agricolas_completos(df)
classes, contagem, _ = carregar_classificacao()
banco = carregar_banco()

ROTACOES = {
    "atual": {"culturas": ["milho"], "prioridade": "renda",
              "rotulos": ["milho", "(pousio)"]},
    "solo":  {"culturas": ["milho", "crotalaria-juncea"], "prioridade": "solo",
              "rotulos": ["milho", "crotalária"]},
    "agua":  {"culturas": ["sorgo", "feijao-caupi"], "prioridade": "agua",
              "rotulos": ["sorgo", "caupi"]},
}

# 1) Mês de semeadura padrão de cada cultura
print("=" * 70)
print("MÊS DE SEMEADURA POR CULTURA (Teresina, revisão 2026-11-14)")
print("=" * 70)
meses_selecionados = {}
for cn in ["milho", "feijao-caupi", "crotalaria-juncea", "sorgo"]:
    if cn not in banco:
        continue
    mes, tem_janela, chuva = melhor_mes_semeadura(
        df, banco[cn], anos_agricolas_completos=completos)
    meses_selecionados[cn] = mes
    marca = "✓ janela" if tem_janela else "✗ sem janela"
    print(f"  {cn:<20} -> {nome_mes(mes):<3} ({marca}, "
          f"chuva mediana ciclo = {chuva:.0f} mm)")

# 2) Tabela 3x3 + pior cenário
print()
print("=" * 70)
print("COMPARATIVO DE ROTAÇÕES x CENÁRIO ENSO (Teresina)")
print("=" * 70)
print(f"{'rotação':<8} {'semeadura':<14} {'El Niño':>8} {'La Niña':>8} "
      f"{'neutro':>8} {'pior':<10}")
print("-" * 70)
scores_finais = {}
for nome_rot, defn in ROTACOES.items():
    meses_rot = [nome_mes(meses_selecionados[cn])
                 for cn in defn["culturas"] if cn in meses_selecionados]
    linha = [nome_rot, " + ".join(meses_rot)]
    pior_c = None; pior_i = None
    for classe in ("El Niño", "La Niña", "neutro"):
        scores = []
        for cn in defn["culturas"]:
            if cn not in banco:
                continue
            cult = banco[cn]
            mes = meses_selecionados[cn]
            # Verifica se o mês é janela (recalcula)
            from core.janelas import calcular_janelas
            r_jan = calcular_janelas(df, cult, anos_agricolas_completos=completos)
            jm = next((jm for jm in r_jan.janelas if jm.mes == mes), None)
            tem_jv = bool(jm and jm.e_janela)
            chuvas = chuva_ciclo_por_classe(df, cult, classes,
                                             completos[0], completos[-1],
                                             mes_semeadura=mes)
            med, n = chuvas[classe]
            sc = pontuar_cultura_cenario(df, cult, classe, med, n,
                                          mes_semeadura=mes,
                                          tem_janela_valida=tem_jv)
            scores.append(sc)
        sr = pontuar_rotacao_cenario(scores, nome_rot, classe, defn["prioridade"])
        scores_finais[(nome_rot, classe)] = sr
        idx = sr.indice if sr.indice is not None else 0
        linha.append(f"{idx:.1f}")
        if pior_i is None or idx < pior_i: pior_i = idx; pior_c = classe
    linha.append(pior_c)
    print(f"{linha[0]:<8} {linha[1]:<14} {linha[2]:>8} {linha[3]:>8} "
          f"{linha[4]:>8} {linha[5]:<10}")

# 3) Semáforos (pior cenário de cada rotação)
print()
print("=" * 70)
print("SEMÁFORO POR ROTAÇÃO (pior cenário, Teresina)")
print("=" * 70)
for nome_rot, defn in ROTACOES.items():
    scores_rot = {classe: scores_finais.get((nome_rot, classe))
                 for classe in ("El Niño", "La Niña", "neutro")}
    pior_c, _ = pior_cenario(
        {k: v for k, v in scores_rot.items() if v is not None})
    if pior_c is None: pior_c = "El Niño"
    culturas_rot = [banco[n] for n in defn["culturas"] if n in banco]
    lacunas = []
    for c in culturas_rot: lacunas.extend(c.lacunas)
    lacunas = list(dict.fromkeys(lacunas))
    usa_est = any(c.usa_agua_estimada for c in culturas_rot)
    sr_pior = scores_finais.get((nome_rot, pior_c))
    tem_jv = (all(sc.tem_janela_valida for sc in sr_pior.scores)
              if sr_pior else True)
    s = calcular_semaforo(
        n_anos_total=len(completos),
        n_anos_por_classe=contagem,
        lacunas_essenciais=lacunas,
        usa_agua_estimada=usa_est,
        local_calibrado=True,
        tem_janela_valida=tem_jv,
        classe_avaliada=pior_c,
    )
    print(f"  {nome_rot:<8} (pior: {pior_c}, semeio: "
          f"{' + '.join(nome_mes(meses_selecionados[cn]) for cn in defn['culturas'] if cn in meses_selecionados)}): "
          f"{emoji_cor(s.cor)} {s.cor} ({s.pontos} pts)")
