"""
tests/test_culturas.py - Testes da Etapa 4 (core/culturas.py).

Valida:
- Leitura do CSV: lacunas são None (não zero), lista de lacunas por cultura.
- Regra de rotação revisada (2026-11-14): uma cultura é apta se tiver
  `ciclo_dias`. `agua_mm_ciclo` vazio NÃO exclui — a cultura continua
  apta e `agua_efetiva_mm_ciclo` usa `config.CHUVA_MINIMA_CICLO_MM`
  (marcado "parâmetro estimado pela equipe" via `usa_agua_estimada`).
- Cabeçalho inesperado e nome duplicado geram erro.
- Lista de lacunas é consumida pelo semáforo.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from core import culturas
from core.culturas import Cultura, ler_culturas_csv, carregar_banco


# ---------------------------------------------------------------------------
# Fixtures locais
# ---------------------------------------------------------------------------
@pytest.fixture
def csv_preenchido(tmp_path):
    """CSV com cultura de exemplo totalmente preenchida."""
    p = tmp_path / "culturas.csv"
    p.write_text(
        "nome,tipo,ciclo_dias,agua_mm_ciclo,tmax_limite_c,fixa_nitrogenio,"
        "protecao_erosao,valor_mercado,taxa_semeadura_kg_ha,"
        "rendimento_potencial_kg_ha,rendimento_regional_kg_ha,fonte\n"
        "feijao-caupi,comercial,70,325,38,sim,2,3,18,2000,800,Embrapa\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def csv_cobertura_com_ciclo_sem_agua(tmp_path):
    """Cobertura com ciclo_dias mas SEM agua_mm_ciclo (cobre o caso novo).

    Regra revisada: continua APTA a rotações. A água efetiva usada nos
    cálculos de janela é config.CHUVA_MINIMA_CICLO_MM (= 250 mm), e a
    cultura é marcada como "parâmetro estimado pela equipe".
    """
    p = tmp_path / "culturas.csv"
    p.write_text(
        "nome,tipo,ciclo_dias,agua_mm_ciclo,tmax_limite_c,fixa_nitrogenio,"
        "protecao_erosao,valor_mercado,taxa_semeadura_kg_ha,"
        "rendimento_potencial_kg_ha,rendimento_regional_kg_ha,fonte\n"
        "crotalaria-juncea,cobertura,120,,,sim,,,25,,,Embrapa\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def csv_cobertura_sem_ciclo(tmp_path):
    """Cobertura sem ciclo_dias nem agua_mm_ciclo (fora de rotações)."""
    p = tmp_path / "culturas.csv"
    p.write_text(
        "nome,tipo,ciclo_dias,agua_mm_ciclo,tmax_limite_c,fixa_nitrogenio,"
        "protecao_erosao,valor_mercado,taxa_semeadura_kg_ha,"
        "rendimento_potencial_kg_ha,rendimento_regional_kg_ha,fonte\n"
        "crotalaria-juncea,cobertura,,,,sim,,,25,,,Embrapa\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def csv_com_sorgo_preenchido(tmp_path):
    """CSV com sorgo COM ciclo_dias e agua_mm_ciclo (entra em rotação)."""
    p = tmp_path / "culturas.csv"
    p.write_text(
        "nome,tipo,ciclo_dias,agua_mm_ciclo,tmax_limite_c,fixa_nitrogenio,"
        "protecao_erosao,valor_mercado,taxa_semeadura_kg_ha,"
        "rendimento_potencial_kg_ha,rendimento_regional_kg_ha,fonte\n"
        "sorgo,comercial,100,490,,nao,,,,,,Embrapa\n"
        "milho,comercial,120,600,,nao,,,,5000,,Embrapa\n",
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# 1. Leitura do CSV - caso cheio (sem lacuna)
# ---------------------------------------------------------------------------
def test_csv_cultura_cheia_sem_lacunas(csv_preenchido):
    """Cultura totalmente preenchida não tem lacunas."""
    banco = ler_culturas_csv(csv_preenchido)
    assert "feijao-caupi" in banco
    c = banco["feijao-caupi"]
    assert c.ciclo_dias == 70
    assert c.agua_mm_ciclo == 325.0
    assert c.tmax_limite_c == 38.0
    assert c.fixa_nitrogenio == "sim"
    assert c.protecao_erosao == 2
    assert c.valor_mercado == 3
    assert c.taxa_semeadura_kg_ha == 18.0
    assert c.rendimento_potencial_kg_ha == 2000.0
    assert c.rendimento_regional_kg_ha == 800.0
    assert c.lacunas == []
    assert c.tem_dados_para_rotacao is True
    assert c.campos_faltantes_para_rotacao == []
    # Cultura com agua_mm_ciclo no CSV usa o dado real, não o fallback.
    assert c.agua_efetiva_mm_ciclo == 325.0
    assert c.usa_agua_estimada is False


# ---------------------------------------------------------------------------
# 2. Leitura do CSV - cobertura com ciclo mas sem agua (regra revisada)
# ---------------------------------------------------------------------------
def test_cobertura_com_ciclo_sem_agua_continua_apta(csv_cobertura_com_ciclo_sem_agua):
    """Regra revisada: ciclo_dias preenchido -> apta, mesmo sem agua_mm_ciclo.

    A água efetiva é config.CHUVA_MINIMA_CICLO_MM (250 mm) e a cultura
    é marcada como "parâmetro estimado pela equipe".
    """
    banco = ler_culturas_csv(csv_cobertura_com_ciclo_sem_agua)
    c = banco["crotalaria-juncea"]
    assert c.ciclo_dias == 120          # tem ciclo
    assert c.agua_mm_ciclo is None     # água vazia no CSV
    # Continua apta a rotações (regra revisada: só ciclo_dias é obrigatório)
    assert c.tem_dados_para_rotacao is True
    assert c.campos_faltantes_para_rotacao == []
    # Água efetiva = fallback da equipe (não o valor do CSV)
    assert c.agua_efetiva_mm_ciclo == config.CHUVA_MINIMA_CICLO_MM
    assert c.agua_efetiva_mm_ciclo == 250
    # Marcada como estimada (desconta ponto no semáforo)
    assert c.usa_agua_estimada is True
    # Aparece na lista de aptas e NÃO na de excluídas
    assert "crotalaria-juncea" in culturas.culturas_para_rotacao(banco)
    assert "crotalaria-juncea" not in culturas.culturas_excluidas(banco)
    # A lacuna de agua_mm_ciclo continua registrada para o semáforo
    assert "agua_mm_ciclo" in c.lacunas


def test_cobertura_com_ciclo_sem_agua_lista_em_apitas(
        csv_cobertura_com_ciclo_sem_agua):
    """A cobertura sem água aparece em culturas_para_rotacao (regra nova)."""
    banco = ler_culturas_csv(csv_cobertura_com_ciclo_sem_agua)
    assert culturas.culturas_para_rotacao(banco) == ["crotalaria-juncea"]
    assert culturas.culturas_excluidas(banco) == []


# ---------------------------------------------------------------------------
# 3. Cobertura sem ciclo_dias continua fora de rotações
# ---------------------------------------------------------------------------
def test_cobertura_sem_ciclo_fora_de_rotacao(csv_cobertura_sem_ciclo):
    """Sem ciclo_dias -> não entra em rotações (briefing 6.1)."""
    banco = ler_culturas_csv(csv_cobertura_sem_ciclo)
    c = banco["crotalaria-juncea"]
    assert c.ciclo_dias is None
    assert c.agua_mm_ciclo is None
    assert c.tem_dados_para_rotacao is False
    assert "ciclo_dias" in c.campos_faltantes_para_rotacao
    assert culturas.culturas_para_rotacao(banco) == []
    assert "crotalaria-juncea" in culturas.culturas_excluidas(banco)
    # Sem ciclo, a lacuna de água também está registrada
    assert "ciclo_dias" in c.lacunas
    assert "agua_mm_ciclo" in c.lacunas


def test_cobertura_sem_ciclo_agua_efetiva_nao_estoura(csv_cobertura_sem_ciclo):
    """Mesmo fora de rotações, ler agua_efetiva não deve quebrar — mas
    quando agua_mm_ciclo E config.CHUVA_MINIMA_CICLO_MM são None, levanta.

    Aqui config.CHUVA_MINIMA_CICLO_MM é 250, então agua_efetiva funciona.
    """
    banco = ler_culturas_csv(csv_cobertura_sem_ciclo)
    c = banco["crotalaria-juncea"]
    # Mesmo sem ciclo, agua_efetiva retorna o fallback (a cultura é "apta"
    # só para a água; o controle de aptidão é por ciclo_dias).
    assert c.agua_efetiva_mm_ciclo == config.CHUVA_MINIMA_CICLO_MM


# ---------------------------------------------------------------------------
# 4. listar_lacunas (consumido pelo semáforo)
# ---------------------------------------------------------------------------
def test_listar_lacunas_filtra_culturas_sem_lacuna(csv_preenchido):
    """listar_lacunas só inclui culturas que TÊM ao menos uma lacuna."""
    banco = ler_culturas_csv(csv_preenchido)
    lacunas_dict = culturas.listar_lacunas(banco)
    # feijao-caupi está totalmente preenchido -> não aparece
    assert "feijao-caupi" not in lacunas_dict


def test_listar_lacunas_inclui_culturas_com_lacuna(
        csv_cobertura_com_ciclo_sem_agua):
    """Cobertura com ciclo mas sem água: a lacuna de água aparece."""
    banco = ler_culturas_csv(csv_cobertura_com_ciclo_sem_agua)
    lacunas_dict = culturas.listar_lacunas(banco)
    assert "crotalaria-juncea" in lacunas_dict
    assert "agua_mm_ciclo" in lacunas_dict["crotalaria-juncea"]


# ---------------------------------------------------------------------------
# 5. Sorgo (comercial) — entra em rotações com dado real do CSV
# ---------------------------------------------------------------------------
def test_sorgo_com_dados_entra_em_rotacao(csv_com_sorgo_preenchido):
    """Sorgo COM ciclo_dias e agua_mm_ciclo entra em rotações.

    Não há exclusão por nome. A água efetiva é o valor real do CSV (490 mm).
    """
    banco = ler_culturas_csv(csv_com_sorgo_preenchido)
    s = banco["sorgo"]
    assert s.ciclo_dias == 100
    assert s.agua_mm_ciclo == 490.0
    assert s.tem_dados_para_rotacao is True
    assert s.campos_faltantes_para_rotacao == []
    assert s.agua_efetiva_mm_ciclo == 490.0
    assert s.usa_agua_estimada is False
    assert "sorgo" in culturas.culturas_para_rotacao(banco)
    assert "sorgo" not in culturas.culturas_excluidas(banco)
    assert "milho" in culturas.culturas_para_rotacao(banco)


# ---------------------------------------------------------------------------
# 6. agua_efetiva_mm_ciclo: erro se CSV vazio E config fallback None
# ---------------------------------------------------------------------------
def test_agua_efetiva_erro_se_csv_e_fallback_none(tmp_path, monkeypatch):
    """Se agua_mm_ciclo vazio E config.CHUVA_MINIMA_CICLO_MM = None -> erro.

    Regra do briefing 6.1: se o parâmetro da equipe também não estiver
    definido, não calcular a janela da cultura. Aqui simulamos isso
    desligando o fallback via monkeypatch.
    """
    p = tmp_path / "culturas.csv"
    p.write_text(
        "nome,tipo,ciclo_dias,agua_mm_ciclo,tmax_limite_c,fixa_nitrogenio,"
        "protecao_erosao,valor_mercado,taxa_semeadura_kg_ha,"
        "rendimento_potencial_kg_ha,rendimento_regional_kg_ha,fonte\n"
        "crotalaria-juncea,cobertura,120,,,sim,,,25,,,Embrapa\n",
        encoding="utf-8",
    )
    banco = ler_culturas_csv(p)
    c = banco["crotalaria-juncea"]
    # Desliga o fallback da equipe — simula "parâmetro ainda não definido"
    monkeypatch.setattr(config, "CHUVA_MINIMA_CICLO_MM", None)
    with pytest.raises(culturas.CulturasError, match="não é possível"):
        _ = c.agua_efetiva_mm_ciclo


# ---------------------------------------------------------------------------
# 7. Erros de leitura
# ---------------------------------------------------------------------------
def test_csv_inexistente_erro(tmp_path):
    with pytest.raises(culturas.CulturasError, match="não encontrado"):
        ler_culturas_csv(tmp_path / "inexistente.csv")


def test_csv_cabecalho_errado_erro(tmp_path):
    p = tmp_path / "culturas.csv"
    p.write_text("nome,tipo,ciclo_dias\nfoo,comercial,70\n", encoding="utf-8")
    with pytest.raises(culturas.CulturasError, match="faltam colunas"):
        ler_culturas_csv(p)


def test_csv_nome_duplicado_erro(tmp_path):
    p = tmp_path / "culturas.csv"
    p.write_text(
        "nome,tipo,ciclo_dias,agua_mm_ciclo,tmax_limite_c,fixa_nitrogenio,"
        "protecao_erosao,valor_mercado,taxa_semeadura_kg_ha,"
        "rendimento_potencial_kg_ha,rendimento_regional_kg_ha,fonte\n"
        "milho,comercial,120,600,,nao,,,,5000,,Embrapa\n"
        "milho,comercial,120,600,,nao,,,,5000,,Embrapa\n",
        encoding="utf-8",
    )
    with pytest.raises(culturas.CulturasError, match="duplicadas"):
        ler_culturas_csv(p)


def test_csv_nome_vazio_erro(tmp_path):
    p = tmp_path / "culturas.csv"
    p.write_text(
        "nome,tipo,ciclo_dias,agua_mm_ciclo,tmax_limite_c,fixa_nitrogenio,"
        "protecao_erosao,valor_mercado,taxa_semeadura_kg_ha,"
        "rendimento_potencial_kg_ha,rendimento_regional_kg_ha,fonte\n"
        ",comercial,120,600,,nao,,,,5000,,Embrapa\n",
        encoding="utf-8",
    )
    with pytest.raises(culturas.CulturasError, match="vazio"):
        ler_culturas_csv(p)


# ---------------------------------------------------------------------------
# 8. valor_ou_aviso() helper
# ---------------------------------------------------------------------------
def test_valor_ou_aviso_devolve_valor_quando_tem(csv_preenchido):
    banco = ler_culturas_csv(csv_preenchido)
    c = banco["feijao-caupi"]
    assert c.valor_ou_aviso("ciclo_dias") == "70"
    assert c.valor_ou_aviso("agua_mm_ciclo") == "325.0"


def test_valor_ou_aviso_devolve_aviso_quando_falta(csv_cobertura_sem_ciclo):
    banco = ler_culturas_csv(csv_cobertura_sem_ciclo)
    c = banco["crotalaria-juncea"]
    assert c.valor_ou_aviso("ciclo_dias") == config.AVISO_DADO_FALTANTE


# ---------------------------------------------------------------------------
# 9. Integração com o CSV real (atualizado pelo usuário em 2026-11-14)
# ---------------------------------------------------------------------------
def test_csv_real_carrega_e_todas_as_6_sao_aptas():
    """O data/culturas.csv atualizado: 6 culturas, todas aptas (têm ciclo_dias).

    Com a regra revisada, as 3 coberturas (sem agua_mm_ciclo) também
    entram em rotações, usando agua_efetiva = 250 mm (estimada).
    """
    banco = carregar_banco()
    assert len(banco) == 6, f"esperava 6 culturas, veio: {list(banco)}"

    # As 6 culturas do CSV atualizado
    esperadas = {"feijao-caupi", "milho", "sorgo",
                 "crotalaria-juncea", "feijao-de-porco", "guandu"}
    assert set(banco.keys()) == esperadas

    # TODAS têm ciclo_dias -> todas aptas a rotações
    aptas = culturas.culturas_para_rotacao(banco)
    assert set(aptas) == esperadas
    assert culturas.culturas_excluidas(banco) == []

    # Comerciais: usam agua_mm_ciclo do CSV (não estimada)
    for nome in ("feijao-caupi", "milho", "sorgo"):
        c = banco[nome]
        assert c.agua_mm_ciclo is not None
        assert c.usa_agua_estimada is False
        assert c.agua_efetiva_mm_ciclo == c.agua_mm_ciclo

    # Coberturas: agua_mm_ciclo vazio -> usam fallback 250 (estimada)
    for nome in ("crotalaria-juncea", "feijao-de-porco", "guandu"):
        c = banco[nome]
        assert c.ciclo_dias is not None
        assert c.agua_mm_ciclo is None
        assert c.usa_agua_estimada is True
        assert c.agua_efetiva_mm_ciclo == 250


def test_csv_real_lacunas_por_cultura():
    """Confere as lacunas restantes em cada cultura do CSV atualizado."""
    banco = carregar_banco()
    # Comerciais: falta tmax, protecao_erosao, valor_mercado,
    # rendimento_regional. Sorgo também falta rendimento_potencial e
    # taxa_semeadura. Milho falta taxa_semeadura.
    f = banco["feijao-caupi"]
    assert set(f.lacunas) == {"tmax_limite_c", "protecao_erosao",
                              "valor_mercado", "rendimento_regional_kg_ha"}
    m = banco["milho"]
    assert "taxa_semeadura_kg_ha" in m.lacunas
    assert "rendimento_regional_kg_ha" in m.lacunas
    s = banco["sorgo"]
    # Sorgo: tudo vazio exceto nome, tipo, ciclo_dias, agua_mm_ciclo, fonte
    assert set(s.lacunas) == {"tmax_limite_c", "protecao_erosao",
                              "valor_mercado", "taxa_semeadura_kg_ha",
                              "rendimento_potencial_kg_ha",
                              "rendimento_regional_kg_ha"}
    # Coberturas: falta agua_mm_ciclo + os mesmos que faltam nas comerciais
    for nome in ("crotalaria-juncea", "feijao-de-porco", "guandu"):
        c = banco[nome]
        assert "agua_mm_ciclo" in c.lacunas
        assert "tmax_limite_c" in c.lacunas
        assert "rendimento_regional_kg_ha" in c.lacunas
