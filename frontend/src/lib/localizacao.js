// Regras de troca de localização da propriedade (funções puras, testadas em localizacao.test.js).

export const SEM_LOCAL = 'Localização não identificada'
export const FONTE_USUARIO = 'informado pelo usuário'

const TOL = 1e-4

export function coordsIguais(a, b, tol = TOL) {
  if (!a || !b) return false
  return Math.abs(Number(a.lat) - Number(b.lat)) <= tol && Math.abs(Number(a.lon) - Number(b.lon)) <= tol
}

export function coordsValidas(lat, lon) {
  return Number.isFinite(lat) && Number.isFinite(lon) && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180
}

export function rotuloLocal(p) {
  const partes = [p?.regiao, p?.pais].filter((x) => x && String(x).trim())
  return partes.length ? partes.join(', ') : SEM_LOCAL
}

/** Dados de manejo que foram informados para o local anterior e precisam ser revistos. */
function itensParaRevisar(f) {
  const itens = []
  const solo = f.solo || {}
  if (['textura', 'profundidade_cm', 'materia_organica_pct', 'ph'].some((k) => solo[k] !== null && solo[k] !== undefined && solo[k] !== '')) itens.push('dados de solo')
  if (f.rotacao_atual?.length) itens.push('culturas e calendário da rotação atual (meses de semeadura)')
  if (f.historico && f.historico.trim()) itens.push('histórico de plantio')
  if (f.culturas_permitidas?.length) itens.push('lista de culturas permitidas')
  if (f.declividade_pct !== null && f.declividade_pct !== undefined && f.declividade_pct !== '') itens.push('declividade')
  if (Number(f.irrigacao_mm_ano) > 0) itens.push('água disponível para irrigação')
  return itens
}

/**
 * Aplica novas coordenadas. Descarta município/região/país do local anterior (não são válidos para o novo ponto),
 * desmarca "demonstrativa" e, se o nome for o da propriedade demonstrativa, limpa o nome para o usuário definir outro.
 * Nome de propriedade real nunca é alterado.
 */
export function trocarLocalizacao(f, lat, lon, { nomeDemo } = {}) {
  const la = Number(Number(lat).toFixed(4))
  const lo = Number(Number(lon).toFixed(4))
  if (!coordsValidas(la, lo)) return { f, aviso: null }
  if (coordsIguais(f, { lat: la, lon: lo })) return { f: { ...f, lat: la, lon: lo }, aviso: null }
  // Só o nome demonstrativo é limpo. Se o usuário já deu outro nome (mesmo partindo da demonstração), ele é mantido.
  const nomeEhDemo = nomeDemo ? f.nome === nomeDemo : Boolean(f.demonstrativa)
  const novo = {
    ...f, lat: la, lon: lo, regiao: null, pais: null, localidade_fonte: null, demonstrativa: false,
    nome: nomeEhDemo ? '' : f.nome,
    // a declividade era do terreno anterior; SRTM é consultado de novo para o novo ponto
    declividade_pct: null,
  }
  const aviso = {
    de: { lat: f.lat, lon: f.lon, local: rotuloLocal(f) },
    revisar: itensParaRevisar(f),
    nomeLimpo: Boolean(nomeEhDemo),
  }
  return { f: novo, aviso }
}

/** Aplica o resultado da geocodificação só se ele for das coordenadas atuais e o usuário não tiver digitado o local. */
export function aplicarGeocodificacao(f, geo, coordsConsultadas) {
  if (!geo || !geo.identificado) return f
  if (!coordsIguais(f, coordsConsultadas)) return f
  if (f.localidade_fonte === FONTE_USUARIO) return f
  const regiao = [geo.municipio, geo.regiao].filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).join(' – ') || null
  return { ...f, regiao, pais: geo.pais || null, localidade_fonte: geo.fonte }
}

/** Uma análise só pode ser exibida se foi calculada para as mesmas coordenadas da propriedade ativa. */
export function analiseCorresponde(analise, prop) {
  return Boolean(analise && prop && coordsIguais(analise.propriedade, prop))
}

export function nomeValido(f) {
  return Boolean(f?.nome && String(f.nome).trim())
}
