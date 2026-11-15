"""
config.py - Parâmetros, limiares e caminhos do projeto Rotação Inteligente.

Por que este arquivo existe:
    Tudo que é número, peso, limiar ou caminho de arquivo vive aqui.
    Nada de números soltos no código (regra do briefing, seção 2).
    Facilita ajustar valores sem mexer na lógica das funções em core/.

Como usar:
    import config
    config.LAT_DEFAULT
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Caminhos base do projeto
#    Tudo é relativo a este arquivo, então funciona mesmo se você mover a pasta.
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"          # onde ficam as respostas da API NASA POWER

CULTURAS_CSV = DATA_DIR / "culturas.csv"        # fornecido pelo briefing (parcial)
ROTACOES_JSON = DATA_DIR / "rotacoes.json"     # 3 estratégias (atual, solo, agua)
ONI_CSV = DATA_DIR / "oni.csv"                  # índice ONI da NOAA (manual)
PRODUTIVIDADE_CSV = DATA_DIR / "produtividade.csv"  # IBGE/SIDRA (manual)


# ---------------------------------------------------------------------------
# 2. Local padrão (Piauí - Teresina)
#    Apenas um default; o usuário pode trocar na interface.
#    O motor (nasa_power, enso, janelas, culturas, planejador) recebe
#    lat/lon de qualquer ponto do globo — não há hardcode geográfico.
#    LOCAIS_VALIDADOS lista os pontos com cache pré-baixado e parâmetros
#    de culturas calibrados localmente (caso de validação no semiárido
#    do Piauí). Locais fora desta lista ainda funcionam, mas o semáforo
#    desconta 1 ponto ("parâmetros de culturas sem calibração local").
# ---------------------------------------------------------------------------
LAT_DEFAULT = -5.09   # latitude de Teresina-PI
LON_DEFAULT = -42.81  # longitude de Teresina-PI

# Locais com cache pré-baixado (demo offline) e culturas calibradas.
# Chave: nome amigável; valor: (lat, lon, municipio, uf, observacao).
LOCAIS_VALIDADOS = [
    {
        "nome": "Teresina-PI",
        "lat": -5.09, "lon": -42.81,
        "municipio": "Teresina", "uf": "PI",
        "obs": "sede municipal; caso de validação no semiárido do Piauí",
    },
    {
        "nome": "Picos-PI",
        "lat": -7.07694, "lon": -41.46694,
        "municipio": "Picos", "uf": "PI",
        "obs": "sede municipal; coordenadas da Wikipédia (IBGE indisponível)",
    },
    {
        "nome": "São Raimundo Nonato-PI",
        "lat": -9.015, "lon": -42.69889,
        "municipio": "São Raimundo Nonato", "uf": "PI",
        "obs": "sede municipal; coordenadas da Wikipédia (IBGE indisponível)",
    },
]

# Rótulo do aviso quando o local não está calibrado (sem citar o Nordeste).
AVISO_SEM_CALIBRACAO_LOCAL = (
    "parâmetros de culturas sem calibração local para esta região"
)

# Locais de demonstração (cache pré-baixado, mas SEM calibração local).
# Servem para mostrar que o app funciona em qualquer hemisfério, mas os
# parâmetros de culturas do CSV não foram calibrados para essas regiões
# (descontam 1 ponto no semáforo, briefing 6.5). Os 3 pontos cobrem
# hemisférios e climas distintos: África equatorial (Nairóbi), América
# do Norte temperada (Iowa) e Ásia subtropical (Punjab).
LOCAIS_DEMOS = [
    {
        "nome": "Nairóbi (demo)",
        "lat": -1.29, "lon": 36.82,
        "pais": "Quênia",
        "obs": "demo; clima equatorial de altitude, sem calibração local",
    },
    {
        "nome": "Iowa (demo)",
        "lat": 41.6, "lon": -93.6,
        "pais": "EUA",
        "obs": "demo; clima temperado continental, sem calibração local",
    },
    {
        "nome": "Punjab (demo)",
        "lat": 31.1, "lon": 75.3,
        "pais": "Índia",
        "obs": "demo; clima subtropical monçônico, sem calibração local",
    },
]


def local_validado(lat: float, lon: float) -> bool:
    """True se (lat, lon) bate com algum dos LOCAIS_VALIDADOS.

    Comparação com 2 casas decimais (precisão dos arquivos de cache).
    Usado pelo semáforo: locais não validados descontam 1 ponto.
    """
    for loc in LOCAIS_VALIDADOS:
        if (round(loc["lat"], 2) == round(lat, 2)
                and round(loc["lon"], 2) == round(lon, 2)):
            return True
    return False


def local_demo(lat: float, lon: float) -> bool:
    """True se (lat, lon) bate com algum dos LOCAIS_DEMOS.

    Demos têm cache (abrem offline) mas NÃO têm calibração local —
    descontam 1 ponto no semáforo igual a qualquer outro local não
    validado (revisão 2026-11-14).
    """
    for loc in LOCAIS_DEMOS:
        if (round(loc["lat"], 2) == round(lat, 2)
                and round(loc["lon"], 2) == round(lon, 2)):
            return True
    return False


def local_tem_cache(lat: float, lon: float,
                    ano_inicio: int = 1991, ano_fim: int = 2026) -> bool:
    """True se existe arquivo de cache para (lat, lon) no período.

    Confere se o arquivo de cache de UMA variável (PRECTOTCORR) existe,
    usando a mesma convenção de nome de `_nome_cache` do nasa_power.py.
    Como todas as variáveis são baixadas juntas, se uma existe, todas
    existem. Usado para decidir se o aviso "Exige internet" aparece
    (revisão 2026-11-14: só mostra o aviso quando realmente vai precisar
    de rede).
    """
    lat_s = f"{lat:+.2f}".replace(".", "p").replace("+", "m").replace("-", "n")
    lon_s = f"{lon:+.2f}".replace(".", "p").replace("+", "m").replace("-", "n")
    nome = (f"power_{lat_s}_{lon_s}_{ano_inicio}_{ano_fim}"
            f"_PRECTOTCORR.json")
    return (CACHE_DIR / nome).exists()


# ---------------------------------------------------------------------------
# 2.b. Mapa interativo (bloco "🗺️ Mapa", revisão 2026-11-14)
#    Camadas de satélite da NASA GIBS (WMTS, EPSG:3857, "best"), ligáveis.
#    Os identificadores abaixo foram LIDOS do GetCapabilities do GIBS
#    (https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/
#     WMTSCapabilities.xml) em 2026-11-14 — não são nomes de memória.
# ---------------------------------------------------------------------------

# Endpoint base do GIBS para tiles WMTS em EPSG:3857 (Web Mercator).
GIBS_WMTS_BASE = (
    "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
    "/{layer}/default/{time}/{tile_matrix_set}/{z}/{y}/{x}.png"
)

# Camadas de satélite do GIBS (identificadores reais do GetCapabilities).
# Cada camada tem: id (Identifier), tile_matrix_set (lido do XML),
# nome amigável, descrição e formato de data aceito pelo GIBS.
GIBS_CAMADAS = {
    "ndvi": {
        "id": "MODIS_Terra_L3_NDVI_16Day",
        "tile_matrix_set": "GoogleMapsCompatible_Level9",
        "nome": "NDVI (MODIS Terra, 16 dias)",
        "descricao": "Índice de vegetação — verde = vegetação ativa.",
        "freq": "16day",   # 16-dias, data = primeiro dia do período
    },
    "imerg": {
        "id": "IMERG_Precipitation_Rate",
        "tile_matrix_set": "GoogleMapsCompatible_Level6",
        "nome": "Precipitação (IMERG, diário)",
        "descricao": "Taxa de precipitação estimada por satélite.",
        "freq": "daily",
    },
    "smap": {
        "id": "SMAP_L4_Analyzed_Root_Zone_Soil_Moisture",
        "tile_matrix_set": "GoogleMapsCompatible_Level6",
        "nome": "Umidade do solo raiz (SMAP L4)",
        "descricao": "Umidade estimada na zona radicular.",
        "freq": "daily",
    },
}

# Rótulo obrigatório nas camadas de satélite (não entram nos cálculos).
GIBS_ROTULO_VISUAL = "observação de satélite (visual, não entra nos cálculos)"

# URL do GetCapabilities (para validar IDs em runtime, se houver rede).
GIBS_CAPABILITIES_URL = (
    "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
    "1.0.0/WMTSCapabilities.xml"
)


# ---------------------------------------------------------------------------
# 2.c. Grade de risco hídrico do Piauí (camada "Risco hídrico (modelo)",
#    revisão 2026-11-14). Grade de ~1° sobre o estado, baixando só
#    PRECTOTCORR 1991-2026. Apenas pontos DENTRO do estado.
# ---------------------------------------------------------------------------

# Bbox de fallback do Piauí (retângulo envoltório, em graus decimais).
# Usado por gerar_pontos_grade SOMENTE quando não há malha oficial
# (data/piaui_uf.geojson). É um retângulo aproximado; a malha oficial
# (correção 2) faz o ponto-em-polígono e é preferida quando existe.
# Os valores abaixo são o retângulo envoltório do estado, ajustado em
# 2026-11-14 para reduzir os pontos fora da fronteira. NÃO afirmamos
# proveniência oficial — verifique antes de publicar.
PIAUI_BBOX = {
    "lat_min": -10.93, "lat_max": -2.74,   # sul -> norte
    "lon_min": -45.99, "lon_max": -40.37,  # oeste -> leste
}

# Malha oficial do Piauí (GeoJSON), baixada uma vez pelo usuário via
# scripts/baixar_malha_piaui.py. Se este arquivo existir, a grade usa
# ponto-em-polígono (filtro exato pela fronteira); senão, usa o
# retângulo PIAUI_BBOX acima como fallback.
PIAUI_MALHA_GEOJSON = DATA_DIR / "piaui_uf.geojson"

# Resolução da grade em graus (1.0 = ~111 km no equador). O NASA POWER
# tem resolução nativa de ~0.5°, mas 1° deixa a grade leve e
# suficiente para uma visualização de risco regional.
GRADE_PASSO_GRAUS = 1.0

# Diretório de cache da grade (separado do cache de pontos individuais).
GRADE_PIAUI_DIR = CACHE_DIR / "grade_piaui"

# Rótulo obrigatório na camada de risco (não é nível de campo).
GRADE_ROTULO = "resolução da grade do NASA POWER, não é nível de campo"


# ---------------------------------------------------------------------------
# 3. Janela de Oportunidade (briefing, seção 6.1)
#    "Meses em que o campo está livre E a chuva esperada >= agua_mm_ciclo * fator"
# ---------------------------------------------------------------------------
FATOR_MINIMO_CHUVA = 0.6
# Se agua_mm_ciclo estiver vazio no CSV, usamos este valor como fallback
# (briefing 6.1: "usar CHUVA_MINIMA_CICLO_MM de config.py e marcar o resultado
# como 'parâmetro estimado pela equipe'").
#
# Valor: 250 mm — suposição da equipe: piso da faixa da Embrapa para o
# caupi (300-400 mm de ciclo na literatura, faixa de demanda hídrica do
# feijão-caupi 250-400 mm conforme Embrapa Meio-Norte). É o piso
# conservador para uma cultura de cobertura no semiárido piauiense.
# Parâmetro AJUSTÁVEL: calibrar com agrônomo local (briefing 6.9).
CHUVA_MINIMA_CICLO_MM = 250
# Rótulo exato do briefing para cultura que usa este fallback:
CHUVA_MINIMA_CICLO_ROTULO = (
    "suposição da equipe: piso da faixa da Embrapa para o caupi"
)

# Critério de ESTABELECIMENTO (Etapa 5, ajuste 2026-11-14):
# A janela do ciclo inteiro ignora o MOMENTO da chuva — uma semeadura
# em setembro em Teresina passa no critério do ciclo (160 mm no ciclo de
# 120 dias) mesmo chovendo só ~4 mm nos primeiros 30 dias (a semente
# nem germina). Por isso há um segundo critério: o mês só é janela se a
# chuva dos primeiros JANELA_ESTABELECIMENTO_DIAS dias também atingir
# CHUVA_MINIMA_ESTABELECIMENTO_MM (germinação/emergência).
#
# Valores: 30 dias e 20 mm — suposição da equipe, validar com agrônomo
# local (briefing 6.9). A literatura agronômica cita ~25-50 mm nos
# primeiros 7-30 dias para estabelecimento de culturas de sequeiro no
# semiárido; usamos 20 mm/30 dias como piso conservador.
# Parâmetros AJUSTÁVEIS.
JANELA_ESTABELECIMENTO_DIAS = 30
CHUVA_MINIMA_ESTABELECIMENTO_MM = 20
JANELA_ESTABELECIMENTO_ROTULO = (
    "suposição da equipe, validar com agrônomo local"
)

# Fase 2: limiar NDVI para "solo nu" (validação da janela).
NDVI_LIMIAR_SOLO_NU = 0.3


# ---------------------------------------------------------------------------
# 4. Classificação ENSO (briefing, seção 4 e 6.2)
#    El Niño: ONI >= +0.5 | La Niña: ONI <= -0.5 | Neutro: entre os dois
# ---------------------------------------------------------------------------
ONI_EL_NINO = 0.5
ONI_LA_NINA = -0.5
# Convenção de ano agrícola (definida com o usuário):
#   ano agrícola 2024 = nov/2024 a out/2025.
#   Classificação desse ano = média ONI de DJF, onde DJF corresponde a
#   dez/2024, jan/2025 e fev/2025.
#   Ou seja, o ano agrícola N usa o DJF do ano civil N+1 (mais especificamente,
#   o trimestre DJF que cruza a virada de N para N+1).
ANO_AGRICOLA_INICIO_MES = 11   # novembro
DJF_MESES = [12, 1, 2]         # dezembro, janeiro, fevereiro (em ordem cronológica do ano agrícola)


# ---------------------------------------------------------------------------
# 5. Pontuação de uma cultura num cenário (briefing, seção 6.3)
#    score_agua = min(100, chuva_ciclo_mm / agua_mm_ciclo * 100)
#    score_cultura = score_agua - penalidade_calor   (limitado a 0..100)
# ---------------------------------------------------------------------------
SCORE_AGUA_CAP = 100   # teto do score de água
SCORE_MIN = 0
SCORE_MAX = 100


# ---------------------------------------------------------------------------
# 6. Índice de resiliência da rotação (briefing, seção 6.4)
#    Média ponderada dos scores das culturas da sequência.
#    Pesos por prioridade do agricultor. Se um critério estiver vazio,
#    ele sai da média e os pesos renormalizam (entra como lacuna).
#
#    AVISO: os pesos abaixo são PARÂMETROS AJUSTÁVEIS, suposição da equipe.
#    Não vieram do briefing; são ponto de partida para calibrar com agrônomo.
#    Mantemos só os critérios listados no briefing 6.4 (fixa_nitrogenio,
#    protecao_erosao, valor_mercado) + score_agua (do briefing 6.3).
# ---------------------------------------------------------------------------
PESOS_PRIORIDADE = {
    "agua": {
        "score_agua": 0.6,
        "fixa_nitrogenio": 0.15,
        "protecao_erosao": 0.15,
        "valor_mercado": 0.1,
    },
    "solo": {
        "score_agua": 0.25,
        "fixa_nitrogenio": 0.3,
        "protecao_erosao": 0.3,
        "valor_mercado": 0.15,
    },
    "renda": {
        "score_agua": 0.25,
        "fixa_nitrogenio": 0.15,
        "protecao_erosao": 0.1,
        "valor_mercado": 0.5,
    },
}


# ---------------------------------------------------------------------------
# 7. Semáforo de Confiança (briefing, seção 6.5)
#    Pontos somados. Verde >= 5 | Amarelo 3 a 4 | Vermelho <= 2.
#
#    Limiares "anos na classe" recalibrados para a série de 35 anos
#    (aprovado pelo usuário em 2026-11-14). Os valores originais do briefing
#    (8/4) foram pensados para outra série; estes refletem a distribuição
#    real observada (El Niño=12, La Niña=14, neutro=9).
# ---------------------------------------------------------------------------
SEMAFORO_PONTOS = {
    "anos_classe_maior_igual_10": 2,
    "anos_classe_5_a_9": 1,
    "anos_classe_menor_5": 0,
    "serie_total_maior_igual_10": 1,
    "sem_lacuna_essencial": 1,        # agua_mm_ciclo e ciclo_dias preenchidos
    "dados_solo_locais": 1,           # usuário informou dados do próprio solo
    "validacao_ndvi_smap": 1,         # Fase 2: NDVI/SMAP disponíveis
    "desconto_parametro_estimado": -1,
}
SEMAFORO_VERDE_MIN = 5
SEMAFORO_AMARELO_MIN = 3
# Vermelho: <= 2
# Rotulo dos limiares de "anos na classe" (parâmetro estimado pela equipe):
SEMAFORO_LIMIARES_ROTULO = "parâmetro estimado pela equipe"


# ---------------------------------------------------------------------------
# 8. Calculadora de sementes (briefing, seção 6.6)
#    area_m2 = (kg_semente / taxa_semeadura_kg_ha) * 10000
# ---------------------------------------------------------------------------
FATOR_HA_M2 = 10000   # 1 hectare = 10.000 m²


# ---------------------------------------------------------------------------
# 9. Alerta (briefing, seção 6.8)
#    Gatilho: chuva_7d >= limiar_chuva_mm E umidade_solo >= limiar_umidade
#    Os limiares ainda precisam ser definidos pela equipe.
#    Mantidos como None seguindo a regra "não invente dado".
# ---------------------------------------------------------------------------
LIMIAR_CHUVA_7D_MM = None
LIMIAR_UMIDADE_SOLO = None


# ---------------------------------------------------------------------------
# 10. NASA POWER (briefing, seção 4)
#     API diária por ponto, comunidade agroclimatologia "AG", sem conta.
#
#     Período fixo (não relativo ao ano atual):
#       - Série diária da NASA POWER (comunidade AG) começa em 1981-01-01
#         (confirmado por chamada real à API em 2026-11-13).
#       - Usamos 1991-2026 (36 anos civis; 35 anos agrícolas completos):
#         (a) ganhamos 10 anos de cobertura ENSO em relação a 2001-2026;
#         (b) evitamos a década de 1980, com mais revisações no ERSST;
#         (c) o ano agrícola 2025 (nov/2025 a out/2026) fica COMPLETO.
#       - ANO_FIM_SERIE = 2026 (não 2025) para incluir a estação chuvosa
#         de out/2026 do ano agrícola 2025 (a série 1991-2025 deixava o ano
#         agrícola 2025 sem o outono/inverno de 2026).
#       - Os arquivos de cache usam esses anos no nome, então o nome
#         fica estável (não depende do ano atual). A demo offline
#         funciona com o cache pré-baixado.
# ---------------------------------------------------------------------------
NASA_POWER_BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_POWER_COMMUNITY = "AG"
NASA_POWER_FORMAT = "JSON"
NASA_POWER_VARS = [
    "T2M",                # temperatura média a 2 m (°C)
    "T2M_MAX",            # temperatura máxima a 2 m (°C)
    "T2M_MIN",            # temperatura mínima a 2 m (°C)
    "PRECTOTCORR",        # precipitação corrigida (mm/dia)
    "RH2M",               # umidade relativa a 2 m (%)
    "ALLSKY_SFC_SW_DWN",  # radiação solar (MJ/m²/dia)
    "GWETROOT",           # umidade do solo na zona de raízes (0-1) — confirmado
    "GWETTOP",            # umidade do solo na superfície (0-1) — confirmado
]
# Confirmação: testamos as 8 variáveis uma a uma na API NASA POWER
# (community=AG) e todas retornaram metadados válidos em 2026-11-13.
# Cada variável é pedida em requisição separada, então se a API mudar
# e uma variável deixar de existir, só ela falha e o restante funciona.
ANO_INICIO_SERIE = 1991   # 1º ano civil da série (fixo, não relativo)
ANO_FIM_SERIE = 2026      # último ano civil; cobre ano agrícola 2025 completo
# Pausa entre requisições à API pública (segundos). Só é aplicada quando
# houve chamada de rede — se a variável veio do cache, não pausa.
NASA_POWER_PAUSA_SEGUNDOS = 0.5

# ---------------------------------------------------------------------------
# 11. Ano agrícola (briefing, seção 4)
#     ano agrícola N = nov/N a out/N+1. Para a análise estar completa,
#     precisamos de todos os dias nesse intervalo.
#     Com ANO_INICIO_SERIE=1991 e ANO_FIM_SERIE=2026, os anos agrícolas
#     completos disponíveis são 1991 (nov/1991-out/1992) até 2025
#     (nov/2025-out/2026). Se a série não cobrir um ano agrícola inteiro,
#     o app deve avisar (regra "use SOMENTE anos agrícolas completos").
# ---------------------------------------------------------------------------
ANO_AGRICOLA_PRIMEIRO_COMPLETO = ANO_INICIO_SERIE        # nov/1991-out/1992
ANO_AGRICOLA_ULTIMO_COMPLETO = ANO_FIM_SERIE - 1         # nov/2025-out/2026


# ---------------------------------------------------------------------------
# 11. Mensagens fixas (português-br) usadas em vários lugares da interface
# ---------------------------------------------------------------------------
RODAPE = (
    "Ferramenta de apoio. Não substitui o julgamento do agricultor "
    "nem a orientação de especialistas locais."
)
AVISO_DADO_FALTANTE = "dado não preenchido"
AVISO_POTENCIAL_EXPERIMENTAL = (
    "potencial experimental, costuma ser maior que a colheita real"
)
AVISO_PARAMETRO_ESTIMADO = "parâmetro estimado pela equipe"
AVISO_VALIDAR_AGRONOMO = "validar com agrônomo local"
AVISO_DADOS_IBGE = "dados do IBGE ainda não carregados"
AVISO_TAXA_SEMEADURA_FALTANTE = "taxa de semeadura não preenchida"
AVISO_ANO_AGRICOLA_INCOMPLETO = (
    "ano agrícola com série climática incompleta (período parcial)"
)
AVISO_COORDENADAS_NAO_IBGE = (
    "coordenadas obtidas da Wikipédia (sede municipal); "
    "API do IBGE indisponível para confirmação no momento"
)
