import { OrientacaoAgricultor, AlertasTermicos } from '../components/OrientacaoAgricultor'
import RotationRibbon, { RibbonLegend } from '../components/RotationRibbon'
import MapaVulnerabilidade from '../components/MapaVulnerabilidade'
import { AnaliseGate, Badge, Button, ClasseBadge, PageHeader, Panel, Section, VulnScale } from '../components/ui'
import { CORES_ESTRATEGIA, n, pct } from '../lib/format'
import { rotuloLocal } from '../lib/localizacao'
import { avisoIndiceTermico, CHAVE_REVISAO_MANEJO, precisaRevisarManejo } from '../lib/revisaoManejo'

const NIVEL = { alto: '#A23B2A', medio: '#B7791F', info: '#2F6690' }

export default function Dashboard(props) {
  const { analise, culturas, prop, demo, ir, camadas, pontos } = props
  let selo = ''
  try { selo = localStorage.getItem(CHAVE_REVISAO_MANEJO) || '' } catch { /* armazenamento desabilitado */ }
  return (
    <>
      <PageHeader title={prop.nome} actions={<Button variant="ghost" onClick={() => ir('propriedade')}>Editar propriedade</Button>}>
        {rotuloLocal(prop)} · {n(prop.lat, 3)}, {n(prop.lon, 3)}
        {prop.area_ha ? ` · ${n(prop.area_ha, 1)} ha` : ''}
        {prop.demonstrativa && <span className="ml-2"><Badge>propriedade demonstrativa</Badge></span>}
      </PageHeader>
      {precisaRevisarManejo(prop, demo, selo) && <div role="alert" className="mb-5 rounded-md border border-ochre/50 bg-[#fbf5ea] p-4 text-sm text-ink"><b>Dados de manejo ainda não confirmados para esta localização.</b> Os resultados são apenas exploratórios. Revise solo, histórico, culturas e calendário na tela <button className="font-semibold text-field underline" onClick={() => ir('propriedade')}>Propriedade</button> antes de utilizá-los.</div>}
      <AnaliseGate {...props}>
        {analise && <Conteudo analise={analise} culturas={culturas} ir={ir} camadas={camadas} pontos={pontos} prop={prop} />}
      </AnaliseGate>
    </>
  )
}

