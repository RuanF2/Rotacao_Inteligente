# Metodologia — Rotação Inteligente 2.0

Este documento descreve exatamente o que o código calcula (`backend/app`). Todo parâmetro escolhido pela equipe está
marcado como tal. Nenhum resultado foi validado em campo.

## 1. Dados de entrada e pré-processamento (`clima.py`)

- **Série:** NASA POWER Daily API, comunidade AG, 1991-01-01 a 2026 (último dia disponível). Variáveis: `PRECTOTCORR`
  (mm/dia), `T2M`, `T2M_MAX`, `T2M_MIN` (°C), `RH2M` (%), `ALLSKY_SFC_SW_DWN` (MJ/m²/dia), `GWETROOT`, `GWETTOP` (fração 0–1).
  Download e cache são feitos pelo módulo `core/nasa_power.py` do NASA1 (uma requisição por variável; `-999` → ausente).
- **Limpeza:** a cauda final sem dados é descartada; lacunas de temperatura de até 3 dias são interpoladas; **chuva nunca é
  interpolada**. Ano civil "completo" = ≥ 360 dias com chuva válida.
- **ET0:** Hargreaves-Samani (FAO-56, Eq. 52): `ET0 = 0,0023 (Tmed + 17,8) (Tmax − Tmin)^0,5 · 0,408 Ra`, com Ra pela
  FAO-56 Eqs. 21–25 (testado contra o Exemplo 8 da FAO-56). Usado porque a série não inclui vento (Penman-Monteith exigiria).
- **Chuva efetiva:** método USDA-SCS sobre o total mensal (usado no CROPWAT/FAO): `Pe = P(125 − 0,2P)/125` se P ≤ 250 mm,
  senão `125 + 0,1P`. Para uso diário, cada dia recebe o fator `Pe/P` do seu mês.

## 2. Indicadores climáticos

| Indicador | Definição |
|---|---|
| Chuva anual média, mediana, CV | Sobre anos civis completos |
| Índice de aridez | P anual média / ET0 anual média; classes UNEP/UNCCD (árido < 0,20; semiárido < 0,50; subúmido seco < 0,65) |
| Meses chuvosos | Meses com P ≥ 0,5·ET0 na climatologia (critério de período de crescimento FAO/AEZ) |
| Veranico na estação chuvosa | Maior sequência de dias com chuva < 1 mm (ETCCDI) dentro dos meses chuvosos, média anual |
| CDD anual, Rx1day, Rx5day, R20mm | Índices ETCCDI |
| Dias de calor | Dias/ano com Tmax ≥ 35 °C |
| GWETROOT médio | Média anual (estimativa de modelo MERRA-2, **não** é SMAP) |
| Índice de Fournier modificado | Σ p_m² / P (climatologia mensal), classes de Arnoldus (1980) |
| Tendências | Inclinação de Theil-Sen por década + teste de Mann-Kendall (tau de Kendall), significância p < 0,05 |
| Comparação de períodos | 1991–2005 × 2011–2025 |
| ENSO | Classes do ONI v6 (DJF, NOAA/CPC), ano agrícola N = nov/N–out/N+1 (convenção do NASA1); mediana da chuva dos meses chuvosos por classe |

## 3. Índice experimental de vulnerabilidade (`vulnerabilidade.py`)

Cada indicador recebe uma nota 0–1 por faixas fixas:

| Indicador | Faixas → nota | Base |
|---|---|---|
| Aridez (P/ET0) | < 0,20 → 1; < 0,50 → 0,67; < 0,65 → 0,33; ≥ 0,65 → 0 | UNEP/UNCCD |
| CV da chuva anual | < 0,15 → 0; < 0,25 → 0,33; < 0,35 → 0,67; ≥ 0,35 → 1 | Equipe |
| Veranico na estação (dias) | < 10 → 0; < 15 → 0,33; < 25 → 0,67; ≥ 25 → 1 | Equipe |
| GWETROOT médio | < 0,25 → 1; < 0,35 → 0,67; < 0,50 → 0,33; ≥ 0,50 → 0 | Equipe |
| Dias Tmax ≥ 35 °C | < 10 → 0; < 30 → 0,33; < 90 → 0,67; ≥ 90 → 1 | Equipe (35 °C: Hatfield & Prueger 2015) |
| Índice de Fournier | < 60 → 0; < 90 → 0,25; < 120 → 0,5; < 160 → 0,75; ≥ 160 → 1 | Arnoldus (1980) |
| Declividade (%) | < 3 → 0; < 8 → 0,33; < 20 → 0,67; ≥ 20 → 1 | Classes de relevo Embrapa/SiBCS |
| Solo descoberto (rotação atual) | fração de meses em pousio (0–1) | Manejo informado |

