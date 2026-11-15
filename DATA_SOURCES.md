# Fontes de dados — Rotação Inteligente 2.0

Situação: **integrado** = entra nos cálculos · **visual** = camada no mapa, fora dos cálculos · **não integrado** = previsto.

| Conjunto | Instituição | Link | Resolução espacial | Resolução temporal | Variáveis | Situação |
|---|---|---|---|---|---|---|
| NASA POWER Daily (comunidade AG) | NASA Langley Research Center | https://power.larc.nasa.gov/ | ≈0,5° × 0,625° (MERRA-2); ≈1° radiação | diária, usamos 1991–2026 | PRECTOTCORR, T2M, T2M_MAX, T2M_MIN, RH2M, ALLSKY_SFC_SW_DWN, GWETROOT, GWETTOP | **integrado** |
| ONI v6 (Oceanic Niño Index) | NOAA Climate Prediction Center | https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/ | índice Niño 3.4 | trimestral (DJF) | anomalia de TSM | **integrado** (arquivo `oni.csv` do NASA1) |
| SRTM 90 m via OpenTopoData | NASA/NGA; serviço OpenTopoData | https://www.earthdata.nasa.gov/data/instruments/srtm · https://www.opentopodata.org/ | ≈90 m | estático (2000) | elevação → declividade | **integrado** (exige internet; 60°N–56°S) |
| MODIS Terra NDVI 16 dias | NASA EOSDIS GIBS | https://nasa-gibs.github.io/gibs-api-docs/ | 250 m | 16 dias | NDVI | visual |
| GPM IMERG — taxa de precipitação | NASA GPM / GIBS | https://gpm.nasa.gov/data/imerg | 0,1° | diária (camada GIBS) | precipitação | visual |
| SMAP L4 — umidade da zona radicular | NASA JPL / GIBS | https://smap.jpl.nasa.gov/ | 9 km | diária | umidade do solo | visual |
| Landsat / HLS | NASA / USGS | https://landsat.gsfc.nasa.gov/ | 30 m | 8–16 dias | refletância/NDVI | não integrado |
| ECOSTRESS | NASA JPL | https://ecostress.jpl.nasa.gov/ | ≈70 m | irregular (ISS, ~52°N–52°S) | LST, ET | não integrado |
| NEX-GDDP-CMIP6 | NASA NCCS | https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6 | 0,25° | diária, 1950–2100 | pr, tas, tasmax, tasmin… | não integrado |

Identificadores GIBS (lidos do GetCapabilities pelo NASA1): `MODIS_Terra_L3_NDVI_16Day` (GoogleMapsCompatible_Level9),
`IMERG_Precipitation_Rate` e `SMAP_L4_Analyzed_Root_Zone_Soil_Moisture` (GoogleMapsCompatible_Level6).
Mapas de fundo: OpenStreetMap e Esri World Imagery.

## Fontes de parâmetros agronômicos

| Fonte | Uso |
|---|---|
| Allen et al. (1998), FAO Irrigation and Drainage Paper 56 | Kc (Tabela 12), estádios (Tabela 11), Ra e Hargreaves (Eqs. 21–25, 52) |
| Doorenbos & Kassam (1979), FAO Irrigation and Drainage Paper 33 | Fator de resposta à água Ky |
| `rotacao_inteligente/data/culturas.csv` (NASA1, fontes Embrapa citadas no arquivo) | Ciclos e demandas de referência de 6 culturas |
| Hatfield & Prueger (2015), *Weather and Climate Extremes* 10:4–10 | Limiares de temperatura de referência |
| Embrapa — plantas de cobertura | Aporte de biomassa de crotalária, feijão-de-porco, guandu, milheto |
| USDA-SCS (método do CROPWAT/FAO) | Chuva efetiva |
| Arnoldus (1980) | Classes do Índice de Fournier modificado |
| UNEP/UNCCD | Classes de aridez |
| Embrapa/SiBCS | Classes de relevo (declividade) |
| ETCCDI | Definições de dia seco e índices de extremos |

## Limitações por fonte

- **NASA POWER:** reanálise/modelo em grade grossa; chuva de reanálise pode diferir de pluviômetros locais; GWETROOT/GWETTOP
  são estimativas de modelo (não SMAP). Os últimos dias da série podem faltar (descartados automaticamente).
- **ONI:** a NOAA revisa valores recentes; o monitoramento operacional usa o RONI.
- **SRTM:** representa a superfície em 2000, inclui vegetação/edificações; declividade em 90 m suaviza o relevo.
- **GIBS:** imagens para visualização, sem valores numéricos extraídos; datas podem não ter cobertura (nuvens, órbita, processamento).
- - **Cache climático:** os dados climáticos pré-baixados não são distribuídos neste repositório. As séries são obtidas sob demanda do NASA POWER e armazenadas localmente.