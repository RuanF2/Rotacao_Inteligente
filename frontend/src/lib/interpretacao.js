/** Helpers puros, sem alterar a modelagem científica existente. */
export const ROTULO_PERDA_AGUA = 'Perda potencial por falta de água'
export const ROTULO_INDICE_AGUA_FRIO = 'Índice água e adequação térmica'
export function haExposicaoTermica(avaliacao) {
  return (avaliacao?.slots || []).some((s) => (s.fracao_dias_frio || 0) >= 0.05 || (s.fracao_dias_calor || 0) >= 0.05)
}
export function requerAlertaAgronomico(avaliacao) {
  return avaliacao?.restricoes?.viavel === false || haExposicaoTermica(avaliacao)
}
export function ausenciaPerdaHidricaNaoGaranteSeguranca(avaliacao) {
  return requerAlertaAgronomico(avaliacao) && (avaliacao?.slots || []).some((s) => s.perda_rendimento_media === 0)
}