**Índice = média simples** das notas disponíveis (pesos iguais, opção padrão do *Handbook on Constructing Composite
Indicators* OCDE/JRC quando não há base para pesos diferentes). Com menos de 5 indicadores o sistema responde
"dados insuficientes". Classes: < 0,25 baixa; < 0,50 moderada; < 0,75 alta; ≥ 0,75 crítica.
Subíndices: hídrico (aridez, CV, veranico, GWETROOT), térmico (calor), erosão (Fournier, declividade, solo descoberto).

No simulador, GWETROOT é retirado do índice do cenário hipotético (é saída de modelo e não pode ser perturbado pelo método delta).

## 4. Motor de rotação (`rotacao.py`)

### 4.1 Representação
- Horizonte fixo de **24 meses** (2 anos agrícolas), calendário circular — a rotação se repete a cada 2 anos.
- Estratégia = até 4 *slots* (cultura, ano 1|2, mês de semeadura). Meses ocupados = ⌈ciclo/30,4⌉.
- Todas as estratégias (inclusive a atual) são avaliadas com o mesmo horizonte, a mesma série e o mesmo modelo.

### 4.2 Catálogo de culturas (`data/catalogo_culturas.json`)
13 culturas (milho, sorgo, milheto, feijão-caupi, feijão-comum, soja, amendoim, gergelim, girassol, trigo, crotalária
juncea, feijão-de-porco, guandu). Cada atributo tem **fonte** e **nível de confiança** (literatura, literatura aproximada,
análogo, estimativa da equipe):
- Kc inicial/médio/final: FAO-56 Tabela 12 (cobertura: análogo feijão-caupi);
- Ky: FAO-33 (ausente para caupi, milheto, gergelim e plantas de cobertura → assumido 1,0 e sinalizado);
- ciclo: `culturas.csv` do NASA1 (Embrapa) ou faixas típicas;
- Tmax crítica e temperatura-base: referências aproximadas de literatura;
- proteção do solo (1–3): estimativa qualitativa da equipe (exceto plantas de cobertura, Embrapa).

### 4.3 Avaliação de um slot em cada ano histórico
Para cada cultura × mês × ano da série (tabela pré-computada):

- `ETc = Σ Kc(d)·ET0(d)` — curva de Kc em 4 estádios (frações 20/30/30/20 % do ciclo, simplificação da Tabela 11 FAO-56);
- `Pe = Σ P(d)·f_mês`;
- `calor` = fração de dias com Tmax ≥ Tmax crítica;
- `frio` = fração de dias com Tmed < temperatura-base ou Tmin ≤ 0 °C (exceto trigo, tolerante a geada);
- `estab` = chuva dos primeiros 30 dias (critério de estabelecimento do NASA1).

Para uma estratégia, em cada par de anos (≈34 pares para a série 1991–2025):
- irrigação: orçamento `2 × mm/ano` distribuído proporcionalmente ao déficit de cada slot;
- `ETa = min(ETc, Pe + irrigação)`; `d = 1 − ETa/ETc`;
- perda potencial de rendimento `= min(1, Ky·d)` (FAO-33);
- estresse térmico `h = 1 − (1 − calor)(1 − frio)`; vulnerabilidade do slot `v = 1 − (1 − d)(1 − h)`.

### 4.4 Objetivos
| Objetivo | Sentido | Cálculo |
|---|---|---|
| Água faltante (demanda não suprida pela chuva) | min | média anual de Σ max(0, ETc − Pe) — equivale à irrigação necessária para atender 100 % |
| Vulnerabilidade climática | min | média, nos pares de anos, de `v` ponderado pelo ciclo das culturas **comerciais** |
| Potencial de erosão | min | Σ (fração mensal da erosividade p_m²/Σp²) × (1 − cobertura do mês), média dos 2 anos |
| Melhoria do solo | max | 0,5·min(1, meses-leguminosa/12) + 0,5·min(1, meses-alta-biomassa/12), ponderados pela satisfação hídrica |
| Cobertura vegetal efetiva | max | média mensal de cobertura = {1: 0,4; 2: 0,6; 3: 0,8}[proteção] × satisfação hídrica × (1 − frio); 1º mês × 0,5 |
| Diversificação | max | 0,5·min(1,(espécies−1)/3) + 0,5·min(1,(famílias−1)/2) |

