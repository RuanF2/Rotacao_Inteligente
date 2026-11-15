/** Mantém o diagnóstico estruturado do backend sem convertê-lo em [object Object]. */
export function interpretarErro(corpo, status) {
  let detalhe = corpo && typeof corpo === 'object' && corpo.detail ? corpo.detail : `Erro ${status}`
  if (Array.isArray(detalhe)) {
    detalhe = detalhe.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ')
  }
  if (detalhe && typeof detalhe === 'object' && detalhe.diagnostico) {
    const erro = new Error(detalhe.mensagem || 'Nenhuma rotação viável foi encontrada.')
    erro.diagnostico = detalhe.diagnostico
    return erro
  }
  return new Error(typeof detalhe === 'string' ? detalhe : JSON.stringify(detalhe))
}
