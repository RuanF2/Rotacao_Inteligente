import { CLASSE_COR } from '../lib/format'
import { analiseCorresponde } from '../lib/localizacao'

export function Section({ title, aside, children, className = '' }) {
  return (
    <section className={`mb-10 ${className}`}>
      {(title || aside) && (
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-2">
          {title && <h2 className="text-lg font-bold text-ink">{title}</h2>}
          {aside && <div className="text-sm text-stone">{aside}</div>}
        </div>
      )}
      {children}
    </section>
  )
}

export function Panel({ children, className = '' }) {
  return <div className={`rounded-md border border-line bg-white p-4 ${className}`}>{children}</div>
}

export function Metric({ label, value, unit, hint, tone = 'ink' }) {
  const cor = { ink: 'text-ink', sky: 'text-sky', clay: 'text-clay', field: 'text-field' }[tone]
  return (
    <div>
      <div className="text-sm text-stone">{label}</div>
      <div className={`num text-3xl font-semibold ${cor}`}>
        {value}
        {unit && <span className="ml-1 text-base font-normal text-stone">{unit}</span>}
      </div>
      {hint && <div className="mt-0.5 text-xs text-stone">{hint}</div>}
    </div>
  )
}

export function Badge({ children, color = '#6B7570', solid = false }) {
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium"
      style={solid ? { background: color, color: 'white' } : { color, background: `${color}18`, border: `1px solid ${color}40` }}
    >
      {children}
    </span>
  )
}

export function ClasseBadge({ classe }) {
  return <Badge color={CLASSE_COR[classe] || '#6B7570'} solid>{classe}</Badge>
}

export function NatureBadge({ tipo }) {
  const m = {
    observado: ['Observado', '#2F6690'],
    modelo: ['Estimativa de modelo', '#B7791F'],
    hipotetico: ['Hipotético', '#A23B2A'],
    demonstrativo: ['Demonstrativo', '#6B7570'],
  }[tipo]
  return <Badge color={m[1]}>{m[0]}</Badge>
}

export function Loader({ text = 'Calculando…' }) {
  return (
    <div className="flex items-center gap-3 py-10 text-stone" role="status">
      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-line border-t-field" />
      {text}
    </div>
  )
}

export function ErrorBox({ error, onRetry, onConfigure }) {
  if (!error) return null
  const diagnostico = error.diagnostico
  if (diagnostico?.tipo === 'sem_estrategia_viavel') return (
    <section className="my-5 rounded-lg border border-ochre/50 bg-[#fbf5ea] p-5 text-sm text-ink" role="alert" aria-labelledby="titulo-inviabilidade">
      <div className="mb-2 text-lg font-bold" id="titulo-inviabilidade">{diagnostico.titulo}</div>
      <p className="mb-4">{diagnostico.resumo}</p>
      <h3 className="font-semibold">O que foi possível verificar</h3>
      <ul className="mt-2 space-y-3">
        {(diagnostico.verificacoes || []).map((v) => (
          <li key={v.codigo} className="rounded-md border border-line bg-white p-3">
            <div className="flex flex-wrap items-center gap-2">
              <b>{v.titulo}</b>
              <span className={`rounded px-2 py-0.5 text-xs ${v.resultado === 'bloqueio_confirmado' ? 'bg-clay/10 text-clay' : 'bg-field-soft text-ink'}`}>
                {v.resultado === 'bloqueio_confirmado' ? 'Bloqueio identificado' :
                 v.resultado === 'restricao_parcial' ? 'Restringe algumas opções' :
                 v.resultado === 'nao_conclusivo' ? 'Causa não determinada' : 'Informação da análise'}
              </span>
            </div>
            <p className="mt-1 text-stone">{v.detalhe}</p>
          </li>
        ))}
      </ul>
      <h3 className="mt-5 font-semibold">O que você pode revisar</h3>
      <ul className="mt-2 list-disc space-y-1 pl-5">{(diagnostico.orientacoes || []).map((o, i) => <li key={i}>{o}</li>)}</ul>
      <p className="mt-4 text-xs text-stone">{diagnostico.limitacao}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {onConfigure && <Button onClick={onConfigure}>Revisar propriedade e culturas</Button>}
        {onRetry && <Button variant="ghost" onClick={onRetry}>Tentar novamente</Button>}
      </div>
    </section>
  )
  return (
    <div className="my-4 rounded-md border border-clay/40 bg-clay/5 p-4 text-sm text-clay" role="alert">
      <div className="font-semibold">Não foi possível concluir a operação.</div>
      <div className="mt-1 text-[#5a2a20]">{String(error.message || error)}</div>
      {onRetry && <button onClick={onRetry} className="mt-2 underline">Tentar novamente</button>}
    </div>
  )
}

export function EmptyState({ title, text, action }) {
  return (
    <div className="rounded-md border border-dashed border-line p-10 text-center">
      <div className="text-lg font-semibold text-ink">{title}</div>
      <p className="mx-auto mt-1 max-w-md text-stone">{text}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Button({ children, variant = 'primary', className = '', ...p }) {
  const v = {
    primary: 'bg-field text-white hover:bg-ink',
    ghost: 'border border-line bg-white text-ink hover:border-field',
    danger: 'border border-clay/40 bg-white text-clay hover:bg-clay/5',
  }[variant]
  return (
    <button className={`rounded-md px-3.5 py-2 text-sm font-semibold transition-colors disabled:opacity-50 ${v} ${className}`} {...p}>
      {children}
    </button>
  )
}

/** Escala 0–1 com as quatro faixas de vulnerabilidade e um marcador. */
export function VulnScale({ value }) {
  const zonas = [['baixa', 0.25], ['moderada', 0.25], ['alta', 0.25], ['crítica', 0.25]]
  return (
    <div>
      <div className="relative flex h-3 overflow-hidden rounded-sm">
        {zonas.map(([c, w]) => <div key={c} style={{ width: `${w * 100}%`, background: CLASSE_COR[c], opacity: 0.85 }} />)}
        {value != null && (
          <div className="absolute -top-1 h-5 w-1 rounded bg-ink ring-2 ring-white" style={{ left: `calc(${value * 100}% - 2px)` }} />
        )}
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-stone">
        <span>0 baixa</span><span>0,25</span><span>0,50</span><span>0,75</span><span>1 crítica</span>
      </div>
    </div>
  )
}

export function PageHeader({ title, children, actions }) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight text-ink" style={{ fontStretch: '88%' }}>{title}</h1>
        {children && <p className="mt-1 max-w-3xl text-stone">{children}</p>}
      </div>
      {actions && <div className="no-print flex gap-2">{actions}</div>}
    </header>
  )
}

export function AnaliseGate({ analise, carregando, erro, analisar, prop, ir, children }) {
  if (carregando) return <Loader text="Baixando/lendo dados NASA POWER, calculando vulnerabilidade e otimizando rotações (NSGA-II)…" />
  if (erro) return <ErrorBox error={erro} onRetry={() => analisar(prop)} onConfigure={() => ir('propriedade')} />
  if (analise && !analiseCorresponde(analise, prop)) return (
    <EmptyState title="Resultados de outra localização" text="A análise disponível foi calculada para outras coordenadas. Rode a análise para a propriedade atual."
      action={<Button onClick={() => analisar(prop)}>Analisar propriedade</Button>} />
  )
  if (!analise) return (
    <EmptyState title="Nenhuma análise ainda" text="Configure a propriedade e rode a análise para ver os resultados."
      action={<Button onClick={() => ir('propriedade')}>Configurar propriedade</Button>} />
  )
  return children
}
