# Rotação Inteligente 2.0 — Global Agricultural Intelligence

**Apoio à decisão para rotação de culturas adaptada ao clima, com dados de observação da Terra da NASA.**

Projeto desenvolvido para o **NASA Space Apps Challenge 2026**, no desafio *Field Shift: Adapting Farms with NASA Data*.

> **Ferramenta de apoio à decisão, não uma prescrição agronômica.** Os resultados representam cenários gerados por modelos e não substituem medições em campo ou a orientação de profissionais locais qualificados.

**Idioma:** [English](README.md) | Português (Brasil)

## O problema

A variabilidade das chuvas, o calor extremo, a escassez de água e a degradação do solo dificultam o planejamento agrícola. Para escolher uma sequência de culturas, é necessário considerar tanto o histórico climático local quanto as características e restrições de cada cultivo.

## A solução

O Rotação Inteligente 2.0 é uma aplicação web interativa para apoiar o planejamento da rotação de culturas em coordenadas geográficas selecionadas pelo usuário. A ferramenta combina análise ambiental histórica, otimização multiobjetivo, simulações de sensibilidade climática e explicações comparativas.

A aplicação permite:

1. **Analisar o clima local:** consultar séries diárias do NASA POWER e calcular precipitação, temperatura, umidade do solo modelada, evapotranspiração de referência (ET₀), aridez, veranicos, calor extremo, erosividade e tendências históricas. Informações ENSO/ONI da NOAA complementam a análise.
2. **Avaliar a vulnerabilidade ambiental:** calcular um índice experimental com oito indicadores e faixas de classificação documentadas.
3. **Explorar rotações agrícolas:** avaliar um catálogo de **13 culturas** e otimizar sequências de **24 meses** com o algoritmo multiobjetivo **NSGA-II** (`pymoo`), considerando restrições agronômicas.
4. **Comparar quatro estratégias:** **A — Rotação atual**, **B — Conservação do solo**, **C — Resiliência hídrica** e **D — Equilíbrio pelas prioridades do usuário**.
5. **Considerar a variabilidade histórica:** comparar resultados modelados em aproximadamente 34 janelas históricas sobrepostas de dois anos, conforme a disponibilidade dos dados.
6. **Simular sensibilidade climática:** explorar mudanças hipotéticas na temperatura, precipitação e irrigação, sem tratá-las como previsões meteorológicas ou projeções oficiais.
7. **Explicar os resultados:** apresentar compromissos entre objetivos, hipóteses, períodos de referência, incertezas, completude das evidências e possíveis razões para uma otimização não identificar uma sequência adequada.
8. **Gerar relatórios:** produzir relatórios em Markdown e visualizações preparadas para impressão, que podem ser salvas como PDF pelo navegador.

Um dos destaques é a **linha do tempo de rotação de 24 meses**, que permite visualizar a sequência de culturas, as famílias botânicas e a duração modelada da cobertura do solo, em conjunto com o contexto climático local.

## Telas da aplicação

| Tela | Principais funcionalidades |
|---|---|
| **Painel** | Condições ambientais, índice experimental de vulnerabilidade, avisos analíticos de risco, visão geral das estratégias e mapa |
| **Propriedade** | Escolha de coordenadas ou ponto no mapa; informações de solo, declividade, irrigação, rotação atual, culturas permitidas e prioridades; salvamento local em SQLite |
| **Análise ambiental** | Séries NASA POWER, contexto ENSO, comparação de períodos históricos, indicadores de vulnerabilidade e camadas visuais NASA GIBS |
| **Rotação inteligente** | Estratégias A–D, sequências de 24 meses, indicadores comparativos, fronteira de Pareto e explicações |
| **Simulador climático** | Alterações hipotéticas de temperatura, chuva e irrigação, seleção de período-base e comparação de sensibilidade |
| **Relatório** | Resultados, evidências, fontes, riscos, limitações e formato próprio para impressão |

Quando o otimizador não encontra uma rotação válida, a interface apresenta informações de diagnóstico sobre as restrições verificadas. **Não encontrar uma solução em uma execução não comprova matematicamente que nenhuma solução possível exista.**

## Fontes de dados e integrações

| Fonte | Utilização na aplicação |
|---|---|
| **NASA POWER** | Dados meteorológicos diários históricos e estimativas modeladas de umidade do solo usados nos cálculos ambientais e de rotação |
| **NOAA ENSO/ONI** | Contexto histórico de El Niño e La Niña |
| **NASA GIBS** | Camadas visuais de NDVI, precipitação IMERG e umidade do solo SMAP; essas imagens **não são assimiladas** pelo otimizador |
| **OpenTopoData / SRTM** | Elevação e declividade do terreno, sujeitas à cobertura geográfica e disponibilidade do serviço |
| **OpenStreetMap / Nominatim** | Geocodificação reversa e informações cartográficas |

