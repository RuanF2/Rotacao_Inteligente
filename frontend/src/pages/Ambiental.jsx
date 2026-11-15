import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, BarChart, ReferenceLine } from 'recharts'
import MapaVulnerabilidade from '../components/MapaVulnerabilidade'
import { AnaliseGate, Badge, ClasseBadge, NatureBadge, PageHeader, Panel, Section } from '../components/ui'
import { CLASSE_COR, n } from '../lib/format'
import { avisoIndiceTermico } from '../lib/revisaoManejo'

const SKY = '#2F6690', OCHRE = '#B7791F', CLAY = '#A23B2A', INK = '#12352A', LINE = '#DCE2DD'
const eixo = { fontSize: 12, fill: '#6B7570' }

export default function Ambiental(props) {
  return (
    <>
      <PageHeader title="Análise ambiental">
        Observações da NASA para o ponto da propriedade: clima diário do NASA POWER (1991–2026), indicadores derivados, ENSO e camadas de satélite.
      </PageHeader>
      <AnaliseGate {...props}>{props.analise && <Conteudo {...props} />}</AnaliseGate>
    </>
  )
}

function tendenciaTexto(t, u) {
  if (t.inclinacao_por_decada == null) return '—'
  return `${t.inclinacao_por_decada > 0 ? '+' : ''}${n(t.inclinacao_por_decada, u === 'mm' ? 0 : 2)} ${u}/década · p = ${n(t.p_valor, 3)} ${t.significativa ? '(significativa)' : '(não significativa)'}`
}

