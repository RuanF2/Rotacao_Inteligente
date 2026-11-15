# Revisão final adicional — manejo, risco térmico, alertas e relatório

## Mudanças
1. Confirmação explícita dos dados de manejo para locais não demonstrativos. A assinatura local considera coordenadas, solo, rotação, histórico, culturas e irrigação; mudar esses dados exige nova confirmação. Sem confirmação, analisar/salvar é bloqueado. A confirmação é registrada **somente neste navegador** em `localStorage`, sem modificar o esquema ou a lógica do backend. O usuário deve confirmar os valores ou reconhecer conscientemente que são demonstrativos. Os dados não são inventados nem apagados automaticamente.
2. Esclarecido no Painel e na Análise ambiental que o subíndice térmico regional refere-se exclusivamente a calor extremo ≥ 35 °C, não a geadas. O alerta por cultura continua separado.
3. Na Rotação, avisos agronômicos permanecem abertos na rotação atual, quando inválida e na estratégia selecionada; avisos de outras estratégias válidas ficam expansíveis para reduzir repetição, sem omitir informações.
4. Inserido resumo executivo antes do relatório técnico, usando exclusivamente os resultados existentes (estratégia D quando viável, ou outra alternativa viável; calendário, água, benefícios, riscos e ressalvas de frio). O resumo acompanha tanto o PDF impresso quanto o Markdown.

## Limitações
- Confirmar dados locais é uma declaração do usuário; não verifica o solo ou valida a rotação em campo.
- O modelo de perda potencial quantifica déficit hídrico, não produção total afetada por geada/doença.
- A confirmação é local ao navegador: ao trocar de dispositivo ou limpar dados, precisa confirmar novamente.
- Não houve alteração de algoritmos, parâmetros agronômicos, otimização ou fontes NASA.

## Testar no Windows
Na raiz do projeto: `.\.venv\Scripts\python.exe -m pytest backend\tests -q`. No frontend: `npm test`, `npm run build`. No navegador: abrir uma localidade nova, tentar analisar antes de confirmar (deve bloquear), confirmar, analisar, alterar solo e verificar que pede nova confirmação. Revisar relatório e PDF.

## Verificações nesta execução
- Frontend: 20 testes unitários JavaScript aprovados (`node --test frontend/src/lib/*.test.js`), incluindo 4 novos testes da conferência do manejo e do escopo térmico.
- Backend: `test_resumo_executivo.py` aprovado sem depender de serviços externos ou do otimizador.
- Sintaxe JSX: arquivos `.jsx` verificados com parser TypeScript, **zero erros sintáticos**. Corrigido `>` literal antigo no `Dashboard.jsx`.
- Sintaxe Python: `python -m compileall -q backend/app` sem erros.
- **Não foi possível** executar a suíte completa do backend nesta máquina porque não há `pymoo` instalado; testes que chamam otimização falham por dependência ausente. O ambiente do usuário já havia passado em 53/53 antes desta revisão.
- **Não foi possível** executar `npm run build` nesta máquina porque `npm ci` não conseguiu obter os pacotes do registro npm. A compilação precisa ser repetida no Windows do usuário.
- Não houve auditoria manual do navegador/visual nesta execução.
