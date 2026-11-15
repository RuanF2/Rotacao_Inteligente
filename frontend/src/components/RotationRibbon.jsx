import { FAMILIAS, MESES_INICIAL, MESES } from '../lib/format'

/**
 * Faixa de rotação de 24 meses: o elemento visual central do produto.
 * Cada célula é um mês; a cor é a família botânica; listras = cultura de cobertura;
 * hachura cinza = solo em pousio. A altura do preenchimento mostra a cobertura efetiva.
 */
export default function RotationRibbon({ avaliacao, culturas, compact = false }) {
  const cal = avaliacao?.calendario || []
  const cob = avaliacao?.cobertura_mensal || []
  const inicio = new Set((avaliacao?.slots || []).map((s) => (s.ano - 1) * 12 + (s.mes - 1)))
  const h = compact ? 'h-7' : 'h-11'
  return (
    <div>
      <div className="flex gap-[2px]">
        {Array.from({ length: 24 }).map((_, i) => {
          const cid = cal[i]
          const c = cid ? culturas[cid] : null
          const cor = c ? FAMILIAS[c.familia]?.cor || '#999' : null
          const titulo = `${MESES[i % 12]} · ano ${i < 12 ? 1 : 2}: ${c ? `${c.nome} (cobertura efetiva ${Math.round((cob[i] || 0) * 100)}%)` : 'solo em pousio'}`
          return (
            <div key={i} title={titulo} className={`relative flex-1 ${h} ${i === 12 ? 'ml-1.5' : ''} overflow-hidden rounded-[3px] ${c ? '' : 'fallow'}`}
              style={c ? { background: `${cor}30` } : undefined}>
              {c && (
                <div className={`absolute inset-x-0 bottom-0 ${c.tipo === 'cobertura' ? 'cover-hatch' : ''}`}
                  style={{ height: `${Math.max(18, (cob[i] || 0) * 100)}%`, background: cor }} />
              )}
              {c && inicio.has(i) && !compact && (
                <span className="absolute left-0.5 top-0.5 z-10 text-[10px] font-bold leading-none text-ink">{c.nome.slice(0, 3)}</span>
              )}
            </div>
          )
        })}
      </div>
      {!compact && (
        <div className="mt-1 flex gap-[2px] text-[10px] text-stone">
          {Array.from({ length: 24 }).map((_, i) => (
            <div key={i} className={`flex-1 text-center ${i === 12 ? 'ml-1.5' : ''}`}>{MESES_INICIAL[i % 12]}</div>
          ))}
        </div>
      )}
    </div>
  )
}

export function RibbonLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-stone">
      {Object.values(FAMILIAS).map((f) => (
        <span key={f.nome} className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm" style={{ background: f.cor }} />{f.nome}</span>
      ))}
      <span className="flex items-center gap-1.5"><span className="cover-hatch h-3 w-3 rounded-sm bg-field" />cultura de cobertura</span>
      <span className="flex items-center gap-1.5"><span className="fallow h-3 w-3 rounded-sm border border-line" />pousio</span>
      <span>Altura da barra = cobertura efetiva do solo (ponderada pela água disponível). Ano 1 | Ano 2.</span>
    </div>
  )
}
