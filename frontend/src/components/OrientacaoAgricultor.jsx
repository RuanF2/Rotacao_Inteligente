import { requerAlertaAgronomico } from '../lib/interpretacao'
import { n, pct } from '../lib/format'
import { Badge, Panel } from './ui'

/** Apresentação acessível de resultados existentes, sem criar previsões ou alterar o modelo. */
export function AlertasTermicos({ avaliacao, referencia = false, compacto = false }) {
  const slots = avaliacao?.slots || []
  const expostos = slots.filter((s) => (s.fracao_dias_frio || 0) >= 0.05 || (s.fracao_dias_calor || 0) >= 0.05)
  const inviavel = avaliacao?.restricoes?.viavel === false
  if (!requerAlertaAgronomico(avaliacao)) return null
  const alerta = <div role="alert" className="rounded-md border border-clay/40 bg-[#fff5f0] px-4 py-3 text-sm text-[#743024]">
    <strong>Alerta de adequação do plantio:</strong> {referencia && 'A rotação atual é apenas uma referência de comparação, não uma recomendação de plantio. '}
    {inviavel && 'Esta sequência não atende a todas as restrições agronômicas do modelo. '}
    {expostos.map((s, i) => <div key={i} className="mt-1">{s.nome}: frio/geada em {pct(s.fracao_dias_frio || 0)} dos dias avaliados; calor excessivo em {pct(s.fracao_dias_calor || 0)}.</div>)}
    <div className="mt-1">Uma perda potencial por falta de água de 0% <b>não significa colheita segura</b>: o modelo não quantifica perdas de produção por geada, doenças ou outros fatores.</div>
  </div>
  if (!compacto || inviavel || referencia) return alerta
  return <details className="rounded-md border border-clay/30 bg-[#fff8f4] px-3 py-2 text-sm text-[#743024]"><summary className="cursor-pointer font-semibold">{expostos.length} cultura(s) com alerta de frio ou calor — abrir detalhes</summary><div className="mt-2">{alerta}</div></details>
}

export function DetalhesTecnicos({ children, titulo = 'Ver detalhes técnicos e metodologia' }) {
  return <details className="mb-8 rounded-lg border border-line bg-white px-4 py-3">
    <summary className="cursor-pointer select-none font-semibold text-ink focus-visible:outline-2">{titulo}</summary>
    <div className="mt-5 border-t border-line pt-5">{children}</div>
  </details>
}

export function OrientacaoAgricultor({ analise, ir }) {
  const estrategias = analise?.estrategias || []
  const selecionada = estrategias.find((e) => e.chave === 'D' && e.avaliacao?.restricoes?.viavel !== false)
    || estrategias.find((e) => e.chave !== 'A' && e.avaliacao?.restricoes?.viavel !== false)
  const base = estrategias.find((e) => e.chave === 'A')
  if (!selecionada) return <Panel><p className="font-semibold text-clay">Nenhuma alternativa elegível foi encontrada.</p><p className="text-sm text-stone">Revise as culturas, a época de plantio e as restrições com assistência técnica local.</p></Panel>
  const av = selecionada.avaliacao
  const slots = av.slots || []
  return <section aria-label="Orientação prática" className="mb-8 rounded-xl border border-field/30 bg-field-soft/50 p-4 sm:p-6">
    <div className="mb-3 flex flex-wrap items-center gap-2"><Badge color="#3f7d4e">Orientação para o agricultor</Badge><span className="text-xs text-stone">Estimativa do modelo, não recomendação agronômica definitiva</span></div>
    <h2 className="text-xl font-bold text-ink">Uma opção conforme as prioridades informadas</h2>
    <p className="mt-1 text-sm text-stone">Estratégia {selecionada.chave} — {selecionada.titulo}. Existem outras alternativas válidas, com diferentes vantagens em água, solo e diversidade.</p>
    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <div className="rounded-md bg-white p-4"><div className="text-sm font-semibold text-ink">O que plantar e quando</div><ol className="mt-2 space-y-1 text-sm">{slots.map((s,i)=><li key={i}><b>{s.nome}</b> — {s.mes_nome}, ano {s.ano}</li>)}</ol></div>
      <div className="rounded-md bg-white p-4"><div className="text-sm font-semibold text-ink">Água das culturas</div><div className="mt-2 text-sm">Necessidade estimada: <b>{n(av.indicadores.etc_total_mm_ano)} mm/ano</b></div><div className="mt-1 text-sm">Água não atendida: <b>{n(av.objetivos.demanda_irrigacao_mm_ano)} mm/ano</b></div><p className="mt-2 text-xs text-stone">Média simulada na série histórica, não consumo medido na fazenda.</p></div>
      <div className="rounded-md bg-white p-4 sm:col-span-2 xl:col-span-1"><div className="text-sm font-semibold text-ink">Por que considerar esta opção?</div><p className="mt-2 text-sm">{selecionada.explicacao?.objetivo}</p><p className="mt-2 text-xs text-stone">Compare com o manejo atual antes de decidir; benefício potencial não é garantia de produção.</p></div>
    </div>
    <div className="mt-4"><AlertasTermicos avaliacao={av}/>{base?.avaliacao?.restricoes?.viavel === false && <p className="mt-3 text-sm font-semibold text-clay">Atenção: o plantio atual informado não passa nas restrições agronômicas e não deve ser interpretado como opção segura.</p>}</div>
    {(selecionada.explicacao?.riscos || []).length > 0 && <details className="mt-4 rounded bg-white px-4 py-3"><summary className="cursor-pointer font-semibold text-ink">Cuidados e limitações antes de plantar</summary><ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-stone">{selecionada.explicacao.riscos.slice(0, 7).map((r,i)=><li key={i}>{r}</li>)}</ul></details>}
    {ir && <button type="button" onClick={() => ir('rotacao')} className="mt-4 rounded-md border border-field bg-white px-4 py-2 text-sm font-semibold text-field hover:bg-field-soft">Comparar todas as estratégias</button>}
  </section>
}
