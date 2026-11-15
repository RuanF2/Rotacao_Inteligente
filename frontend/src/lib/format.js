export const MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
export const MESES_INICIAL = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']

export function n(v, casas = 0, suf = '') {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas }) + suf
}
export const pct = (v, casas = 0) => (v === null || v === undefined ? '—' : n(v * 100, casas, '%'))

// Cores por família botânica: são categorias de dado (legenda na faixa de rotação).
export const FAMILIAS = {
  Poaceae: { cor: '#C79A2E', nome: 'Gramíneas (Poaceae)' },
  Fabaceae: { cor: '#3F7D4E', nome: 'Leguminosas (Fabaceae)' },
  Pedaliaceae: { cor: '#8C6A4A', nome: 'Pedaliáceas (gergelim)' },
  Asteraceae: { cor: '#C8642E', nome: 'Asteráceas (girassol)' },
}

export const CORES_ESTRATEGIA = { A: '#6B7570', B: '#3F7D4E', C: '#2F6690', D: '#B7791F' }

export const CLASSE_COR = {
  baixa: '#3F7D4E', moderada: '#B7991F', alta: '#C8642E', 'crítica': '#A23B2A', 'dados insuficientes': '#6B7570',
}