As consultas ao NASA POWER podem abranger **1991 até as datas disponíveis de 2026**, mas os comparativos de anos civis completos geralmente utilizam **1991–2025** (35 anos completos), desde que os critérios de disponibilidade sejam atendidos. Cerca de 34 janelas sobrepostas de dois anos representam **68 observações de modelo do tipo cultura/ano, e não 68 anos independentes ou ensaios de campo**.

Detalhes: [Fontes de dados](DATA_SOURCES.md) e [Metodologia científica](METHODOLOGY.md).

## Tecnologias

- **Backend:** Python, FastAPI, pandas, NumPy, SciPy, `pymoo` (NSGA-II) e SQLite.
- **Processamento científico:** módulos Python para coleta de dados NASA POWER, análise ENSO, indicadores climáticos, vulnerabilidade, avaliação de culturas, otimização e explicabilidade.
- **Frontend:** React 19, Vite 7, Tailwind CSS 4, Recharts e React Leaflet.
- **Interface analítica adicional:** Streamlit, disponível no mesmo repositório.

A aplicação atual não possui pipelines integrados de dados Landsat, ECOSTRESS ou NEX-GDDP-CMIP6. GeoPandas, Rasterio, Xarray e scikit-learn não são dependências necessárias.

## Estrutura do repositório

```text
Rotacao_Inteligente/
├── backend/
│   ├── app/                 # API FastAPI, análises, otimização e relatórios
│   │   └── data/            # Catálogo de culturas
│   └── tests/               # Testes do backend
├── frontend/
│   └── src/                 # Interface React, componentes e testes
├── rotacao_inteligente/
│   ├── core/                # Módulos de processamento científico
│   ├── data/                # Dados de referência e diretórios de cache
│   ├── tests/               # Testes dos módulos científicos
│   └── app.py               # Interface Streamlit adicional
├── scripts/                 # Scripts de verificação e integração
├── METHODOLOGY.md
├── DATA_SOURCES.md
├── README.pt-BR.md
├── README.md
├── LICENSE
└── .gitignore
```

A interface React envia as configurações da propriedade para o backend FastAPI, incluindo a rota `POST /api/analise`. O backend obtém ou reutiliza séries climáticas armazenadas em cache, calcula indicadores ambientais, avalia rotações candidatas, executa o NSGA-II, compara estratégias e devolve resultados e explicações estruturados.

Com o backend em execução, a documentação interativa da API fica disponível em **http://localhost:8000/docs**.

## Instalação e execução local

### Pré-requisitos

- **Python 3.10 ou superior**
- **Node.js 20.19+ ou 22.12+** (Vite 7)
- Internet para a primeira obtenção de dados climáticos e para serviços cartográficos online

### 1. Instalar as dependências do backend

Execute a partir da raiz do repositório.

**Windows / PowerShell:**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

### 2. Iniciar o backend

Na raiz do repositório, com o ambiente Python ativado:

```bash
cd backend
python -m uvicorn app.main:app --port 8000
```

### 3. Iniciar o frontend

Abra outro terminal na raiz do repositório:

```bash
cd frontend
npm ci
npm run dev
```

Acesse **http://localhost:5173**. A aplicação disponibiliza uma propriedade demonstrativa no semiárido do Piauí. A primeira análise pode demorar mais por depender do download das séries climáticas; consultas posteriores podem utilizar o cache local.

Para verificar a compilação de produção, dentro de `frontend/`:

```bash
npm run build
npm run preview
```

### Interface Streamlit opcional

Na raiz do repositório, com o ambiente Python ativado:

```bash
python -m pip install -r rotacao_inteligente/requirements.txt
cd rotacao_inteligente
python -m streamlit run app.py
```

## Configuração

| Variável de ambiente | Finalidade |
|---|---|
| `ROTACAO_DB_PATH` | Caminho do banco de dados SQLite local |
| `ROTACAO_CORS_ORIGINS` | Origens permitidas para acesso ao backend |
| `ROTACAO_OFFLINE` | Com valor `1`, desativa determinadas consultas externas de topografia e geocodificação; **não disponibiliza dados climáticos de locais ainda não armazenados em cache** |
| `ROTACAO_GEOCODER_UA` | User-Agent do Nominatim; configure uma identificação do projeto e contato |
| `ROTACAO_GEOCODER_URL` | Endereço alternativo opcional para o Nominatim |
| `ROTACAO_NSGA_POP`, `ROTACAO_NSGA_GEN`, `ROTACAO_NSGA_SEED` | População, gerações e semente do otimizador (padrões: `120`, `120`, `42`) |
| `VITE_API_URL` | Endereço opcional da API; no desenvolvimento local, normalmente é utilizado o proxy do Vite |

