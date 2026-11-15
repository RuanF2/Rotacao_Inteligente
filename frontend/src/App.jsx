import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './lib/api'
import { n } from './lib/format'
import { rotuloLocal } from './lib/localizacao'
import Dashboard from './pages/Dashboard'
import Propriedade from './pages/Propriedade'
import Ambiental from './pages/Ambiental'
import Rotacao from './pages/Rotacao'
import Simulador from './pages/Simulador'
import Relatorio from './pages/Relatorio'

const PAGINAS = [
  ['dashboard', 'Painel'],
  ['propriedade', 'Propriedade'],
  ['ambiental', 'Análise ambiental'],
  ['rotacao', 'Rotação inteligente'],
  ['simulador', 'Simulador climático'],
  ['relatorio', 'Relatório'],
]
const CHAVE_LOCAL = 'rotacao2.propriedade'

function lerLocal() {
  try { return JSON.parse(localStorage.getItem(CHAVE_LOCAL)) } catch { return null }
}

export default function App() {
  const [pagina, setPagina] = useState(() => (location.hash.slice(1) || 'dashboard'))
  const [prop, setProp] = useState(null)
  const [demo, setDemo] = useState(null)
  const [culturas, setCulturas] = useState({})
  const [catalogo, setCatalogo] = useState([])
  const [camadas, setCamadas] = useState(null)
  const [pontos, setPontos] = useState([])
  const [analise, setAnalise] = useState(null)
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState(null)
  const [erroInicial, setErroInicial] = useState(null)
  const [sim, setSim] = useState(null)

  const ir = (p) => { setPagina(p); location.hash = p; window.scrollTo(0, 0) }
  useEffect(() => {
    const f = () => setPagina(location.hash.slice(1) || 'dashboard')
    window.addEventListener('hashchange', f)
    return () => window.removeEventListener('hashchange', f)
  }, [])

  const pedido = useRef(0)
  const analisar = useCallback(async (p) => {
    // Resultados anteriores são descartados ANTES de calcular: nada de outra localização fica na tela
    // durante a nova análise nem depois de uma falha. Respostas fora de ordem são ignoradas.
    const id = ++pedido.current
    setAnalise(null); setSim(null); setErro(null); setCarregando(true)
    try { localStorage.setItem(CHAVE_LOCAL, JSON.stringify(p)) } catch { /* armazenamento indisponível */ }
    try {
      const a = await api.analise(p)
      if (id === pedido.current) setAnalise(a)
    } catch (e) {
      if (id === pedido.current) setErro(e)
    } finally {
      if (id === pedido.current) setCarregando(false)
    }
  }, [])

  useEffect(() => {
    (async () => {
      try {
        const [d, c, cam] = await Promise.all([api.demo(), api.culturas(), api.camadas()])
        setDemo(d)
        setCatalogo(c.culturas)
        setCulturas(Object.fromEntries(c.culturas.map((x) => [x.id, x])))
        setCamadas(cam)
        const p = lerLocal() || d
        setProp(p)
        analisar(p)
        api.mapaPontos().then((r) => setPontos(r.pontos)).catch(() => {})
      } catch (e) { setErroInicial(e) }
    })()
  }, [analisar])

  const ctx = { prop, setProp, demo, culturas, catalogo, camadas, pontos, analise, carregando, erro, analisar, ir, sim, setSim }

  return (
    <div className="flex min-h-full flex-col lg:flex-row">
      <aside className="no-print bg-ink text-white lg:fixed lg:inset-y-0 lg:w-64">
        <div className="px-5 pb-4 pt-6">
          <div className="text-xl font-extrabold leading-tight" style={{ fontStretch: '85%' }}>Rotação Inteligente <span className="font-normal opacity-70">2.0</span></div>
          <div className="mt-1 text-sm text-white/60">Global Agricultural Intelligence</div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:overflow-visible" aria-label="Seções">
          {PAGINAS.map(([k, t]) => (
            <button key={k} onClick={() => ir(k)} aria-current={pagina === k ? 'page' : undefined}
              className={`whitespace-nowrap rounded-md px-3 py-2 text-left text-sm transition-colors ${pagina === k ? 'bg-white text-ink font-semibold' : 'text-white/80 hover:bg-ink-2'}`}>
              {t}
            </button>
          ))}
        </nav>
        {prop && (
          <div className="hidden border-t border-white/10 px-5 py-4 text-sm lg:block">
            <div className="text-white/60">Propriedade ativa</div>
            <div className="mt-0.5 font-semibold">{prop.nome}</div>
            <div className="text-white/70">{rotuloLocal(prop)}</div>
            <div className="num text-white/70">{n(prop.lat, 3)}, {n(prop.lon, 3)}</div>
            {prop.demonstrativa && <div className="mt-2 text-xs text-white/60">Dados de manejo demonstrativos; clima real NASA POWER.</div>}
          </div>
        )}
        <div className="hidden px-5 pb-6 text-xs text-white/50 lg:absolute lg:bottom-0 lg:block">
          NASA Space Apps Challenge 2026 — Field Shift: adaptando fazendas com dados da NASA.
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-3 py-5 sm:px-5 sm:py-8 lg:ml-64 lg:px-10">
        <div className="mx-auto w-full min-w-0 max-w-[1200px]">
          {erroInicial ? (
            <div className="rounded-md border border-clay/40 bg-clay/5 p-6 text-clay" role="alert">
              <div className="text-lg font-semibold">O servidor da análise não respondeu.</div>
              <p className="mt-1 text-[#5a2a20]">Inicie o backend (pasta backend: <code>./run_backend.sh</code>) e recarregue a página. Detalhe: {String(erroInicial.message)}</p>
            </div>
          ) : !prop ? null : (
            <>
              {pagina === 'dashboard' && <Dashboard {...ctx} />}
              {pagina === 'propriedade' && <Propriedade {...ctx} />}
              {pagina === 'ambiental' && <Ambiental {...ctx} />}
              {pagina === 'rotacao' && <Rotacao {...ctx} />}
              {pagina === 'simulador' && <Simulador {...ctx} />}
              {pagina === 'relatorio' && <Relatorio {...ctx} />}
            </>
          )}
          <footer className="no-print mt-16 border-t border-line pt-4 text-xs text-stone">
            Ferramenta de apoio à decisão. Não substitui o julgamento do agricultor nem a orientação de especialistas locais.
          </footer>
        </div>
      </main>
    </div>
  )
}
