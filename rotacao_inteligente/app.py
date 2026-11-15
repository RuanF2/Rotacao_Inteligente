"""
app.py - Interface Streamlit do projeto Rotação Inteligente.

Etapas concluídas até aqui:
  - Etapa 2: bloco da NASA POWER (climatologia de chuva mensal).
  - Etapa 3: bloco ENSO (classificação El Niño / La Niña / neutro).
  - Etapa 4: bloco Planejador (kg de semente -> m² + colheita estimada).
  - Etapa 5: bloco Janelas (linha do tempo das janelas de oportunidade).

Escopo global (camada 2026-11-14): o motor (nasa_power, enso, janelas,
culturas, planejador) recebe lat/lon de qualquer ponto do globo. A
interface deixa o usuário escolher o local (3 municípios validados no
semiárido do Piauí + "outro local" com latitude/longitude, qualquer
hemisfério) e carregar o próprio culturas.csv.

Nas próximas etapas, esta página terá os 4 passos do fluxo (briefing 7):
  1. Escolher local + informar rotação atual, prioridade e kg de semente.
  2. Linha do tempo das janelas de oportunidade.
  3. Comparação das 3 rotações por cenário + semáforo e lacunas.
  4. Planejador (m², colheita estimada, histórico) + simulação do alerta.

Como rodar:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px

import config
from core import nasa_power, enso, culturas, planejador, janelas


# Configuração da página (deve ser a 1ª chamada Streamlit).
st.set_page_config(
    page_title="Rotação Inteligente",
    page_icon="🌱",
    layout="wide",
)


# --- Cache do Streamlit: a carga da série fica em memória entre execuções.
# IMPORTANTE: lat/lon ENTRA na chave do cache — locais diferentes não
# compartilham o DataFrame. O culturas_csv_path também entra, para o
# upload do usuário não vazar entre sessões.
@st.cache_data(show_spinner=False, ttl=3600)
def _carregar_clima(lat: float, lon: float,
                    ano_inicio: int, ano_fim: int):
    """Wrapper com cache do Streamlit para nasa_power.carregar_series."""
    return nasa_power.carregar_series(
        lat=lat, lon=lon, ano_inicio=ano_inicio, ano_fim=ano_fim,
    )


@st.cache_data(show_spinner=False, ttl=3600)
def _carregar_enso():
    """Wrapper com cache do Streamlit para enso.carregar_classificacao."""
    return enso.carregar_classificacao()


@st.cache_data(show_spinner=False, ttl=3600)
def _carregar_banco_culturas(culturas_csv_path: str = None):
    """Wrapper com cache do Streamlit para culturas.carregar_banco.

    O parâmetro `culturas_csv_path` entra na chave do cache: se o
    usuário fizer upload de um CSV, o cache é invalidado e o novo
    arquivo é lido.
    """
    if culturas_csv_path:
        return culturas.carregar_banco(culturas_csv_path)
    return culturas.carregar_banco()


# --- Cabeçalho --------------------------------------------------------------
st.title("🌱 Rotação Inteligente")
st.caption(
    "Ferramenta global de apoio à decisão para rotação de culturas, "
    "usando dados da NASA (POWER) e a tabela ONI da NOAA. Caso de "
    "validação no semiárido do Piauí (Brasil)."
)

st.markdown("---")

# --- Seletor de local (camada global) --------------------------------------
# 3 municípios validados (cache + calibração) + 3 demos (cache, sem
# calibração) + "outro local" com lat/lon de qualquer hemisfério. Para
# locais sem cache, baixa do NASA POWER sob demanda (exige internet).
st.subheader("📍 Local")

# Três grupos no seletor: validados, demos, outro (revisão 2026-11-14).
nomes_validados = [loc["nome"] for loc in config.LOCAIS_VALIDADOS]
nomes_demos = [loc["nome"] for loc in config.LOCAIS_DEMOS]
nomes_locais = (nomes_validados
                + ["— locais de demonstração (sem calibração local) —"]
                + nomes_demos
                + ["Outro local (lat/lon)"])
# O separador "—" não é selecionável: se cair nele, usa o 1º validado.
idx_padrao = 0
loc_sel = st.selectbox(
    "Escolha o local",
    options=nomes_locais,
    index=idx_padrao,
    help="Os 3 municípios pré-baixados (Teresina, Picos, São Raimundo "
         "Nonato) têm cache e culturas calibradas. Os 3 demos (Nairóbi, "
         "Iowa, Punjab) têm cache mas SEM calibração local (-1 no "
         "semáforo). 'Outro local' exige internet para baixar da NASA "
         "POWER (qualquer hemisfério).",
)
if loc_sel.startswith("—"):
    loc_sel = nomes_validados[0]   # separador não selecionável

is_outro = (loc_sel == "Outro local (lat/lon)")
is_demo = loc_sel in nomes_demos

if is_outro:
    col_lat, col_lon = st.columns(2)
    lat_sel = col_lat.number_input(
        "Latitude (graus decimais, -90 a 90)",
        min_value=-90.0, max_value=90.0,
        value=config.LAT_DEFAULT, format="%.4f", step=0.01,
        help="Positivo = norte, negativo = sul. Ex.: -1.29 (Nairóbi), "
             "41.6 (Iowa/EUA), 31.1 (Punjab/Índia).",
    )
    lon_sel = col_lon.number_input(
        "Longitude (graus decimais, -180 a 180)",
        min_value=-180.0, max_value=180.0,
        value=config.LON_DEFAULT, format="%.4f", step=0.01,
        help="Positivo = leste, negativo = oeste. Ex.: 36.82 (Nairóbi), "
             "-93.6 (Iowa/EUA), 75.3 (Punjab/Índia).",
    )
    local_calibrado = False
    nome_local_exibicao = f"({lat_sel:.4f}, {lon_sel:.4f})"
    # Ajuste 2: aviso "Exige internet" só quando NÃO tem cache. Se o
    # usuário digitar lat/lon que coincidem com um cache existente (ex.:
    # um demo), não há aviso de internet — só o de calibração.
    tem_cache = config.local_tem_cache(lat_sel, lon_sel)
    if not tem_cache:
        st.warning(
            "⚠️ **Exige internet** — este local não tem cache pré-"
            "baixado. A NASA POWER será consultada sob demanda "
            "(8 variáveis × ~13.000 dias = alguns minutos na 1ª vez)."
        )
elif is_demo:
    loc_dict = next(l for l in config.LOCAIS_DEMOS if l["nome"] == loc_sel)
    lat_sel = loc_dict["lat"]
    lon_sel = loc_dict["lon"]
    local_calibrado = False   # demo NÃO é calibrado (desconta 1 pt)
    nome_local_exibicao = loc_sel
    st.caption(
        f"📍 **{loc_sel}** ({loc_dict['pais']}) — "
        f"{lat_sel}, {lon_sel}. {loc_dict['obs']}. Cache pré-baixado "
        "(funciona offline)."
    )
else:
    # Município validado: pega lat/lon da lista
    loc_dict = next(l for l in config.LOCAIS_VALIDADOS if l["nome"] == loc_sel)
    lat_sel = loc_dict["lat"]
    lon_sel = loc_dict["lon"]
    local_calibrado = True
    nome_local_exibicao = loc_sel
    st.caption(
        f"📍 **{loc_sel}** ({loc_dict['municipio']}-{loc_dict['uf']}) — "
        f"{lat_sel}, {lon_sel}. {loc_dict['obs']}. Cache pré-baixado "
        "(funciona offline)."
    )

# Validação extra de latitude/longitude (revisão 2026-11-14): mesmo com
# min/max no number_input, confirmamos e damos mensagem clara se algum
# valor escapar do intervalo válido.
if is_outro:
    if not (-90.0 <= lat_sel <= 90.0):
        st.error(
            f"❌ Latitude inválida: {lat_sel}. Use um valor entre -90 "
            "e 90 graus (positivo = norte, negativo = sul)."
        )
    if not (-180.0 <= lon_sel <= 180.0):
        st.error(
            f"❌ Longitude inválida: {lon_sel}. Use um valor entre -180 "
            "e 180 graus (positivo = leste, negativo = oeste)."
        )
    lat_lon_validos = (-90.0 <= lat_sel <= 90.0
                       and -180.0 <= lon_sel <= 180.0)
else:
    lat_lon_validos = True   # validados/demos já têm coords corretas

# Aviso de "sem calibração local" — vale para demos E para "outro local"
# (ambos descontam 1 ponto no semáforo). Não cita o Nordeste (briefing).
if not local_calibrado:
    st.info(
        f"ℹ️ **{config.AVISO_SEM_CALIBRACAO_LOCAL}.** Os parâmetros de "
        f"culturas em `data/culturas.csv` foram calibrados para o caso "
        f"de validação (semiárido do Piauí). Use-os com cautela em "
        f"outras regiões ou carregue um CSV local. Isso desconta 1 "
        f"ponto no Semáforo de Confiança (Etapa 6)."
    )

# --- Upload de culturas.csv (camada global) --------------------------------
with st.expander("📁 Carregar seu próprio culturas.csv (opcional)"):
    st.caption(
        "O `data/culturas.csv` padrão vem calibrado para o caso de "
        "validação no semiárido do Piauí. Se você tem dados de "
        "culturas para outra região, carregue um CSV no mesmo formato "
        "(mesmas colunas e regras de lacuna). O arquivo enviado "
        "substitui temporariamente o padrão nesta sessão."
    )
    upload_csv = st.file_uploader(
        "culturas.csv",
        type=["csv"],
        key="upload_culturas",
        help="Colunas esperadas (mesmas do padrão): nome, tipo, "
             "ciclo_dias, agua_mm_ciclo, tmax_limite_c, fixa_nitrogenio, "
             "protecao_erosao, valor_mercado, taxa_semeadura_kg_ha, "
             "rendimento_potencial_kg_ha, rendimento_regional_kg_ha, fonte.",
    )
    caminho_culturas_upload = None
    if upload_csv is not None:
        # Salva o upload em /tmp e passa o caminho para carregar_banco.
        import tempfile, os
        caminho_culturas_upload = os.path.join(
            tempfile.gettempdir(), "culturas_upload.csv")
        with open(caminho_culturas_upload, "wb") as f:
            f.write(upload_csv.getvalue())
        st.success(
            f"✅ CSV carregado: {upload_csv.name} "
            f"({len(upload_csv.getvalue())} bytes). Será usado no lugar "
            "do `data/culturas.csv` nesta sessão."
        )

st.markdown("---")

# --- Bloco da NASA POWER (Etapa 2) -----------------------------------------
st.subheader("🌦️ Dados climáticos (NASA POWER)")
st.caption(
    f"Período fixo: {config.ANO_INICIO_SERIE} a {config.ANO_FIM_SERIE} "
    f"({config.ANO_FIM_SERIE - config.ANO_INICIO_SERIE + 1} anos civis, "
    f"{config.ANO_AGRICOLA_ULTIMO_COMPLETO - config.ANO_AGRICOLA_PRIMEIRO_COMPLETO + 1} "
    "anos agrícolas completos nov-out). Locais validados ficam em cache "
    "em `data/cache/`; outros locais são baixados sob demanda."
)

# Bloqueia o resto do app se lat/lon digitados forem inválidos (revisão
# 2026-11-14): não faz sentido carregar clima para coordenadas fora do
# intervalo. O number_input já limita, mas o guard protege contra edge
# cases (ex.: valor colado via session state).
if not lat_lon_validos:
    st.stop()

with st.spinner(f"Carregando dados climáticos para {nome_local_exibicao}..."):
    try:
        df_clima, falhas, infos = _carregar_clima(
            lat=lat_sel,
            lon=lon_sel,
            ano_inicio=config.ANO_INICIO_SERIE,
            ano_fim=config.ANO_FIM_SERIE,
        )
    except Exception as e:  # noqa: BLE001 - erro inesperado não deve quebrar a tela
        st.error(f"Erro ao carregar dados da NASA POWER: {e}")
        df_clima = pd.DataFrame()
        falhas = [str(e)]
        infos = []

# Aviso de ano agrícola incompleto (regra do briefing: só use anos completos)
completos_aa, incompletos_aa = enso.anos_agricolas_completos(df_clima)
if incompletos_aa:
    st.warning(
        f"⚠️ **Ano agrícola com série climática incompleta**: "
        f"{', '.join(str(a) for a in incompletos_aa)}. "
        "Estes anos NÃO são usados nas análises por cenário ENSO "
        "(regra do briefing: usar SOMENTE anos agrícolas completos, "
        "nov a out)."
    )
else:
    st.caption(
        f"✅ Todos os {len(completos_aa)} anos agrícolas "
        f"({completos_aa[0]} a {completos_aa[-1]}) têm série completa."
    )

if not df_clima.empty:
    # Resumo do período
    col1, col2, col3 = st.columns(3)
    col1.metric("Período", f"{df_clima.index.min().date()} a {df_clima.index.max().date()}")
    col2.metric("Dias", len(df_clima))
    col3.metric("Variáveis", len(df_clima.columns))

    # Lista de variáveis com metadados
    with st.expander("Ver variáveis carregadas"):
        if infos:
            df_meta = pd.DataFrame(
                [{"sigla": i.nome, "descrição": i.longname, "unidade": i.units}
                 for i in infos]
            )
            st.dataframe(df_meta, use_container_width=True, hide_index=True)
        else:
            st.write(list(df_clima.columns))

    # Gráfico de chuva mensal média (critério de "pronto" da Etapa 2)
    if "PRECTOTCORR" in df_clima.columns:
        chuva_mensal = nasa_power.resumo_mensal(df_clima, "PRECTOTCORR")
        # Agrupa por mês do ano (jan..dez) e tira a média entre os anos
        # SOMENTE dos anos agrícolas completos (exclui incompletos).
        chuva_mensal["ano_agr"] = chuva_mensal.index.year
        # Cada mês M pertence ao ano agrícola N se M >= 11, senão N-1
        chuva_mensal["ano_agr"] = (
            chuva_mensal["ano_agr"].where(chuva_mensal.index.month >= 11,
                                          chuva_mensal["ano_agr"] - 1)
        )
        chuva_mensal = chuva_mensal[chuva_mensal["ano_agr"].isin(completos_aa)]
        chuva_mensal["mes"] = chuva_mensal.index.month
        n_anos = len(completos_aa)
        chuva_climatologia = (
            chuva_mensal.groupby("mes")["PRECTOTCORR_soma_mm"]
            .mean()
            .round(1)
            .reset_index()
        )
        meses_pt = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                    "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        chuva_climatologia["mes_nome"] = chuva_climatologia["mes"].apply(
            lambda m: meses_pt[m - 1]
        )

        fig = px.bar(
            chuva_climatologia,
            x="mes_nome",
            y="PRECTOTCORR_soma_mm",
            title=f"Chuva média mensal (mm/mês) — média de {n_anos} anos "
                  f"agrícolas completos ({completos_aa[0]}-{completos_aa[-1]})",
            labels={"mes_nome": "Mês", "PRECTOTCORR_soma_mm": "Chuva (mm/mês)"},
        )
        fig.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "Fonte: NASA POWER (comunidade AG), variável PRECTOTCORR. "
            "Cada barra é a média da soma mensal de chuva considerando "
            f"apenas os {n_anos} anos agrícolas completos (nov-out) para a "
            f"coordenada ({lat_sel}, {lon_sel})."
        )
    else:
        st.warning("Variável PRECTOTCORR não disponível nos dados carregados.")

    # Avisos de falhas (se alguma variável não carregou)
    if falhas:
        with st.expander(f"⚠️ {len(falhas)} variável(is) com problema"):
            for f in falhas:
                st.write(f"- {f}")
else:
    st.warning(
        "Não foi possível carregar dados da NASA POWER. Verifique sua "
        "conexão ou rode `python3 -m core.nasa_power` no terminal para "
        "ver o erro."
    )

st.markdown("---")

# --- Bloco ENSO (Etapa 3) ---------------------------------------------------
st.subheader("🌊 Cenários ENSO (El Niño / La Niña / neutro)")
st.caption(
    f"Classificação do índice ONI (DJF) — anos agrícolas "
    f"{config.ANO_AGRICOLA_PRIMEIRO_COMPLETO} a "
    f"{config.ANO_AGRICOLA_ULTIMO_COMPLETO}. Fonte: ONI v6 (ERSSTv6), "
    "NOAA/CPC. Regra: ONI >= +0,5 El Niño; ONI <= -0,5 La Niña; neutro "
    "no meio. Apresentado como **tendência**, não determinismo."
)

try:
    classes_enso, contagem_enso, anos_limite = _carregar_enso()
except enso.EnsoError as e:
    st.error(f"Erro ao carregar o CSV do ONI: {e}")
    classes_enso, contagem_enso, anos_limite = [], {}, []

if classes_enso:
    # Cards de contagem por classe
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("El Niño", contagem_enso.get("El Niño", 0))
    col2.metric("La Niña", contagem_enso.get("La Niña", 0))
    col3.metric("Neutro", contagem_enso.get("neutro", 0))
    col4.metric("Total de anos", len(classes_enso))

    # Aviso de anos no limite (borderline)
    if anos_limite:
        st.warning(
            f"⚠️ **Anos exatamente no limite** (ONI = ±0,5): "
            f"{', '.join(str(a) for a in anos_limite)}. "
            "Esses anos são classificados pela regra do briefing (>= +0,5 El Niño; "
            "<= -0,5 La Niña), mas estão no limite: uma pequena revisão do ONI "
            "pode mudar a classe."
        )

    # Tabela completa ano a ano
    with st.expander("Ver classificação ano a ano"):
        df_enso = pd.DataFrame([
            {"ano": c.ano, "djf_oni": c.oni, "classe": c.classe,
             "no_limite": "sim" if c.no_limite else ""}
            for c in classes_enso
        ])
        st.dataframe(df_enso, use_container_width=True, hide_index=True)

    # Gráfico de barras: ONI DJF por ano, colorido por classe
    df_plot = pd.DataFrame([
        {"ano": c.ano, "djf_oni": c.oni, "classe": c.classe}
        for c in classes_enso if not pd.isna(c.oni)
    ])
    cores = {"El Niño": "#d62728", "La Niña": "#1f77b4", "neutro": "#bdbdbd"}
    fig = px.bar(
        df_plot, x="ano", y="djf_oni", color="classe",
        color_discrete_map=cores,
        title="Índice ONI (DJF) por ano agrícola",
        labels={"ano": "Ano agrícola", "djf_oni": "ONI DJF (°C anomalia)"},
    )
    # Linhas de referência em ±0.5
    fig.add_hline(y=0.5, line_dash="dash", line_color="red",
                  annotation_text="+0,5 (El Niño)")
    fig.add_hline(y=-0.5, line_dash="dash", line_color="blue",
                  annotation_text="-0,5 (La Niña)")
    fig.update_layout(height=400, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Fonte: NOAA/CPC, ONI v6 (ERSSTv6). "
        "Link: https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/"
    )
    st.caption(
        "⚠️ **Limitações:** valores recentes podem ser revisados quando a NOAA "
        "atualiza o ERSST; a NOAA usa o RONI (Relative ONI) no monitoramento "
        "oficial de ENSO em tempo real. Aqui usamos o ONI clássico (histórico)."
    )

st.markdown("---")

# --- Bloco Mapa (camada global, revisão 2026-11-14) -------------------------
# Mapa interativo (folium + streamlit-folium) centrado no local selecionado.
# - Marcadores para os 3 validados + 3 demos.
# - Click no mapa define "Outro local" (lat/lon); sem cache, baixa da
#   NASA POWER com o aviso de internet.
# - Camadas de satélite da NASA GIBS (WMTS, EPSG:3857), ligáveis, com
#   seletor de data. VISUAL: não entram nos cálculos.
# - Camada "Risco hídrico (modelo)": grade ~1° sobre o Piauí, baixa só
#   PRECTOTCORR, colore por % de anos da classe ENSO com chuva < água
#   efetiva, no mês de semeadura padrão. Reutiliza risco_hidrico_por_classe.
st.subheader("🗺️ Mapa")
st.caption(
    "Mapa interativo centrado no local selecionado. Clique no mapa para "
    "definir um novo local (lat/lon). As camadas de satélite da NASA GIBS "
    "são **observação de satélite (visual, não entram nos cálculos)**. "
    "A camada de risco hídrico é um **modelo com resolução da grade do "
    "NASA POWER (~1°), não é nível de campo**."
)

import folium
from streamlit_folium import st_folium

# Local atual e marcadores ----------------------------------------------
_map_center = [float(lat_sel), float(lon_sel)]
_m = folium.Map(location=_map_center, zoom_start=5,
                control_scale=True, prefer_canvas=True)

# Marcadores dos 3 validados (verde) + 3 demos (laranja, sem calibração).
for loc in config.LOCAIS_VALIDADOS:
    folium.Marker(
        [loc["lat"], loc["lon"]],
        popup=(f"<b>{loc['nome']}</b><br>{loc['municipio']}-{loc['uf']}<br>"
               f"{loc['lat']}, {loc['lon']}<br>"
               f"<i>validado, com calibração local</i>"),
        tooltip=loc["nome"],
        icon=folium.Icon(color="green", icon="ok-sign"),
    ).add_to(_m)
for loc in config.LOCAIS_DEMOS:
    folium.Marker(
        [loc["lat"], loc["lon"]],
        popup=(f"<b>{loc['nome']}</b><br>{loc['pais']}<br>"
               f"{loc['lat']}, {loc['lon']}<br>"
               f"<i>{loc['obs']}</i>"),
        tooltip=loc["nome"],
        icon=folium.Icon(color="orange", icon="info-sign"),
    ).add_to(_m)
# Marcador do local atual (azul, destaca).
folium.Marker(
    _map_center,
    popup=(f"<b>Local atual</b><br>{nome_local_exibicao}<br>"
           f"{lat_sel:.4f}, {lon_sel:.4f}"),
    tooltip="Local atual",
    icon=folium.Icon(color="blue", icon="star"),
).add_to(_m)

# --- Camadas de satélite GIBS (ligáveis, seletor de data) -------------------
with st.expander("🛰️ Camadas de satélite (NASA GIBS, visual)"):
    st.caption(f"ℹ️ **{config.GIBS_ROTULO_VISUAL}.**")
    from core import gibs as _gibs_mod

    # Valida IDs e lê a dimensão temporal contra o GetCapabilities
    # (best-effort, se houver rede). camadas_disponiveis() traz
    # validado, data_padrao (mais recente) e intervalos de cada camada.
    _camadas = _gibs_mod.camadas_disponiveis()
    _algum_validado = any(c.get("validado") for c in _camadas.values())
    if not _algum_validado:
        st.warning(
            "⚠️ Não foi possível validar as camadas no GIBS (sem internet "
            "ou timeout no GetCapabilities). Os tiles podem não carregar "
            "offline — o mapa segue sem eles."
        )

    # Seletor de data única (GIBS aceita YYYY-MM-DD). Padrão = data mais
    # recente comum: a mais antiga entre os <Default> das camadas ativas
    # (correção 2026-11-14). Se nenhuma tem Default, cai em 1º/nov do
    # fim da série (comportamento anterior).
    _defaults = [c["data_padrao"] for c in _camadas.values()
                 if c.get("data_padrao")]
    if _defaults:
        # Mais antiga entre as mais-recentes: garante que todas as
        # camadas têm uma data >= a escolhida (evita "sem dado" em
        # alguma camada). Depois ajustamos por camada.
        _default_sel = min(_defaults)
    else:
        _default_sel = pd.Timestamp(config.ANO_FIM_SERIE, 11, 1).date()
    _data_gibs = st.date_input(
        "Data da observação de satélite",
        value=_default_sel,
        help="Data (YYYY-MM-DD) dos tiles. Padrão: a data mais recente "
             "comum a todas as camadas (lida do GetCapabilities). Cada "
             "camada é ajustada para a data VÁLIDA mais próxima (ex.: "
             "NDVI é de 16 em 16 dias).",
    )

    # Checkboxes para ligar/desligar cada camada. Mostra a data ajustada.
    _camadas_ativas = []
    _cols = st.columns(len(config.GIBS_CAMADAS))
    for _col, (_chave, _c) in zip(_cols, config.GIBS_CAMADAS.items()):
        _lig = _col.checkbox(_c["nome"], value=False, key=f"gibs_{_chave}")
        if _lig:
            _camadas_ativas.append(_chave)
        # Data ajustada para a válida mais próxima desta camada.
        _prox = _gibs_mod.data_mais_proxima_valida(_chave, _data_gibs)
        if _prox is not None and _prox != _data_gibs:
            _col.caption(f"{_c['descricao']} — data ajustada: "
                         f"**{_prox.isoformat()}**")
        else:
            _col.caption(_c["descricao"])

    # Adiciona as camadas ativas ao mapa, cada uma com sua data ajustada.
    # Se o tile falhar (verificar_tile=False), avisa — o mapa segue.
    for _chave in _camadas_ativas:
        _prox = _gibs_mod.data_mais_proxima_valida(_chave, _data_gibs)
        _data_camada = (_prox or _data_gibs).isoformat()
        _url = _gibs_mod.tile_url_gibs(_chave, _data_camada)
        if not _url:
            continue
        _c = config.GIBS_CAMADAS[_chave]
        folium.raster_layers.TileLayer(
            tiles=_url,
            name=f"{_c['nome']} ({_data_camada})",
            attr="NASA GIBS",
            overlay=True,
            control=True,
            show=False,   # começa desligada para não poluir
        ).add_to(_m)
        # Verifica se o tile responde; se não, avisa (correção 2026-11-14).
        if not _gibs_mod.verificar_tile(_chave, _data_camada):
            st.warning(
                f"⚠️ A camada **{_c['nome']}** em {_data_camada} não "
                "respondeu (sem internet ou data inválida). O mapa segue "
                "sem essa camada."
            )

# --- Camada "Risco hídrico (modelo)" — grade Piauí -------------------------
with st.expander("🌡️ Risco hídrico (modelo, grade Piauí ~1°)"):
    st.caption(f"ℹ️ **{config.GRADE_ROTULO}.**")
    st.caption(
        "Grade de ~1° sobre o Piauí (somente PRECTOTCORR 1991-2026). "
        "Para a cultura e o cenário ENSO escolhidos, cada ponto é "
        "colorido pelo **% de anos da classe com chuva do ciclo "
        "abaixo da água efetiva**, no mês de semeadura padrão da "
        "cultura (reutiliza `risco_hidrico_por_classe` — mesma regra "
        "do Etapa 6, sem mudar o cálculo)."
    )
    # Filtro da grade: malha oficial (ponto-em-polígono) se existir,
    # senão retângulo envoltório. Rotula qual foi usado.
    from core import grade_risco as _gr_filtro
    _n_pts_grade = len(_gr_filtro.gerar_pontos_grade())
    _fonte_filtro = _gr_filtro.fonte_do_filtro()
    if _fonte_filtro == "malha oficial":
        st.caption(
            f"✅ **Filtro: malha oficial** (ponto-em-polígono, "
            f"`data/piaui_uf.geojson`) — {_n_pts_grade} pontos na grade."
        )
    else:
        st.caption(
            f"⚠️ **Filtro: retângulo envoltório** (sem "
            f"`data/piaui_uf.geojson`) — {_n_pts_grade} pontos. Para "
            f"filtro exato pela fronteira, rode "
            f"`python scripts/baixar_malha_piaui.py` uma vez (com "
            f"internet) e recarregue o app."
        )

    # Carrega o banco de culturas local (não depende do bloco Planejador).
    try:
        _banco_mapa = _carregar_banco_culturas(caminho_culturas_upload)
    except culturas.CulturasError as e:
        st.error(f"Erro ao carregar culturas para o mapa: {e}")
        _banco_mapa = {}
    _culturas_aptas = culturas.culturas_para_rotacao(_banco_mapa) if _banco_mapa else []

    _mostrar_grade = False
    if not _banco_mapa:
        st.warning("Sem culturas carregadas — a grade de risco não pode "
                   "ser calculada.")
    elif not _culturas_aptas:
        st.warning("Nenhuma cultura apta (todas sem `ciclo_dias`).")
    elif not classes_enso:
        st.warning("Sem classificação ENSO — a grade não pode ser calculada.")
    else:
        _col_cult, _col_enso = st.columns(2)
        _nome_cultura_mapa = _col_cult.selectbox(
            "Cultura para a grade",
            options=sorted(_culturas_aptas),
            help="A água efetiva desta cultura (do CSV ou fallback 250 "
                 "mm) é o limiar do risco.",
        )
        _classe_mapa = _col_enso.selectbox(
            "Cenário ENSO para a grade",
            options=["El Niño", "La Niña", "neutro"],
            index=2,
            help="Classe ENSO usada para filtrar os anos da série.",
        )
        _mes_mapa = st.number_input(
            "Mês de semeadura (1=jan..12=dez) — 0 = padrão (melhor mês)",
            min_value=0, max_value=12, value=0, step=1,
            help="0 (padrão) usa melhor_mes_semeadura. Você pode fixar.",
        )
        _mostrar_grade = st.button("📡 Baixar/recalcular grade",
                                   help="Baixa a grade (1ª vez exige "
                                        "internet; depois usa cache em "
                                        "data/cache/grade_piaui/).")

    # Botão disparado -> baixa a grade (parar_em_erro=True: se falhar,
    # avisa e NÃO mostra parcial).
    if _mostrar_grade and _banco_mapa and classes_enso:
        from core import grade_risco as _gr
        with st.spinner(f"Baixando/recalculando grade do Piauí "
                        f"(PRECTOTCORR, {_n_pts_grade} pontos)..."):
            try:
                _pontos_dfs, _stats = _gr.baixar_grade(
                    parar_em_erro=True)
            except nasa_power.NasaPowerRedeIndisponivel as e:
                st.error(
                    f"❌ Falha no download da grade: {e}. A grade não "
                    "foi atualizada (nada parcial foi salvo). Verifique "
                    "a conexão e tente de novo."
                )
                _pontos_dfs, _stats = [], {"total": 0, "ok": 0,
                                           "falhas": 0, "tempo_s": 0}
        if _pontos_dfs:
            st.success(
                f"Grade baixada: **{_stats['ok']}/{_stats['total']} "
                f"pontos** em {_stats['tempo_s']} s "
                f"({_stats['falhas']} falha(s))."
            )
            _cult = _banco_mapa[_nome_cultura_mapa]
            _mes_arg = (int(_mes_mapa) if _mes_mapa else None)
            _risco_pts = _gr.calcular_risco_grade(
                _pontos_dfs, _cult, classes_enso, _classe_mapa,
                mes_semeadura=_mes_arg)
            # Adiciona CircleMarkers coloridos pelo risco.
            for _p in _risco_pts:
                if _p["risco_pct"] is None:
                    _cor = "#cccccc"
                elif _p["risco_pct"] < 25:
                    _cor = "#2c7bb6"   # azul = baixo risco
                elif _p["risco_pct"] < 50:
                    _cor = "#f7f7f7"
                elif _p["risco_pct"] < 75:
                    _cor = "#fdae61"   # laranja
                else:
                    _cor = "#d7191c"   # vermelho = alto risco
                folium.CircleMarker(
                    [_p["lat"], _p["lon"]],
                    radius=8,
                    color=_cor,
                    fill=True,
                    fill_color=_cor,
                    fill_opacity=0.7,
                    popup=(f"<b>Grade ({_p['lat']:.2f}, {_p['lon']:.2f})</b><br>"
                           f"Cultura: {_cult.nome}<br>"
                           f"Cenário: {_classe_mapa}<br>"
                           f"Risco: {_p['risco_pct']}% "
                           f"({ _p['n_anos']} anos)<br>"
                           f"<i>{config.GRADE_ROTULO}</i>"),
                    tooltip=(f"{_p['risco_pct']}%" if _p["risco_pct"] is not None
                             else "sem anos da classe"),
                ).add_to(_m)
            # Legenda do risco.
            st.markdown(
                "**Legenda do risco:** 🔵 <25% (baixo) | ⚪ 25–50% | "
                "🟠 50–75% | 🔴 ≥75% (alto). Cinza = sem anos da classe."
            )
            st.session_state["grade_risco_pts"] = _risco_pts
        elif _stats["total"] > 0:
            st.warning("Grade vazia (nenhum ponto baixado).")

    # Re-desenha grade já calculada nesta sessão (sem baixar de novo).
    elif (_mostrar_grade is False
          and "grade_risco_pts" in st.session_state
          and st.session_state["grade_risco_pts"]):
        for _p in st.session_state["grade_risco_pts"]:
            if _p["risco_pct"] is None:
                _cor = "#cccccc"
            elif _p["risco_pct"] < 25:
                _cor = "#2c7bb6"
            elif _p["risco_pct"] < 50:
                _cor = "#f7f7f7"
            elif _p["risco_pct"] < 75:
                _cor = "#fdae61"
            else:
                _cor = "#d7191c"
            folium.CircleMarker(
                [_p["lat"], _p["lon"]], radius=8, color=_cor, fill=True,
                fill_color=_cor, fill_opacity=0.7,
                tooltip=(f"{_p['risco_pct']}%" if _p["risco_pct"] is not None
                         else "sem anos da classe"),
            ).add_to(_m)

folium.LayerControl(collapsed=False).add_to(_m)

# Renderiza o mapa e captura cliques.
_map_out = st_folium(_m, width=None, returned_objects=["last_clicked"])

# Click no mapa -> atualiza "Outro local" (lat/lon).
if _map_out.get("last_clicked"):
    _click = _map_out["last_clicked"]
    _click_lat = float(_click["lat"])
    _click_lon = float(_click["lng"])
    # Valida limites (revisão 2026-11-14).
    if (-90.0 <= _click_lat <= 90.0
            and -180.0 <= _click_lon <= 180.0):
        st.info(
            f"📍 Você clicou em **({_click_lat:.4f}, {_click_lon:.4f})**. "
            "Para usar este local, copie as coordenadas para o seletor "
            "'Outro local (lat/lon)' acima e recarregue."
        )
        # Se não tem cache, avisa exigir internet (regra do ajuste 2).
        if not config.local_tem_cache(_click_lat, _click_lon):
            st.warning(
                "⚠️ **Exige internet** — este ponto não tem cache "
                "pré-baixado. A NASA POWER será consultada sob demanda."
            )
    else:
        st.error("❌ Coordenadas do clique fora do intervalo válido "
                 "(lat -90..90, lon -180..180).")

st.markdown("---")

# --- Bloco Janelas de Oportunidade (Etapa 5) --------------------------------
st.subheader("🌦️ Janelas de oportunidade (linha do tempo)")
st.caption(
    "Para cada mês de semeadura, somamos a chuva que cai ao longo do "
    "ciclo da cultura (mediana entre os anos agrícolas completos) e "
    "comparamos com `agua_efetiva × "
    f"{config.FATOR_MINIMO_CHUVA}` (briefing 6.1). O mês é janela se a "
    "chuva do ciclo for suficiente. Coberturas sem `agua_mm_ciclo` no "
    "CSV usam `config.CHUVA_MINIMA_CICLO_MM = "
    f"{config.CHUVA_MINIMA_CICLO_MM} mm` (parâmetro estimado pela equipe)."
)

try:
    banco_janelas = _carregar_banco_culturas(caminho_culturas_upload)
except culturas.CulturasError as e:
    st.error(f"Erro ao carregar o banco de culturas: {e}")
    banco_janelas = {}

if df_clima.empty or "PRECTOTCORR" not in df_clima.columns:
    st.warning("Sem dados de chuva (PRECTOTCORR) — o bloco de janelas "
               "não pode ser calculado.")
elif banco_janelas:
    aptas = culturas.culturas_para_rotacao(banco_janelas)
    if not aptas:
        st.warning("Nenhuma cultura apta (todas sem `ciclo_dias` no CSV).")
    else:
        # Seletor de meses livres (calendário do agricultor) — Etapa 5 ajuste 2.
        # Padrão: todos os meses livres. Alimenta meses_livres de calcular_janelas.
        meses_opcoes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                        "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        meses_idx = list(range(1, 13))
        meses_livres_sel = st.multiselect(
            "Meses em que o campo está livre (calendário)",
            options=meses_opcoes,
            default=meses_opcoes,   # padrão: todos
            help="Selecione os meses em que o campo está disponível para "
                 "semeadura. Meses não selecionados ficam de fora da janela "
                 "(mesmo se a chuva for suficiente). Padrão: todos os meses.",
        )
        # Converte nomes para índices (1..12)
        meses_livres_idx = [meses_idx[meses_opcoes.index(m)]
                           for m in meses_livres_sel] or None
        if not meses_livres_sel:
            st.warning(
                "Nenhum mês selecionado como livre — nenhuma janela será "
                "calculada. Selecione ao menos um mês."
            )

        # Seletor de cultura para as janelas (só as aptas)
        cultura_janelas_nome = st.selectbox(
            "Cultura para avaliar a janela",
            options=aptas,
            index=0,
            help="Só aparecem as culturas com `ciclo_dias` preenchido. "
                 "Culturas sem `agua_mm_ciclo` usam um valor estimado "
                 "pela equipe (parâmetro ajustável).",
            key="sel_cultura_janelas",
        )
        c_jan = banco_janelas[cultura_janelas_nome]

        with st.spinner("Calculando janelas..."):
            r_jan = janelas.calcular_janelas(
                df_clima, c_jan,
                anos_agricolas_completos=completos_aa,
                meses_livres=meses_livres_idx,
            )

        # Aviso geral (estimativa de água ou outro problema)
        if r_jan.aviso_geral:
            st.info(f"ℹ️ {r_jan.aviso_geral}")

        if not r_jan.janelas:
            st.warning("Não foi possível calcular a janela para esta cultura.")
        else:
            # Métricas de cabeçalho
            cj1, cj2, cj3, cj4, cj5 = st.columns(5)
            cj1.metric("Ciclo (dias)", r_jan.ciclo_dias or "—",
                       help="Em coberturas, dias até o corte no pico de floração.")
            cj2.metric("Água efetiva (mm)",
                       f"{r_jan.agua_efetiva_mm:.0f}" if r_jan.agua_efetiva_mm else "—",
                       help="Do CSV (dado real) ou fallback da equipe (250 mm).")
            cj3.metric("Chuva mínima do ciclo (mm)",
                       f"{r_jan.janelas[0].agua_necessaria_mm:.0f}",
                       help=f"= agua_efetiva × {config.FATOR_MINIMO_CHUVA}")
            cj4.metric(f"Estabelec. {r_jan.estab_dias}d (mm)",
                       f"{r_jan.estab_min_mm:.0f}",
                       help=f"Chuva mínima nos primeiros "
                            f"{r_jan.estab_dias} dias (germinação). "
                            f"{config.JANELA_ESTABELECIMENTO_ROTULO}.")
            cj5.metric("Meses-janela", len(r_jan.meses_janela),
                       help="Meses que passam nos 2 critérios (ciclo + "
                            "estabelecimento) E estão livres no calendário.")

            # DataFrame + gráfico de barras (chuva do ciclo E dos 30 dias)
            df_jan = janelas.janelas_para_dataframe(r_jan)
            df_jan["status"] = df_jan["e_janela"].map(
                {True: "✓ janela", False: "✗ não"})
            df_jan["chuva_ciclo_mm"] = df_jan["chuva_ciclo_mm"].round(0)
            df_jan["chuva_estab_mm"] = df_jan["chuva_estab_mm"].round(0)

            # Gráfico: chuva do ciclo por mês, com linha de mínimo
            fig = px.bar(
                df_jan, x="mes_nome", y="chuva_ciclo_mm",
                color="status",
                color_discrete_map={"✓ janela": "#2ca02c",
                                    "✗ não": "#d62728"},
                title=(f"Chuva mediana do ciclo por mês de semeadura — "
                       f"{r_jan.cultura} (ciclo {r_jan.ciclo_dias}d)"),
                labels={"mes_nome": "Mês de semeadura",
                        "chuva_ciclo_mm": "Chuva do ciclo (mm, mediana)"},
            )
            # Linha de referência: chuva mínima do ciclo
            fig.add_hline(
                y=r_jan.janelas[0].agua_necessaria_mm,
                line_dash="dash", line_color="gray",
                annotation_text=(
                    f"mínimo ciclo: {r_jan.janelas[0].agua_necessaria_mm:.0f} mm "
                    f"(agua × {config.FATOR_MINIMO_CHUVA})"
                ),
            )
            fig.update_layout(height=400, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

            # Gráfico 2: chuva dos primeiros 30 dias (estabelecimento)
            fig2 = px.bar(
                df_jan, x="mes_nome", y="chuva_estab_mm",
                color="status",
                color_discrete_map={"✓ janela": "#2ca02c",
                                    "✗ não": "#d62728"},
                title=(f"Chuva mediana dos primeiros {r_jan.estab_dias} dias "
                       f"(estabelecimento) — {r_jan.cultura}"),
                labels={"mes_nome": "Mês de semeadura",
                        "chuva_estab_mm": f"Chuva {r_jan.estab_dias}d (mm, mediana)"},
            )
            fig2.add_hline(
                y=r_jan.estab_min_mm,
                line_dash="dash", line_color="orange",
                annotation_text=(
                    f"mínimo estab.: {r_jan.estab_min_mm:.0f} mm "
                    f"(germinação)"
                ),
            )
            fig2.update_layout(height=350, showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)

            # Tabela detalhada
            with st.expander("Ver detalhe mês a mês"):
                st.dataframe(df_jan, use_container_width=True, hide_index=True)
                if r_jan.meses_janela:
                    st.caption(
                        f"**Meses-janela:** {', '.join(r_jan.meses_janela)}. "
                        "São os meses que passam nos dois critérios "
                        f"(chuva do ciclo ≥ {r_jan.janelas[0].agua_necessaria_mm:.0f} mm "
                        f"E chuva de estabelecimento ≥ {r_jan.estab_min_mm:.0f} mm "
                        f"nos primeiros {r_jan.estab_dias} dias) E estão "
                        "livres no calendário."
                    )
                else:
                    st.caption("Nenhum mês é janela de oportunidade para "
                               "esta cultura neste local.")
                st.caption(
                    f"Cálculo: para cada mês M, somamos a chuva diária "
                    f"dos {r_jan.ciclo_dias} dias do ciclo E dos "
                    f"{r_jan.estab_dias} dias de estabelecimento, em cada "
                    f"um dos {r_jan.janelas[0].anos_usados} anos agrícolas "
                    "completos, e tiramos a **mediana** entre os anos "
                    "(robusta a anos extremos)."
                )

            st.caption(
                "⚠️ **Limitações:** (1) Não há validação por NDVI/SMAP "
                "(Fase 2, briefing 6.1). (2) A janela é climatológica "
                "(todos os anos agrícolas juntos); a separação por "
                "cenário ENSO vem na Etapa 6. (3) Os limiares de "
                "estabelecimento (30 dias / 20 mm) são "
                f"{config.JANELA_ESTABELECIMENTO_ROTULO}."
            )

st.markdown("---")

# --- Bloco Planejador (Etapa 4) ---------------------------------------------
st.subheader("🌱 Planejador de sementes (kg → m² + colheita estimada)")
st.caption(
    "Escolha uma cultura e digite os kg de semente disponíveis. A "
    "calculadora usa a taxa de semeadura do banco de culturas. Se "
    "faltar a taxa (ou algum rendimento), a interface mostra o aviso "
    "de lacuna em vez de inventar valor."
)

try:
    banco = _carregar_banco_culturas(caminho_culturas_upload)
except culturas.CulturasError as e:
    st.error(f"Erro ao carregar o banco de culturas: {e}")
    banco = {}

if banco:
    # Seletor de cultura: todas as do banco, com indicação de exclusão.
    # Regra revisada (2026-11-14): só ciclo_dias é obrigatório. Culturas
    # sem agua_mm_ciclo continuam aptas e usam config.CHUVA_MINIMA_CICLO_MM
    # (marcado "parâmetro estimado pela equipe").
    opcoes = []
    for nome, c in banco.items():
        if not c.tem_dados_para_rotacao:
            faltam = ", ".join(c.campos_faltantes_para_rotacao)
            opcoes.append(f"{nome} (sem dados para rotação — falta: {faltam})")
        elif c.usa_agua_estimada:
            opcoes.append(
                f"{nome} (água estimada: {config.CHUVA_MINIMA_CICLO_MM} mm)"
            )
        else:
            opcoes.append(nome)
    nome_selecionado = st.selectbox(
        "Cultura",
        options=opcoes,
        index=0,
        help="Culturas sem ciclo_dias não entram em rotações. Culturas "
             "com ciclo_dias mas sem agua_mm_ciclo usam um valor estimado "
             "pela equipe (parâmetro ajustável).",
    )
    # Limpa o sufixo informativo para pegar o nome real
    nome_real = nome_selecionado.split(" (")[0]
    cultura_sel = banco[nome_real]

    kg_semente = st.number_input(
        "Kg de semente disponível",
        min_value=0.0,
        value=10.0,
        step=1.0,
        help="Quantidade de semente (em kg) que você tem em mãos.",
    )

    # Exibe a ficha da cultura (com lacunas)
    with st.expander(f"Ver ficha da cultura: {nome_real}"):
        ficha = pd.DataFrame([
            {"campo": "tipo", "valor": cultura_sel.valor_ou_aviso("tipo")},
            {"campo": "ciclo_dias",
             "valor": cultura_sel.valor_ou_aviso("ciclo_dias")},
            {"campo": "agua_mm_ciclo",
             "valor": cultura_sel.valor_ou_aviso("agua_mm_ciclo")},
            {"campo": "agua_efetiva_mm_ciclo",
             "valor": (f"{cultura_sel.agua_efetiva_mm_ciclo:.0f} mm"
                       if cultura_sel.ciclo_dias is not None
                       else config.AVISO_DADO_FALTANTE)},
            {"campo": "tmax_limite_c",
             "valor": cultura_sel.valor_ou_aviso("tmax_limite_c")},
            {"campo": "fixa_nitrogenio",
             "valor": cultura_sel.valor_ou_aviso("fixa_nitrogenio")},
            {"campo": "protecao_erosao",
             "valor": cultura_sel.valor_ou_aviso("protecao_erosao")},
            {"campo": "valor_mercado",
             "valor": cultura_sel.valor_ou_aviso("valor_mercado")},
            {"campo": "taxa_semeadura_kg_ha",
             "valor": cultura_sel.valor_ou_aviso("taxa_semeadura_kg_ha")},
            {"campo": "rendimento_potencial_kg_ha",
             "valor": cultura_sel.valor_ou_aviso("rendimento_potencial_kg_ha")},
            {"campo": "rendimento_regional_kg_ha",
             "valor": cultura_sel.valor_ou_aviso("rendimento_regional_kg_ha")},
        ])
        st.dataframe(ficha, use_container_width=True, hide_index=True)
        if cultura_sel.lacunas:
            st.caption(
                f"⚠️ **Lacunas nesta cultura ({len(cultura_sel.lacunas)}):** "
                + ", ".join(cultura_sel.lacunas)
            )
        if not cultura_sel.tem_dados_para_rotacao:
            st.caption(
                "⚠️ Esta cultura não entra em rotações — faltam: "
                + ", ".join(cultura_sel.campos_faltantes_para_rotacao)
                + ". Preencha esses campos no `data/culturas.csv` para "
                "incluí-la."
            )
        if cultura_sel.usa_agua_estimada:
            st.caption(
                f"⚠️ **{config.AVISO_PARAMETRO_ESTIMADO}** — "
                f"`agua_mm_ciclo` está vazio no CSV; a janela usa "
                f"`config.CHUVA_MINIMA_CICLO_MM = "
                f"{config.CHUVA_MINIMA_CICLO_MM} mm` como fallback "
                f"({config.CHUVA_MINIMA_CICLO_ROTULO}). Isso desconta "
                "1 ponto no Semáforo de Confiança."
            )
        if cultura_sel.fonte:
            st.caption(f"Fonte declarada no CSV: {cultura_sel.fonte}")

    # Cálculo
    resultado = planejador.planejar(kg_semente, cultura_sel)

    col1, col2, col3 = st.columns(3)

    # Área
    if resultado.area.area_m2 is not None:
        col1.metric(
            "Área plantável",
            f"{resultado.area.area_m2:,.0f} m²",
            help=f"= ({kg_semente} kg / "
                 f"{cultura_sel.taxa_semeadura_kg_ha} kg/ha) × 10.000",
        )
    else:
        col1.metric("Área plantável", "—")
        col1.error(resultado.area.aviso or "não calculado")

    # Colheita
    if resultado.colheita.colheita_kg is not None:
        col2.metric(
            "Colheita estimada",
            f"{resultado.colheita.colheita_kg:,.0f} kg",
            help=f"= {resultado.area.area_ha:.4f} ha × "
                 f"{resultado.colheita.rendimento_kg_ha_usado} kg/ha",
        )
        if resultado.colheita.fonte_rendimento == "regional":
            col2.caption("✅ " + resultado.colheita.aviso)
        else:
            col2.warning("⚠️ " + resultado.colheita.aviso)
    else:
        col2.metric("Colheita estimada", "—")
        col2.error(resultado.colheita.aviso or "não calculado")

    # Rendimento usado
    if resultado.colheita.rendimento_kg_ha_usado is not None:
        col3.metric(
            "Rendimento usado",
            f"{resultado.colheita.rendimento_kg_ha_usado:,.0f} kg/ha",
            help="Fonte do rendimento: "
                 + ("regional (IBGE, caso de validação no Piauí)" if
                    resultado.colheita.fonte_rendimento == "regional"
                    else "potencial experimental"),
        )
    else:
        col3.metric("Rendimento usado", "—")

    st.markdown(
        f"""
        **Fórmula** (briefing 6.6):
        `area_m² = (kg de semente / taxa de semeadura kg/ha) × 10.000`

        - **Colheita estimada** usa `rendimento_regional_kg_ha` quando
          existe (preferência, dado real do IBGE para o caso de validação
          no Piauí). Se só houver `rendimento_potencial_kg_ha`, usa esse
          — mas é experimental e costuma ser maior que a colheita real.
          Se ambos faltarem, nada é mostrado (regra "não invente dado").
        """
    )

    # Seção "Dados que faltam" (briefing 7): consolida as lacunas de todas
    # as culturas — convite para o agrônomo/agricultor completar o CSV.
    lacunas_todas = culturas.listar_lacunas(banco)
    if lacunas_todas:
        with st.expander(f"📋 Dados que faltam no CSV ({len(lacunas_todas)} "
                         "culturas com lacunas)"):
            df_lac = pd.DataFrame(
                [{"cultura": n, "lacunas": ", ".join(ls)}
                 for n, ls in lacunas_todas.items()]
            )
            st.dataframe(df_lac, use_container_width=True, hide_index=True)
            st.caption(
                "Convite para o agrônomo/agricultor completar o "
                "`data/culturas.csv`. Célula vazia = lacuna (nunca zero)."
            )
else:
    st.warning("Banco de culturas vazio ou não carregado.")

st.markdown("---")

# --- Bloco Comparativo de Rotações (Etapa 6) --------------------------------
st.subheader("🔄 Comparativo de rotações por cenário ENSO")
st.caption(
    "Para cada estratégia de rotação (atual, focada em solo, focada em "
    "água) e cada cenário ENSO (El Niño, La Niña, neutro), calculamos o "
    "índice de resiliência (0..100) combinando o score de água das "
    "culturas com critérios agronômicos (fixação de N, proteção contra "
    "erosão, valor de mercado), ponderados pela prioridade. Lacunas "
    "saem da média com renormalização dos pesos (briefing 6.4)."
)

# Definição das 3 rotações (briefing 6.4 + ajuste "atual = milho + pousio"):
# ROTAÇÃO_ATUAL = milho + pousio (sem cultura de cobertura — degrada o solo)
# ROTAÇÃO_SOLO  = milho + crotalaria-juncea (aduba o solo com N)
# ROTAÇÃO_AGUA  = sorgo + feijao-caupi (ambas resistentes à seca)
# (Se uma cultura do CSV não existir, a rotação pula aquele elo.)
from core import resiliencia, semaforo
from core.resiliencia import (chuva_ciclo_por_classe, pontuar_cultura_cenario,
                              pontuar_rotacao_cenario, pior_cenario,
                              melhor_mes_semeadura, risco_hidrico_por_classe,
                              mes_da_colheita, janela_pos_colheita)
from core.semaforo import calcular_semaforo, emoji_cor
from core.janelas import nome_mes

ROTACOES_DEF = {
    "atual": {
        "rotulos": ["milho", "(pousio)"],
        "culturas": ["milho"],   # pousio não pontua
        "prioridade": "renda",
        "descricao": "milho + pousio (prática comum, degrada o solo)",
    },
    "solo": {
        "rotulos": ["milho", "crotalaria-juncea"],
        "culturas": ["milho", "crotalaria-juncea"],
        "prioridade": "solo",
        "descricao": "milho + crotalária (aduba o solo com N)",
    },
    "agua": {
        "rotulos": ["sorgo", "feijao-caupi"],
        "culturas": ["sorgo", "feijao-caupi"],
        "prioridade": "agua",
        "descricao": "sorgo + feijão-caupi (ambas resistentes à seca)",
    },
}

# Seletor de prioridade (define os pesos da média ponderada)
prioridade_sel = st.radio(
    "Prioridade do agricultor (define os pesos do índice)",
    options=["agua", "solo", "renda"],
    index=0,
    horizontal=True,
    help="agua: peso maior no score de água; solo: peso maior em fixação "
         "de N e proteção contra erosão; renda: peso maior no valor de "
         "mercado (config.PESOS_PRIORIDADE).",
)

if df_clima.empty or not banco:
    st.warning("Sem dados climáticos ou banco de culturas — o comparativo "
               "não pode ser calculado.")
else:
    # Carrega ENSO (já carregado acima em classes_enso)
    try:
        classes_enso_local, contagem_enso_local, _ = enso.carregar_classificacao()
    except enso.EnsoError as e:
        st.error(f"Erro ao carregar ENSO: {e}")
        classes_enso_local = []

    if not classes_enso_local:
        st.warning("Sem classificação ENSO — o comparativo não pode ser calculado.")
    elif not completos_aa:
        st.warning("Sem anos agrícolas completos — o comparativo não pode "
                   "ser calculado.")
    else:
        # --- Seletor de mês de semeadura por cultura (revisão 2026-11-14)
        # Cada cultura é avaliada no seu mês de semeadura (não em 1/nov fixo).
        # Padrão: o mês-janela com maior chuva mediana do ciclo; se não
        # houver mês-janela, usa o mês de maior chuva e marca "sem janela
        # válida" (desconta 1 ponto no semáforo). O usuário pode trocar.
        # Lista todas as culturas usadas nas rotações (dedup, preservando ordem).
        culturas_no_comparativo = []
        for defn in ROTACOES_DEF.values():
            for cn in defn["culturas"]:
                if cn not in culturas_no_comparativo:
                    culturas_no_comparativo.append(cn)
        # Calcula o padrão de cada cultura (uma vez).
        padroes_mes = {}    # nome_cultura -> (mes, tem_janela, chuva)
        for cn in culturas_no_comparativo:
            if cn not in banco:
                continue
            padroes_mes[cn] = melhor_mes_semeadura(
                df_clima, banco[cn], anos_agricolas_completos=completos_aa)

        st.markdown("**Mês de semeadura por cultura** (revisão 2026-11-14)")
        st.caption(
            "Padrão: o mês-janela (Etapa 5: ciclo + estabelecimento) com "
            "maior chuva mediana do ciclo. Se nenhuma janela é válida, usa "
            "o mês de maior chuva (marca 'sem janela válida', -1 no "
            "semáforo). Você pode trocar o mês de cada cultura."
        )
        meses_selecionados = {}    # nome_cultura -> mes (int)
        cols_mes = st.columns(len(culturas_no_comparativo) or 1)
        for col, cn in zip(cols_mes, culturas_no_comparativo):
            if cn not in banco:
                col.markdown(f"**{cn}** — (não está no CSV)")
                continue
            padrao_mes, tem_janela, chuva_padrao = padroes_mes[cn]
            opcoes_idx = list(range(1, 13))
            opcoes_nomes = [nome_mes(m) for m in opcoes_idx]
            # Índice do padrão
            idx_padrao = (opcoes_idx.index(padrao_mes)
                          if padrao_mes is not None else 0)
            sel = col.selectbox(
                f"{cn}",
                options=opcoes_nomes,
                index=idx_padrao,
                key=f"mes_sem_{cn}",
                help=(f"Padrão: {nome_mes(padrao_mes) if padrao_mes else '—'} "
                      f"({'janela válida' if tem_janela else 'sem janela válida'}, "
                      f"chuva mediana ciclo = "
                      f"{chuva_padrao:.0f} mm" if chuva_padrao else
                      f"{cn}: sem mês calculável"),
            )
            meses_selecionados[cn] = opcoes_idx[opcoes_nomes.index(sel)]
            if not tem_janela and padrao_mes is not None:
                col.caption("⚠️ sem janela válida (-1 no semáforo)")

        # Calcula índice de cada rotação em cada cenário
        resultados = {}   # {(rotacao, classe): {"scores":[], "prioridade":p}}
        janelas_pos_colheita = {}   # {rotacao: JanelaPosColheita}
        todas_lacunas = []
        usa_alguma_agua_estimada = False
        alguma_sem_janela = False

        for nome_rot, defn in ROTACOES_DEF.items():
            # Usa a prioridade do seletor se a rotação for "atual", senão
            # usa a prioridade própria da rotação (solo/agua).
            prio = (prioridade_sel if nome_rot == "atual"
                    else defn["prioridade"])
            culturas_rot = defn["culturas"]
            # --- Alternância safra 1 / safra 2 (revisão 2026-11-14)
            # Cada cultura da rotação é uma safra (alternância entre
            # safras), NÃO semeadas no mesmo mês. Rotulamos como
            # "safra 1" / "safra 2" para deixar claro.
            for idx_safra, nome_cult in enumerate(culturas_rot):
                posicao = (f"safra {idx_safra + 1}"
                           if len(culturas_rot) > 1 else "safra 1")
                if nome_cult not in banco:
                    continue
                cult = banco[nome_cult]
                mes_sem = meses_selecionados.get(nome_cult)
                # Verifica se o mês escolhido pelo usuário é janela válida
                # (comparado ao padrão calculado). Se for o mesmo mês do
                # padrão, usa o tem_janela do padrão; senão, recalcula.
                padrao_mes, tem_janela_padrao, _ = padroes_mes[nome_cult]
                if mes_sem == padrao_mes:
                    tem_janela = tem_janela_padrao
                else:
                    # Mês trocado pelo usuário: confere se é janela.
                    r_jan = janelas.calcular_janelas(
                        df_clima, cult,
                        anos_agricolas_completos=completos_aa)
                    jm = next((jm for jm in r_jan.janelas
                               if jm.mes == mes_sem), None)
                    tem_janela = bool(jm and jm.e_janela)
                # Mediana da chuva do ciclo por classe (com mes_semeadura)
                chuvas = chuva_ciclo_por_classe(
                    df_clima, cult, classes_enso_local,
                    completos_aa[0], completos_aa[-1],
                    mes_semeadura=mes_sem)
                # Risco hídrico por classe (% anos c/ chuva < agua)
                riscos = risco_hidrico_por_classe(
                    df_clima, cult, classes_enso_local,
                    completos_aa[0], completos_aa[-1],
                    mes_semeadura=mes_sem)
                for classe in ("El Niño", "La Niña", "neutro"):
                    med, n = chuvas[classe]
                    sc = pontuar_cultura_cenario(
                        df_clima, cult, classe, med, n,
                        mes_semeadura=mes_sem,
                        tem_janela_valida=tem_janela,
                        risco_hidrico_pct=riscos[classe])
                    # Acumula scores por (rotacao, classe)
                    key = (nome_rot, classe)
                    if key not in resultados:
                        resultados[key] = {
                            "scores": [], "prioridade": prio}
                    resultados[key]["scores"].append(sc)
                    # Coleta lacunas
                    for l in sc.lacunas:
                        if l not in todas_lacunas:
                            todas_lacunas.append(l)
                    if cult.usa_agua_estimada:
                        usa_alguma_agua_estimada = True
                    if not tem_janela:
                        alguma_sem_janela = True

            # --- Janela pós-colheita para cultura de cobertura
            # (revisão 2026-11-14). Se a rotação tem 2 culturas e a 2ª é
            # de cobertura (tipo "cobertura"), confere se há janela para
            # ela logo após a colheita da safra 1.
            if len(culturas_rot) == 2:
                cult1_nome, cult2_nome = culturas_rot
                if (cult1_nome in banco and cult2_nome in banco
                        and banco[cult2_nome].tipo == "cobertura"):
                    mes1 = meses_selecionados.get(cult1_nome)
                    ciclo1 = banco[cult1_nome].ciclo_dias
                    if mes1 and ciclo1:
                        mes_colh = mes_da_colheita(mes1, ciclo1)
                        r_cob = janelas.calcular_janelas(
                            df_clima, banco[cult2_nome],
                            anos_agricolas_completos=completos_aa)
                        jpc = janela_pos_colheita(r_cob, mes_colh)
                        # Guarda em dicionário próprio (não em resultados,
                        # que só tem {scores, prioridade}).
                        janelas_pos_colheita[nome_rot] = jpc

        # Monta o ScoreRotacaoCenario final
        scores_finais = {}   # {(rot, classe): ScoreRotacaoCenario}
        for (nome_rot, classe), dados in resultados.items():
            sr = pontuar_rotacao_cenario(
                dados["scores"], nome_rot, classe, dados["prioridade"])
            scores_finais[(nome_rot, classe)] = sr

        # Tabela de índices (3 rotações × 3 cenários) + mês de semeadura
        linhas_tabela = []
        for nome_rot in ROTACOES_DEF:
            defn = ROTACOES_DEF[nome_rot]
            culturas_rot = defn["culturas"]
            # Mês de semeadura + rótulo de safra 1/safra 2 (alternância)
            # ex.: "safra 1: Jan | safra 2: Fev" (revisão 2026-11-14).
            # Antes mostrávamos "Jan + Jan", o que não é rotação — agora
            # cada cultura é uma safra que se alterna entre anos.
            partes = []
            for idx_safra, cn in enumerate(culturas_rot):
                if cn in meses_selecionados and meses_selecionados[cn]:
                    rotulo = (f"safra {idx_safra + 1}" if len(culturas_rot) > 1
                              else "safra 1")
                    partes.append(f"{rotulo}: {nome_mes(meses_selecionados[cn])}")
            linha = {
                "rotação": nome_rot,
                "semeadura": " | ".join(partes) if partes else "—",
            }
            # Pior cenário (agora desempata por risco hídrico)
            scores_rot = {classe: scores_finais.get((nome_rot, classe))
                         for classe in ("El Niño", "La Niña", "neutro")}
            pior_classe, _ = pior_cenario(
                {k: v for k, v in scores_rot.items() if v is not None})
            # Para cada cenário: índice + risco hídrico (entre parênteses)
            for classe in ("El Niño", "La Niña", "neutro"):
                sr = scores_finais.get((nome_rot, classe))
                if sr and sr.indice is not None:
                    risco_str = ""
                    if sr.risco_hidrico_pct is not None:
                        risco_str = f" (r:{sr.risco_hidrico_pct:.0f}%)"
                    marca_pior = " ▼" if classe == pior_classe else ""
                    linha[classe] = f"{sr.indice:.1f}{risco_str}{marca_pior}"
                else:
                    linha[classe] = "—"
            linha["pior cenário"] = pior_classe or "—"
            # Janela pós-colheita (se a rotação tem cultura de cobertura)
            jpc = janelas_pos_colheita.get(nome_rot)
            if jpc is not None:
                if jpc.tem_janela_pos_colheita:
                    linha["cobertura pós-colheita"] = (
                        f"✓ janela em {', '.join(jpc.meses_disponiveis)}")
                else:
                    linha["cobertura pós-colheita"] = (
                        f"✗ sem janela ({nome_mes(jpc.mes_colheita_safra1)})"
                        if jpc.mes_colheita_safra1 else "✗ sem janela")
            else:
                linha["cobertura pós-colheita"] = "—"
            linhas_tabela.append(linha)

        df_comp = pd.DataFrame(linhas_tabela)
        st.dataframe(df_comp, use_container_width=True, hide_index=True)
        st.caption(
            "Cada rotação é uma **alternância entre safras** (safra 1 / "
            "safra 2), não culturas semeadas no mesmo mês. Os valores são "
            "índice (0..100) + **risco hídrico** (r:% de anos com chuva do "
            "ciclo abaixo da demanda da cultura). O ▼ marca o pior cenário "
            "(desempatado pelo risco hídrico quando o índice empata). "
            "'cobertura pós-colheita' indica se a cultura de cobertura "
            "tem janela logo após a colheita da safra 1."
        )

        # Gráfico de barras: índice por rotação x cenário (+ risco hídrico hover)
        df_plot = []
        for (nome_rot, classe), sr in scores_finais.items():
            if sr and sr.indice is not None:
                risco = (f"{sr.risco_hidrico_pct:.0f}%"
                         if sr.risco_hidrico_pct is not None else "—")
                df_plot.append({
                    "rotação": nome_rot, "cenário": classe,
                    "índice": sr.indice,
                    "risco_hídrico": risco,
                    "descrição": ROTACOES_DEF[nome_rot]["descricao"],
                })
        if df_plot:
            df_plot = pd.DataFrame(df_plot)
            fig = px.bar(
                df_plot, x="rotação", y="índice", color="cenário",
                barmode="group",
                color_discrete_map={
                    "El Niño": "#d62728", "La Niña": "#1f77b4",
                    "neutro": "#bdbdbd"},
                title="Índice de resiliência por rotação × cenário ENSO",
                labels={"índice": "Índice (0..100)"},
                hover_data=["descrição", "risco_hídrico"],
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Passe o mouse sobre as barras para ver o risco hídrico "
                "(% de anos com chuva do ciclo abaixo da demanda). "
                "Quando o índice satura em 100, o risco hídrico é o que "
                "discrimina os cenários."
            )

        # Detalhe por rotação
        with st.expander("Ver detalhe por rotação"):
            for nome_rot, defn in ROTACOES_DEF.items():
                culturas_rot = defn["culturas"]
                st.markdown(f"**{nome_rot}** — "
                            f"{' + '.join(defn['rotulos'])} "
                            f"(prioridade: "
                            f"{prioridade_sel if nome_rot == 'atual' else defn['prioridade']})")
                st.caption(defn["descricao"])
                if len(culturas_rot) > 1:
                    st.caption(
                        "🔄 **Alternância entre safras**: safra 1 e safra 2 "
                        "são semeadas em meses diferentes e se alternam "
                        "entre anos (não no mesmo mês)."
                    )
                for classe in ("El Niño", "La Niña", "neutro"):
                    sr = scores_finais.get((nome_rot, classe))
                    if not sr:
                        continue
                    risco_rot = (f"{sr.risco_hidrico_pct:.0f}%"
                                 if sr.risco_hidrico_pct is not None else "—")
                    if sr.indice is not None:
                        st.write(
                            f"  - {classe}: índice **{sr.indice:.1f}** "
                            f"(risco hídrico médio: {risco_rot}, "
                            f"{len(sr.scores)} culturas pontuadas)")
                    else:
                        st.write(f"  - {classe}: sem índice")
                    for idx_safra, sc in enumerate(sr.scores):
                        ag = f"{sc.score_agua:.0f}" if sc.score_agua is not None else "—"
                        ms = (nome_mes(sc.mes_semeadura)
                              if sc.mes_semeadura else "—")
                        marca_jan = ("✓ janela" if sc.tem_janela_valida
                                     else "✗ sem janela")
                        sc_str = (f"{sc.score_cultura:.0f}"
                                  if sc.score_cultura is not None else "0")
                        risco_c = (f"{sc.risco_hidrico_pct:.0f}%"
                                   if sc.risco_hidrico_pct is not None
                                   else "—")
                        rotulo_safra = (f"safra {idx_safra + 1}"
                                        if len(culturas_rot) > 1
                                        else "safra 1")
                        st.write(
                            f"      · **{rotulo_safra}** {sc.cultura}: "
                            f"semeio em **{ms}** ({marca_jan}), "
                            f"score_agua={ag}, "
                            f"risco_hídrico={risco_c}, "
                            f"score={sc_str}, "
                            f"anos={sc.anos_usados}"
                            + (" [agua estimada]" if sc.agua_estimada else "")
                            + (f", lacunas={sc.lacunas}" if sc.lacunas else ""))
                st.write("")

        # --- Semáforo de confiança ---
        st.subheader("🚦 Semáforo de confiança")
        st.caption(
            "Pontos somados (briefing 6.5): +2 amostra ENSO >=10 anos, "
            "+1 5-9 anos, +0 <5; +1 série >=10 anos; +1 sem lacuna "
            "essencial; +1 dados do solo (Etapa 7); +1 NDVI/SMAP (Fase 2); "
            "-1 parâmetro estimado pela equipe; -1 local sem calibração; "
            "-1 sem janela válida (revisão 2026-11-14). "
            "Verde >=5, amarelo 3-4, vermelho <=2."
        )
        # Calcula o semáforo para o cenário "pior" de cada rotação
        semaforos = {}
        for nome_rot in ROTACOES_DEF:
            # Pega o pior cenário desta rotação
            scores_rot = {classe: scores_finais.get((nome_rot, classe))
                         for classe in ("El Niño", "La Niña", "neutro")}
            pior_classe, _ = pior_cenario(
                {k: v for k, v in scores_rot.items() if v is not None})
            if pior_classe is None:
                pior_classe = "El Niño"
            # Lacunas essenciais: acha as culturas da rotação e pega lacunas
            culturas_rot = [banco[n] for n in ROTACOES_DEF[nome_rot]["culturas"]
                            if n in banco]
            lacunas_ess = []
            for cult in culturas_rot:
                lacunas_ess.extend(cult.lacunas)
            lacunas_ess = list(dict.fromkeys(lacunas_ess))  # dedup
            # Usa água estimada se alguma cultura da rotação usa
            usa_est = any(c.usa_agua_estimada for c in culturas_rot)
            # Sem janela válida: alguma cultura da rotação no pior cenário
            sr_pior = scores_finais.get((nome_rot, pior_classe))
            tem_jv = True
            if sr_pior:
                # Se ALGUMA cultura está sem janela, desconta.
                tem_jv = all(sc.tem_janela_valida for sc in sr_pior.scores)
            s = calcular_semaforo(
                n_anos_total=len(completos_aa),
                n_anos_por_classe=contagem_enso_local,
                lacunas_essenciais=lacunas_ess,
                usa_agua_estimada=usa_est,
                local_calibrado=local_calibrado,
                tem_janela_valida=tem_jv,
                classe_avaliada=pior_classe,
            )
            semaforos[nome_rot] = (s, pior_classe)

        # Cards do semáforo (3 rotações) com mês de semeadura
        cs1, cs2, cs3 = st.columns(3)
        for col, nome_rot in zip([cs1, cs2, cs3], ROTACOES_DEF):
            s, pior_cl = semaforos[nome_rot]
            defn = ROTACOES_DEF[nome_rot]
            meses_rot = []
            for cn in defn["culturas"]:
                if cn in meses_selecionados and meses_selecionados[cn]:
                    meses_rot.append(nome_mes(meses_selecionados[cn]))
            sem_label = " + ".join(meses_rot) if meses_rot else "—"
            col.metric(
                f"Rotação {nome_rot} (semeio: {sem_label})",
                f"{emoji_cor(s.cor)} {s.cor}",
                f"{s.pontos} pts (pior: {pior_cl})",
            )
        st.caption(
            "Semáforo calculado para o **pior cenário** de cada rotação "
            "(menor índice). Locais fora de `config.LOCAIS_VALIDADOS` "
            "descontam 1 ponto; culturas semeadas fora de mês-janela "
            "descontam 1 ponto (revisão 2026-11-14)."
        )

        # Detalhe do semáforo da rotação "atual"
        with st.expander("Ver evidências e lacunas (rotação atual)"):
            s_atual, _ = semaforos["atual"]
            st.write(f"**Pontos: {s_atual.pontos} -> "
                     f"{emoji_cor(s_atual.cor)} {s_atual.cor}**")
            st.markdown("**Evidências (somaram pontos):**")
            for e in s_atual.evidencias:
                st.write(f"- ✅ {e}")
            st.markdown("**Lacunas (descontaram ou não somaram):**")
            for l in s_atual.lacunas:
                st.write(f"- ⚠️ {l}")

st.markdown("---")

# --- Etapa 7: Calendário do agricultor + Dados de solo + Alerta simulado ----
# Esta seção reúne as 3 entradas da Etapa 7:
#   (a) Calendário: meses em que o campo está livre (já existia como seletor
#       dentro do bloco Janelas; aqui é a entrada canônica que o usuário
#       vê como passo do fluxo de 4 passos do briefing).
#   (b) Dados de solo: o usuário informa textura, profundidade, MO, pH.
#       Se informar, sobe 1 ponto no semáforo (briefing 6.5).
#   (c) Alerta simulado: dada uma data e cultura, diz se está na hora de
#       plantar (janela + chuva 7d + umidade do solo).

st.subheader("🚜 Passo final: calendário, solo e alerta de plantio")
st.caption(
    "Etapa 7 (briefing 6.5, 6.6, 6.8). O agricultor informa (a) os meses "
    "em que o campo está livre, (b) os dados do próprio solo, e (c) "
    "recebe o alerta de plantio para uma data e cultura. Os dados de "
    "solo somam +1 ponto no semáforo."
)

# (a) Calendário do agricultor — meses livres (entrada canônica da Etapa 7)
st.markdown("#### (a) Calendário do agricultor — meses em que o campo está livre")
meses_opcoes_et7 = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                    "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
meses_idx_et7 = list(range(1, 13))
meses_livres_et7_nomes = st.multiselect(
    "Selecione os meses em que o campo está livre",
    options=meses_opcoes_et7,
    default=meses_opcoes_et7,   # padrão: todos
    key="meses_livres_et7",
    help="Meses em que o campo está disponível para semeadura. "
         "Meses não selecionados ficam de fora das janelas (mesmo se a "
         "chuva for suficiente).",
)
meses_livres_et7 = [meses_idx_et7[meses_opcoes_et7.index(m)]
                    for m in meses_livres_et7_nomes] or None

# (b) Dados de solo (Etapa 7, briefing 6.5)
st.markdown("#### (b) Dados do solo (opcional, +1 no semáforo)")
from core.solo import criar_dados_solo

with st.expander("Informar dados do meu solo (opcional)"):
    st.caption(
        "A NASA POWER dá o clima, não o solo. Os parâmetros de culturas "
        "do CSV são calibrados para o caso de validação (Piauí). Se você "
        "informar dados do seu solo, a confiança sobe 1 ponto no "
        "semáforo (briefing 6.5). Não calculamos nada com esses dados "
        "ainda — só registramos que você tem dados locais."
    )
    st.caption(
        "⚠️ Para contar, informe **pelo menos 2 campos** entre "
        "textura, profundidade, matéria orgânica, pH e umidade inicial "
        "(revisão 2026-11-14). Observações em texto livre NÃO contam — "
        "uma nota solta não é 'dado de solo'."
    )
    cs_t, cs_p, cs_mo, cs_ph = st.columns(4)
    textura_sel = cs_t.selectbox(
        "Textura", options=["(não informado)", "arenoza", "media", "argilosa"],
        key="solo_textura",
    )
    prof_sel = cs_p.number_input(
        "Profundidade da camada arável (cm)", min_value=0.0, value=0.0,
        step=5.0, key="solo_prof",
        help="Deixe 0 para não informar.",
    )
    mo_sel = cs_mo.number_input(
        "Matéria orgânica (%)", min_value=0.0, value=0.0, step=0.5,
        key="solo_mo",
    )
    ph_sel = cs_ph.number_input(
        "pH", min_value=0.0, max_value=14.0, value=0.0, step=0.5,
        key="solo_ph",
    )
    umid_sel = st.slider(
        "Umidade inicial do solo (fração 0..1)", min_value=0.0, max_value=1.0,
        value=0.0, step=0.05, key="solo_umid",
        help="Estimativa da umidade atual do solo. 0 = seco, 1 = saturado.",
    )
    obs_sel = st.text_input(
        "Observações (texto livre — NÃO conta para o +1 do semáforo)",
        key="solo_obs",
        placeholder="Ex.: solo vermelho, bem drenado, pedregoso.",
    )

    # Monta DadosSolo (valores 0 viram None).
    dados_solo = criar_dados_solo(
        textura=(None if textura_sel == "(não informado)" else textura_sel),
        profundidade_cm=(None if prof_sel <= 0 else prof_sel),
        materia_organica_pct=(None if mo_sel <= 0 else mo_sel),
        ph=(None if ph_sel <= 0 else ph_sel),
        umidade_inicial=(None if umid_sel <= 0 else umid_sel),
        observacoes=(None if not obs_sel.strip() else obs_sel.strip()),
    )
    # Conta quantos campos estruturados estão preenchidos (para feedback).
    campos_preenchidos = sum(1 for v in (
        dados_solo.textura, dados_solo.profundidade_cm,
        dados_solo.materia_organica_pct, dados_solo.ph,
        dados_solo.umidade_inicial) if v is not None and v != "")
    if dados_solo.informado:
        st.success(
            f"✅ Dados de solo informados ({campos_preenchidos}/5 campos "
            f"estruturados) — o semáforo de confiança sobe 1 ponto."
        )
        st.caption(
            f"Textura: {dados_solo.textura or '—'} | "
            f"Profundidade: {dados_solo.profundidade_cm or '—'} cm | "
            f"MO: {dados_solo.materia_organica_pct or '—'}% | "
            f"pH: {dados_solo.ph or '—'} | "
            f"Umidade: {dados_solo.umidade_inicial or '—'}"
        )
    elif campos_preenchidos == 1:
        st.warning(
            f"Você preencheu 1 campo estruturado. Informe **pelo menos "
            f"2** para o semáforo somar +1 ponto (revisão 2026-11-14)."
        )
    else:
        st.info(
            "Nenhum dado de solo informado. O semáforo permanece sem o "
            "+1 ponto de solo (briefing 6.5)."
        )

# (c) Alerta simulado (Etapa 7, briefing 6.8)
st.markdown("#### (c) Alerta simulado de plantio")
from core.alerta import calcular_alerta as _calc_alerta

# Rótulo: a série climática é HISTÓRICA (NASA POWER 1991-2026), não uma
# previsão. O alerta é uma SIMULAÇÃO que usa os dados históricos até a
# última data disponível (revisão 2026-11-14).
ultima_data = (df_clima.index.max() if not df_clima.empty else None)
if ultima_data is not None:
    st.caption(
        f"ℹ️ **Simulação com dados históricos até "
        f"{pd.Timestamp(ultima_data).strftime('%d/%m/%Y')}** (NASA POWER). "
        f"Não é previsão: a chuva e a umidade abaixo são do ano "
        f"correspondente na série histórica, não do clima em tempo real."
    )

if df_clima.empty or not banco:
    st.warning("Sem dados climáticos ou culturas — o alerta não pode ser "
               "calculado.")
else:
    col_al1, col_al2 = st.columns(2)
    cultura_alerta_nome = col_al1.selectbox(
        "Cultura para o alerta",
        options=list(banco.keys()),
        index=(0 if "milho" not in banco
               else list(banco.keys()).index("milho")),
        key="cultura_alerta",
    )
    data_alerta = col_al2.date_input(
        "Data da simulação",
        value=pd.Timestamp.now().date(),
        key="data_alerta",
    )
    col_l1, col_l2 = st.columns(2)
    usar_limiares = col_l1.checkbox(
        "Definir limiares de chuva 7d e umidade manualmente",
        value=False, key="usar_limiares",
        help="Os limiares do config estão None (regra 'não invente dado'). "
             "Sem limiares calibrados, o alerta só pode dizer 'JANELA "
             "ABERTA (sinais não calibrados)' em amarelo — não 'PLANTE "
             "AGORA'. Marque para calibrar manualmente.",
    )
    if usar_limiares:
        limiar_chuva = col_l1.number_input(
            "Limiar de chuva 7d (mm)", min_value=0.0, value=30.0, step=5.0,
            key="lim_chuva",
        )
        limiar_umid = col_l2.number_input(
            "Limiar de umidade do solo (0..1)", min_value=0.0, max_value=1.0,
            value=0.3, step=0.05, key="lim_umid",
        )
    else:
        limiar_chuva = config.LIMIAR_CHUVA_7D_MM
        limiar_umid = config.LIMIAR_UMIDADE_SOLO

    cult_alerta = banco[cultura_alerta_nome]
    r_jan_alerta = janelas.calcular_janelas(
        df_clima, cult_alerta,
        anos_agricolas_completos=completos_aa,
        meses_livres=meses_livres_et7,
    )
    a = _calc_alerta(
        df_clima, cult_alerta, r_jan_alerta,
        pd.Timestamp(data_alerta),
        limiar_chuva_7d_mm=limiar_chuva,
        limiar_umidade=limiar_umid,
    )
    emoji_a = {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}[a.cor]
    msg_header = (f"{emoji_a} **{a.status}** — {a.cultura} em "
                  f"{pd.Timestamp(data_alerta).strftime('%d/%m/%Y')}")
    if a.status == "PLANTE AGORA":
        st.success(msg_header)
    elif a.status == "NÃO PLANTE":
        st.error(msg_header)
    else:
        # "AGUARDE" e "JANELA ABERTA (sinais não calibrados)" -> amarelo
        st.warning(msg_header)

    sc_a1, sc_a2, sc_a3 = st.columns(3)
    sc_a1.metric(
        "Na janela?",
        "✓ sim" if a.na_janela else "✗ não",
        help=f"O mês {pd.Timestamp(data_alerta).month} é mês-janela "
             f"da cultura?",
    )
    sc_a2.metric(
        "Chuva 7d (mm, histórico)",
        f"{a.chuva_7d_mm:.1f}" if a.chuva_7d_mm is not None else "—",
        help=f"Soma dos 7 dias anteriores na série histórica. "
             f"Limiar calibrado: "
             f"{a.limiares_usados.get('limiar_chuva_7d_mm') or 'None (não calibrado)'}",
    )
    sc_a3.metric(
        "Umidade solo (estimada, GWETROOT)",
        f"{a.umidade_solo:.2f}" if a.umidade_solo is not None else "—",
        help="Umidade estimada pelo modelo NASA POWER (GWETROOT, fração "
             "0..1) — NÃO é medição de campo. Limiar calibrado: "
             f"{a.limiares_usados.get('limiar_umidade_solo') or 'None (não calibrado)'}",
    )

    with st.expander("Ver motivos e lacunas do alerta"):
        st.markdown("**Motivos:**")
        for m in a.motivos:
            st.write(f"- {m}")
        if a.lacunas:
            st.markdown("**Lacunas:**")
            for l in a.lacunas:
                st.write(f"- ⚠️ {l}")
        st.caption(
            "Sem os limiares de chuva/umidade (config = None, regra "
            "'não invente dado'), o alerta só usa o critério de janela. "
            "Para um alerta completo, calibre os limiares com agrônomo "
            "local e defina-os em `config.LIMIAR_CHUVA_7D_MM` e "
            "`config.LIMIAR_UMIDADE_SOLO`."
        )

    if dados_solo.informado:
        st.info(
            "ℹ️ Com os dados de solo informados, o semáforo de confiança "
            "lá em cima sobe 1 ponto (+1, briefing 6.5)."
        )

st.markdown("---")
# O texto vem de config.RODAPE para não ficar duplicado no código.
# position:fixed mantém o rodapé sempre visível no rodapé da janela do navegador.
# Em versões recentes do Streamlit (1.30+), o conteúdo principal fica dentro
# de div[data-testid="stMain"], por isso aplicamos o padding-bottom lá.
st.markdown(
    f"""
    <style>
    .rodape-fixo {{
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #f0f2f6;
        color: #31333f;
        text-align: center;
        padding: 8px 12px;
        font-size: 13px;
        border-top: 1px solid #d4d4d8;
        z-index: 999;
    }}
    /* Evita que o conteúdo fique escondido atrás do rodapé.
       Em Streamlit 1.30+ o main tem data-testid="stMain".
       Mantemos o seletor antigo (.main .block-container) por compatibilidade. */
    div[data-testid="stMain"] .block-container,
    .main .block-container {{
        padding-bottom: 60px;
    }}
    </style>
    <div class="rodape-fixo">
        {config.RODAPE}
    </div>
    """,
    unsafe_allow_html=True,
)
