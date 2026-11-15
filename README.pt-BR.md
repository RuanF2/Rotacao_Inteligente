# Rotação Inteligente 2.0 — Global Agricultural Intelligence

Ferramenta de apoio à decisão para **rotação de culturas adaptada ao clima**, construída sobre observações da Terra da NASA.
Projeto para o NASA Space Apps Challenge 2026 — desafio *Field Shift: adaptando fazendas com dados da NASA*.

> Ferramenta de apoio. Não substitui o julgamento do agricultor nem a orientação de especialistas locais.

## Problema

Agricultores precisam escolher o que plantar, e quando, diante de chuva cada vez mais irregular, mais dias de calor
extremo, solo degradado e pouca água. As decisões de rotação raramente usam a série climática do próprio local, e os
benefícios de leguminosas e plantas de cobertura são difíceis de comparar com o risco de quebra de safra.

## Solução

Para qualquer coordenada do planeta, o sistema:

1. **Analisa o ambiente** com aproximadamente 35 anos completos de dados diários do NASA POWER (chuva, temperaturas, umidade do solo modelada),
   calcula ET0, aridez, veranicos, calor extremo, erosividade, tendências e a relação com El Niño / La Niña.
2. **Mede a vulnerabilidade** da propriedade com um índice experimental documentado (8 indicadores, faixas publicadas).
3. **Gera estratégias de rotação** com otimização multiobjetivo **NSGA-II** (pymoo) sobre 13 culturas, respeitando
   restrições agronômicas (sobreposição, janela de semeadura, janela térmica, monocultura, renda anual).
4. **Compara** a rotação atual (A) com Conservação do solo (B), Resiliência hídrica (C) e Equilíbrio pelas prioridades (D),
   avaliando cada uma em ~34 pares de anos históricos reais — não só na média.
5. **Simula** o comportamento das estratégias sob perturbações hipotéticas de temperatura e chuva.
6. **Explica** cada recomendação: por quê, evidências (com fonte e período), benefícios potenciais, riscos,
   completude das evidências e o que está faltando.
7. **Gera relatório** imprimível (PDF pelo navegador) e em Markdown.

O diferencial é a **faixa de rotação de 24 meses**: uma régua de calendário em que cada mês mostra a família botânica e a
cobertura efetiva do solo, ponderada pela água realmente disponível naquele local.

## Estado atual de implementação — esclarecimentos

| Funcionalidade | Situação real |
|---|---|
| NASA POWER, ENSO, vulnerabilidade, catálogo de 13 culturas, otimização NSGA-II, estratégias A–D, simulador e relatório | Implementados na aplicação web 2.0 |
| Módulos antigos `planejador.py`, `janelas.py`, `alerta.py` e `semaforo.py` | Disponíveis na aplicação Streamlit NASA1; **não integrados à API FastAPI 2.0** |
| Aviso automático de **“PLANTE AGORA”** e envio por WhatsApp, SMS, e-mail ou push | **Não implementados no 2.0**. O alerta Streamlit é um experimento e mantém limiares de chuva/umidade não calibrados (`None`). |
| Quantidade de sementes em kg e produção prevista em kg/ha, toneladas ou sacas | **Não estimadas de modo validado**. O catálogo de 13 culturas não contém taxas de semeadura/rendimentos observados e o banco regional de produtividade não está preenchido. |
| Perda potencial relativa de rendimento hídrico | **Estimativa de modelo** via Ky e déficit hídrico, não estimativa de produção absoluta ou resultado observado |
| Indicador de confiança | Qualidade/completude das evidências, **não** probabilidade de sucesso agrícola |

**Integração NASA1:** o arquivo `backend/app/legacy.py` importa seletivamente apenas `core.nasa_power`, `core.enso` e constantes de `config.py`. O planejador e as regras de alerta do NASA1 não são executados pelos endpoints de rotação da versão 2.0.

**Período da série:** o cliente NASA POWER pode consultar 1991–2026 para fechar anos agrícolas. Comparativos que usam 1991–2025 analisam 35 anos civis completos. Uma análise de rotação pode empregar cerca de 34 pares deslizantes de dois anos — 68 observações de cultivo/ano **não independentes**.

