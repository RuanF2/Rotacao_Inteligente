"""Intelligent Crop Rotation Engine.

Modelo (detalhado em METHODOLOGY.md, seção 4):

* Horizonte fixo de 24 meses (2 anos agrícolas) em calendário circular — a
  rotação se repete a cada 2 anos. Todas as estratégias usam o MESMO horizonte
  e a MESMA série climática.
* Cada estratégia é uma lista de "slots" (cultura, ano 1|2, mês de semeadura).
* Cada slot é avaliado em TODOS os pares de anos históricos da série NASA POWER
  (≈34 pares), e não só na média climatológica:
    ETc  = Σ Kc(d)·ET0(d)            (FAO-56, Kc em curva de 4 estádios)
    Peff = Σ P(d)·f_mês              (USDA-SCS mensal, método do CROPWAT)
    ETa  = min(ETc, Peff + irrigação alocada)
    d    = 1 − ETa/ETc               (déficit relativo)
    perda= min(1, Ky·d)              (FAO-33; Ky=1 quando não tabelado — sinalizado)
    h    = fração de dias do ciclo com Tmax ≥ Tcrítica da cultura
    v    = 1 − (1−d)(1−h)            (vulnerabilidade do slot)
* Objetivos (NSGA-II, pymoo): minimizar demanda de irrigação, vulnerabilidade
  climática e potencial de erosão; maximizar melhoria do solo, cobertura e
  diversificação. Potencial econômico NÃO é otimizado (faltam preços e
  produtividades locais confiáveis) — isso é informado ao usuário.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from . import catalogo, settings
from .catalogo import Cultura
from .clima import MESES_PT, SerieClimatica, climatologia_mensal, precipitacao_efetiva_mensal
from .legacy import legacy_config

HORIZONTE_MESES = 24
MAX_SLOTS = 4
ESTAB_DIAS = int(legacy_config.JANELA_ESTABELECIMENTO_DIAS)          # 30 (NASA1)
ESTAB_MIN_MM = float(legacy_config.CHUVA_MINIMA_ESTABELECIMENTO_MM)  # 20 (NASA1)
COBERTURA_POR_PROTECAO = {1: 0.4, 2: 0.6, 3: 0.8}  # fração de cobertura do solo (estimativa da equipe)
FRACOES_ESTADIOS = (0.20, 0.30, 0.30, 0.20)         # simplificação da Tabela 11 FAO-56
LIMIAR_FRIO = 0.10      # > 10% dos dias do ciclo abaixo da temperatura-base/geada = fora da janela térmica
LIMIAR_QUEBRA = 0.5                                  # perda relativa > 50% = "ano de quebra"

OBJETIVOS = {
    "demanda_irrigacao_mm_ano": {"nome": "Demanda hídrica não suprida pela chuva", "sentido": "min", "unidade": "mm/ano"},
    "vulnerabilidade_climatica": {"nome": "Vulnerabilidade climática", "sentido": "min", "unidade": "0–1"},
    "potencial_erosao": {"nome": "Potencial de erosão", "sentido": "min", "unidade": "0–1"},
    "melhoria_solo": {"nome": "Potencial de melhoria do solo", "sentido": "max", "unidade": "0–1"},
    "cobertura": {"nome": "Cobertura vegetal efetiva", "sentido": "max", "unidade": "0–1"},
    "diversificacao": {"nome": "Diversificação", "sentido": "max", "unidade": "0–1"},
}


class RotacaoError(Exception):
    """Erro de rotação com diagnóstico opcional fundamentado nas restrições calculadas."""

    def __init__(self, mensagem: str, diagnostico: Optional[dict] = None):
        super().__init__(mensagem)
        self.diagnostico = diagnostico


def diagnosticar_inviabilidade(tab: "TabelaAvaliacao", irrigacao_mm_ano: float,
                              culturas_permitidas: Optional[Sequence[str]] = None) -> dict:
    """Audita as janelas de semeadura; não tenta inferir a causa da falha do NSGA-II.

    Cada cultura comercial e mês é avaliado pelos MESMOS limiares de
    validar_restricoes: frio/geada e chuva de estabelecimento em sequeiro.
    Uma janela viável isoladamente NÃO garante uma rotação de 24 meses viável.
    """
    permitidas = set(culturas_permitidas) if culturas_permitidas else {c.id for c in tab.culturas}
    comerciais = [c for c in tab.culturas if c.id in permitidas and c.tipo == "comercial"]
    diagnostico = {
        "tipo": "sem_estrategia_viavel",
        "titulo": "Nenhuma rotação viável foi encontrada",
        "resumo": "O otimizador não encontrou uma combinação que atendesse a todas as restrições no cenário analisado.",
        "verificacoes": [],
        "orientacoes": [
            "Confira quais culturas são permitidas e se são adequadas à região.",
            "Revise os meses de semeadura, os dados de solo e a disponibilidade real de irrigação.",
            "Se necessário, peça orientação agronômica local. Não altere informações apenas para obter uma recomendação.",
        ],
        "limitacao": "O diagnóstico examina janelas individuais de semeadura; não demonstra que exista uma rotação completa viável. A busca NSGA-II não é prova matemática de inexistência de soluções.",
    }
    if not comerciais:
        diagnostico["verificacoes"].append({
            "codigo": "sem_comercial", "titulo": "Nenhuma cultura comercial permitida",
            "detalhe": "O modelo exige pelo menos uma cultura comercial em cada ano da rotação.",
            "resultado": "bloqueio_confirmado",
        })
        return diagnostico

    frio = chuva = aptos = 0
    total = len(comerciais) * 12
    exemplos = []
    for c in comerciais:
        ci = tab.idx[c.id]
        meses_aptos = []
        for m in range(12):
            aceita_frio = bool(np.isfinite(tab.frio_mediana[ci, m]) and
                               tab.frio_mediana[ci, m] <= LIMIAR_FRIO)
            aceita_chuva = bool(irrigacao_mm_ano > 0 or
                                (np.isfinite(tab.estab_mediana[ci, m]) and
                                 tab.estab_mediana[ci, m] >= ESTAB_MIN_MM))
            if not aceita_frio:
                frio += 1
            if not aceita_chuva:
                chuva += 1
            if aceita_frio and aceita_chuva:
                aptos += 1
                meses_aptos.append(MESES_PT[m])
        if meses_aptos and len(exemplos) < 3:
            exemplos.append(f"{c.nome}: {', '.join(meses_aptos[:5])}" +
                            ("…" if len(meses_aptos) > 5 else ""))

    diagnostico["verificacoes"].append({
        "codigo": "janela_termica", "titulo": "Temperatura e risco de geada",
        "detalhe": f"{frio} de {total} combinações cultura comercial × mês não passam no limite de frio/geada do catálogo (mais de {LIMIAR_FRIO * 100:.0f}% dos dias do ciclo).",
        "resultado": "bloqueio_confirmado" if frio == total else "restricao_parcial" if frio else "sem_bloqueio_nesta_verificacao",
    })
    if irrigacao_mm_ano <= 0:
        diagnostico["verificacoes"].append({
            "codigo": "estabelecimento", "titulo": "Chuva para iniciar o plantio",
            "detalhe": f"{chuva} de {total} combinações cultura comercial × mês não atingem a mediana mínima de {ESTAB_MIN_MM:.0f} mm nos primeiros {ESTAB_DIAS} dias em sequeiro.",
            "resultado": "bloqueio_confirmado" if chuva == total else "restricao_parcial" if chuva else "sem_bloqueio_nesta_verificacao",
        })
    else:
        diagnostico["verificacoes"].append({
            "codigo": "irrigacao", "titulo": "Irrigação informada",
            "detalhe": f"Foram informados {irrigacao_mm_ano:g} mm/ano de irrigação. Por isso a restrição de chuva inicial do sequeiro não foi aplicada; isso não comprova disponibilidade real de água.",
            "resultado": "informativo",
        })
    if aptos == 0:
        diagnostico["verificacoes"].append({
            "codigo": "sem_janelas", "titulo": "Nenhuma janela individual passou nos filtros",
            "detalhe": "Nenhuma combinação de cultura comercial e mês atende simultaneamente aos filtros de frio/geada e chuva inicial aplicáveis. Assim, não é possível montar a rotação comercial exigida com essas opções.",
            "resultado": "bloqueio_confirmado",
        })
    else:
        diagnostico["verificacoes"].append({
            "codigo": "calendario_completo", "titulo": "Ainda faltam as restrições da sequência",
            "detalhe": f"{aptos} de {total} janelas individuais passaram nos filtros. Exemplos: " +
                       ("; ".join(exemplos) if exemplos else "não disponíveis") +
                       ". Uma rotação precisa também evitar sobreposição, repetir a mesma espécie em sequência e manter cultura comercial nos dois anos. A busca não encontrou uma sequência completa; não é possível atribuir a falha a um único fator.",
            "resultado": "nao_conclusivo",
        })
    return diagnostico


@dataclass(frozen=True)
class Slot:
    cultura: str
    ano: int   # 1 ou 2
    mes: int   # 1..12

    @property
    def inicio(self) -> int:
        return (self.ano - 1) * 12 + (self.mes - 1)

    def to_dict(self) -> dict:
        return {"cultura": self.cultura, "ano": self.ano, "mes": self.mes}


def curva_kc(c: Cultura, n_dias: int) -> np.ndarray:
    """Curva de Kc diária em 4 estádios (FAO-56, Fig. 25)."""
    f = FRACOES_ESTADIOS
    l1 = max(1, round(n_dias * f[0]))
    l2 = max(1, round(n_dias * f[1]))
    l3 = max(1, round(n_dias * f[2]))
    l4 = max(1, n_dias - l1 - l2 - l3)
    ini = np.full(l1, c.kc_ini)
    dev = np.linspace(c.kc_ini, c.kc_mid, l2, endpoint=False)
    mid = np.full(l3, c.kc_mid)
    late = np.linspace(c.kc_mid, c.kc_end, l4)
    return np.concatenate([ini, dev, mid, late])[:n_dias]


# ---------------------------------------------------------------------------
# Tabela de avaliação: cultura × mês de semeadura × ano (pré-computada)
# ---------------------------------------------------------------------------
class TabelaAvaliacao:
    def __init__(self, serie: SerieClimatica, culturas: Optional[Sequence[Cultura]] = None):
        self.serie = serie
        self.culturas = list(culturas or catalogo.listar())
        self.idx = {c.id: i for i, c in enumerate(self.culturas)}
        df = serie.df.asfreq("D")
        p = df["PRECTOTCORR"].values.astype(float)
        et0 = df["ET0"].values.astype(float)
        tmax = df["T2M_MAX"].values.astype(float)
        tmed = df["T2M"].values.astype(float)
        tmin = df["T2M_MIN"].values.astype(float)
        # fator de precipitação efetiva por (ano, mês) — USDA-SCS sobre o total mensal
        mensal = df["PRECTOTCORR"].resample("MS").sum(min_count=1)
        fator = pd.Series(np.where(mensal.values > 0,
                                   precipitacao_efetiva_mensal(mensal.values) / np.maximum(mensal.values, 1e-9),
                                   0.0), index=mensal.index)
        f_dia = fator.reindex(df.index.to_period("M").to_timestamp()).values
        peff = p * f_dia
        datas = df.index
        anos_dados = sorted(set(datas.year))
        self.anos = anos_dados
        n_c, n_a = len(self.culturas), len(anos_dados)
        shape = (n_c, 12, n_a)
        self.etc = np.full(shape, np.nan)
        self.peff = np.full(shape, np.nan)
        self.heat = np.full(shape, np.nan)
        self.estab = np.full(shape, np.nan)
        self.frio = np.full(shape, np.nan)
        pos0 = {(d.year, d.month): i for i, d in enumerate(datas) if d.day == 1}
        n = len(datas)
        kcs = {c.id: curva_kc(c, c.ciclo_dias) for c in self.culturas}
        for ci, c in enumerate(self.culturas):
            L = c.ciclo_dias
            kc = kcs[c.id]
            for ai, ano in enumerate(anos_dados):
                for m in range(1, 13):
                    s = pos0.get((ano, m))
                    if s is None or s + L > n:
                        continue
                    pw = p[s:s + L]
                    if np.isnan(pw).any() or np.isnan(et0[s:s + L]).any():
                        continue
                    self.etc[ci, m - 1, ai] = float(np.dot(kc, et0[s:s + L]))
                    self.peff[ci, m - 1, ai] = float(np.nansum(peff[s:s + L]))
                    self.heat[ci, m - 1, ai] = float(np.mean(tmax[s:s + L] >= c.tmax_critica_c))
                    self.estab[ci, m - 1, ai] = float(np.sum(pw[:ESTAB_DIAS]))
                    frio = tmed[s:s + L] < c.tbase_c
                    if not c.tolera_geada:
                        frio = frio | (tmin[s:s + L] <= 0.0)
                    self.frio[ci, m - 1, ai] = float(np.mean(frio))
        ano_ok = ~np.isnan(self.etc).any(axis=(0, 1))
        self.pares = [anos_dados[i] for i in range(n_a - 1) if ano_ok[i] and ano_ok[i + 1]]
        if len(self.pares) < 10:
            raise RotacaoError("Menos de 10 pares de anos completos na série — avaliação não confiável.")
        self.pares_idx = np.array([anos_dados.index(a) for a in self.pares])
        # climatologia: distribuição mensal da erosividade (p_m² / Σ p²)
        clim = climatologia_mensal(serie)
        p_m = clim["P"].reindex(range(1, 13)).fillna(0).values
        self.share_erosividade = p_m ** 2 / np.sum(p_m ** 2) if np.sum(p_m ** 2) > 0 else np.full(12, 1 / 12)
        # mediana do estabelecimento por cultura × mês (para a restrição de semeadura)
        self.estab_mediana = np.nanmedian(self.estab[:, :, self.pares_idx], axis=2)
        # satisfação hídrica mediana (sequeiro) por cultura × mês
        sat = np.minimum(1.0, self.peff / np.where(self.etc > 0, self.etc, np.nan))
        self.sat_mediana = np.nanmedian(sat[:, :, self.pares_idx], axis=2)
        self.frio_mediana = np.nanmedian(self.frio[:, :, self.pares_idx], axis=2)

    # -------------------------------------------------------------------
    def slot_series(self, s: Slot) -> Dict[str, np.ndarray]:
        ci = self.idx[s.cultura]
        cols = self.pares_idx + (s.ano - 1)
        return {"etc": self.etc[ci, s.mes - 1, cols], "peff": self.peff[ci, s.mes - 1, cols],
                "heat": self.heat[ci, s.mes - 1, cols], "estab": self.estab[ci, s.mes - 1, cols],
                "frio": self.frio[ci, s.mes - 1, cols]}


# ---------------------------------------------------------------------------
# Avaliação de uma estratégia
# ---------------------------------------------------------------------------
def meses_do_slot(c: Cultura, s: Slot) -> List[int]:
    return [(s.inicio + j) % HORIZONTE_MESES for j in range(c.meses_ocupados)]


def validar_restricoes(slots: Sequence[Slot], tab: TabelaAvaliacao, irrigacao_mm_ano: float
                       ) -> Tuple[Dict[str, int], List[str], List[str]]:
    """Retorna (violações por tipo, mensagens de violação, alertas não bloqueantes)."""
    viol = {"sobreposicao": 0, "sem_comercial_no_ano": 0, "estabelecimento": 0, "mesma_especie_seguida": 0,
            "janela_termica": 0}
    msgs: List[str] = []
    alertas: List[str] = []
    ocup = np.zeros(HORIZONTE_MESES, dtype=int)
    for s in slots:
        c = catalogo.obter(s.cultura)
        for m in meses_do_slot(c, s):
            ocup[m] += 1
    viol["sobreposicao"] = int(np.clip(ocup - 1, 0, None).sum())
    if viol["sobreposicao"]:
        msgs.append(f"Culturas sobrepostas no calendário ({viol['sobreposicao']} mês(es) em conflito).")
    for ano in (1, 2):
        if not any(catalogo.obter(s.cultura).tipo == "comercial" and s.ano == ano for s in slots):
            viol["sem_comercial_no_ano"] += 1
            msgs.append(f"Ano {ano} sem cultura comercial (sem fonte de renda prevista).")
    if irrigacao_mm_ano <= 0:
        for s in slots:
            med = tab.estab_mediana[tab.idx[s.cultura], s.mes - 1]
            if not (med >= ESTAB_MIN_MM):
                viol["estabelecimento"] += 1
                msgs.append(f"{catalogo.obter(s.cultura).nome} semeado em {MESES_PT[s.mes - 1]}: chuva mediana "
                            f"dos primeiros {ESTAB_DIAS} dias = {med:.0f} mm (< {ESTAB_MIN_MM:.0f} mm) em sequeiro.")
    for s in slots:
        fr = tab.frio_mediana[tab.idx[s.cultura], s.mes - 1]
        if not (fr <= LIMIAR_FRIO):
            viol["janela_termica"] += 1
            c = catalogo.obter(s.cultura)
            msgs.append(f"{c.nome} semeado em {MESES_PT[s.mes - 1]}: {fr * 100:.0f}% dos dias do ciclo abaixo de "
                        f"{c.tbase_c:.0f} °C{'' if c.tolera_geada else ' ou com geada'} (fora da janela térmica).")
    ordem = sorted(slots, key=lambda x: x.inicio)
    if len(ordem) >= 2:
        for a, b in zip(ordem, ordem[1:] + ordem[:1]):
            if a is b:
                continue
            ca, cb = catalogo.obter(a.cultura), catalogo.obter(b.cultura)
            if ca.id == cb.id:
                viol["mesma_especie_seguida"] += 1
                msgs.append(f"{ca.nome} repetido em sequência (monocultura): maior risco fitossanitário.")
            elif ca.familia == cb.familia:
                par = " e ".join(sorted({ca.nome, cb.nome}))
                alertas.append(f"{par} em sequência: mesma família botânica ({ca.familia}); "
                               "pode favorecer pragas e doenças comuns.")
    return viol, msgs, alertas


def avaliar(slots: Sequence[Slot], tab: TabelaAvaliacao, irrigacao_mm_ano: float = 0.0,
            detalhar: bool = True) -> dict:
    slots = sorted(slots, key=lambda s: s.inicio)
    n_p = len(tab.pares)
    etc_tot = np.zeros(n_p)
    def_tot = np.zeros(n_p)
    unmet_tot = np.zeros(n_p)
    vuln_num = np.zeros(n_p)
    vuln_den = 0.0
    # Correção da auditoria: quebra e falha de estabelecimento são contadas POR ANO-SAFRA
    # (ano 1 e ano 2 de cada par), não por par de anos — antes um par com uma quebra contava como "ano de quebra".
    quebra = {1: np.zeros(n_p, dtype=bool), 2: np.zeros(n_p, dtype=bool)}
    estab_falha = {1: np.zeros(n_p, dtype=bool), 2: np.zeros(n_p, dtype=bool)}
    cover = np.zeros(HORIZONTE_MESES)
    leg_m = bio_m = 0.0
    calendario: List[Optional[str]] = [None] * HORIZONTE_MESES
    det_slots = []
    series = [tab.slot_series(s) for s in slots]
    deficits = [np.maximum(0.0, sr["etc"] - sr["peff"]) for sr in series]
    soma_def = np.sum(deficits, axis=0) if deficits else np.zeros(n_p)
    orcamento = 2.0 * max(0.0, irrigacao_mm_ano)
    frac_irrig = np.where(soma_def > 0, np.minimum(1.0, orcamento / np.maximum(soma_def, 1e-9)), 0.0)
    ky_ausente = []
    for s, sr, dfc in zip(slots, series, deficits):
        c = catalogo.obter(s.cultura)
        etc, peff = sr["etc"], sr["peff"]
        irr = dfc * frac_irrig
        eta = np.minimum(etc, peff + irr)
        d = np.where(etc > 0, 1 - eta / etc, 0.0)
        ky = c.ky if c.ky is not None else 1.0
        if c.ky is None:
            ky_ausente.append(c.nome)
        perda = np.minimum(1.0, ky * d)
        h = 1 - (1 - sr["heat"]) * (1 - sr["frio"])   # estresse térmico: calor OU frio/geada
        v = 1 - (1 - d) * (1 - h)
        sat = float(np.mean(eta / np.where(etc > 0, etc, np.nan))) * (1 - float(np.mean(sr["frio"])))
        etc_tot += etc
        def_tot += dfc
        unmet_tot += etc - eta
        if c.tipo == "comercial":
            vuln_num += v * c.ciclo_dias
            vuln_den += c.ciclo_dias
            quebra[s.ano] |= perda > LIMIAR_QUEBRA
        if irrigacao_mm_ano <= 0:
            estab_falha[s.ano] |= sr["estab"] < ESTAB_MIN_MM
        meses = meses_do_slot(c, s)
        for j, m in enumerate(meses):
            cov = COBERTURA_POR_PROTECAO[c.protecao_solo] * (0.5 if j == 0 else 1.0) * sat
            cover[m] = max(cover[m], cov)
            calendario[m] = c.id
        if c.fixa_nitrogenio:
            leg_m += len(meses) * sat
        if c.alta_biomassa:
            bio_m += len(meses) * sat
        if detalhar:
            det_slots.append({
                **s.to_dict(), "nome": c.nome, "tipo": c.tipo, "familia": c.familia,
                "mes_nome": MESES_PT[s.mes - 1], "ciclo_dias": c.ciclo_dias, "meses_ocupados": len(meses),
                "etc_mm": round(float(np.mean(etc)), 1), "chuva_efetiva_mm": round(float(np.mean(peff)), 1),
                "irrigacao_alocada_mm": round(float(np.mean(irr)), 1),
                "satisfacao_hidrica": round(sat, 3),
                "deficit_relativo_medio": round(float(np.mean(d)), 3),
                "perda_rendimento_media": round(float(np.mean(perda)), 3),
                "perda_rendimento_p90": round(float(np.percentile(perda, 90)), 3),
                "ky_usado": ky, "ky_tabelado": c.ky is not None,
                "fracao_dias_calor": round(float(np.mean(sr["heat"])), 3),
                "fracao_dias_frio": round(float(np.mean(sr["frio"])), 3), "tbase_c": c.tbase_c,
                "tmax_critica_c": c.tmax_critica_c,
                "estabelecimento_ok_fracao": round(float(np.mean(sr["estab"] >= ESTAB_MIN_MM)), 3),
                "vulnerabilidade": round(float(np.mean(v)), 3),
            })
    meses_cobertos = int(np.sum(cover > 0))
    cobertura = float(np.mean(cover))
    share24 = np.concatenate([tab.share_erosividade, tab.share_erosividade])
    erosao = float(np.sum(share24 * (1 - cover)) / 2.0)
    leg = min(1.0, leg_m / 12.0)
    bio = min(1.0, bio_m / 12.0)
    melhoria = 0.5 * leg + 0.5 * bio
    especies = {s.cultura for s in slots}
    familias = {catalogo.obter(s.cultura).familia for s in slots}
    diversif = (0.5 * min(1.0, (len(especies) - 1) / 3) + 0.5 * min(1.0, (len(familias) - 1) / 2)) if slots else 0.0
    vuln = float(np.mean(vuln_num / vuln_den)) if vuln_den > 0 else None
    estresse = float(np.mean(unmet_tot / np.where(etc_tot > 0, etc_tot, np.nan))) if slots else None
    comps = {"exposicao_solo": 1 - cobertura, "erosao": erosao, "sem_aporte_biologico": 1 - leg}
    if estresse is not None:
        comps["estresse_hidrico"] = estresse
    das = 100.0 * float(np.mean(list(comps.values())))
    res = {
        "objetivos": {
            "demanda_irrigacao_mm_ano": round(float(np.mean(def_tot)) / 2.0, 1),
            "vulnerabilidade_climatica": None if vuln is None else round(vuln, 4),
            "potencial_erosao": round(erosao, 4),
            "melhoria_solo": round(melhoria, 4),
            "cobertura": round(cobertura, 4),
            "diversificacao": round(diversif, 4),
        },
        "indicadores": {
            "etc_total_mm_ano": round(float(np.mean(etc_tot)) / 2.0, 1),
            "deficit_nao_atendido_mm_ano": round(float(np.mean(unmet_tot)) / 2.0, 1),
            "risco_quebra_anos": round(float(np.mean(np.concatenate([quebra[1], quebra[2]]))), 3),
            "falha_estabelecimento_anos": (round(float(np.mean(np.concatenate([estab_falha[1], estab_falha[2]]))), 3)
                                           if irrigacao_mm_ano <= 0 else None),
            "anos_safra_avaliados": 2 * n_p,
            "meses_com_cobertura": meses_cobertos,
            "meses_solo_descoberto": HORIZONTE_MESES - meses_cobertos,
            "meses_leguminosa": int(sum(len(meses_do_slot(catalogo.obter(s.cultura), s))
                                        for s in slots if catalogo.obter(s.cultura).fixa_nitrogenio)),
            "n_especies": len(especies), "n_familias": len(familias),
            "pares_de_anos_avaliados": len(tab.pares),
            "periodo_avaliado": [tab.pares[0], tab.pares[-1] + 1],
        },
        "das": {"valor": round(das, 1), "componentes": {k: round(v, 3) for k, v in comps.items()},
                "metodo": "média simples dos componentes × 100 (indicador experimental)"},
        "ky_assumido_1": sorted(set(ky_ausente)),
    }
    if detalhar:
        viol, msgs, alertas = validar_restricoes(slots, tab, irrigacao_mm_ano)
        res["slots"] = det_slots
        res["calendario"] = calendario
        res["cobertura_mensal"] = [round(float(x), 3) for x in cover]
        res["restricoes"] = {"violacoes": viol, "mensagens": list(dict.fromkeys(msgs)),
                             "viavel": sum(viol.values()) == 0}
        res["alertas_fitossanitarios"] = list(dict.fromkeys(alertas))
    return res


def vetor_objetivos(av: dict) -> np.ndarray:
    o = av["objetivos"]
    v = o["vulnerabilidade_climatica"] if o["vulnerabilidade_climatica"] is not None else 1.0
    return np.array([o["demanda_irrigacao_mm_ano"], v, o["potencial_erosao"],
                     -o["melhoria_solo"], -o["cobertura"], -o["diversificacao"]])


# ---------------------------------------------------------------------------
# Otimização multiobjetivo — NSGA-II (pymoo)
# ---------------------------------------------------------------------------
def _decodificar(x: np.ndarray, ids: List[str]) -> List[Slot]:
    slots = []
    for k in range(MAX_SLOTS):
        code, ini = int(round(x[2 * k])), int(round(x[2 * k + 1]))
        if code <= 0 or code > len(ids):
            continue
        ini = ini % HORIZONTE_MESES
        slots.append(Slot(ids[code - 1], ini // 12 + 1, ini % 12 + 1))
    return slots


def _chave(slots: Sequence[Slot]) -> Tuple:
    return tuple(sorted((s.inicio, s.cultura) for s in slots))


def otimizar(tab: TabelaAvaliacao, irrigacao_mm_ano: float = 0.0,
             culturas_permitidas: Optional[Sequence[str]] = None,
             pop: Optional[int] = None, geracoes: Optional[int] = None,
             semente: Optional[int] = None) -> dict:
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.core.problem import Problem
    from pymoo.core.sampling import Sampling
    from pymoo.operators.crossover.sbx import SBX
    from pymoo.operators.mutation.pm import PM
    from pymoo.operators.repair.rounding import RoundingRepair
    from pymoo.optimize import minimize
    from pymoo.util.nds.non_dominated_sorting import NonDominatedSorting

    pop = pop or settings.NSGA_POP
    geracoes = geracoes or settings.NSGA_GEN
    semente = settings.NSGA_SEED if semente is None else semente
    ids = [c.id for c in tab.culturas if (not culturas_permitidas or c.id in culturas_permitidas)]
    if not any(catalogo.obter(i).tipo == "comercial" for i in ids):
        raise RotacaoError("É preciso permitir pelo menos uma cultura comercial.",
                           diagnosticar_inviabilidade(tab, irrigacao_mm_ano, culturas_permitidas))
    arquivo: Dict[Tuple, Tuple[List[Slot], np.ndarray]] = {}
    n_av = {"n": 0}
    sequeiro = irrigacao_mm_ano <= 0

    class Prob(Problem):
        def __init__(self):
            xl = np.zeros(2 * MAX_SLOTS)
            xu = np.array([len(ids), HORIZONTE_MESES - 1] * MAX_SLOTS, dtype=float)
            super().__init__(n_var=2 * MAX_SLOTS, n_obj=6, n_ieq_constr=5, xl=xl, xu=xu, vtype=int)

        def _evaluate(self, X, out, *args, **kwargs):
            F = np.zeros((len(X), 6))
            G = np.zeros((len(X), 5))
            for r, x in enumerate(X):
                slots = _decodificar(x, ids)
                n_av["n"] += 1
                if not slots:
                    F[r] = [0, 1, 1, 0, 0, 0]
                    G[r] = [0, 2, 0, 0, 0]
                    continue
                viol, _, _ = validar_restricoes(slots, tab, irrigacao_mm_ano)
                av = avaliar(slots, tab, irrigacao_mm_ano, detalhar=False)
                F[r] = vetor_objetivos(av)
                G[r] = [viol["sobreposicao"], viol["sem_comercial_no_ano"],
                        viol["estabelecimento"], viol["mesma_especie_seguida"], viol["janela_termica"]]
                if sum(viol.values()) == 0:
                    arquivo.setdefault(_chave(slots), (slots, F[r].copy()))
            out["F"] = F
            out["G"] = G

    rng = np.random.default_rng(semente)
    comerciais = [k for k, i in enumerate(ids) if catalogo.obter(i).tipo == "comercial"]

    class Amostragem(Sampling):
        """Gera indivíduos plausíveis: uma comercial por ano em mês de semeadura viável."""
        def _do(self, problem, n_samples, **kwargs):
            X = np.zeros((n_samples, 2 * MAX_SLOTS))
            for r in range(n_samples):
                for k in range(MAX_SLOTS):
                    ano = k % 2
                    cand = comerciais if k < 2 else list(range(len(ids)))
                    if k >= 2 and rng.random() < 0.4:
                        continue
                    ci = int(rng.choice(cand))
                    cidx = tab.idx[ids[ci]]
                    meses_ok = [m for m in range(12)
                                if ((not sequeiro) or tab.estab_mediana[cidx, m] >= ESTAB_MIN_MM)
                                and tab.frio_mediana[cidx, m] <= LIMIAR_FRIO]
                    m = int(rng.choice(meses_ok)) if meses_ok else int(rng.integers(12))
                    X[r, 2 * k] = ci + 1
                    X[r, 2 * k + 1] = ano * 12 + m
            return X

    alg = NSGA2(pop_size=pop, sampling=Amostragem(),
                crossover=SBX(prob=0.9, eta=15, vtype=float, repair=RoundingRepair()),
                mutation=PM(eta=20, vtype=float, repair=RoundingRepair()),
                eliminate_duplicates=True)
    minimize(Prob(), alg, ("n_gen", geracoes), seed=semente, verbose=False)
    if not arquivo:
        raise RotacaoError("Nenhuma estratégia viável encontrada com as restrições atuais.",
                           diagnosticar_inviabilidade(tab, irrigacao_mm_ano, culturas_permitidas))
    chaves = list(arquivo.keys())
    F = np.array([arquivo[k][1] for k in chaves])
    frente = NonDominatedSorting().do(F, only_non_dominated_front=True)
    pareto = [arquivo[chaves[i]][0] for i in frente]
    return {"pareto": pareto, "n_avaliacoes": n_av["n"], "n_viaveis": len(arquivo),
            "pop": pop, "geracoes": geracoes, "semente": semente,
            "algoritmo": "NSGA-II (pymoo) com variáveis inteiras, restrições de desigualdade e arquivo de soluções viáveis"}


# ---------------------------------------------------------------------------
# Seleção das estratégias B (conservação), C (resiliência hídrica) e D (prioridades)
# ---------------------------------------------------------------------------
PESOS_PADRAO_PRIORIDADES = {"agua": 1.0, "solo": 1.0, "erosao": 1.0, "diversificacao": 1.0, "risco": 1.0}


def _normalizar(matriz: np.ndarray) -> np.ndarray:
    lo, hi = matriz.min(axis=0), matriz.max(axis=0)
    rng_ = np.where(hi - lo > 1e-12, hi - lo, 1.0)
    return (matriz - lo) / rng_


def selecionar(candidatos: List[dict], prioridades: Optional[Dict[str, float]] = None) -> dict:
    """candidatos: lista de avaliações (inclui a estratégia A no índice 0).

    Todas as colunas são normalizadas 0–1 no conjunto (Pareto ∪ A), com 1 = melhor.
    B = maior média de (melhoria do solo, cobertura, baixa erosão).
    C = maior média de (baixa demanda hídrica, baixa vulnerabilidade).
    D = soma ponderada pelas prioridades do agricultor (pesos informados na tela).
    """
    M = np.array([vetor_objetivos(a) for a in candidatos])
    bom = 1 - _normalizar(M)  # todas as colunas viram "maior = melhor"
    agua, vuln, eros, solo, cob, div = (bom[:, i] for i in range(6))
    idx_pareto = list(range(1, len(candidatos)))
    if not idx_pareto:
        raise RotacaoError("Fronteira de Pareto vazia.")
    score_b = (solo + cob + eros) / 3
    score_c = (agua + vuln) / 2
    b = max(idx_pareto, key=lambda i: (score_b[i], score_c[i]))
    ordem_c = sorted(idx_pareto, key=lambda i: (score_c[i], score_b[i]), reverse=True)
    c = next((i for i in ordem_c if i != b), ordem_c[0])
    w = {**PESOS_PADRAO_PRIORIDADES, **(prioridades or {})}
    tot = sum(max(0.0, v) for v in w.values()) or 1.0
    score_d = (w["agua"] * agua + w["risco"] * vuln + w["erosao"] * eros + w["solo"] * (solo + cob) / 2
               + w["diversificacao"] * div) / tot
    ordem_d = sorted(idx_pareto, key=lambda i: score_d[i], reverse=True)
    usados = {tuple(np.round(M[b], 4)), tuple(np.round(M[c], 4)), tuple(np.round(M[0], 4))}
    d = next((i for i in ordem_d if tuple(np.round(M[i], 4)) not in usados), None)
    return {"B": b, "C": c, "D": d, "scores": {"B": score_b.tolist(), "C": score_c.tolist(), "D": score_d.tolist()},
            "pesos_prioridades": w}


def slots_de_dicts(itens: Sequence[dict]) -> List[Slot]:
    out = []
    for it in itens:
        cid = it["cultura"]
        catalogo.obter(cid)
        ano, mes = int(it.get("ano", 1)), int(it["mes"])
        if ano not in (1, 2) or not (1 <= mes <= 12):
            raise RotacaoError(f"Slot inválido: ano={ano}, mês={mes}")
        out.append(Slot(cid, ano, mes))
    return out
