"""Gera as tabelas dos 3 municípios do Piauí (revisão 2026-11-14) com:
- mês de semeadura por cultura (não 1/nov fixo)
- risco hídrico (% anos c/ chuva < agua) por cultura/cenário
- desempate do pior cenário pelo risco hídrico
- alternância safra 1 / safra 2 (não mesmo mês)
- janela pós-colheita para cultura de cobertura
Diz em qual dos 3 municípios os cenários mais se separam.
"""
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
                              melhor_mes_semeadura, risco_hidrico_por_classe,
                              mes_da_colheita, janela_pos_colheita)
from core.janelas import nome_mes, calcular_janelas
import config

ROTACOES = {
    "atual": {"culturas": ["milho"], "prioridade": "renda",
              "rotulos": ["milho", "(pousio)"]},
    "solo":  {"culturas": ["milho", "crotalaria-juncea"], "prioridade": "solo",
              "rotulos": ["milho", "crotalária"]},
    "agua":  {"culturas": ["sorgo", "feijao-caupi"], "prioridade": "agua",
              "rotulos": ["sorgo", "caupi"]},
}

LOCAIS = [
    ("Teresina", -5.09, -42.81),
    ("Picos", -7.07694, -41.46694),
    ("São Raimundo Nonato", -9.015, -42.69889),
]

classes_ordem = ("El Niño", "La Niña", "neutro")

def tabela_municipio(nome_loc, lat, lon, classes, banco):
    df, _, _ = carregar_series(lat=lat, lon=lon)
    completos, _ = anos_agricolas_completos(df)
    if not completos:
        return None, None
    # Mês de semeadura padrão por cultura
    meses_sel = {}
    for cn in ["milho", "feijao-caupi", "crotalaria-juncea", "sorgo"]:
        if cn not in banco: continue
        mes, _, _ = melhor_mes_semeadura(df, banco[cn], anos_agricolas_completos=completos)
        meses_sel[cn] = mes

    print(f"\n{'='*78}")
    print(f"MÊS DE SEMEADURA POR CULTURA — {nome_loc}")
    print(f"{'='*78}")
    for cn in ["milho", "feijao-caupi", "crotalaria-juncea", "sorgo"]:
        if cn not in banco or meses_sel.get(cn) is None: continue
        print(f"  {cn:<20} -> {nome_mes(meses_sel[cn])}")

    print(f"\nCOMPARATIVO DE ROTAÇÕES x CENÁRIO ENSO — {nome_loc}")
    print(f"{'rotação':<8} {'semeadura':<26} {'El Niño':>14} {'La Niña':>14} {'neutro':>14} {'pior':<14}")
    print("-"*78)
    scores_finais = {}
    janelas_pos = {}
    for nome_rot, defn in ROTACOES.items():
        culturas_rot = defn["culturas"]
        partes = []
        for idx, cn in enumerate(culturas_rot):
            if cn in meses_sel and meses_sel[cn]:
                rotulo = f"safra {idx+1}" if len(culturas_rot) > 1 else "safra 1"
                partes.append(f"{rotulo}:{nome_mes(meses_sel[cn])}")
        linha = [nome_rot, " | ".join(partes)]
        for classe in classes_ordem:
            scores = []
            for cn in culturas_rot:
                if cn not in banco: continue
                cult = banco[cn]
                mes = meses_sel[cn]
                r_jan = calcular_janelas(df, cult, anos_agricolas_completos=completos)
                jm = next((jm for jm in r_jan.janelas if jm.mes == mes), None)
                tem_jv = bool(jm and jm.e_janela)
                chuvas = chuva_ciclo_por_classe(df, cult, classes,
                                                 completos[0], completos[-1],
                                                 mes_semeadura=mes)
                riscos = risco_hidrico_por_classe(df, cult, classes,
                                                   completos[0], completos[-1],
                                                   mes_semeadura=mes)
                med, n = chuvas[classe]
                sc = pontuar_cultura_cenario(df, cult, classe, med, n,
                                              mes_semeadura=mes,
                                              tem_janela_valida=tem_jv,
                                              risco_hidrico_pct=riscos[classe])
                scores.append(sc)
            sr = pontuar_rotacao_cenario(scores, nome_rot, classe, defn["prioridade"])
            scores_finais[(nome_rot, classe)] = sr
            idx_val = sr.indice if sr.indice is not None else 0
            risco = f"r:{sr.risco_hidrico_pct:.0f}%" if sr.risco_hidrico_pct is not None else "r:—"
            linha.append(f"{idx_val:.1f} ({risco})")
        # pior cenário (desempate por risco)
        scores_rot = {classe: scores_finais.get((nome_rot, classe)) for classe in classes_ordem}
        pior_c, _ = pior_cenario({k: v for k, v in scores_rot.items() if v is not None})
        linha.append(pior_c or "—")
        # janela pós-colheita (se rotação tem cobertura)
        if len(culturas_rot) == 2:
            c1, c2 = culturas_rot
            if c1 in banco and c2 in banco and banco[c2].tipo == "cobertura":
                m1 = meses_sel.get(c1); ciclo1 = banco[c1].ciclo_dias
                if m1 and ciclo1:
                    mes_colh = mes_da_colheita(m1, ciclo1)
                    r_cob = calcular_janelas(df, banco[c2], anos_agricolas_completos=completos)
                    jpc = janela_pos_colheita(r_cob, mes_colh)
                    janelas_pos[nome_rot] = jpc
        print(f"{linha[0]:<8} {linha[1]:<26} {linha[2]:>14} {linha[3]:>14} {linha[4]:>14} {linha[5]:<14}")

    # Janela pós-colheita
    if janelas_pos:
        print(f"\nJANELA PÓS-COLHEITA (cultura de cobertura após safra 1):")
        for nome_rot, jpc in janelas_pos.items():
            if jpc.tem_janela_pos_colheita:
                print(f"  {nome_rot}: ✓ janela em {', '.join(jpc.meses_disponiveis)} "
                      f"(colheita safra 1 em {nome_mes(jpc.mes_colheita_safra1)})")
            else:
                print(f"  {nome_rot}: ✗ {jpc.aviso}")

    # Separação entre cenários: para cada rotação, amplitude do índice
    # e amplitude do risco hídrico entre os 3 cenários.
    print(f"\nSEPARAÇÃO ENTRE CENÁRIOS (amplitude índice e risco):")
    for nome_rot in ROTACOES:
        idxs = [scores_finais[(nome_rot, c)].indice for c in classes_ordem
                if scores_finais.get((nome_rot, c)) and scores_finais[(nome_rot, c)].indice is not None]
        riscos = [scores_finais[(nome_rot, c)].risco_hidrico_pct for c in classes_ordem
                  if scores_finais.get((nome_rot, c)) and scores_finais[(nome_rot, c)].risco_hidrico_pct is not None]
        amp_idx = (max(idxs) - min(idxs)) if idxs else 0
        amp_risco = (max(riscos) - min(riscos)) if riscos else 0
        print(f"  {nome_rot:<8}: amplitude índice = {amp_idx:.1f} pts, "
              f"amplitude risco = {amp_risco:.0f}%")
    return scores_finais, janelas_pos