**Transparência:** alertas mostrados no painel são avisos analíticos de risco, não ordens de plantio nem notificações externas. Cenários de temperatura/chuva são hipóteses de sensibilidade, não previsões climáticas oficiais.

## Funcionalidades (todas implementadas e testadas)

| Tela | O que faz |
|---|---|
| Painel | Vulnerabilidade, condições ambientais, alertas (tendências significativas), estratégias e mapa |
| Propriedade | Local por clique no mapa ou coordenadas (município/país identificados por geocodificação reversa OpenStreetMap; ao trocar de local, os dados do local anterior são descartados e o usuário é avisado do que revisar), solo, declividade, irrigação, rotação atual, culturas permitidas, prioridades; salvar/abrir (SQLite) |
| Análise ambiental | Fontes e cobertura por local, gráficos NASA POWER, umidade do solo, ENSO, comparação 1991–2005 × 2011–2025, indicadores de vulnerabilidade, mapa com camadas GIBS (NDVI, IMERG, SMAP) |
| Rotação inteligente | Estratégias A–D, tabela e radar comparativos, explicações em abas, fronteira de Pareto |
| Simulador climático | ΔT, ΔP, irrigação, período-base; histórico × recente × hipotético; curvas de sensibilidade |
| Relatório | Documento completo com fontes, resultados, riscos e limitações |

## Tecnologias

- **Backend:** Python, FastAPI, pandas, NumPy, SciPy (Theil-Sen, Mann-Kendall), pymoo (NSGA-II), SQLite.
- **Núcleo científico herdado do NASA1** (`rotacao_inteligente/core`): download e cache NASA POWER, ENSO/ONI, critério de
  estabelecimento — reutilizado diretamente pelo backend, sem cópia.
- **Frontend:** React 19 + Vite, Tailwind CSS 4, Recharts, React Leaflet.
- **Não usados:** GeoPandas, Rasterio, Xarray e scikit-learn foram avaliados e deixados de fora — nenhuma funcionalidade
  atual precisa deles e aumentariam muito a instalação. Entram quando Landsat/CMIP6 forem integrados.

## Arquitetura

```
rotacao2/
├── rotacao_inteligente/     # NASA1 original (Streamlit) — preservado e funcional
│   ├── core/                # NASA POWER, ENSO, janelas, resiliência... (reutilizado pelo backend)
│   └── data/                # cache NASA POWER 1991–2026 (6 locais), oni.csv, culturas.csv
├── backend/                 # API FastAPI (motor científico)
│   ├── app/
│   │   ├── legacy.py        # ponte para rotacao_inteligente/core
│   │   ├── clima.py         # série NASA POWER, ET0, indicadores, ENSO, perturbações
│   │   ├── vulnerabilidade.py
│   │   ├── rotacao.py       # avaliação de rotações + NSGA-II + seleção B/C/D
│   │   ├── explicabilidade.py
│   │   ├── servico.py       # orquestra análise e simulador
│   │   ├── topografia.py    # SRTM 90 m via OpenTopoData
│   │   ├── fontes.py, relatorio.py, db.py, main.py
│   │   └── data/catalogo_culturas.json
│   └── tests/               # 52 testes
├── frontend/                # React + Vite
└── *.md                     # documentação
```

Fluxo: o frontend envia a propriedade para `POST /api/analise`; o backend carrega a série (cache → API NASA POWER),
calcula indicadores e vulnerabilidade, pré-computa uma tabela cultura × mês × ano, roda o NSGA-II, seleciona B/C/D,
gera as explicações e devolve tudo em JSON. Documentação interativa da API: `http://localhost:8000/docs`.

## Instalação

Pré-requisitos: **Python 3.10+** (testado em 3.13) e **Node.js 20.19+ ou 22.12+** (exigência do Vite 7; testado em 22.23).

```bash
# 1) Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2) Frontend
cd ../frontend
npm install
```

## Execução

Em dois terminais:

```bash
# Terminal 1 — API em http://localhost:8000
cd backend
uvicorn app.main:app --port 8000          # ou ./run_backend.sh

# Terminal 2 — interface em http://localhost:5173
cd frontend
npm run dev
```

Abra `http://localhost:5173`. A propriedade demonstrativa (semiárido do Piauí) é analisada automaticamente
(≈5 s). Para produção: `npm run build` e `npm run preview` (porta 4173, com proxy para a API).

