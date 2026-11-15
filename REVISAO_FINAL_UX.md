# Revisão final — orientação ao agricultor e interpretação científica

## Alterações
- A fórmula do motor de rotação foi preservada: `perda = min(1, Ky × (1 − ETa/ETc))` (estimativa pelo componente hídrico). Temperatura baixa/geada e calor entram em restrições e vulnerabilidade, **não** no percentual de perda por água.
- O campo preexistente `satisfacao_hidrica` é calculado como atendimento hídrico × (1 − fração de dias frios), portanto sua apresentação agora esclarece que é um **índice combinado água e adequação térmica**, não uma porcentagem simples de água entregue. O valor não foi alterado.
- Telas de painel, rotação e simulador usam rótulos explícitos de **perda potencial por falta de água**, sem apresentar 0% como ausência de risco total.
- Rotação atual que descumpre restrições permanece como comparação, acompanhada de alerta destacado.
- Foi acrescentada orientação prática com calendário, necessidades e déficit de água, justificativa e riscos. Gráficos de otimização detalhados estão recolhidos em seções expansíveis, mantendo acesso ao método científico.
- Relatório Markdown/PDF destaca a limitação térmica e discrimina perda hídrica e exposição ao frio em cada cultura.

## Limitações que permanecem
- Os indicadores são modelados e não calibrados em ensaios locais; não estimam quantitativamente perdas por geada, pragas e doenças.
- A adequação de cultivos e calendário deve ser validada por técnicos agrícolas locais antes da adoção.
- Ky assumidos, dados locais de solo e potencial econômico seguem as limitações anteriores.
- Testes de serviços externos dependem de conectividade real; nenhum dado satelital novo foi introduzido.

## Validação neste ambiente
- `npm test`: **16 aprovados**, 0 falhas (12 anteriores + 4 novos em `interpretacao.test.js`).
- `pytest backend/tests/test_clima.py backend/tests/test_vulnerabilidade.py backend/tests/test_topografia_explic.py`: **18 aprovados**, 0 falhas.
- Suíte completa do backend: **não concluída** neste ambiente, porque o pacote `pymoo` não está instalado. Tentativas de alguns testes dependentes do otimizador falharam por falta da dependência, não por regressão comprovada.
- `npm ci`/`npm run build`: **não validados neste ambiente**, pois a instalação das dependências do npm não terminou por restrição de rede.
- Não foi executado teste de navegador automatizado para as alterações visuais. Recomenda-se abrir localmente as seis telas no Windows e validar a apresentação com dados reais, especialmente o caso do milho semeado em janeiro em região fria.

## Comandos para confirmação no Windows
Da raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm ci
npm test
npm run build
npm run dev
```

Se `npm ci` já foi executado e as dependências estão atualizadas, não precisa repetir a instalação para testar. Abra a tela de Rotação em um cenário frio e confirme que o alerta aparece mesmo com perda hídrica igual a 0%.
