import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../lib/api'
import { CORES_ESTRATEGIA, n, pct } from '../lib/format'
import { AnaliseGate, Badge, Button, ClasseBadge, ErrorBox, Loader, NatureBadge, PageHeader, Panel, Section } from '../components/ui'

const NAT = { historico: 'observado', recente: 'observado', hipotetico: 'hipotetico' }

export default function Simulador(props) {
  return (
    <>
      <PageHeader title="Simulador climático">
        Como as estratégias de rotação se comportariam se o clima mudasse? Compare o histórico observado, o período recente observado e uma perturbação hipotética definida por você.
      </PageHeader>
      <AnaliseGate {...props}>{props.analise && <Conteudo {...props} />}</AnaliseGate>
    </>
  )
}

function Slider({ label, value, set, min, max, step, unit }) {
  return (
    <label className="block">
      <span className="flex justify-between text-sm"><span className="font-medium text-ink">{label}</span><span className="num font-semibold text-sky">{value > 0 ? '+' : ''}{n(value, step < 1 ? 1 : 0)} {unit}</span></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => set(Number(e.target.value))} className="mt-2 w-full accent-[#2F6690]" />
      <span className="flex justify-between text-[11px] text-stone"><span>{min}</span><span>{max}</span></span>
    </label>
  )
}

function Conteudo({ analise, prop, sim, setSim }) {
  const [dt, setDt] = useState(sim?.parametros?.delta_t_c ?? 2)
  const [dp, setDp] = useState(sim?.parametros?.delta_p_pct ?? -15)
  const [irr, setIrr] = useState(sim?.parametros?.irrigacao_mm_ano ?? prop.irrigacao_mm_ano ?? 0)
  const [base, setBase] = useState(sim?.parametros?.base_cenario ?? 'historico')
  const [rot, setRot] = useState(sim?.parametros?.rotulo_horizonte ?? '')
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState(null)
  const ests = analise.estrategias

  const rodar = async () => {
    setCarregando(true); setErro(null)
    try {
      const r = await api.simulacao({
        lat: prop.lat, lon: prop.lon, delta_t: dt, delta_p_pct: dp, irrigacao_mm_ano: Number(irr) || 0,
        declividade_pct: analise.topografia.declividade_pct, base_cenario: base, rotulo_horizonte: rot || null,
        estrategias: Object.fromEntries(ests.map((e) => [e.chave, e.slots])),
      })
      setSim(r)
    } catch (e) { setErro(e) } finally { setCarregando(false) }
  }

  const presets = [[1, -5], [2, -15], [3, -25]]
  return (
    <>
      <Section title="Configurar cenário">
        <Panel className="p-6">
          <div className="grid gap-6 md:grid-cols-3">
            <Slider label="Variação de temperatura" value={dt} set={setDt} min={-1} max={4} step={0.5} unit="°C" />
            <Slider label="Variação de chuva" value={dp} set={setDp} min={-40} max={20} step={5} unit="%" />
            <label className="block">
              <span className="text-sm font-medium text-ink">Disponibilidade de irrigação</span>
              <input type="number" min="0" step="10" value={irr} onChange={(e) => setIrr(e.target.value)} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm" />
              <span className="text-xs text-stone">mm por ano (0 = sequeiro)</span>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-ink">Clima de partida da perturbação</span>
              <select value={base} onChange={(e) => setBase(e.target.value)} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm">
                <option value="historico">Histórico completo observado (1991–2025)</option>
                <option value="recente">Período recente observado (2011–2025)</option>
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-medium text-ink">Horizonte temporal (rótulo)</span>
              <select value={rot} onChange={(e) => setRot(e.target.value)} className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm">
                <option value="">Sem horizonte</option><option>2030</option><option>2050</option><option>2070</option>
              </select>
              <span className="text-xs text-stone">Identifica o cenário no relatório; não altera os cálculos.</span>
            </label>
            <div>
              <span className="text-sm font-medium text-ink">Testes de sensibilidade rápidos</span>
              <div className="mt-1 flex flex-wrap gap-2">
                {presets.map(([t, p]) => <button key={t} onClick={() => { setDt(t); setDp(p) }} className="rounded border border-line px-2 py-1 text-xs hover:border-sky">+{t} °C, {p}%</button>)}
              </div>
              <span className="text-xs text-stone">Combinações hipotéticas, não projeções oficiais.</span>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <Button onClick={rodar} disabled={carregando}>Simular cenário</Button>
            <p className="max-w-2xl text-xs text-stone">Projeções NEX-GDDP-CMIP6 ainda não estão integradas. As variações acima são perturbações hipotéticas (método delta) aplicadas à série observada do NASA POWER; servem para testar sensibilidade, não para prever o futuro.</p>
          </div>
        </Panel>
      </Section>
      <ErrorBox error={erro} />
      {carregando && <Loader text="Recalculando ET0, balanço hídrico e indicadores para cada cenário…" />}
      {sim && !carregando && <Resultado sim={sim} ests={ests} />}
    </>
  )
}