O app Streamlit original continua disponível: `cd rotacao_inteligente && pip install -r requirements.txt && streamlit run app.py`.

### Variáveis de ambiente (opcionais)

| Variável | Padrão | Uso |
|---|---|---|
| `ROTACAO_DB_PATH` | `backend/rotacao.db` | Banco SQLite |
| `ROTACAO_CORS_ORIGINS` | `http://localhost:5173,…` | Origens permitidas |
| `ROTACAO_OFFLINE` | `0` | `1` desliga chamadas ao SRTM e à geocodificação |
| `ROTACAO_GEOCODER_UA` | `RotacaoInteligente/2.0 (...)` | User-Agent enviado ao Nominatim (a política de uso pede identificação; inclua um contato) |
| `ROTACAO_GEOCODER_URL` | Nominatim público | Outro servidor Nominatim, se houver |
| `ROTACAO_NSGA_POP` / `_GEN` / `_SEED` | `120` / `120` / `42` | Parâmetros do NSGA-II |
| `VITE_API_URL` | vazio (usa proxy) | URL da API para o frontend em outro host |

Nenhuma chave de API é necessária: NASA POWER, OpenTopoData, GIBS e Nominatim são públicos. A geocodificação respeita o
limite de 1 requisição/segundo do Nominatim e guarda os resultados em cache.

### Testes

```bash
cd backend && python -m pytest -q                 # 52 testes (clima, vulnerabilidade, rotação, NSGA-II, geocodificação, API)
cd frontend && npm test                           # 12 testes da troca de localização (node --test)
cd rotacao_inteligente && python -m pytest -q     # 212 testes do núcleo NASA1 (3 ignorados: exigem --run-online)

# Na raiz do projeto, com o ambiente do backend:
python scripts/smoke_global_3pontos.py            # pipeline em Nairóbi, Iowa e Punjab (informa cache × ao vivo)
python scripts/verificacao_independente_srn.py    # recálculo independente dos números da demonstração
python scripts/validar_integracoes.py             # COM INTERNET: NASA POWER (ponto novo), SRTM, Nominatim e GIBS reais
```

`validar_integracoes.py` gera `VALIDACAO_INTEGRACOES.md` com URL, status, data/hora e falhas de cada requisição.
**Rode-o antes de publicar**: as integrações ao vivo ainda não foram validadas (ver AUDITORIA.md).

## Internet e modo offline

- 6 locais têm série NASA POWER em cache e funcionam **sem internet**: Teresina, Picos e São Raimundo Nonato (PI),
  Nairóbi, Iowa e Punjab.
- Qualquer outro ponto baixa a série do NASA POWER na primeira análise (8 variáveis × 36 anos, ≈1–3 min) e depois usa o cache.
- Sem internet, um ponto novo gera mensagem clara; a declividade SRTM aparece como "não obtida" e pode ser digitada.
- Camadas de satélite do mapa (GIBS) e mapas de fundo exigem internet no navegador.

## Limitações (leia antes de interpretar)

- NASA POWER representa uma célula de ~50 km, não o talhão.
- Balanço hídrico simplificado: sem armazenamento de água no solo entre meses, ET0 por Hargreaves (sem vento).
- Índice de vulnerabilidade e Dívida Ambiental do Solo são **indicadores experimentais**; a DAS não mede fertilidade,
  carbono ou degradação observada.
- Parâmetros de culturas têm níveis de confiança declarados; os marcados como estimativa/análogo precisam de validação local.
- Potencial econômico não é avaliado (faltam preços e produtividades locais confiáveis).
- SMAP, IMERG e NDVI aparecem apenas como camadas visuais; Landsat, ECOSTRESS e NEX-GDDP-CMIP6 não estão integrados.
- O simulador aplica perturbações **hipotéticas**; não são projeções climáticas.

Detalhes: [AUDITORIA.md](AUDITORIA.md) · [METHODOLOGY.md](METHODOLOGY.md) · [DATA_SOURCES.md](DATA_SOURCES.md) · [DEMO_SCRIPT.md](DEMO_SCRIPT.md) ·
[PROJECT_DESCRIPTION.md](PROJECT_DESCRIPTION.md)