Os serviços públicos utilizados atualmente não exigem chaves de API específicas do projeto. Respeite os limites, as atribuições e as políticas de cada provedor. **Não publique arquivos `.env`, credenciais, bancos locais ou caches baixados.**

## Testes e validação

O repositório inclui testes automatizados e scripts para verificações técnicas e de integração com serviços externos. A existência desses testes **não comprova que uma execução específica passou em todas as verificações**.

Instale as dependências necessárias antes de executar os comandos.

**Backend (a partir da raiz):**

```powershell
cd backend
python -m pytest -q
cd ..
```

**Módulos científicos (instale antes `rotacao_inteligente/requirements.txt`):**

```powershell
cd rotacao_inteligente
python -m pytest -q
cd ..
```

**Frontend:**

```powershell
cd frontend
npm ci
npm test
npm run build
cd ..
```

**Scripts adicionais de verificação (na raiz):**

```powershell
python scripts/smoke_global_3pontos.py
python scripts/verificacao_independente_srn.py
python scripts/validar_integracoes.py
```

O script `validar_integracoes.py` consulta serviços externos reais: NASA POWER, OpenTopoData, Nominatim e NASA GIBS. Os resultados dependem da conexão, dos limites de uso e da disponibilidade dos serviços.

## Internet, cache e funcionamento offline

- Os dados históricos do NASA POWER são obtidos **sob demanda** e armazenados em cache durante a execução.
- **Caches climáticos pré-baixados não estão incluídos no repositório público.** Uma instalação nova normalmente precisa de internet para a primeira análise, inclusive para a propriedade demonstrativa.
- Uma localidade já analisada pode reutilizar observações disponíveis no cache local.
- Sem dados climáticos armazenados e sem conexão com a fonte, não é possível analisar uma nova localidade.
- Topografia, geocodificação reversa, imagens NASA GIBS e mapas de fundo podem depender de seus serviços online.
- A configuração `ROTACAO_OFFLINE` não transforma o projeto em uma base de dados climáticos global totalmente disponível sem internet.

## Limitações científicas e uso responsável

- **Resolução espacial:** os dados NASA POWER são estimativas em grade, não medições feitas no talhão específico.
- **Balanço hídrico simplificado:** os cálculos não transportam o armazenamento de água no solo entre meses; a evapotranspiração de referência utiliza Hargreaves, e não a formulação completa de Penman–Monteith.
- **Indicadores experimentais:** o índice de vulnerabilidade e a *Dívida Ambiental do Solo* são construções para apoio à decisão, não medições diretas de fertilidade, carbono ou degradação do solo.
- **Parâmetros agronômicos:** parte dos valores foi estimada ou adaptada de referências e requer calibração local.
- **Produção e sementes:** não são fornecidos cálculos validados de quantidade de sementes ou previsões absolutas de colheita em kg/ha, toneladas ou sacas. As perdas potenciais relativas por estresse hídrico são **resultados de modelo, não produtividades observadas**.
- **Retorno financeiro:** uma análise confiável de rentabilidade exige preços, custos e produtividades locais calibradas que não estão disponíveis na implementação atual.
- **Comparação histórica:** janelas sobrepostas de dois anos não representam experimentos independentes; resultados modelados não equivalem a validação em campo.
- **Camadas de satélite:** as sobreposições SMAP, IMERG e NDVI não são entradas numéricas do otimizador de rotação.
- **Cenários climáticos:** as alterações definidas pelo usuário são testes hipotéticos de sensibilidade, não previsões ou projeções climáticas oficiais.
- **Alertas:** avisos do painel descrevem riscos analíticos. A aplicação **não** emite comandos calibrados de “plante agora” nem envia notificações por WhatsApp, SMS, e-mail ou push.
- **Indicador de evidências:** a pontuação de 0 a 100 reflete qualidade/completude das informações, **não** a probabilidade de sucesso da rotação.

**Este software é um protótipo exploratório de apoio à decisão. Antes de decisões agrícolas reais, os resultados precisam ser avaliados por profissionais e confrontados com as condições locais.**

## Documentação

- [Metodologia científica](METHODOLOGY.md)
- [Fontes de dados e atribuição](DATA_SOURCES.md)
- [README in English](README.md)
- [Licença MIT](LICENSE)

## Contexto do projeto

Protótipo desenvolvido para o **NASA Space Apps Challenge 2026**. As referências a dados e imagens da NASA indicam as fontes utilizadas e não representam endosso, certificação ou validação de campo por parte da agência.
