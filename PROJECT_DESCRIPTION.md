# Rotação Inteligente 2.0 — Global Agricultural Intelligence

**Desafio:** Field Shift — adaptando fazendas com dados da NASA (NASA Space Apps Challenge 2026)

## Resumo

O Rotação Inteligente 2.0 é uma plataforma aberta de apoio à decisão que ajuda agricultores e técnicos a escolher
estratégias de rotação de culturas mais resistentes à seca, ao calor e à degradação do solo. A partir de uma coordenada em
qualquer lugar do mundo, ela usa 35 anos de observações diárias do NASA POWER para medir a vulnerabilidade climática da
propriedade, gera rotações alternativas por otimização multiobjetivo (NSGA-II) e explica cada recomendação com as
evidências, os riscos e as lacunas de dados envolvidas.

## O que fizemos

- **Motor de dados:** série diária NASA POWER (chuva, temperaturas, umidade do solo modelada) com cache para uso offline,
  ET0 pela FAO-56, índices de extremos ETCCDI, tendências (Theil-Sen/Mann-Kendall), erosividade e classes ENSO (NOAA).
- **Vulnerabilidade:** índice experimental com 8 indicadores e faixas publicadas; recusa classificar quando faltam dados.
- **Rotação:** catálogo de 13 culturas com fonte e nível de confiança por atributo (FAO-56, FAO-33, Embrapa); cada rotação
  é avaliada em cerca de 34 pares de anos históricos com balanço hídrico, perda potencial de rendimento (FAO-33), estresse
  por calor e frio, cobertura do solo e erosividade.
- **Otimização:** NSGA-II (pymoo) com restrições agronômicas — janela de semeadura, janela térmica, renda anual, sem
  monocultura — produz a fronteira de Pareto; dela saem as estratégias de Conservação do solo, Resiliência hídrica e
  Equilíbrio pelas prioridades do agricultor, sempre comparadas com a rotação atual.
- **Simulador:** histórico × recente × perturbação hipotética de temperatura e chuva, com curvas de sensibilidade.
- **IA explicável:** explicações geradas a partir dos números calculados, com fonte e período de cada evidência e um
  índice de completude das evidências que deixa claro que não é probabilidade de sucesso.
- **Interface:** aplicação web (React + FastAPI) com painel, cadastro da propriedade em mapa, análise ambiental, mapa com
  camadas NASA GIBS (NDVI MODIS, IMERG, SMAP), comparação de estratégias, simulador e relatório imprimível.

## Demonstração

Propriedade demonstrativa no semiárido brasileiro (São Raimundo Nonato-PI, coordenadas reais, manejo de exemplo). A
análise mostra aquecimento estatisticamente significativo na série NASA POWER e compara a monocultura de milho de sequeiro
com rotações de sorgo/milheto e de leguminosas de cobertura. A mesma ferramenta roda em Iowa, Punjab, Nairóbi ou em
qualquer coordenada informada.

## Uso de dados da NASA

NASA POWER (base de todos os cálculos), SRTM (declividade, via OpenTopoData), NASA GIBS (MODIS NDVI, GPM IMERG, SMAP L4
como camadas visuais). Landsat, ECOSTRESS e NEX-GDDP-CMIP6 estão mapeados na arquitetura, mas não integrados nesta versão.

## Transparência

O projeto não inventa dados nem apresenta resultados como garantidos. Dados regionais são exibidos com sua escala real
(~50 km), perturbações do simulador são rotuladas como hipotéticas, parâmetros estimados são identificados e o potencial
econômico não é avaliado por falta de dados confiáveis. Os resultados ainda não foram validados em campo.

## Próximos passos

Integrar projeções NEX-GDDP-CMIP6, NDVI Landsat/HLS por talhão e umidade SMAP numérica; balanço hídrico com
armazenamento no solo; calibração dos parâmetros com instituições de pesquisa locais; módulo econômico com preços regionais.

## Tecnologias

Python, FastAPI, pandas, NumPy, SciPy, pymoo, SQLite, React, Vite, Tailwind CSS, Recharts, Leaflet.
Evolução do projeto NASA1 (Streamlit), cujo núcleo científico foi preservado e reutilizado.