function Resultado({ sim, ests }) {
  const cen = sim.cenarios
  const ordem = ['historico', 'recente', 'hipotetico']
  const barras = ests.map((e) => ({ est: `${e.chave} ${e.titulo}`, chave: e.chave, ...Object.fromEntries(ordem.map((k) => [k, cen[k].estrategias[e.chave].objetivos.vulnerabilidade_climatica])) }))
  const quebra = ests.map((e) => ({ est: `${e.chave} ${e.titulo}`, ...Object.fromEntries(ordem.map((k) => [k, cen[k].estrategias[e.chave].indicadores.risco_quebra_anos])) }))
  const CORES = { historico: '#9FB3C8', recente: '#2F6690', hipotetico: '#A23B2A' }
  return (
    <>
      <p className="mb-5 rounded-md border border-ochre/40 bg-[#fff9eb] p-3 text-sm">As porcentagens de perda representam somente o componente de falta de água. Risco térmico e geada são analisados separadamente; 0% de perda hídrica não significa segurança da colheita.</p>
      <Section title="Três climas, as mesmas estratégias">
        <div className="grid gap-4 md:grid-cols-3">
          {ordem.map((k) => {
            const c = cen[k]; const i = c.indicadores_clima
            return (
              <Panel key={k} className={k === 'hipotetico' ? 'border-clay/40' : ''}>
                <div className="flex items-start justify-between gap-2"><div className="font-semibold text-ink">{c.rotulo}</div><NatureBadge tipo={NAT[k]} /></div>
                {k === 'hipotetico' && <p className="mt-1 text-xs text-clay">{c.natureza}{c.rotulo_horizonte ? ` · rótulo: ${c.rotulo_horizonte}` : ''}</p>}
                <dl className="num mt-3 grid grid-cols-2 gap-y-2 text-sm">
                  <dt className="font-sans text-stone">Chuva anual</dt><dd>{n(i.precipitacao_anual_media_mm)} mm</dd>
                  <dt className="font-sans text-stone">ET0 anual</dt><dd>{n(i.et0_anual_media_mm)} mm</dd>
                  <dt className="font-sans text-stone">Aridez</dt><dd>{n(i.indice_aridez, 2)} <span className="font-sans text-xs text-stone">{i.classe_aridez}</span></dd>
                  <dt className="font-sans text-stone">Dias ≥ 35 °C</dt><dd>{n(i.dias_calor_ano_medio)}</dd>
                  <dt className="font-sans text-stone">Estação chuvosa</dt><dd>{i.duracao_estacao_chuvosa_meses} meses</dd>
                  <dt className="font-sans text-stone">Vulnerabilidade</dt><dd>{n(c.vulnerabilidade.indice, 2)} <ClasseBadge classe={c.vulnerabilidade.classe} /></dd>
                </dl>
              </Panel>
            )
          })}
        </div>
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Vulnerabilidade das estratégias">
          <Panel>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={barras} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid stroke="#DCE2DD" horizontal={false} />
                <XAxis type="number" domain={[0, 1]} tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="est" width={150} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v, k) => [n(v, 2), cen[k].rotulo]} />
                <Legend formatter={(k) => cen[k].rotulo} wrapperStyle={{ fontSize: 11 }} />
                {ordem.map((k) => <Bar key={k} dataKey={k} fill={CORES[k]} />)}
              </BarChart>
            </ResponsiveContainer>
          </Panel>
        </Section>
        <Section title="Anos-safra com perda potencial por falta de água > 50%">
          <Panel>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={quebra} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid stroke="#DCE2DD" horizontal={false} />
                <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => pct(v)} tick={{ fontSize: 12 }} />
                <YAxis type="category" dataKey="est" width={150} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v, k) => [pct(v), cen[k].rotulo]} />
                {ordem.map((k) => <Bar key={k} dataKey={k} fill={CORES[k]} />)}
              </BarChart>
            </ResponsiveContainer>
          </Panel>
        </Section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Sensibilidade ao aquecimento" aside={`com chuva ${sim.parametros.delta_p_pct > 0 ? '+' : ''}${sim.parametros.delta_p_pct}%`}>
          <Panel>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={sim.sensibilidade_temperatura}>
                <CartesianGrid stroke="#DCE2DD" />
                <XAxis dataKey="delta_t" tickFormatter={(v) => `+${v} °C`} tick={{ fontSize: 12 }} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 12 }} width={35} />
                <Tooltip formatter={(v, k) => [n(v, 2), `Estratégia ${k}`]} labelFormatter={(v) => `ΔT = +${v} °C`} />
                <Legend formatter={(k) => `Estratégia ${k}`} wrapperStyle={{ fontSize: 11 }} />
                {ests.map((e) => <Line key={e.chave} dataKey={e.chave} stroke={CORES_ESTRATEGIA[e.chave]} strokeWidth={2} />)}
              </LineChart>
            </ResponsiveContainer>
            <p className="text-xs text-stone">Vulnerabilidade climática (0–1) de cada estratégia conforme a temperatura sobe.</p>
          </Panel>
        </Section>
        <Section title="Sensibilidade à chuva" aside={`com temperatura ${sim.parametros.delta_t_c >= 0 ? '+' : ''}${sim.parametros.delta_t_c} °C`}>
          <Panel>
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={sim.sensibilidade_precipitacao}>
                <CartesianGrid stroke="#DCE2DD" />
                <XAxis dataKey="delta_p_pct" tickFormatter={(v) => `${v > 0 ? '+' : ''}${v}%`} tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} width={45} />
                <Tooltip formatter={(v, k) => [`${n(v)} mm/ano`, `Estratégia ${k}`]} labelFormatter={(v) => `ΔP = ${v}%`} />
                <Legend formatter={(k) => `Estratégia ${k}`} wrapperStyle={{ fontSize: 11 }} />
                {ests.map((e) => <Line key={e.chave} dataKey={e.chave} stroke={CORES_ESTRATEGIA[e.chave]} strokeWidth={2} />)}
              </LineChart>
            </ResponsiveContainer>
            <p className="text-xs text-stone">Água faltante (mm/ano não supridos pela chuva) conforme a chuva varia.</p>
          </Panel>
        </Section>
      </div>

      <Section title="Detalhe por cultura no cenário hipotético">
        <div className="overflow-x-auto rounded-md border border-line bg-white">
          <table className="num w-full text-sm">
            <thead className="bg-field-soft text-left"><tr><th className="px-3 py-2 font-sans">Estratégia</th><th className="px-3 py-2 font-sans">Cultura</th><th className="px-3 py-2">Índice água e adequação térmica (hist. → hip.)</th><th className="px-3 py-2">Perda potencial por falta de água (hist. → hip.)</th><th className="px-3 py-2">Dias acima do limite térmico (hist. → hip.)</th></tr></thead>
            <tbody>
              {ests.map((e) => cen.hipotetico.estrategias[e.chave].slots.map((s, i) => {
                const h = cen.historico.estrategias[e.chave].slots[i]
                return (
                  <tr key={e.chave + i} className="border-t border-line">
                    <td className="px-3 py-1.5 font-sans">{i === 0 && <Badge color={CORES_ESTRATEGIA[e.chave]} solid>{e.chave}</Badge>}</td>
                    <td className="px-3 py-1.5 font-sans">{s.nome} <span className="text-stone">({s.mes_nome}/a{s.ano})</span></td>
                    <td className="px-3 py-1.5">{pct(h.satisfacao_hidrica)} → {pct(s.satisfacao_hidrica)}</td>
                    <td className="px-3 py-1.5">{pct(h.perda_rendimento_media)} → {pct(s.perda_rendimento_media)}</td>
                    <td className="px-3 py-1.5">{pct(h.fracao_dias_calor)} → {pct(s.fracao_dias_calor)}</td>
                  </tr>
                )
              }))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-stone">{sim.metodo} {sim.aviso}</p>
      </Section>
    </>
  )
}
