# Auditoria final — Rotação Inteligente 2.0

_Atualizada na última validação científica (15/11/2026, ≈02:20 UTC)._

Executada em 15/11/2026 (≈02h UTC) em ambiente Linux, Python 3.13, Node 22.23, com dependências instaladas do zero
a partir dos `requirements.txt` e do `package-lock.json`. Este ambiente **não tem acesso de rede** a
power.larc.nasa.gov, api.opentopodata.org nem gibs.earthdata.nasa.gov (o proxy recusa a conexão).

## 1. Resultado dos testes

| Suíte | Aprovados | Falhos | Ignorados |
|---|---|---|---|
| Backend (`backend/tests`, venv limpo) | 52 | 0 | 0 |
| Frontend (`npm test`, troca de localização) | 12 | 0 | 0 |
| Núcleo NASA1 (`rotacao_inteligente/tests`, venv limpo) | 212 | 0 | 3 (`--run-online`: GIBS, grade de risco, NASA POWER ao vivo) |
| App Streamlit legado (AppTest) | abre sem exceções | — | — |
| Frontend `npm ci` + `npm run build` | sem erros | — | — |
| `scripts/smoke_global_3pontos.py` | 3 de 3 pontos | 0 | — |
| Conferência interface × backend (9 valores, navegador headless) | 9 | 0 | — |
| Verificação independente × API (estratégias A e C, 16 itens) | 16 | 0 | — |

Versões resolvidas na instalação limpa: fastapi 0.163, pymoo 0.6.2, pandas 3.1.1, numpy 2.5.4, scipy 1.18.1, streamlit 1.67,
folium 0.20, plotly 7.1; React 19.3, Vite 7.3.8, Recharts 3.10, React Leaflet 5.0.

## 2. Teste global (Nairóbi, Iowa, Punjab)

Os três pontos rodaram o pipeline completo. **Origem dos dados: cache local (8/8 variáveis) nos três pontos — nenhuma
consulta ao vivo foi feita.** Os arquivos de cache são respostas autênticas da API (cabeçalho NASA POWER v2.10.3,
fontes MERRA-2 e GEOS-IT, série 01/01/1991–14/11/2026), obtidas pela equipe antes desta auditoria.

| Ponto | Chuva anual média (35 anos completos) | Meses-janela de milho (critério do NASA1) |
|---|---|---|
| Nairóbi | 592 mm | nenhum |
| Iowa | 874 mm | Mar, Abr, Mai, Jun |
| Punjab | 582 mm | Jun, Jul |

Observação: o critério de janelas do NASA1 considera apenas chuva. Por isso Iowa aparece com março como janela, mesmo
sendo frio demais para o milho. O motor 2.0 aplica a restrição térmica; o módulo legado não.

## 3. Integrações externas

| Integração | Situação nesta auditoria |
|---|---|
| NASA POWER — ponto novo sem cache | **NÃO VALIDADA** — conexão recusada pelo proxy (tentativas em 15/11/2026 02:07 e 02:21 UTC). O tratamento de erro funcionou: mensagem clara e nenhum arquivo parcial salvo. |
| OpenTopoData (SRTM) | **NÃO VALIDADA** — conexão recusada. Lógica testada só com resposta simulada (testes unitários). |
| NASA GIBS no navegador | **NÃO VALIDADA** — tiles bloqueados no navegador headless; os IDs das camadas vêm do GetCapabilities lido pelo NASA1. |
| OpenStreetMap Nominatim (geocodificação reversa) | **NÃO VALIDADA** contra o serviço real — sem rede; testada com respostas simuladas (sucesso, sem endereço, falha de rede, HTTP 429, JSON inválido, intervalo de 1 req/s, cache). |
| NASA POWER via cache | Validada (dados reais pré-baixados, 6 locais). |

Para validar com internet: `python scripts/validar_integracoes.py` (gera `VALIDACAO_INTEGRACOES.md` com URL, status,
data/hora e falhas). Depois, conferir as camadas GIBS visualmente no mapa.

## 4. Conferência científica — São Raimundo Nonato-PI (cenário demonstrativo)

`scripts/verificacao_independente_srn.py` reimplementa o modelo do zero, sem importar o backend: lê os JSON brutos da
NASA POWER, calcula ET0 (Hargreaves), a curva de Kc, a chuva efetiva USDA-SCS, o balanço hídrico e a perda FAO-33 para as
estratégias A (milho jan/milho jan) e C (sorgo jan/milheto jan). Os parâmetros são os do catálogo publicado, **sem ajuste**:
milho 120 d, Ky 1,25; sorgo 100 d, Ky 0,90; **milheto 90 d, Ky = 1,0 assumido** (não tabelado na FAO-33). Não havia dias
sem dado dentro dos ciclos avaliados. Com `--api` o script compara item a item com a API em execução:

