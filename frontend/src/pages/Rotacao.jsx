import { AlertasTermicos, DetalhesTecnicos } from '../components/OrientacaoAgricultor'
import { useMemo, useState } from 'react'
import { CartesianGrid, Legend, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import RotationRibbon, { RibbonLegend } from '../components/RotationRibbon'
import { AnaliseGate, Badge, PageHeader, Panel, Section } from '../components/ui'
import { CORES_ESTRATEGIA, n, pct } from '../lib/format'

const OBJ = [
  ['demanda_irrigacao_mm_ano', 'Água faltante', 'min', 'mm/ano', 0],
  ['vulnerabilidade_climatica', 'Vulnerabilidade', 'min', '0–1', 2],
  ['potencial_erosao', 'Erosão', 'min', '0–1', 2],
  ['melhoria_solo', 'Melhoria do solo', 'max', '0–1', 2],
  ['cobertura', 'Cobertura', 'max', '0–1', 2],
  ['diversificacao', 'Diversificação', 'max', '0–1', 2],
]

export default function Rotacao(props) {
  return (
    <>
      <PageHeader title="Rotação inteligente">
        Estratégias geradas por otimização multiobjetivo (NSGA-II) sobre o clima histórico do local e comparadas com a rotação atual no mesmo horizonte de 24 meses.
      </PageHeader>
      <AnaliseGate {...props}>{props.analise && <Conteudo {...props} />}</AnaliseGate>
    </>
  )
}

function Conteudo({ analise, culturas }) {
  const ests = analise.estrategias
  const [sel, setSel] = useState(ests[2]?.chave || 'B')
  const radar = useMemo(() => {
    const pts = analise.pareto
    return OBJ.map(([k, t, s]) => {
      const vals = pts.map((p) => p[k]).filter((x) => x != null)
      const lo = Math.min(...vals), hi = Math.max(...vals)
      const linha = { obj: t }
      ests.forEach((e) => {
        const v = e.avaliacao.objetivos[k]
        const z = hi - lo > 1e-9 ? (v - lo) / (hi - lo) : 0.5
        linha[e.chave] = s === 'min' ? 1 - z : z
      })
      return linha
    })
  }, [analise])
  const est = ests.find((e) => e.chave === sel)
  const opt = analise.otimizacao
  return (
    <>
      <div className="mb-6 rounded-lg border border-field/30 bg-field-soft/50 p-4 text-sm">
        <h2 className="text-lg font-bold text-ink">Escolha uma estratégia conforme seu objetivo</h2>
        <p className="mt-1">A é o plantio atual usado como comparação. B prioriza a proteção do solo, C a resiliência à falta de água e D considera os pesos que você informou. Nenhuma delas é a melhor em todas as situações.</p>
        <p className="mt-2 font-medium text-clay">Importante: “perda potencial por falta de água” não inclui perdas por frio ou geada; verifique sempre os alertas.</p>
      </div>
      <Section title="Estratégias lado a lado" aside={<RibbonLegend />}>
        <div className="space-y-4">
          {ests.map((e) => (
            <Panel key={e.chave} className={`cursor-pointer transition-colors ${sel === e.chave ? 'ring-2 ring-field' : 'hover:border-field'}`}>
              <button className="block w-full text-left" onClick={() => setSel(e.chave)} aria-pressed={sel === e.chave}>
                <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="num flex h-7 w-7 items-center justify-center rounded text-sm font-bold text-white" style={{ background: CORES_ESTRATEGIA[e.chave] }}>{e.chave}</span>
                  <span className="text-lg font-bold text-ink">{e.titulo}</span>
                  <span className="text-sm text-stone">{e.objetivo}</span>
                  {!e.avaliacao.restricoes.viavel && <Badge color="#A23B2A">não atende às restrições agronômicas</Badge>}
                </div>
                <RotationRibbon avaliacao={e.avaliacao} culturas={culturas} />
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
                  {e.avaliacao.slots.map((s, i) => (
                    <span key={i}><b className="text-ink">{s.nome}</b> <span className="text-stone">semeadura {s.mes_nome}/ano {s.ano} · {s.ciclo_dias} d · índice água e adequação térmica {pct(s.satisfacao_hidrica)} · perda potencial por falta de água {pct(s.perda_rendimento_media)}{s.ky_tabelado ? '' : ' (Ky assumido)'}</span></span>
                  ))}
                </div>
              </button>
              <div className="mt-3"><AlertasTermicos avaliacao={e.avaliacao} referencia={e.chave === 'A'} compacto={sel !== e.chave} /></div>
            </Panel>
          ))}
        </div>
      </Section>

      <DetalhesTecnicos titulo="Ver comparação numérica, gráficos e otimização">
      <Section title="Comparação de indicadores" aside={`Mesma série: ${ests[0].avaliacao.indicadores.periodo_avaliado.join('–')} · ${ests[0].avaliacao.indicadores.pares_de_anos_avaliados} pares sobrepostos = ${ests[0].avaliacao.indicadores.anos_safra_avaliados} observações de ano-safra`}>
        <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
          <div className="overflow-x-auto rounded-md border border-line bg-white">
            <table className="num w-full text-sm">
              <thead className="bg-field-soft text-left"><tr>
                <th className="px-3 py-2 font-sans">Indicador</th>
                {ests.map((e) => <th key={e.chave} className="px-3 py-2" style={{ color: CORES_ESTRATEGIA[e.chave] }}>{e.chave}</th>)}
              </tr></thead>
              <tbody>
                {OBJ.map(([k, t, s, u, d]) => {
                  const vals = ests.map((e) => e.avaliacao.objetivos[k])
                  const best = s === 'min' ? Math.min(...vals) : Math.max(...vals)
                  return (
                    <tr key={k} className="border-t border-line">
                      <td className="px-3 py-2 font-sans">{t} <span className="text-xs text-stone">({u}, {s === 'min' ? 'menor é melhor' : 'maior é melhor'})</span></td>
                      {ests.map((e) => { const v = e.avaliacao.objetivos[k]; return <td key={e.chave} className={`px-3 py-2 ${v === best ? 'font-bold text-field' : ''}`}>{n(v, d)}</td> })}
                    </tr>
                  )
                })}
                <tr className="border-t border-line"><td className="px-3 py-2 font-sans">Anos-safra com perda potencial por falta de água &gt; 50% <span className="text-xs text-stone">(FAO-33, alguma cultura comercial)</span></td>{ests.map((e) => <td key={e.chave} className="px-3 py-2">{pct(e.avaliacao.indicadores.risco_quebra_anos)}</td>)}</tr>
                <tr className="border-t border-line"><td className="px-3 py-2 font-sans">Necessidade de água das culturas (ETc)</td>{ests.map((e) => <td key={e.chave} className="px-3 py-2">{n(e.avaliacao.indicadores.etc_total_mm_ano)} mm/ano</td>)}</tr>
                <tr className="border-t border-line"><td className="px-3 py-2 font-sans">Meses com solo descoberto (de 24)</td>{ests.map((e) => <td key={e.chave} className="px-3 py-2">{e.avaliacao.indicadores.meses_solo_descoberto}</td>)}</tr>
                <tr className="border-t border-line"><td className="px-3 py-2 font-sans">Dívida Ambiental do Solo <span className="text-xs text-stone">(0–100, menor é melhor)</span></td>{ests.map((e) => <td key={e.chave} className="px-3 py-2 font-semibold">{n(e.avaliacao.das.valor)}</td>)}</tr>
                <tr className="border-t border-line"><td className="px-3 py-2 font-sans">Completude das evidências</td>{ests.map((e) => <td key={e.chave} className="px-3 py-2">{n(e.explicacao.confianca.valor)}/100</td>)}</tr>
              </tbody>
            </table>
          </div>
          <Panel>
            <div className="text-sm font-semibold text-ink">Perfil normalizado (1 = melhor do conjunto)</div>
            <ResponsiveContainer width="100%" height={360}>
              <RadarChart data={radar} outerRadius="62%" margin={{ top: 10, bottom: 10 }}>
                <PolarGrid stroke="#DCE2DD" />
                <PolarAngleAxis dataKey="obj" tick={{ fontSize: 11, fill: '#6B7570' }} />
                <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
                {ests.map((e) => <Radar key={e.chave} dataKey={e.chave} name={`${e.chave} ${e.titulo}`} stroke={CORES_ESTRATEGIA[e.chave]} fill={CORES_ESTRATEGIA[e.chave]} fillOpacity={e.chave === sel ? 0.25 : 0.03} strokeWidth={e.chave === sel ? 2.5 : 1.2} />)}
                <Legend verticalAlign="bottom" wrapperStyle={{ fontSize: 11, paddingTop: 12 }} />
              </RadarChart>
            </ResponsiveContainer>
          </Panel>
        </div>
      </Section>

      </DetalhesTecnicos>
      <Section title={`Por que a estratégia ${est.chave} — ${est.titulo}?`}>
        <Explicacao e={est} />
      </Section>

      <DetalhesTecnicos titulo="Ver fronteira de Pareto (detalhes da otimização)">
      <Section title="Fronteira de Pareto" aside={`${opt.algoritmo} · população ${opt.pop} · ${opt.geracoes} gerações · ${opt.n_avaliacoes} avaliações · ${opt.n_viaveis} soluções viáveis · ${opt.n_pareto} não dominadas`}>
        <Panel>
          <ResponsiveContainer width="100%" height={340}>
            <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
              <CartesianGrid stroke="#DCE2DD" />
              <XAxis type="number" dataKey="demanda_irrigacao_mm_ano" name="Água faltante" unit=" mm" tick={{ fontSize: 12 }} label={{ value: 'Água faltante (mm/ano)', position: 'insideBottom', offset: -10, fontSize: 12 }} />
              <YAxis type="number" dataKey="vulnerabilidade_climatica" name="Vulnerabilidade" tick={{ fontSize: 12 }} domain={[0, 'auto']} label={{ value: 'Vulnerabilidade', angle: -90, position: 'insideLeft', fontSize: 12 }} />
              <ZAxis type="number" dataKey="melhoria_solo" range={[30, 220]} name="Melhoria do solo" />
              <Tooltip content={<TipPareto />} />
              <Scatter data={analise.pareto.filter((p) => !p.estrategia)} fill="#9FB3A6" fillOpacity={0.6} name="Outras soluções não dominadas" isAnimationActive={false} />
              {['A', 'B', 'C', 'D'].map((k) => <Scatter key={k} data={analise.pareto.filter((p) => p.estrategia === k)} fill={CORES_ESTRATEGIA[k]} name={k === "A" ? "Rotação atual (A, referência)" : `Estratégia ${k}`} shape="diamond" isAnimationActive={false} />)}
              <Legend verticalAlign="top" wrapperStyle={{ fontSize: 12 }} />
            </ScatterChart>
          </ResponsiveContainer>
          <p className="text-sm text-stone">Cada ponto é uma rotação que não pode melhorar um objetivo sem piorar outro. O tamanho representa o potencial de melhoria do solo. B = melhor média de solo/cobertura/erosão; C = melhor média de água/vulnerabilidade; D = soma ponderada pelas suas prioridades. Potencial econômico não foi otimizado por falta de preços e produtividades locais confiáveis.</p>
        </Panel>
      </Section>
      </DetalhesTecnicos>
    </>
  )
}

function TipPareto({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="max-w-xs rounded border border-line bg-white p-2 text-xs shadow">
      {p.estrategia && <div className="font-bold">Estratégia {p.estrategia}</div>}
      <div className="mb-1 text-ink">{p.rotulo}</div>
      <div>Água faltante {n(p.demanda_irrigacao_mm_ano)} mm · vulnerabilidade {n(p.vulnerabilidade_climatica, 2)}</div>
      <div>Solo {n(p.melhoria_solo, 2)} · cobertura {n(p.cobertura, 2)} · erosão {n(p.potencial_erosao, 2)} · DAS {n(p.das)}</div>
    </div>
  )
}

const ABAS = [['por_que', 'Por que foi sugerida'], ['evidencias', 'Evidências'], ['beneficios', 'Benefícios esperados'], ['riscos', 'Riscos'], ['confianca', 'Confiança'], ['ausentes', 'Informações ausentes']]

function Explicacao({ e }) {
  const [aba, setAba] = useState('por_que')
  const ex = e.explicacao
  const c = ex.confianca
  return (
    <Panel className="p-0">
      <div className="flex flex-wrap border-b border-line" role="tablist">
        {ABAS.map(([k, t]) => (
          <button key={k} role="tab" aria-selected={aba === k} onClick={() => setAba(k)}
            className={`px-4 py-2.5 text-sm ${aba === k ? 'border-b-2 border-field font-semibold text-ink' : 'text-stone hover:text-ink'}`}>{t}</button>
        ))}
      </div>
      <div className="p-5">
        {aba === 'por_que' && <Lista itens={ex.por_que} />}
        {aba === 'beneficios' && <><Lista itens={ex.beneficios} /><p className="mt-3 text-xs text-stone">Benefícios potenciais estimados por modelo; não são resultados garantidos nem validados em campo.</p></>}
        {aba === 'riscos' && <Lista itens={ex.riscos} />}
        {aba === 'ausentes' && <Lista itens={ex.informacoes_ausentes} />}
        {aba === 'evidencias' && (
          <table className="w-full text-sm">
            <thead className="text-left text-stone"><tr><th className="pb-2 font-medium">Indicador</th><th className="pb-2 font-medium">Valor</th><th className="pb-2 font-medium">Fonte</th><th className="pb-2 font-medium">Período</th></tr></thead>
            <tbody>{ex.evidencias.map((v, i) => (
              <tr key={i} className="border-t border-line"><td className="py-1.5 pr-3">{v.indicador}</td><td className="num py-1.5 pr-3">{typeof v.valor === 'number' ? n(v.valor) : v.valor} <span className="text-stone">{v.unidade}</span></td><td className="py-1.5 pr-3 text-xs text-stone">{v.fonte}</td><td className="py-1.5 text-xs text-stone">{v.periodo}</td></tr>
            ))}</tbody>
          </table>
        )}
        {aba === 'confianca' && (
          <div>
            <div className="num text-4xl font-bold text-ink">{n(c.valor)}<span className="text-lg font-normal text-stone">/100 · completude {c.rotulo}</span></div>
            <p className="mt-1 text-sm font-medium text-clay">{c.nota}</p>
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {Object.entries(c.componentes).map(([k, v]) => (
                <div key={k} className="flex items-center gap-3 text-sm">
                  <span className="w-56 text-stone">{ROT_CONF[k] || k}</span>
                  <span className="h-2 flex-1 overflow-hidden rounded bg-line"><span className="block h-full bg-field" style={{ width: `${v * 100}%` }} /></span>
                  <span className="num w-10 text-right">{n(v, 2)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Panel>
  )
}

const ROT_CONF = {
  serie_climatica: 'Série climática (≥ 30 anos)', parametros_culturas: 'Parâmetros das culturas', dados_solo_locais: 'Análise de solo local',
  topografia: 'Declividade', observacao_satelite_numerica: 'NDVI/SMAP numérico do talhão', calibracao_local: 'Calibração local das culturas',
}

function Lista({ itens }) {
  return <ul className="space-y-2">{itens.map((t, i) => <li key={i} className="flex gap-2 text-sm leading-relaxed"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-field" />{t}</li>)}</ul>
}
