import { interpretarErro } from './erros'
const BASE = import.meta.env.VITE_API_URL || ''

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, { headers: { 'Content-Type': 'application/json' }, ...opts })
  const texto = await r.text()
  let corpo = texto
  try { corpo = JSON.parse(texto) } catch { /* texto puro (relatório) */ }
  if (!r.ok) throw interpretarErro(corpo, r.status)
  return corpo
}

export const api = {
  demo: () => req('/api/demo'),
  culturas: () => req('/api/culturas'),
  locais: () => req('/api/locais'),
  camadas: () => req('/api/camadas'),
  geocodificar: (lat, lon) => req(`/api/geocodificar?lat=${lat}&lon=${lon}`),
  fontes: (lat, lon) => req(`/api/fontes?lat=${lat}&lon=${lon}`),
  analise: (p) => req('/api/analise', { method: 'POST', body: JSON.stringify(p) }),
  simulacao: (b) => req('/api/simulacao', { method: 'POST', body: JSON.stringify(b) }),
  relatorio: (p) => req('/api/relatorio', { method: 'POST', body: JSON.stringify(p) }),
  mapaPontos: () => req('/api/mapa/pontos'),
  listarProps: () => req('/api/propriedades'),
  salvarProp: (p, id) => req(id ? `/api/propriedades/${id}` : '/api/propriedades', { method: id ? 'PUT' : 'POST', body: JSON.stringify(p) }),
  obterProp: (id) => req(`/api/propriedades/${id}`),
  excluirProp: (id) => req(`/api/propriedades/${id}`, { method: 'DELETE' }),
}