| Item | Independente | Backend / interface | Diferença |
|---|---|---|---|
| A — anos-safra com perda > 50 % | 45,6 % | 45,6 % (exibido 46 %) | 0 |
| A — déficit hídrico | 189,63 mm/ano | 189,6 | +0,03 (arredondamento) |
| A — perda média milho ano 1 / ano 2 | 46,3 % / 47,4 % | 46,3 % / 47,4 % | 0 |
| C — anos-safra com perda > 50 % | 13,2 % | 13,2 % (exibido 13 %) | 0 |
| C — déficit hídrico | 97,42 mm/ano | 97,4 | +0,02 (arredondamento) |
| C — perda média sorgo / milheto | 24,9 % / 25,2 % | 24,9 % / 25,2 % | 0 |
| C — ETc sorgo / milheto | 379,1 / 321,1 mm | 379,1 / 321,1 | ≤ 0,05 mm |
| C — chuva efetiva sorgo / milheto | 274,2 / 244,3 mm | 274,2 / 244,3 | ≤ 0,02 mm |
| Tendência de Tmax | +0,494 °C/década, p = 0,00056 | +0,49, p = 0,001 | arredondamento |
| Dias com Tmax ≥ 35 °C | +22,73 dias/década, p = 0,0014 | +22,7, p = 0,001 | arredondamento |
| Chuva anual | −38,0 mm/década, p = 0,177 | −38, p = 0,177 | 0 |

**Nenhuma divergência além do arredondamento de exibição; nada foi alterado no modelo.**
A perda média do milheto depende da hipótese Ky = 1,0. Se o Ky real for menor (cultura mais tolerante), a perda e a
frequência de quebra da estratégia C ficam superestimadas; se for maior, subestimadas.

### 4.1 Metodologia dos anos com quebra (pares deslizantes)

O backend avalia **34 pares de anos consecutivos e sobrepostos** (1991–1992, 1992–1993, …, 2024–2025). Cada par gera
2 observações de ano-safra (68 no total), mas **há apenas 35 anos históricos**: os anos 1992–2024 aparecem duas vezes
(uma em cada fase da rotação), 1991 e 2025 uma vez. A frequência de quebra é a proporção dessas 68 observações.

| Estratégia | Pares (68 obs.) | Anos únicos (35) | Origem da diferença |
|---|---|---|---|
| A | 31/68 = 45,6 % | 16/35 = 45,7 % | 2025 (ano de quebra) só entra na fase "ano 2" |
| C | 9/68 = 13,2 % | 6/35 = 17,1 % ou 4/35 = 11,4 %, conforme a fase; sorgo ou milheto sozinhos 5/35 = 14,3 % | a quebra do sorgo em 2025 fica fora (sorgo avaliado só em 1991–2024) |

Anos com perda > 50 %: milho 16/35 (1993, 1996, 1998, 1999, 2002, 2003, 2007, 2012–2017, 2019, 2021, 2025); sorgo 5/35
(2012, 2013, 2015, 2021, 2025); milheto 5/35 (2012–2015, 2021). Intervalo de confiança de 95 % com n = 35 (Wilson):
milho 30–62 %, sorgo/milheto 6–29 %. A vantagem de C sobre A é robusta; diferenças pequenas entre estratégias, não.
A contagem por pares foi **mantida** (não há erro: é a forma de avaliar uma rotação de 2 anos sobre todo o histórico),
mas os textos da interface e das explicações agora deixam claro que são observações sobrepostas, não anos independentes.

## 5. Problemas encontrados e corrigidos

1. **Indicador "anos com perda > 50 %" inflado** — era contado por *par* de anos (71 % para o milho atual); o correto é
   por ano-safra (46 %). Corrigido em `rotacao.py` (vale também para falha de estabelecimento). Textos da interface,
   do relatório e das explicações foram ajustados, e há um teste de regressão contra cálculo direto.
2. `scripts/smoke_global_3pontos.py` procurava `download/rotacao_inteligente`; corrigido. Agora também informa a origem
   (cache × ao vivo) e o período recebido, e a média anual exclui o ano corrente incompleto (antes ele entrava na média).
3. README dizia Node 18+, mas o Vite 7 exige Node ^20.19 ou ≥22.12; corrigido e declarado em `engines` no `package.json`.
4. Pacote JavaScript de 947 kB num único arquivo; dividido em blocos (react, gráficos, mapas), sem aviso de build.
5. Uso de API do pandas obsoleta (`dayofyear`) que gerava aviso com pandas 3.1; trocada por `day_of_year`.
6. A perda potencial por cultura não aparecia na tela de Rotação; agora aparece, com a marcação "Ky assumido" quando cabe.
7. (Última validação) O Painel dizia "68 anos-safra históricos"; agora diz "34 pares sobrepostos = 68 observações de
   ano-safra (não são 68 anos independentes)". Mesma precisão aplicada na tela de Rotação e nos textos de risco/alerta.
   Nenhum número mudou.

### 5.1 Correção — sincronização geográfica (15/11/2026)

