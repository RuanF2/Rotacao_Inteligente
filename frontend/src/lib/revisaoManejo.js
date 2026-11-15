/** Confirmação local, por coordenada e por conjunto de dados agrícolas. Não altera o modelo. */
export const CHAVE_REVISAO_MANEJO = 'rotacao2.manejo-confirmado-v1'

function numeroOuNull(v) { return v === '' || v === undefined || v === null ? null : Number(v) }

export function assinaturaManejo(p) {
  if (!p) return ''
  return JSON.stringify({
    lat: Number(Number(p.lat).toFixed(4)), lon: Number(Number(p.lon).toFixed(4)),
    solo: p.solo ? {
      textura: p.solo.textura || null,
      profundidade_cm: numeroOuNull(p.solo.profundidade_cm),
      materia_organica_pct: numeroOuNull(p.solo.materia_organica_pct),
      ph: numeroOuNull(p.solo.ph),
    } : null, rotacao: (p.rotacao_atual || []).map((r) => ({ cultura: r.cultura, ano: Number(r.ano), mes: Number(r.mes) })),
    historico: p.historico || '', culturas: p.culturas_permitidas || null,
    irrigacao: Number(p.irrigacao_mm_ano || 0), fonte: p.fonte_agua || '',
  })
}

export function precisaRevisarManejo(p, demo, assinaturaConfirmada) {
  if (!p) return false
  const pontoDemonstrativo = Boolean(p.demonstrativa && demo &&
    Math.abs(Number(p.lat) - Number(demo.lat)) <= 0.0001 &&
    Math.abs(Number(p.lon) - Number(demo.lon)) <= 0.0001)
  if (pontoDemonstrativo) return false
  return assinaturaConfirmada !== assinaturaManejo(p)
}

export function avisoIndiceTermico() {
  return 'O subíndice térmico regional mede apenas dias de calor intenso (Tmax ≥ 35 °C). Não mede geadas nem substitui os alertas de frio de cada cultura e época de plantio.'
}
