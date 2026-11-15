# Rotação Inteligente

> **Rotação Inteligente 2.0:** esta pasta é o app Streamlit original (NASA1), preservado. A nova versão (API FastAPI + interface React) está em `../backend` e `../frontend`; veja o `README.md` na raiz.

Ferramenta **global** de apoio à decisão para rotação de culturas,
usando observações da Terra da NASA. Projeto do NASA Space Apps
Challenge 2026 ("Field Shift: Adapting Farms with NASA Data").

> Ferramenta de apoio. Não substitui o julgamento do agricultor nem a
> orientação de especialistas locais.

## Escopo global

O motor (NASA POWER, ENSO, janelas, culturas, planejador) recebe
latitude/longitude de **qualquer ponto do globo** (qualquer hemisfério).
A interface permite escolher:

- **3 municípios validados** no semiárido do Piauí (Teresina, Picos,
  São Raimundo Nonato) — cache pré-baixado, funciona offline; parâmetros
  de culturas calibrados localmente.
- **Outro local** com latitude/longitude (qualquer hemisfério) — baixa
  do NASA POWER sob demanda, exige internet; o semáforo desconta 1 ponto
  ("parâmetros de culturas sem calibração local para esta região").
- **Upload de culturas.csv** — o usuário pode carregar o próprio banco
  (mesmo formato e regras de lacuna) para substituir o padrão.

**Caso de validação:** semiárido do Piauí (Brasil). As suposições da
equipe (limiares de chuva, estabelecimento, pesos de rotação) são
documentadas em `config.py` e devem ser calibradas com agrônomo local
para outras regiões.

## Como rodar

```bash
cd rotacao_inteligente
pip install -r requirements.txt
streamlit run app.py
```

A página abre no navegador com:
- o **rodapé fixo** (Etapa 1);
- o bloco de **dados climáticos (NASA POWER)** com gráfico de chuva mensal
  considerando apenas anos agrícolas completos (Etapa 2);
- o bloco **Cenários ENSO** com a classificação El Niño / La Niña / neutro
  (Etapa 3);
- o bloco **Planejador de sementes** onde você escolhe a cultura, digita
  os kg e vê a área em m² e a colheita estimada (Etapa 4).

## Como usar em qualquer local (revisão 2026-11-14)

O app roda em **qualquer ponto do globo** — não há hardcode geográfico.
Basta informar latitude/longitude. Há 3 caminhos:

1. **Municípios validados** (Teresina, Picos, São Raimundo Nonato): têm
   cache pré-baixado (abrem offline) e culturas calibradas — sem
   desconto no semáforo.
2. **Locais de demonstração** (Nairóbi, Iowa, Punjab): têm cache (abrem
   offline) mas **sem calibração local** — descontam 1 ponto no
   semáforo. Servem para mostrar o app em hemisférios e climas
   diferentes.
3. **Outro local (lat/lon)**: digite latitude (-90 a 90) e longitude
   (-180 a 180). Se não houver cache, o app baixa da NASA POWER sob
   demanda (**exige internet**, alguns minutos na 1ª vez).

### Upload do seu próprio `culturas.csv`

Os parâmetros de culturas em `data/culturas.csv` vêm calibrados para o
caso de validação (semiárido do Piauí). Para usar o app em outra
região com parâmetros locais, carregue seu próprio CSV no bloco
"📁 Carregar seu próprio culturas.csv" (expander no topo do app). O
CSV deve ter as mesmas colunas do `data/culturas.csv` (ver cabeçalho
do arquivo padrão). O app valida o upload e usa os parâmetros locais
enquanto a sessão durar (não sobrescreve o arquivo padrão).

### Limitações importantes (leia antes de interpretar os resultados)

- **Culturas calibradas só para o Nordeste do Brasil.** Os parâmetros
  de `data/culturas.csv` (ciclo, demanda hídrica, limite de calor,
  fixação de N, etc.) foram calibrados para o semiárido do Piauí. Em
  outras regiões, use o app como **exploração**, não como
  recomendação agronômica definitiva — ou carregue um CSV local com
  parâmetros calibrados para o seu bioma. Locais não calibrados
  descontam 1 ponto no Semáforo de Confiança.
