import numpy as np
import pytest

from app import catalogo, clima, rotacao
from app.rotacao import Slot


def test_catalogo_tem_fonte_e_confianca_para_todo_atributo():
    for c in catalogo.listar():
        for a in ["ciclo_dias", "kc", "tmax_critica_c", "protecao_solo"]:
            assert a in c.fontes, (c.id, a)
            assert a in c.confianca, (c.id, a)
        assert c.tipo in ("comercial", "cobertura")


def test_curva_kc():
    c = catalogo.obter("milho")
    k = rotacao.curva_kc(c, c.ciclo_dias)
    assert len(k) == c.ciclo_dias
    assert k[0] == pytest.approx(c.kc_ini)
    assert k.max() == pytest.approx(c.kc_mid)
    assert k[-1] == pytest.approx(c.kc_end)


def test_tabela_pares(tab_srn):
    assert len(tab_srn.pares) >= 30
    # semeadura em setembro no semiárido não passa no critério de estabelecimento
    assert tab_srn.estab_mediana[tab_srn.idx["milho"], 8] < rotacao.ESTAB_MIN_MM
    assert tab_srn.estab_mediana[tab_srn.idx["milho"], 0] >= rotacao.ESTAB_MIN_MM


def test_avaliacao_monocultura_milho(tab_srn):
    a = rotacao.avaliar([Slot("milho", 1, 1), Slot("milho", 2, 1)], tab_srn)
    o = a["objetivos"]
    assert o["diversificacao"] == 0 and o["melhoria_solo"] == 0
    assert 0 <= o["vulnerabilidade_climatica"] <= 1
    assert a["restricoes"]["violacoes"]["mesma_especie_seguida"] > 0
    assert 0 <= a["das"]["valor"] <= 100
    assert len(a["calendario"]) == 24


def test_irrigacao_reduz_deficit_nao_atendido(tab_srn):
    s = [Slot("milho", 1, 1), Slot("feijao-caupi", 2, 1)]
    seco = rotacao.avaliar(s, tab_srn, 0)
    irr = rotacao.avaliar(s, tab_srn, 300)
    assert irr["indicadores"]["deficit_nao_atendido_mm_ano"] < seco["indicadores"]["deficit_nao_atendido_mm_ano"]
    assert irr["objetivos"]["vulnerabilidade_climatica"] <= seco["objetivos"]["vulnerabilidade_climatica"]
    # a demanda (necessidade) não muda com a irrigação; o que muda é quanto é atendido
    assert irr["objetivos"]["demanda_irrigacao_mm_ano"] == seco["objetivos"]["demanda_irrigacao_mm_ano"]


def test_restricoes(tab_srn):
    viol, msgs, _ = rotacao.validar_restricoes([Slot("milho", 1, 1), Slot("sorgo", 1, 2)], tab_srn, 0)
    assert viol["sobreposicao"] > 0
    viol, msgs, _ = rotacao.validar_restricoes([Slot("milho", 1, 9), Slot("sorgo", 2, 1)], tab_srn, 0)
    assert viol["estabelecimento"] == 1
    viol, _, _ = rotacao.validar_restricoes([Slot("crotalaria-juncea", 1, 1), Slot("sorgo", 2, 1)], tab_srn, 0)
    assert viol["sem_comercial_no_ano"] == 1
    viol, _, alertas = rotacao.validar_restricoes([Slot("feijao-caupi", 1, 1), Slot("soja", 2, 1)], tab_srn, 0)
    assert sum(viol.values()) == 0 and alertas  # mesma família: alerta, não bloqueio


def test_otimizacao_nsga2_gera_pareto_viavel(tab_srn):
    r = rotacao.otimizar(tab_srn, 0.0, pop=40, geracoes=25, semente=1)
    assert r["pareto"] and r["algoritmo"].startswith("NSGA-II")
    F = []
    for p in r["pareto"]:
        viol, _, _ = rotacao.validar_restricoes(p, tab_srn, 0)
        assert sum(viol.values()) == 0
        F.append(rotacao.vetor_objetivos(rotacao.avaliar(p, tab_srn, 0, detalhar=False)))
    F = np.array(F)
    # nenhuma solução da frente é dominada por outra da frente
    for i in range(len(F)):
        dom = np.all(F <= F[i], axis=1) & np.any(F < F[i], axis=1)
        assert not dom.any()


def test_otimizacao_respeita_culturas_permitidas(tab_srn):
    perm = ["sorgo", "feijao-caupi", "guandu"]
    r = rotacao.otimizar(tab_srn, 0.0, culturas_permitidas=perm, pop=30, geracoes=15, semente=3)
    assert all(s.cultura in perm for p in r["pareto"] for s in p)