# === MAIN ===
classes, _, _ = carregar_classificacao()
banco = carregar_banco()
print(f"ENSO: {[c for c in classes_ordem]}")
resultados = {}
for nome_loc, lat, lon in LOCAIS:
    sf, jpc = tabela_municipio(nome_loc, lat, lon, classes, banco)
    resultados[nome_loc] = (sf, jpc)

# Em qual dos 3 municípios os cenários mais se separam?
print(f"\n{'='*78}")
print(f"EM QUAL MUNICÍPIO OS CENÁRIOS MAIS SE SEPARAM?")
print(f"{'='*78}")
print(f"{'município':<24} {'amp índice média':>18} {'amp risco média':>18}")
separacoes = []
for nome_loc in [l[0] for l in LOCAIS]:
    sf, _ = resultados[nome_loc]
    if sf is None: continue
    amp_idx_media = []
    amp_risco_media = []
    for nome_rot in ROTACOES:
        idxs = [sf[(nome_rot, c)].indice for c in classes_ordem
                if sf.get((nome_rot, c)) and sf[(nome_rot, c)].indice is not None]
        riscos = [sf[(nome_rot, c)].risco_hidrico_pct for c in classes_ordem
                  if sf.get((nome_rot, c)) and sf[(nome_rot, c)].risco_hidrico_pct is not None]
        if idxs: amp_idx_media.append(max(idxs) - min(idxs))
        if riscos: amp_risco_media.append(max(riscos) - min(riscos))
    media_idx = sum(amp_idx_media)/len(amp_idx_media) if amp_idx_media else 0
    media_risco = sum(amp_risco_media)/len(amp_risco_media) if amp_risco_media else 0
    separacoes.append((nome_loc, media_idx, media_risco))
    print(f"{nome_loc:<24} {media_idx:>18.2f} {media_risco:>18.1f}%")

# Qual tem a maior amplitude (índice + risco normalizado)
melhor = max(separacoes, key=lambda x: x[1] + x[2]/10)
print(f"\n>>> Os cenários mais se separam em: {melhor[0]} "
      f"(amp índice média {melhor[1]:.2f}, amp risco média {melhor[2]:.1f}%)")
