# Roteiro de demonstração (≈4 minutos)

Preparação: backend e frontend rodando (ver README). O cenário usa coordenadas **reais** de São Raimundo Nonato-PI
(semiárido, Serra da Capivara) com dados NASA POWER 1991–2026 em cache — funciona sem internet. Área, solo e rotação
atual são **demonstrativos**. Os números abaixo são saídas do modelo para esse cenário (configuração padrão), não
resultados de campo.

## 1. O problema, em um ponto do mapa (Painel — 40 s)
- "Sítio demonstrativo no semiárido do Piauí, milho de sequeiro todo janeiro."
- Mostre o índice de vulnerabilidade (**0,56 — alta**) e as condições: ~597 mm de chuva contra ~1.940 mm de ET0,
  estação chuvosa de 3 meses.
- Alertas: Tmax subindo **≈0,49 °C por década** e **+23 dias/ano acima de 35 °C por década**, ambos estatisticamente
  significativos na série NASA POWER.

## 2. Evidências da NASA (Análise ambiental — 50 s)
- Tabela de fontes: o que entra nos cálculos, o que é só visual, o que ainda não está integrado — sem exagero.
- Gráfico chuva × ET0 e a comparação de períodos: chuva média 1991–2005 ≈ 663 mm, 2011–2025 ≈ 500 mm.
- Mapa: célula NASA POWER desenhada (a escala real dos dados) e camadas GIBS de NDVI/IMERG/SMAP (com internet).

## 3. A rotação inteligente (Rotação — 80 s)
- Faixa de 24 meses: cor = família botânica, listras = cobertura, altura = cobertura efetiva ponderada pela água.
- A (atual): perda potencial média do milho ≈ 46–47 %; perda > 50 % em **≈46 %** dos anos-safra históricos.
- C (Resiliência hídrica): sorgo e milheto — perda potencial média ≈ 25 %, água faltante cai de ≈190 para ≈97 mm/ano e
  anos-safra de quebra para ≈13 %.
- B (Conservação): leguminosas de cobertura após a safra — maior melhoria do solo e menor erosão, com mais demanda de água.
- Aba "Por que foi sugerida" e "Confiança": a completude das evidências (~60/100) **não é** probabilidade de sucesso;
  aba "Informações ausentes" diz o que melhoraria a análise.
- Fronteira de Pareto: NSGA-II real (≈14 mil avaliações); cada ponto é um compromisso diferente.
- Se o mapa ou a declividade aparecerem como indisponíveis, a máquina está sem internet: os cálculos continuam com o cache.

## 4. E se o clima mudar? (Simulador — 50 s)
- Aplique "+2 °C, −15 %" (rotulado como **hipotético**, não projeção).
- Compare histórico, recente observado e hipotético: a estratégia A piora mais que C; curvas de sensibilidade mostram a
  distância entre estratégias crescendo com o aquecimento.

## 5. Global e honesto (20 s)
- Em Propriedade, clique em "Iowa (demo)" e analise com milho em maio: o sistema respeita a janela térmica (sem semeaduras
  no inverno). Qualquer ponto do mundo funciona com internet.
- Relatório: imprimir/PDF com fontes, riscos e limitações.

Frase de fechamento: *"Não dizemos ao agricultor o que plantar — mostramos, com 35 anos de dados da NASA, quanto cada
escolha arrisca e por quê."*
