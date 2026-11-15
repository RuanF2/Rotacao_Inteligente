# Diagnóstico de inviabilidade — Rotação Inteligente 2.0

## O que mudou

Antes, quando o NSGA-II não encontrava rotações válidas, o servidor retornava apenas uma mensagem genérica de erro HTTP 422. Agora, o erro de inviabilidade retorna um objeto estruturado (`detail.diagnostico`) com verificações verificáveis e orientações práticas. O frontend apresenta esse diagnóstico em um painel compreensível e permite voltar à tela de Propriedade ou tentar novamente.

## Critérios efetivamente verificados

Para **cada cultura comercial permitida** e cada **mês de semeadura**, o diagnóstico utiliza a tabela climática calculada pelo motor original e os **mesmos filtros** já utilizados pelo algoritmo:

- **Frio/geada**: a mediana da fração de dias abaixo da temperatura-base da cultura ou com geada, se a cultura não tolera geada, deve ser `<= LIMIAR_FRIO` (10%).
- **Estabelecimento em sequeiro**: a mediana da precipitação nos primeiros `ESTAB_DIAS` (30 dias) deve atingir `ESTAB_MIN_MM` (20 mm). Se houver irrigação informada, a restrição de chuva inicial é dispensada, mas isso não valida a disponibilidade real de água.
- **Cultura comercial**: o sistema exige ao menos uma espécie comercial em cada ano.

O frontend distingue situações de **bloqueio comprovado** (por exemplo, nenhuma janela individual comercial passa em ambos os filtros) de restrições que afetam apenas parte das opções. Se existirem janelas individuais possíveis, a mensagem deixa claro que isso **não assegura** a existência de sequência viável de dois anos e que o NSGA-II pode não ter localizado uma solução. Não atribui automaticamente a falha à geada, à chuva ou ao calendário sem evidências.

## Estrutura da resposta

HTTP 422 com `detail.mensagem` e `detail.diagnostico`: `tipo`, `titulo`, `resumo`, `verificacoes[]` (com `codigo`, `titulo`, `detalhe` e `resultado`), `orientacoes[]` e `limitacao`. Os demais erros da API continuam com o formato anterior (`detail` string ou lista de validação).

## Arquivos alterados

- `backend/app/rotacao.py`: diagnóstico sem alterar fórmulas ou restrições de otimização.
- `backend/app/main.py`: serialização estruturada do erro de inviabilidade.
- `frontend/src/lib/api.js` e **novo** `frontend/src/lib/erros.js`: preservam os campos do diagnóstico.
- `frontend/src/components/ui.jsx`: painel explicativo e ações de correção.
- **Novos testes**: `backend/tests/test_diagnostico_inviabilidade.py`, `frontend/src/lib/erros.test.js`.

## Testes nesta edição

- `PYTHONPATH=backend python -m pytest backend/tests/test_diagnostico_inviabilidade.py -q`: **5 passaram**.
- `cd frontend && npm test`: **23 passaram**.
- Sintaxe Python: `compileall` sem erros.
- A suíte completa do backend **não foi executada** neste ambiente porque `pymoo` não está instalado.
- `npm ci --offline` não pôde concluir porque o cache local não contém `yallist-3.1.1.tgz`; portanto, **o build Vite não foi validado neste ambiente**.

## Verificação no Windows

Na raiz do projeto, com `.venv` configurado:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
cd frontend
npm ci
npm test
npm run build
```

Para conferir o diagnóstico, com o backend e frontend em execução, analise uma localização com restrições climáticas severas (ex.: ponto remoto no norte do Canadá), após confirmar os dados agrícolas. Verifique se o painel mostra os motivos **realmente detectados** e oferece o botão **Revisar propriedade e culturas**. Caso as janelas sejam individualmente possíveis, o sistema deve informar que a causa exata da ausência de solução **não foi determinada**, não inventar uma justificativa.