function Conteudo({ analise, culturas, ir, camadas, pontos, prop }) {
  const ind = analise.clima.indicadores
  const v = analise.vulnerabilidade
  const A = analise.estrategias.find((e) => e.chave === 'A')
  return (
    <>
      <OrientacaoAgricultor analise={analise} ir={ir} />
      <div className="mb-10 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <Panel className="p-6">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-bold text-ink">Vulnerabilidade agrícola</h2>
            <ClasseBadge classe={v.classe} />
          </div>
          <div className="num mt-2 text-6xl font-bold text-ink">{v.indice == null ? '—' : n(v.indice, 2)}</div>
          <div className="mb-4 text-sm text-stone">Índice experimental 0–1 · média de {v.n_indicadores} indicadores documentados</div>
          <VulnScale value={v.indice} />
          <div className="mt-5 grid grid-cols-3 gap-3 text-sm">
            {[['Hídrica', v.subindices.hidrico], ['Térmica', v.subindices.termico], ['Erosão', v.subindices.erosao]].map(([t, x]) => (
              <div key={t} className="rounded border border-line p-2">
                <div className="text-stone">{t}</div>
                <div className="num text-xl font-semibold">{x == null ? '—' : n(x, 2)}</div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-stone">{avisoIndiceTermico()}</p>
          {v.ausentes.length > 0 && <p className="mt-3 text-xs text-ochre">Sem dado: {v.ausentes.join(', ')}.</p>}
        </Panel>
        <Panel className="p-6">
          <h2 className="mb-4 text-lg font-bold text-ink">Condições ambientais <span className="text-sm font-normal text-stone">({ind.periodo.inicio}–{ind.periodo.fim}, NASA POWER)</span></h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
            <Item k="Chuva anual média" v={n(ind.precipitacao_anual_media_mm)} u="mm" sky />
            <Item k="Evapotranspiração de referência" v={n(ind.et0_anual_media_mm)} u="mm" sky />
            <Item k="Índice de aridez" v={n(ind.indice_aridez, 2)} u={ind.classe_aridez} />
            <Item k="Estação chuvosa" v={ind.duracao_estacao_chuvosa_meses} u={`meses (${ind.meses_chuvosos_nomes.join(', ') || '—'})`} />
            <Item k="Dias com Tmax ≥ 35 °C" v={n(ind.dias_calor_ano_medio)} u="por ano" />
            <Item k="Maior veranico na estação" v={n(ind.cdd_estacao_chuvosa_medio_dias)} u="dias (média)" />
          </dl>
        </Panel>
      </div>

      <Section title="Alertas">
        <ul className="grid gap-3 md:grid-cols-2">
          {analise.alertas.map((a, i) => (
            <li key={i} className="rounded-md border border-line bg-white p-3 pl-4" style={{ borderLeft: `4px solid ${NIVEL[a.nivel]}` }}>
              <div className="font-semibold text-ink">{a.titulo}</div>
              <div className="text-sm text-stone">{a.texto}</div>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Principais recomendações" aside={<button className="text-field underline" onClick={() => ir('rotacao')}>Comparação completa</button>}>
        <div className="space-y-5">
          {analise.estrategias.map((e) => {
            const o = e.avaliacao.objetivos
            const i = e.avaliacao.indicadores
            return (
              <div key={e.chave} className="grid items-center gap-4 md:grid-cols-[220px_1fr_280px]">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="num flex h-7 w-7 items-center justify-center rounded text-sm font-bold text-white" style={{ background: CORES_ESTRATEGIA[e.chave] }}>{e.chave}</span>
                    <span className="font-semibold text-ink">{e.titulo}</span>
                  </div>
                  <div className="mt-1 text-xs text-stone">{e.avaliacao.slots.map((s) => s.nome).join(' · ')}</div>
                </div>
                <RotationRibbon avaliacao={e.avaliacao} culturas={culturas} compact />
                <div className="num grid grid-cols-3 gap-2 text-sm">
                  <div><div className="text-[11px] text-stone">Quebra por falta de água</div>{pct(i.risco_quebra_anos)}</div>
                  <div><div className="text-[11px] text-stone">Água faltante</div>{n(o.demanda_irrigacao_mm_ano)} mm</div>
                  <div><div className="text-[11px] text-stone">DAS</div>{n(e.avaliacao.das.valor)}</div>
                </div>
                {e.avaliacao.restricoes?.viavel === false && <div className="md:col-span-3"><AlertasTermicos avaliacao={e.avaliacao} referencia={e.chave === 'A'}/></div>}
              </div>
            )
          })}
        </div>
        <div className="mt-4"><RibbonLegend /></div>
        <p className="mt-3 text-xs text-stone">Comparação contra a rotação atual (A) com o clima de {A.avaliacao.indicadores.periodo_avaliado.join('–')}: {A.avaliacao.indicadores.pares_de_anos_avaliados} pares de anos consecutivos e sobrepostos, ou seja, {A.avaliacao.indicadores.anos_safra_avaliados} observações de ano-safra (não são {A.avaliacao.indicadores.anos_safra_avaliados} anos independentes). Anos de quebra = proporção dessas observações em que alguma cultura comercial teria perda potencial &gt; 50% por falta de água. Água faltante = demanda da cultura não suprida pela chuva efetiva. DAS = Dívida Ambiental do Solo (0–100, menor é melhor).</p>
      </Section>

      <Section title="Localização e vulnerabilidade regional">
        <MapaVulnerabilidade lat={prop.lat} lon={prop.lon} pontos={pontos} camadas={camadas} height={380} zoom={6} nome={prop.nome} />
      </Section>
    </>
  )
}

function Item({ k, v, u, sky }) {
  return (
    <div>
      <dt className="text-sm text-stone">{k}</dt>
      <dd className={`num text-2xl font-semibold ${sky ? 'text-sky' : 'text-ink'}`}>{v}<span className="ml-1 text-sm font-normal text-stone">{u}</span></dd>
    </div>
  )
}