- **Limiares do alerta não calibrados.** Os limiares de chuva 7d e
  umidade do solo (`config.LIMIAR_CHUVA_7D_MM` e
  `config.LIMIAR_UMIDADE_SOLO`) estão como `None` (regra "não invente
  dado"). Sem eles, o alerta só pode dizer **"JANELA ABERTA (sinais
  não calibrados)"** em amarelo — nunca "PLANTE AGORA" verde. Para ter
  "PLANTE AGORA", calibre os limiares manualmente no app (checkbox
  "Definir limiares...") ou edite o `config.py`.
- **Umidade do solo estimada, não medida.** A umidade vem do
  **GWETROOT** (Root Zone Soil Wetness) do modelo NASA POWER — uma
  **estimativa do modelo**, não uma medição de campo. A métrica no
  alerta é rotulada como "Umidade solo (estimada, GWETROOT)" para
  deixar isso claro. Para uma decisão real de plantio, confirme com
  uma medição de campo.
- **Simulação com dados históricos, não previsão.** O alerta usa os
  dados da NASA POWER até a última data disponível na série (1991-2026
  no cache). Não é previsão do tempo de hoje — é o que aconteceu na
  série histórica. O bloco é rotulado como "Simulação com dados
  históricos até \<última data\>".

## 🗺️ Mapa (revisão 2026-11-14)

O bloco "🗺️ Mapa" adiciona um mapa interativo (folium + streamlit-folium)
centrado no local selecionado, com três funcionalidades. **Nenhuma das
camadas do mapa muda as regras de cálculo** do app — satélite é visual,
risco é um modelo em grade.

### Marcadores e clique

- **Marcadores verdes**: 3 municípios validados (Teresina, Picos, São
  Raimundo Nonato) — com calibração local.
- **Marcadores laranja**: 3 locais de demonstração (Nairóbi, Iowa,
  Punjab) — cache, mas sem calibração local.
- **Marcador azul**: local atual.
- **Clique no mapa**: define um novo "Outro local" (lat/lon). O app
  mostra as coordenadas e, se o ponto não tem cache, avisa que exige
  internet. Copie as coordenadas para o seletor "Outro local (lat/lon)"
  acima para recarregar com o novo local.

### Camadas de satélite (NASA GIBS) — VISUAL

Três camadas WMTS (EPSG:3857, "best") da NASA GIBS, ligáveis com
checkbox e com seletor de data (YYYY-MM-DD). Os identificadores foram
**lidos do GetCapabilities** do GIBS em 2026-11-14 (não são nomes de
memória) e validados em runtime por `core/gibs.py`:

| Camada | ID GIBS | TileMatrixSet |
| --- | --- | --- |
| NDVI (MODIS Terra, 16 dias) | `MODIS_Terra_L3_NDVI_16Day` | `GoogleMapsCompatible_Level9` |
| Precipitação (IMERG, diário) | `IMERG_Precipitation_Rate` | `GoogleMapsCompatible_Level6` |
| Umidade do solo raiz (SMAP L4) | `SMAP_L4_Analyzed_Root_Zone_Soil_Moisture` | `GoogleMapsCompatible_Level6` |

Rótulo: **"observação de satélite (visual, não entra nos cálculos)"**.
Se os tiles falharem (sem internet), `camadas_disponiveis()` não
consegue validar via GetCapabilities e mostra um aviso, mas o mapa
segue funcionando com os marcadores e a grade de risco.

### Risco hídrico (modelo, grade Piauí ~1°)

Grade de pontos a cada ~1° sobre o Piauí (somente pontos dentro do
estado), baixando **somente PRECTOTCORR 1991-2026** de cada ponto e
salvando em `data/cache/grade_piaui/`. Para a cultura e o cenário ENSO
escolhidos, cada ponto é colorido pelo **% de anos da classe com
chuva do ciclo abaixo da água efetiva**, no mês de semeadura padrão.

- **Reutiliza** `core.resiliencia.risco_hidrico_por_classe` (Etapa 6) —
  mesma regra de cálculo, sem alteração. O limiar é
  `Cultura.agua_efetiva_mm_ciclo` (do CSV ou fallback 250 mm).
- **Rótulo**: "resolução da grade do NASA POWER, não é nível de campo".
- **Legenda**: 🔵 <25% (baixo) | ⚪ 25–50% | 🟠 50–75% | 🔴 ≥75% (alto).
  Cinza = sem anos da classe ENSO na série.
- **Primeira vez exige internet** (download dos pontos da grade);
  depois usa o cache local. O botão "📡 Baixar/recalcular grade" mostra
  o tempo e o nº de pontos baixados.
- **Se o download falhar**, o app mostra um erro e **não salva nada
  parcial** (`parar_em_erro=True` em `baixar_grade`).

### Filtro da grade (fronteira do Piauí)

A grade gera pontos candidatos no retângulo envoltório do estado e
filtra para manter só os que estão dentro do Piauí. Há dois modos,
rotulados no app:

- **Malha oficial (preferencial)**: se `data/piaui_uf.geojson` existe,
  `gerar_pontos_grade` faz **ponto-em-polígono** (ray casting, Python
  puro, sem shapely) e mantém só os pontos dentro da fronteira exata.
  Baixe a malha uma vez no seu computador com internet:

  ```bash
  python scripts/baixar_malha_piaui.py
  ```

  Isso salva `data/piaui_uf.geojson` (API de Malhas Digitais do IBGE,
  UF 22). Sem o arquivo, o app mostra um aviso no bloco de risco e
  cai no fallback.
- **Retângulo envoltório (fallback)**: sem a malha, a grade usa o
  retângulo `config.PIAUI_BBOX` (`lat -10.93 a -2.74`, `lon -45.99 a
  -40.37`). Menos preciso — pode incluir pontos fora da fronteira. Com
  passo de 1°, o retângulo gera **40 pontos**; com a malha oficial o
  número cai para os pontos efetivamente dentro do estado (~32). O
  número exato é mostrado no app.

### Limitações do mapa

- **Bbox do Piauí (fallback)**: sem a malha oficial, o filtro usa o
  retângulo `config.PIAUI_BBOX` (`lat -10.93 a -2.74`, `lon -45.99 a
  -40.37`). É um retângulo aproximado, não uma fronteira oficial
  verificada — pode incluir pontos fora do estado. Para filtro exato,
  rode `scripts/baixar_malha_piaui.py`. Com passo de 1°, o retângulo
  gera 40 pontos; a malha reduz para os ~32 dentro do estado.
- **Tiles GIBS são visuais**: NDVI/IMERG/SMAP não substituem medição de
  campo e não entram em nenhum cálculo do app.
- **Grade de risco é um modelo**: resolução ~1° do NASA POWER, não é
  nível de campo. Use para comparação regional, não para decisão de
  plantio em um talhão específico.

## Estrutura de pastas

```
rotacao_inteligente/
├── app.py                  # Streamlit: telas e fluxo
├── config.py               # limiares, pesos e caminhos (nada de número solto)
├── requirements.txt
├── README.md               # este arquivo
├── scripts/
│   └── baixar_malha_piaui.py  # baixa a malha oficial do Piauí (IBGE, rode 1x)
├── core/
│   ├── __init__.py
│   ├── nasa_power.py       # (Etapa 2) cache de 1991-2026 da NASA POWER
│   ├── enso.py             # (Etapa 3) classifica anos com a tabela ONI
│   ├── culturas.py         # (Etapa 4) lê culturas.csv e lista lacunas
│   ├── planejador.py       # (Etapa 4) calculadora kg de semente -> m²
│   ├── janelas.py          # (Etapa 5) linha do tempo das janelas
│   ├── resiliencia.py       # (Etapa 6) índice por rotação/cenário
│   ├── semaforo.py         # (Etapa 6) semáforo de confiança
│   ├── alerta.py           # (Etapa 7) alerta simulado de plantio
│   ├── solo.py             # (Etapa 7) dados de solo do usuário (+1 semáforo)
│   ├── gibs.py             # (Mapa) GetCapabilities + tile_url WMTS da NASA GIBS
│   └── grade_risco.py      # (Mapa) grade Piauí + risco reusando resiliencia
├── data/
│   ├── culturas.csv        # banco de culturas (fornecido, parcial)
│   ├── rotacoes.json       # 3 estratégias (sequências vazias por enquanto)
│   ├── oni.csv             # índice ONI v6 da NOAA (fornecido)
│   ├── produtividade.csv   # SÓ CABEÇALHO — baixar do IBGE (ver abaixo)
│   ├── piaui_uf.geojson    # OPCIONAL — malha do Piauí (rode scripts/baixar_malha_piaui.py)
│   └── cache/              # respostas da NASA POWER salvas para a demo offline
│       ├── .gitkeep
│       └── grade_piaui/    # cache da grade de risco do Piauí (1 arquivo/ponto)
└── tests/
    ├── __init__.py
    ├── conftest.py            # hooks do pytest (skip de testes online)
    ├── test_smoke.py          # config e caminhos básicos
    ├── test_nasa_power.py     # 9 testes da NASA POWER (cache, parsing, etc.)
    ├── test_enso.py           # 16 testes da classificação ENSO
    ├── test_culturas.py       # 17 testes do banco de culturas
    ├── test_planejador.py     # 15 testes da calculadora de sementes
    ├── test_janelas.py        # 31 testes das janelas de oportunidade
    ├── test_etapa6.py         # 48 testes de resiliência + semáforo + ano agrícola
    ├── test_etapa7.py         # 19 testes de alerta + dados de solo
    └── test_grade_risco.py    # 12 testes da grade de risco do Piauí (1 online)
```

## Período da série climática

A série da NASA POWER (comunidade AG) começa em **1981-01-01** (confirmado
por chamada real à API). Usamos **1991 a 2026** (36 anos civis, 35 anos
agrícolas completos nov-out):

- **1991** em vez de 1981: evita a década de 1980, com mais revisações no
  ERSST, e ainda capta o forte El Niño 1991-92.
- **2026** em vez de 2025: o ano agrícola 2025 = nov/2025 a out/2026. Se
  parássemos em 2025, esse ano ficaria sem o outono/inverno de 2026 (estação
  seca e parte da chuvosa), criando um ano agrícola incompleto.
- **Apenas anos agrícolas completos** entram nos cálculos de climatologia.
  Se algum ano agrícola ficar incompleto (período parcial), o app avisa na
  interface (regra do briefing).

Os arquivos de cache usam esses anos no nome (`power_*_1991_2026_*.json`),
então o nome fica estável e a demo offline funciona.

## Municípios e locais no cache

Pré-baixados para a demo offline (8 variáveis cada, 1991-2026):

**3 municípios validados (com calibração local — sem desconto no semáforo):**

- **Teresina-PI** (-5.09, -42.81) — padrão do app.
- **Picos-PI** (-7.07694, -41.46694) — sede municipal.
- **São Raimundo Nonato-PI** (-9.015, -42.69889) — sede municipal.

**3 locais de demonstração (cache, sem calibração local — descontam 1
ponto no semáforo, revisão 2026-11-14):**

- **Nairóbi** (-1.29, 36.82) — Quênia, clima equatorial de altitude.
- **Iowa** (41.6, -93.6) — EUA, clima temperado continental.
- **Punjab** (31.1, 75.3) — Índia, clima subtropical monçônico.

Os demos servem para mostrar que o app funciona em qualquer hemisfério
(Norte/Sul, Leste/Oeste) e em climas muito diferentes do semiárido
brasileiro — mas os parâmetros de culturas do `data/culturas.csv` **não
foram calibrados** para essas regiões, então o semáforo desconta 1 ponto
de confiança (a mesma regra de qualquer local não calibrado).

> **Observação sobre as coordenadas:** as coordenadas das sedes municipais
> são obtidas de fonte oficial (IBGE) sempre que possível. No caso de
> Picos-PI e São Raimundo Nonato-PI, a API do IBGE estava indisponível no
> momento da coleta (HTTP 000 após timeout); usamos a **Wikipédia** como
> referência secundária (a Wikipédia cita o IBGE nas infocaixas, e os
> artigos PT e EN concordam nas coordenadas de São Raimundo Nonato). Esta
> limitação está registrada no Semáforo de Confiança. Se amanhã a API do
> IBGE voltar, basta recolher as coordenadas oficiais e regravar o cache
> (a função `nasa_power.carregar_series(forcar_download=True)` baixa de
> novo).


## Banco de culturas — regra de exclusão de rotações

Uma cultura **só é excluída de rotações** se faltar `ciclo_dias` no
`data/culturas.csv` (regra revisada pelo usuário em 2026-11-14,
briefing 6.1). **Não há exclusão por nome.**

Se `agua_mm_ciclo` estiver vazio, a cultura **continua apta** e o
cálculo da janela usa `config.CHUVA_MINIMA_CICLO_MM` (= **250 mm**,
suposição da equipe: piso da faixa da Embrapa para o caupi) como
fallback. O resultado é marcado como **"parâmetro estimado pela
equipe"** e desconta 1 ponto no Semáforo de Confiança (briefing 6.5).

Com o `data/culturas.csv` atual (Etapa 4 ajustada), as **6 culturas**
estão aptas a rotações (todas têm `ciclo_dias`):

| Cultura | tipo | ciclo_dias | agua_mm_ciclo | água efetiva |
|---|---|---|---|---|
| feijao-caupi | comercial | 70 | 325 | 325 (CSV) |
| milho | comercial | 120 | 600 | 600 (CSV) |
| sorgo | comercial | 100 | 490 | 490 (CSV) |
| crotalaria-juncea | cobertura | 120 | — | 250 (estimada) |
| feijao-de-porco | cobertura | 90 | — | 250 (estimada) |
| guandu | cobertura | 90 | — | 250 (estimada) |

## Convenção de `ciclo_dias` para culturas de cobertura

Para culturas **comerciais** (milho, feijão, sorgo), `ciclo_dias` é o
número de dias da semeadura à **colheita** (ciclo completo).

Para culturas de **cobertura** (crotalária, feijão-de-porco, guandu),
`ciclo_dias` é o número de dias da semeadura até o **corte no pico de
floração** — momento em que a biomassa acumulada é máxima e a cultura
é rolada/incorporada ao solo para adubação verde. Não há colheita de
grãos. Esta convenção vem das fontes citadas no CSV:

- crotalária-juncea: Embrapa Agrobiologia e Embrapa Oeste ("ciclo até
  o corte"); Embrapa CT181 e CT108 (semente).
- feijao-de-porco: Cadernos de Agroecologia ABA (ciclo, fonte não
  oficial); Embrapa CT108 (semente).
- guandu: Embrapa Caprinos e Ovinos (ciclo, faixa 80-180 dias);
  Agrolink (semente, não oficial).

Por isso a janela de oportunidade de uma cobertura mede a chuva do
**ciclo até o corte** (não até a colheita).

## Dados que você (o usuário) precisa baixar à mão

### 1. `data/oni.csv` — Índice ONI (NOAA)

- **Fonte:** ONI v6 (ERSSTv6), NOAA/CPC.
  Link: https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/
- **Formato esperado:** duas colunas, separadas por vírgula:
  ```csv
  ano,djf_oni
  <valores reais da NOAA>
  ```
  Substitua `<valores reais da NOAA>` pelos números que você baixar. **Não
  invente valores** — cada linha deve vir da tabela oficial.
- **Convenção de ano agrícola** (definida com o usuário): o ano agrícola N
  corresponde a nov/N a out/N+1 e é classificado pelo trimestre DJF
  dez/N a fev/N+1. Na tabela ONI v6 da NOAA, esse é o **DJF rotulado como
  N+1** (a NOAA rotula DJF pelo ano em que o trimestre termina). Ou seja:
  a linha `ano=2024` do nosso `oni.csv` recebe o valor do **DJF 2025** da
  NOAA.
- **Na Etapa 3**, o `enso.py` só lê o CSV e classifica cada ano
  (>= +0,5 El Niño; <= -0,5 La Niña; neutro no meio). **Não reescreve
  nem recalcula a tabela** — o usuário entregou a coluna `djf_oni` já
  com o valor DJF de cada ano agrícola.
- **Limitações registradas:**
  - **Valores recentes podem ser revisados:** o ONI v6 usa o ERSSTv6
    (reanálise de TSM), que a NOAA atualiza periodicamente; valores dos
    últimos meses podem mudar entre versões.
  - **RONI no monitoramento oficial:** a NOAA usa o RONI (Relative ONI)
    no monitoramento oficial de ENSO em tempo real; o ONI clássico
    usado aqui é o histórico.
- Sem este arquivo, a Etapa 3 (`enso.py`) não funciona.

### 2. `data/produtividade.csv` — Produtividade municipal (IBGE/SIDRA)

- **Onde baixar:** IBGE/SIDRA. A **tabela 1612** (Produção Agrícola
  Municipal — PAM) cobre geralmente **até 2017**. Para 2018 em diante, use
  também a **tabela 5457** (PAM — Produção Agrícola Municipal, série
  contínua a partir de 2018). Filtrar pelos municípios do Piauí e pelas
  culturas relevantes (milho, feijão etc.).
- **Atenção:** o IBGE **não separa feijão-caupi de "feijão (em grão)"**.
  Se você precisar de feijão-caupi específico, terá que buscar outra fonte
  (Embrapa/Conab) ou registrar essa limitação no Semáforo de Confiança.
- **Formato esperado:**
  ```csv
  municipio,ano,cultura,rendimento_kg_ha,fonte
  <valores reais do IBGE>
  ```
- Sem este arquivo, a Etapa 7 (comparativo histórico) exibirá o aviso
  "dados do IBGE ainda não carregados".

## Como rodar os testes

```bash
cd rotacao_inteligente
pytest -v
```

Total após o bloco Mapa: **192 passed, 2 skipped** (os 2 `skipped` são
testes online — da NASA POWER e da grade do Piauí — ativam com
`pytest --run-online`). O teste online da grade baixa a grade real e
reporta no output o tempo e o nº de pontos.

Para rodar só os testes da grade de risco:
```bash
pytest -v tests/test_grade_risco.py
```

## O que já está pronto (até a Etapa 7 revisada)

- **Etapa 1** — esqueleto + rodapé.
- **Etapa 2** — `nasa_power.py`: download + cache de 8 variáveis diárias
  da NASA POWER para 1991-2026, com pausa apenas em chamadas de rede,
  `st.cache_data` no app e tempo offline ~0,5 s.
- **Etapa 3** — `enso.py`: classificação El Niño/La Niña/neutro a partir
  do `data/oni.csv` fornecido, com detecção de anos no limite (±0,5).
- **Etapa 4** — `culturas.py` + `planejador.py`: leitura do
  `data/culturas.csv` com lacunas por cultura. Regra de rotação
  revisada (2026-11-14): uma cultura é apta se tiver `ciclo_dias`;
  `agua_mm_ciclo` vazio usa `config.CHUVA_MINIMA_CICLO_MM` (= 250 mm,
  suposição da equipe) e marca "parâmetro estimado pela equipe".
  `ciclo_dias` em cobertura = dias até o corte no pico de floração.
  Calculadora `kg → m²` e colheita estimada (regional > potencial >
  aviso). Bloco na interface com seletor de cultura e entrada de kg.
- **Etapa 5** — `janelas.py`: linha do tempo das janelas de
  oportunidade. Para cada mês de semeadura (jan-dez), dois critérios:
  (1) chuva mediana do ciclo >= `agua_efetiva × FATOR_MINIMO_CHUVA`
  (0,6); (2) chuva mediana dos primeiros
  `JANELA_ESTABELECIMENTO_DIAS` (30) dias >=
  `CHUVA_MINIMA_ESTABELECIMENTO_MM` (20) — suposição da equipe, validar
  com agrônomo. O mês só é janela se passar nos dois critérios. Trata
  lacunas conforme briefing 6.1. Bloco na interface com gráfico de
  barras (chuva do ciclo + chuva de estabelecimento), seletor de meses
  livres (calendário do agricultor) e tabela detalhada.
- **Etapa 6** — `resiliencia.py` + `semaforo.py` + ajustes em `enso.py`:
  - `enso.ano_agricola_da_semeadura`: semeadura em jan-out do ano civil
    Y -> ano agrícola Y-1; nov-dez de Y -> AA Y. Liga cada semeadura à
    classe ENSO correta (AA N usa DJF de N+1).
  - `resiliencia.py`: score_agua = min(100, chuva/agua×100); penalidade
    de calor (0 se tmax_limite_c vazio, registra lacuna); índice de
    resiliência = média ponderada dos scores das culturas (pesos por
    prioridade agua/solo/renda em `config.PESOS_PRIORIDADE`), com
    renormalização quando um critério (fixa_n/protecao/mercado) está
    vazio. Cálculo por cenário ENSO.
  - `semaforo.py`: verde (>=5) / amarelo (3-4) / vermelho (<=2). Pontos:
    +2 amostra ENSO >=10, +1 5-9, +0 <5; +1 série >=10; +1 sem lacuna
    essencial; +1 dados solo (Etapa 7); +1 NDVI/SMAP (Fase 2); -1
    parâmetro estimado; -1 local não calibrado; -1 sem janela válida.
  - Bloco na interface: comparativo das 3 rotações (atual = milho +
    pousio; solo = milho + crotalária; agua = sorgo + caupi) × 3 cenários
    ENSO, com índice de resiliência, pior cenário, e semáforo com
    evidências e lacunas.

- **Etapa 6 revisada** (2026-11-14): método corrigido. Antes, todas as
  culturas eram "semeadas" em 1/nov — isso avaliava o caupi fora da sua
  janela (jan-abr) e fazia o "pior cenário = neutro" ser artefato da
  data fixa. Agora:
  - `resiliencia.melhor_mes_semeadura`: cada cultura é avaliada no seu
    mês de semeadura. Padrão: o mês-janela (Etapa 5: ciclo +
    estabelecimento) com maior chuva mediana do ciclo. Se não houver
    mês-janela, usa o mês de maior chuva e marca "sem janela válida"
    (-1 no semáforo). O usuário pode trocar o mês de cada cultura no
    app (seletor com o padrão pré-selecionado).
  - `chuva_ciclo_por_classe` usa `mes_semeadura` + `ano_agricola_da_semeadura`
    de fato (a docstring dizia que usava, mas o código não chamava).
  - Testes: `test_semeadura_dez_2015_aa_2015` (dez/2015 -> AA 2015, além
    do jan/2016 -> AA 2015 -> El Niño).

- **Etapa 7** — `alerta.py` + `solo.py` + blocos na interface:
  - `alerta.py`: alerta simulado de plantio. Combina 3 sinais: (1) a data
    está num mês-janela? (2) chuva dos últimos 7 dias >= limiar? (3)
    umidade do solo (GWETROOT) >= limiar? Status: PLANTE AGORA (verde) /
    AGUARDE (amarelo) / NÃO PLANTE (vermelho) / JANELA ABERTA (sinais
    não calibrados, amarelo). Sem os limiares (config None, regra "não
    invente dado"), o status NÃO é "PLANTE AGORA" — é "JANELA ABERTA
    (sinais não calibrados)" em amarelo (revisão 2026-11-14).
  - `solo.py`: entrada de dados de solo do usuário (textura, profundidade,
    MO, pH, umidade inicial, observações). `informado` exige >= 2 campos
    estruturados (observações em texto livre NÃO contam, revisão
    2026-11-14). Se informado, sobe +1 no semáforo (briefing 6.5).
  - Calendário do agricultor: seletor de meses livres (entrada canônica
    da Etapa 7; já existia dentro do bloco Janelas).
  - Bloco na interface "🚜 Passo final: calendário, solo e alerta":
    (a) calendário, (b) dados de solo (com aviso "pelo menos 2 campos"),
    (c) alerta simulado rotulado como "simulação com dados históricos
    até <última data>" e umidade "estimada pelo modelo NASA POWER
    (GWETROOT), não é medição".

- **Etapa 7 revisada** (2026-11-14, 4 correções):
  1. **Rotação como alternância safra 1 / safra 2**: antes as 2 culturas
     eram semeadas no mesmo mês ("Jan + Jan"), o que não é rotação. Agora
     cada cultura é rotulada "safra 1" / "safra 2" e se alternam entre
     anos. Para culturas de cobertura, `janela_pos_colheita` confere se
     há janela válida no mês de colheita da safra 1 (semeadura +
     ciclo_dias) ou nos 2 meses seguintes, com aviso "sem janela" quando
     não há.
  2. **Risco hídrico + desempate do pior cenário**: `risco_hidrico_por_classe`
     = % dos anos da classe com chuva do ciclo ABAIXO de agua_efetiva_mm.
     Quando o índice satura em 100 (todos os cenários iguais), o risco
     discrimina. `pior_cenario` agora desempata pelo MAIOR risco hídrico
     (em vez do desempate arbitrário por El Niño). Mostrado na tabela
     ("r:X%") e no hover do gráfico. Nos 3 municípios do Piauí, **Picos**
     é onde os cenários mais se separam (amplitude índice 8.75 + risco
     16.5% em média).
  3. **`solo.DadosSolo.informado` exige >= 2 campos estruturados** e não
     conta observações (texto livre). Antes bastava 1 campo (incluindo
     só observações), o que era fraco.
  4. **`alerta.py` com limiar None**: status não é "PLANTE AGORA" (verde),
     é "JANELA ABERTA (sinais não calibrados)" (amarelo). Bloco rotulado
     como "simulação com dados históricos até <última data>" e umidade
     como "estimada pelo modelo NASA POWER (GWETROOT), não é medição".

## Camada global (2026-11-14)

O desafio é "agricultores em todo o mundo". O motor já recebia lat/lon;
esta camada removeu o hardcode geográfico da interface:

- **Seletor de local**: 3 municípios validados (Teresina, Picos, São
  Raimundo Nonato) com cache pré-baixado + "outro local" com
  latitude/longitude de qualquer hemisfério (baixa da NASA POWER sob
  demanda, exige internet).
- **Upload de culturas.csv**: o usuário pode carregar o próprio banco
  (mesmo formato e regras de lacuna) para substituir o padrão.
- **`config.LOCAIS_VALIDADOS`**: lista dos 3 locais calibrados. Locais
  fora dela mostram "parâmetros de culturas sem calibração local para
  esta região" e descontam 1 ponto no semáforo.
- **Textos**: subtítulo e README passaram a "ferramenta global de apoio
  à decisão, com caso de validação no semiárido do Piauí".
- **Teste de fumaça online** (Nairobi/Iowa/Punjab): pipeline completo
  rodou nos 3 pontos sem quebrar. Ano agrícola nov-out é convenção do
  briefing; em outros hemisférios, a safra local segue outra
  sazonalidade — apenas reportado, sem interpretação agronômica.
