"""Verifica o resumo executivo sem chamar NASA/NSGA-II."""
from app.relatorio import gerar_markdown
from app.rotacao import OBJETIVOS


def _analise():
    ind = {
        'precipitacao_anual_media_mm': 700, 'et0_anual_media_mm': 900, 'indice_aridez': 0.78,
        'classe_aridez': 'úmido', 'meses_chuvosos_nomes': ['Jan'], 'cv_precipitacao_anual': 0.2,
        'cdd_estacao_chuvosa_medio_dias': 10, 'dias_calor_ano_medio': 2, 'gwetroot_medio': 0.5,
        'indice_fournier_modificado': 50, 'classe_erosividade': 'baixa',
        'tendencia_tmax_c': {'inclinacao_por_decada': 0.3, 'p_valor': 0.04},
        'tendencia_precipitacao_mm': {'inclinacao_por_decada': 2, 'p_valor': 0.5},
        'periodo': {'n_anos_completos': 35, 'inicio': 1991, 'fim': 2025},
    }
    def est(chave, viavel):
        return {
            'chave': chave, 'titulo': {'A': 'Rotação atual', 'D': 'Equilíbrio'}[chave],
            'avaliacao': {
                'restricoes': {'viavel': viavel}, 'objetivos': {k: 0.2 for k in OBJETIVOS},
                'indicadores': {'etc_total_mm_ano': 297, 'risco_quebra_anos': 0.05},
                'das': {'valor': 60},
                'slots': [{'nome': 'Trigo', 'mes_nome': 'Set', 'ano': 1,
                           'perda_rendimento_media': 0.01, 'fracao_dias_frio': 0.2}],
            },
            'explicacao': {
                'titulo': 'Equilíbrio', 'objetivo': 'Equilibrar prioridades',
                'riscos': ['Risco de frio'], 'por_que': [], 'beneficios': [],
                'confianca': {'valor': 60, 'rotulo': 'moderada', 'nota': 'Dados parciais'},
            },
        }
    return {
        'propriedade': {'nome': 'Teste', 'lat': 47.01, 'lon': 5.76, 'regiao': 'França', 'pais': 'França'},
        'clima': {'indicadores': ind, 'fonte': {'periodo_dados': ['1991-01-01', '2025-12-31']}},
        'vulnerabilidade': {'indice': 0.3, 'classe': 'moderada', 'n_indicadores': 8, 'metodo': 'média simples'},
        'topografia': {}, 'fontes': [], 'avisos_gerais': [],
        'estrategias': [est('A', False), est('D', True)],
    }


def test_relatorio_tem_resumo_executivo_e_separa_risco_frio():
    md = gerar_markdown(_analise())
    assert md.index('## Resumo para o agricultor') < md.index('## 1. Propriedade')
    assert 'D — Equilíbrio' in md
    assert 'Trigo (Set, ano 1)' in md
    assert '297 mm/ano' in md
    assert 'frio/geada' in md
    assert 'calor extremo' in md