A ponderação pela satisfação hídrica impede que o otimizador "ganhe cobertura" plantando na estação seca.
**Potencial econômico não é otimizado** (sem preços e produtividades locais confiáveis).

Indicadores adicionais: ETc total, déficit não atendido, **anos de quebra** (fração das observações de ano-safra — ano 1 e
ano 2 de cada par sobreposto, 68 no total — em que alguma cultura comercial semeada naquele ano teria perda potencial
> 50 %; ver 4.4.1), falha de estabelecimento (mesma contagem), meses de solo descoberto.

> Correção da auditoria final: até a versão anterior, quebra e falha de estabelecimento eram contadas por *par* de anos,
> o que inflava o valor (ex.: 71 % → 46 % para o milho de sequeiro do cenário demonstrativo).

#### 4.4.1 Como os anos com quebra são contados (pares deslizantes)

- A rotação dura 2 anos. Para avaliá-la com o clima real, a série é percorrida em **pares de anos consecutivos**
  (y, y+1), com y = 1991…2024: **34 pares**. Cultura do "ano 1" usa o clima de y; cultura do "ano 2" usa o de y+1.
- Os pares são **sobrepostos (deslizantes)**: 1991–1992, 1992–1993, 1993–1994… Cada ano interno (1992–2024) aparece
  em dois pares, uma vez em cada fase da rotação; 1991 só aparece como ano 1 e 2025 só como ano 2.
- Cada par gera 2 observações de ano-safra → **68 observações**. Elas **não são 68 anos históricos independentes**:
  há só **35 anos** de clima (1991–2025), e os anos internos foram reaproveitados.
- A **frequência de quebra** é a proporção dessas 68 observações em que alguma cultura comercial daquele ano teria
  perda potencial > 50 %. Equivale à média das duas fases possíveis da rotação sobre o histórico, com as bordas
  (1991 e 2025) contando uma vez a menos. Responde: *"se a rotação começasse em um ano qualquer da série, em que fração
  dos anos-safra haveria quebra?"*
- **Comparação com anos únicos** (verificação independente, cenário demonstrativo):

| Estratégia | Pares deslizantes (68 obs.) | Anos únicos 1991–2025 (35) | Por que difere |
|---|---|---|---|
| A — milho/milho | 31/68 = 45,6 % | 16/35 = 45,7 % (qualquer alinhamento) | 1991 entra só no ano 1 e 2025 só no ano 2 (2025 foi ano de quebra) |
| C — sorgo/milheto | 9/68 = 13,2 % | 6/35 = 17,1 % ou 4/35 = 11,4 %, conforme a fase; cada cultura sozinha: 5/35 = 14,3 % | A quebra do sorgo em 2025 fica fora (o sorgo só é avaliado em 1991–2024) |

- **Incerteza:** como a amostra efetiva é de 35 anos (e anos vizinhos podem ser correlacionados, como na sequência seca
  de 2012–2017 vista nos dados), as frequências são imprecisas. Intervalo de confiança de 95 % (Wilson, n = 35):
  milho 16/35 → 30–62 %; sorgo ou milheto 5/35 → 6–29 %. A diferença entre A e C é robusta; diferenças de poucos pontos
  percentuais entre estratégias não devem ser interpretadas.
- A perda potencial média e o déficit hídrico usam os mesmos pares (médias sobre as 68 observações, déficit dividido
  por 2 para ficar em mm/ano).

### 4.5 Restrições (rígidas no otimizador)
1. sem sobreposição de culturas no calendário;
2. pelo menos uma cultura comercial semeada em cada ano (renda anual);
3. em sequeiro, mediana da chuva dos primeiros 30 dias ≥ 20 mm (critério do NASA1);
4. sem a mesma espécie em sequência (monocultura);
5. janela térmica: mediana de dias frios ≤ 10 % do ciclo (limiar da equipe).

Mesma família botânica em sequência gera **alerta fitossanitário**, não bloqueio. A rotação atual (A) é avaliada mesmo
que viole restrições, e a interface informa isso.

### 4.6 Otimização — NSGA-II (pymoo)
- Variáveis inteiras: 4 × (código da cultura ou vazio, mês 0–23); SBX + mutação polinomial com arredondamento;
  amostragem inicial gera indivíduos plausíveis (comercial por ano, mês viável).
- População 120, 120 gerações, semente 42 (≈14 400 avaliações, ≈5 s).
- Todas as soluções viáveis avaliadas vão para um arquivo; a **fronteira de Pareto final** é obtida por ordenação não
  dominada sobre o arquivo (testado: nenhuma solução da frente é dominada por outra).