Bug: ao escolher um ponto na França (≈47,010; 5,768), o Painel mantinha "Sítio Demonstrativo Serra da Capivara /
São Raimundo Nonato – PI / Brasil", porque `escolherLocal` só atualizava lat/lon. Correções:
- trocar coordenadas (mapa, campos ou locais pré-definidos) descarta município, região, país e declividade anteriores;
  sem fonte geográfica a tela mostra "Localização não identificada" e mantém as coordenadas;
- geocodificação reversa no backend (`/api/geocodificar`, OpenStreetMap Nominatim) com User-Agent, 1 req/s, cache
  SQLite e erros claros (rede, HTTP 429, resposta inválida, ponto sem endereço); respostas atrasadas de outra coordenada
  são descartadas; localidade digitada pelo usuário nunca é sobrescrita; a fonte da localidade é guardada (`localidade_fonte`);
- nome demonstrativo é limpo e passa a ser obrigatório; nome definido pelo usuário é preservado (um teste de navegador
  revelou que a primeira versão limpava também o nome de uma demonstração renomeada — corrigido, com teste);
- aviso listando o que foi informado para o local anterior (solo, culturas e calendário, histórico, declividade, irrigação);
- a análise anterior é apagada ao iniciar uma nova (nada fica na tela durante o cálculo ou após falha); respostas fora de
  ordem são ignoradas; todas as telas só exibem uma análise calculada para as coordenadas da propriedade ativa;
  o relatório escreve "Localização não identificada" quando não há localidade.
- Verificado no navegador: França → aviso, "Localização não identificada", análise falha (sem rede) sem mostrar dados do
  Piauí em nenhuma das 6 telas; depois Iowa → Painel e relatório com o novo nome, local e coordenadas.
- Motor científico inalterado (verificação independente × API com as mesmas diferenças de arredondamento).

## 6. Arquivos alterados nesta auditoria

- `backend/app/rotacao.py`, `backend/app/servico.py`, `backend/app/explicabilidade.py`, `backend/app/relatorio.py`,
  `backend/app/clima.py`
- `backend/tests/test_rotacao.py` (novo teste)
- `frontend/src/pages/Rotacao.jsx`, `frontend/src/pages/Dashboard.jsx`, `frontend/src/pages/Simulador.jsx`
- `frontend/package.json`, `frontend/vite.config.js`
- `scripts/smoke_global_3pontos.py`
- Novos: `scripts/validar_integracoes.py`, `scripts/verificacao_independente_srn.py`, `AUDITORIA.md`
- Última validação: `scripts/verificacao_independente_srn.py` (estratégia C, contagem por anos únicos, comparação com a API),
  `METHODOLOGY.md` (seção 4.4.1), `AUDITORIA.md`, `frontend/src/pages/Dashboard.jsx`, `frontend/src/pages/Rotacao.jsx`,
  `backend/app/servico.py`, `backend/app/explicabilidade.py` (somente textos)
- Sincronização geográfica: novos `backend/app/geocodificacao.py`, `backend/tests/test_geocodificacao.py`,
  `frontend/src/lib/localizacao.js`, `frontend/src/lib/localizacao.test.js`; alterados `backend/app/main.py`,
  `backend/app/relatorio.py`, `frontend/src/App.jsx`, `frontend/src/components/ui.jsx`, `frontend/src/lib/api.js`,
  `frontend/src/pages/Propriedade.jsx`, `frontend/src/pages/Dashboard.jsx`, `frontend/src/pages/Relatorio.jsx`,
  `frontend/package.json`, `scripts/validar_integracoes.py`, `README.md`
- `README.md`, `METHODOLOGY.md`, `DEMO_SCRIPT.md`

## 7. Limitações que permanecem

- As três integrações ao vivo (NASA POWER para ponto novo, SRTM e GIBS) **não foram testadas contra os serviços reais**.
- Python 3.10–3.12 não foram testados (só 3.13).
- Ky não tabelado para milheto, gergelim, caupi e plantas de cobertura (assumido 1,0, sinalizado na tela); afeta a perda
  e a quebra da estratégia C.
- Frequências de quebra vêm de 35 anos de clima (intervalos de confiança largos); a verificação independente reproduz o
  mesmo modelo, portanto confirma a implementação, não a validade agronômica (sem dados de campo).
- Todas as limitações científicas do README e da METHODOLOGY seguem válidas: escala de ~50 km, balanço hídrico sem
  armazenamento no solo, faixas definidas pela equipe, sem avaliação econômica, CMIP6/Landsat/ECOSTRESS não integrados.

## 8. Conclusão

O código, os testes offline e a coerência entre backend e interface estão verificados. **O projeto ainda não pode ser
declarado pronto para publicação**: falta rodar `scripts/validar_integracoes.py` numa máquina com internet (NASA POWER,
SRTM, Nominatim e GIBS) e conferir as camadas GIBS e a identificação de município ao clicar no mapa.