function Conteudo({ analise, prop, pontos, camadas }) {
  const c = analise.clima
  const ind = c.indicadores
  const anuais = c.series_anuais
  const mensal = c.climatologia_mensal.map((m) => ({ ...m, chuvoso: ind.meses_chuvosos.includes(m.mes) }))
  const cmp = c.comparacao_periodos
  return (
    <>
      <Section title="Fontes de dados" aside={`Período dos dados: ${c.fonte.periodo_dados[0]} a ${c.fonte.periodo_dados[1]} · origem nesta execução: ${c.fonte.origem_nesta_execucao}`}>
        <div className="overflow-x-auto rounded-md border border-line bg-white">
          <table className="w-full text-sm">
            <thead className="bg-field-soft text-left text-ink"><tr>
              <th className="px-3 py-2 font-semibold">Fonte</th><th className="px-3 py-2 font-semibold">Uso</th><th className="px-3 py-2 font-semibold">Resolução</th><th className="px-3 py-2 font-semibold">Situação</th>
            </tr></thead>
            <tbody>
              {analise.fontes.map((f) => (
                <tr key={f.id} className="border-t border-line align-top">
                  <td className="px-3 py-2"><a href={f.url} target="_blank" rel="noreferrer" className="font-medium text-ink underline decoration-line underline-offset-2">{f.nome}</a><div className="text-xs text-stone">{f.instituicao}</div></td>
                  <td className="px-3 py-2 text-stone">{f.uso}</td>
                  <td className="px-3 py-2 text-xs text-stone">{f.resolucao_espacial}<br />{f.resolucao_temporal}</td>
                  <td className="px-3 py-2">{!f.cobre_local ? <Badge color={CLAY}>sem cobertura</Badge> : f.status === 'integrado' ? <Badge color="#3F7D4E">usado nos cálculos</Badge> : f.status === 'visual' ? <Badge color={SKY}>camada visual</Badge> : <Badge>não integrado</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-stone">{c.fonte.aviso_escala} Resolução NASA POWER: {c.fonte.resolucao_espacial}.</p>
        {c.avisos.map((a) => <p key={a} className="text-xs text-stone">{a}</p>)}
      </Section>

      <Section title="Ciclo anual: chuva × demanda da atmosfera" aside={<NatureBadge tipo="observado" />}>
        <Panel>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={mensal} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
              <CartesianGrid stroke={LINE} vertical={false} />
              <XAxis dataKey="mes_nome" tick={eixo} />
              <YAxis yAxisId="mm" tick={eixo} width={45} tickFormatter={(v) => n(v)} label={{ value: "mm/mês", angle: -90, position: "insideLeft", fontSize: 11, fill: "#6B7570" }} />
              <YAxis yAxisId="c" orientation="right" tick={eixo} domain={[(m) => Math.floor(m - 2), (m) => Math.ceil(m + 1)]} allowDecimals={false} tickFormatter={(v) => `${n(v)} °C`} width={50} />
              <Tooltip formatter={(v, k) => [n(v, 1), k]} />
              <Legend />
              <Bar yAxisId="mm" dataKey="P" name="Chuva média (mm/mês)" fill={SKY} radius={[3, 3, 0, 0]} />
              <Line yAxisId="mm" dataKey="ET0" name="ET0 (mm/mês)" stroke={OCHRE} strokeWidth={2} dot={false} />
              <Line yAxisId="c" dataKey="T2M_MAX" name="Tmax média (°C)" stroke={CLAY} strokeDasharray="4 3" dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
          <p className="mt-2 text-sm text-stone">Estação chuvosa (chuva ≥ metade da ET0, critério FAO): <b className="text-ink">{ind.meses_chuvosos_nomes.join(', ') || 'nenhum mês'}</b>. ET0 por Hargreaves-Samani (FAO-56), porque o conjunto não inclui vento.</p>
        </Panel>
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Chuva anual" aside={<NatureBadge tipo="observado" />}>
          <Panel>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={anuais}>
                <CartesianGrid stroke={LINE} vertical={false} />
                <XAxis dataKey="ano" tick={eixo} interval={4} />
                <YAxis tick={eixo} width={50} />
                <Tooltip formatter={(v) => [`${n(v)} mm`, 'Chuva']} />
                <ReferenceLine y={ind.precipitacao_anual_media_mm} stroke={INK} strokeDasharray="4 3" />
                <Bar dataKey="P_mm" fill={SKY} />
              </BarChart>
            </ResponsiveContainer>
            <p className="text-sm text-stone">Tendência: {tendenciaTexto(ind.tendencia_precipitacao_mm, 'mm')}. Variação entre anos (CV): {n(ind.cv_precipitacao_anual * 100)}%.</p>
          </Panel>
        </Section>
        <Section title="Calor extremo" aside={<NatureBadge tipo="observado" />}>
          <Panel>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={anuais}>
                <CartesianGrid stroke={LINE} vertical={false} />
                <XAxis dataKey="ano" tick={eixo} interval={4} />
                <YAxis tick={eixo} width={50} />
                <Tooltip formatter={(v) => [`${v} dias`, 'Tmax ≥ 35 °C']} />
                <Bar dataKey="dias_calor" fill={CLAY} />
              </BarChart>
            </ResponsiveContainer>
            <p className="text-sm text-stone">Dias/ano com Tmax ≥ 35 °C: {tendenciaTexto(ind.tendencia_dias_calor, 'dias')}. Tmax média: {tendenciaTexto(ind.tendencia_tmax_c, '°C')}.</p>
          </Panel>
        </Section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Umidade do solo (zona radicular)" aside={<NatureBadge tipo="modelo" />}>
          <Panel>
            <ResponsiveContainer width="100%" height={220}>
              <ComposedChart data={mensal}>
                <CartesianGrid stroke={LINE} vertical={false} />
                <XAxis dataKey="mes_nome" tick={eixo} />
                <YAxis tick={eixo} domain={[0, 1]} width={40} />
                <Tooltip formatter={(v, k) => [n(v, 2), k]} />
                <Legend />
                <Line dataKey="GWETROOT" name="Zona radicular (GWETROOT)" stroke={INK} strokeWidth={2} dot={false} />
                <Line dataKey="GWETTOP" name="Superfície (GWETTOP)" stroke={SKY} strokeDasharray="4 3" dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="text-sm text-stone">Fração 0–1 de saturação estimada pelo modelo (MERRA-2 via NASA POWER). Não é medição SMAP nem de campo; o SMAP L4 aparece como camada visual no mapa.</p>
          </Panel>
        </Section>
        <Section title="El Niño, La Niña e a chuva da estação" aside="ONI v6 · NOAA/CPC">
          <Panel>
            {analise.clima.enso ? (
              <>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={analise.clima.enso.por_classe}>
                    <CartesianGrid stroke={LINE} vertical={false} />
                    <XAxis dataKey="classe" tick={eixo} />
                    <YAxis tick={eixo} width={50} />
                    <Tooltip formatter={(v, k, p) => [`${n(v)} mm (${p.payload.n_anos} anos)`, 'Mediana']} />
                    <Bar dataKey="mediana_mm" fill={SKY} />
                  </BarChart>
                </ResponsiveContainer>
                <p className="text-sm text-stone">Mediana da chuva nos meses chuvosos por classe ENSO do ano agrícola (nov–out). Amostras pequenas: interprete como tendência, não como previsão.</p>
              </>
            ) : <p className="text-sm text-stone">Sem estação chuvosa definida ou sem dados ONI.</p>}
          </Panel>
        </Section>
      </div>

      <Section title="O clima mudou? Comparação de períodos observados" aside={<NatureBadge tipo="observado" />}>
        <div className="overflow-x-auto rounded-md border border-line bg-white">
          <table className="num w-full text-sm">
            <thead className="bg-field-soft text-left"><tr>
              <th className="px-3 py-2">Indicador</th><th className="px-3 py-2">{cmp.periodo_a.intervalo.join('–')}</th><th className="px-3 py-2">{cmp.periodo_b.intervalo.join('–')}</th><th className="px-3 py-2">Diferença</th>
            </tr></thead>
            <tbody>
              {[['Chuva anual média (mm)', 'precipitacao_anual_media_mm', 0], ['Tmax média (°C)', 'tmax_media_c', 2], ['Dias com Tmax ≥ 35 °C', 'dias_calor_ano_medio', 0], ['Maior veranico na estação (dias)', 'cdd_estacao_chuvosa_medio_dias', 1], ['Índice de aridez', 'indice_aridez', 2]].map(([t, k, d]) => {
                const a = cmp.periodo_a[k], b = cmp.periodo_b[k]
                return (
                  <tr key={k} className="border-t border-line"><td className="px-3 py-2 font-sans">{t}</td><td className="px-3 py-2">{n(a, d)}</td><td className="px-3 py-2">{n(b, d)}</td>
                    <td className="px-3 py-2">{a == null || b == null ? '—' : `${b - a > 0 ? '+' : ''}${n(b - a, d)}`}</td></tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Indicadores de vulnerabilidade" aside={<span>Índice {n(analise.vulnerabilidade.indice, 2)} · <ClasseBadge classe={analise.vulnerabilidade.classe} /></span>}>
        <div className="overflow-x-auto rounded-md border border-line bg-white">
          <table className="w-full text-sm">
            <thead className="bg-field-soft text-left"><tr>
              <th className="px-3 py-2">Indicador</th><th className="px-3 py-2">Valor</th><th className="px-3 py-2">Nota 0–1</th><th className="px-3 py-2">Base das faixas e fonte</th>
            </tr></thead>
            <tbody>
              {analise.vulnerabilidade.indicadores.map((i) => (
                <tr key={i.chave} className="border-t border-line align-top">
                  <td className="px-3 py-2 font-medium text-ink">{i.nome}</td>
                  <td className="num px-3 py-2">{i.valor == null ? <span className="text-ochre">sem dado</span> : `${n(i.valor, i.valor < 2 ? 2 : 0)} ${i.unidade}`}</td>
                  <td className="num px-3 py-2">{i.nota == null ? '—' : <span className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: CLASSE_COR[i.classe] }} />{n(i.nota, 2)}</span>}</td>
                  <td className="px-3 py-2 text-xs text-stone">{i.base_faixas}<br /><i>Fonte: {i.fonte}</i></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-sm font-medium text-ink">{avisoIndiceTermico()}</p>
        <p className="mt-2 text-xs text-stone">{analise.vulnerabilidade.metodo}. {analise.vulnerabilidade.aviso}</p>
        {analise.topografia.erro && <p className="mt-1 text-xs text-ochre">Declividade não obtida: {analise.topografia.erro}. Informe-a na tela Propriedade para completar o indicador.</p>}
      </Section>

      <Section title="Mapa de vulnerabilidade e camadas de satélite">
        <MapaVulnerabilidade lat={prop.lat} lon={prop.lon} pontos={pontos} camadas={camadas} height={520} zoom={7} nome={prop.nome} />
      </Section>
    </>
  )
}