def test_selecao_b_c_distintas(tab_srn):
    a = rotacao.avaliar([Slot("milho", 1, 1), Slot("milho", 2, 1)], tab_srn)
    r = rotacao.otimizar(tab_srn, 0.0, pop=40, geracoes=25, semente=1)
    cands = [a] + [rotacao.avaliar(p, tab_srn) for p in r["pareto"]]
    sel = rotacao.selecionar(cands)
    assert sel["B"] != sel["C"] and 0 not in (sel["B"], sel["C"])
    assert cands[sel["C"]]["objetivos"]["vulnerabilidade_climatica"] <= a["objetivos"]["vulnerabilidade_climatica"]


def test_estrategias_dependem_do_local(tab_srn):
    from tests.conftest import IOWA
    tab_iowa = rotacao.TabelaAvaliacao(clima.carregar(*IOWA))
    # em Iowa o inverno é frio e seco: semear milho em janeiro não tem sentido climático
    assert tab_iowa.sat_mediana[tab_iowa.idx["milho"], 0] != pytest.approx(tab_srn.sat_mediana[tab_srn.idx["milho"], 0])
    r1 = rotacao.otimizar(tab_srn, 0.0, pop=30, geracoes=15, semente=2)
    r2 = rotacao.otimizar(tab_iowa, 0.0, pop=30, geracoes=15, semente=2)
    k1 = {rotacao._chave(p) for p in r1["pareto"]}
    k2 = {rotacao._chave(p) for p in r2["pareto"]}
    assert k1 != k2


def test_slot_invalido():
    with pytest.raises(rotacao.RotacaoError):
        rotacao.slots_de_dicts([{"cultura": "milho", "ano": 3, "mes": 1}])
    with pytest.raises(catalogo.CatalogoError):
        rotacao.slots_de_dicts([{"cultura": "abacaxi", "ano": 1, "mes": 1}])


def test_janela_termica_bloqueia_inverno_frio():
    from tests.conftest import IOWA
    tab = rotacao.TabelaAvaliacao(clima.carregar(*IOWA))
    viol, msgs, _ = rotacao.validar_restricoes([Slot("milho", 1, 11), Slot("soja", 2, 5)], tab, 300)
    assert viol["janela_termica"] == 1 and any("janela térmica" in m for m in msgs)
    viol, _, _ = rotacao.validar_restricoes([Slot("milho", 1, 5), Slot("soja", 2, 5)], tab, 300)
    assert viol["janela_termica"] == 0
    r = rotacao.otimizar(tab, 0.0, pop=30, geracoes=15, semente=4)
    for p in r["pareto"]:
        for s in p:
            assert tab.frio_mediana[tab.idx[s.cultura], s.mes - 1] <= rotacao.LIMIAR_FRIO


def test_quebra_e_contada_por_ano_safra(tab_srn):
    """Auditoria: 'anos com perda > 50%' deve ser a fração de anos-safra, não de pares de anos.
    Monocultura de milho em jan nos 2 anos => igual à fração de anos em que a perda do milho passa de 50%."""
    a = rotacao.avaliar([Slot("milho", 1, 1), Slot("milho", 2, 1)], tab_srn)
    s = rotacao.avaliar([Slot("milho", 1, 1), Slot("sorgo", 2, 1)], tab_srn)
    ser = tab_srn.slot_series(Slot("milho", 1, 1))
    etc, pe = ser["etc"], ser["peff"]
    perda = np.minimum(1, 1.25 * (1 - np.minimum(etc, pe) / etc))
    ser2 = tab_srn.slot_series(Slot("milho", 2, 1))
    perda2 = np.minimum(1, 1.25 * (1 - np.minimum(ser2["etc"], ser2["peff"]) / ser2["etc"]))
    esperado = np.mean(np.concatenate([perda > 0.5, perda2 > 0.5]))
    assert a["indicadores"]["risco_quebra_anos"] == pytest.approx(esperado, abs=1e-3)
    assert a["indicadores"]["anos_safra_avaliados"] == 2 * len(tab_srn.pares)
    assert 0.35 < a["indicadores"]["risco_quebra_anos"] < 0.6   # ≈46 % no recálculo independente (35 anos)
    assert a["slots"][0]["perda_rendimento_media"] == pytest.approx(0.47, abs=0.03)
    assert s["indicadores"]["risco_quebra_anos"] <= a["indicadores"]["risco_quebra_anos"]