### 4.7 Seleção das estratégias
Objetivos normalizados min–max no conjunto (Pareto ∪ A), com 1 = melhor:
- **B — Conservação do solo:** maior média de (melhoria do solo, cobertura, baixa erosão);
- **C — Resiliência hídrica:** maior média de (baixa água faltante, baixa vulnerabilidade); C ≠ B;
- **D — Equilíbrio:** soma ponderada pelas prioridades do agricultor (água, risco, erosão, solo, diversificação; 0–5);
  só aparece se for distinta de A, B e C.

## 5. Dívida Ambiental do Solo (DAS) — indicador experimental

`DAS = 100 × média(exposição, erosão, estresse hídrico, sem aporte biológico)`, onde
exposição = 1 − cobertura; erosão = potencial de erosão; estresse hídrico = déficit não atendido / ETc total;
sem aporte biológico = 1 − min(1, meses-leguminosa/12). Pesos iguais.

Representa **pressões acumuladas pelo manejo e pelo clima no horizonte de 24 meses**. Não é medição de fertilidade,
carbono orgânico, compactação ou degradação observada, e não foi calibrada com dados de solo.

## 6. Simulador climático (`servico.simular`)

- **Histórico observado:** série completa; **recente observado:** 2011–2025; **hipotético:** método delta sobre a base
  escolhida — `T2M, T2M_MAX, T2M_MIN + ΔT`; chuva diária × (1 + ΔP/100); ET0 recalculada.
- As **mesmas** estratégias da análise são reavaliadas em todos os pares de anos de cada cenário.
- Curvas de sensibilidade: vulnerabilidade × ΔT (0 a +4 °C) e água faltante × ΔP (−30 % a +10 %).
- O "horizonte" é apenas um rótulo do cenário. Projeções NEX-GDDP-CMIP6 não estão integradas.
- Limitação do método delta: não altera a frequência de eventos extremos nem a sazonalidade da chuva.

## 7. Explicabilidade (`explicabilidade.py`)

Explicações montadas por regras a partir dos números calculados — não há modelo generativo nem dado inventado.
Cada estratégia traz: por que foi sugerida, evidências (valor, unidade, fonte, período), benefícios potenciais
(condicionais), riscos (quebra, estabelecimento, calor, frio, família, Ky assumido, cobertura sem renda, economia não
avaliada), informações ausentes e **completude das evidências** (0–100) = média de: série ≥ 30 anos, confiança média dos
parâmetros das culturas usadas, análise de solo informada, declividade disponível, observação de satélite numérica
(sempre 0 nesta versão) e calibração local. **Não é probabilidade de sucesso agrícola.**

## 8. Topografia (`topografia.py`)

9 pontos SRTM 90 m (OpenTopoData) em janela 3×3 de 90 m; declividade pelo método de Horn (1981). Estimativa da vizinhança
(~180 m), não levantamento do talhão. Coberto entre 60°N e 56°S. Sem internet, o usuário digita a declividade.

## 9. Testes

`backend/tests` (42 testes): Ra contra o Exemplo 8 da FAO-56, ET0, chuva efetiva, classes, indicadores, perturbação,
faixas e insuficiência de dados da vulnerabilidade, curva de Kc, restrições (sobreposição, estabelecimento, renda,
monocultura, janela térmica), não dominância da frente NSGA-II, culturas permitidas, dependência do local, SRTM com
resposta simulada, API completa (análise, coerência entre telas, simulação, relatório, CRUD, entradas inválidas) e a contagem de quebra por
ano-safra conferida contra um cálculo direto. `scripts/verificacao_independente_srn.py` recalcula, a partir dos JSON brutos e sem importar
o backend, as tendências e o balanço hídrico completo das estratégias A (milho/milho) e C (sorgo/milheto), pelas duas
contagens (pares e anos únicos); com `--api` compara item a item com a API em execução.
O núcleo NASA1 mantém seus 212 testes.

## 10. Limitações principais

1. Escala: célula NASA POWER (~0,5°); nenhum dado é do talhão.
2. Balanço hídrico sem armazenamento de água no solo e sem escoamento; Hargreaves pode superestimar ET0 em clima úmido.
3. Curvas de Kc genéricas; datas de semeadura no dia 1 do mês.
4. Faixas do índice de vulnerabilidade, DAS, cobertura por classe de proteção e limiares de frio/quebra são escolhas da equipe.
5. Sem avaliação econômica, de pragas específicas, de manejo de nutrientes ou de mão de obra.
