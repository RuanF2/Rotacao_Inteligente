import { useEffect, useRef, useState } from 'react'
import { MapContainer, Marker, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import { api } from '../lib/api'
import { MESES, n } from '../lib/format'
import { Badge, Button, ErrorBox, PageHeader, Panel, Section } from '../components/ui'
import { CHAVE_REVISAO_MANEJO, assinaturaManejo, precisaRevisarManejo } from '../lib/revisaoManejo'
import { FONTE_USUARIO, SEM_LOCAL, aplicarGeocodificacao, coordsValidas, nomeValido, rotuloLocal, trocarLocalizacao } from '../lib/localizacao'

const pin = L.divIcon({
  className: '',
  html: '<div style="width:18px;height:18px;border-radius:50% 50% 50% 0;background:#12352A;transform:rotate(-45deg);border:3px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>',
  iconSize: [18, 18], iconAnchor: [9, 18],
})

const PRIORIDADES = [
  ['agua', 'Economizar água'],
  ['risco', 'Reduzir risco climático'],
  ['solo', 'Melhorar o solo'],
  ['erosao', 'Reduzir erosão'],
  ['diversificacao', 'Diversificar culturas'],
]

function Picker({ lat, lon, onPick }) {
  const map = useMap()
  useEffect(() => { map.setView([lat, lon]) }, [lat, lon]) // eslint-disable-line
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) })
  return <Marker position={[lat, lon]} icon={pin} />
}

const inp = 'w-full rounded-md border border-line bg-white px-3 py-2 text-sm text-ink focus:border-field'

function Campo({ label, hint, children }) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink">{label}</span>
      <div className="mt-1">{children}</div>
      {hint && <span className="mt-0.5 block text-xs text-stone">{hint}</span>}
    </label>
  )
}

const numOuNull = (v) => (v === '' || v === null || v === undefined ? null : Number(v))

export default function Propriedade({ prop, setProp, demo, catalogo, analisar, ir, carregando }) {
  const [f, setF] = useState(prop)
  const [seloRevisao, setSeloRevisao] = useState(() => { try { return localStorage.getItem(CHAVE_REVISAO_MANEJO) || '' } catch { return '' } })
  const [locais, setLocais] = useState([])
  const [salvas, setSalvas] = useState([])
  const [salvaId, setSalvaId] = useState(null)
  const [msg, setMsg] = useState(null)
  const [erro, setErro] = useState(null)
  const [fontes, setFontes] = useState(null)
  const [aviso, setAviso] = useState(null)          // troca de localização: o que revisar
  const [geo, setGeo] = useState({ estado: 'ocioso', msg: null })
  const [tentativa, setTentativa] = useState(0)
  const geoReq = useRef(0)

  useEffect(() => { api.locais().then((r) => setLocais(r.locais)).catch(() => {}); recarregar() }, [])
  useEffect(() => {
    const t = setTimeout(() => api.fontes(f.lat, f.lon).then((r) => setFontes(r.fontes)).catch(() => setFontes(null)), 300)
    return () => clearTimeout(t)
  }, [f.lat, f.lon])
  // Geocodificação reversa: só quando a localidade está vazia (ponto novo). Espera 900 ms sem mudanças
  // (o backend ainda limita a 1 req/s e usa cache). Respostas de coordenadas antigas são descartadas.
  useEffect(() => {
    const lat = Number(f.lat), lon = Number(f.lon)
    if (f.regiao || f.pais || !coordsValidas(lat, lon)) return
    const id = ++geoReq.current
    setGeo({ estado: 'aguardando', msg: null })
    const t = setTimeout(async () => {
      setGeo({ estado: 'buscando', msg: null })
      try {
        const r = await api.geocodificar(lat, lon)
        if (id !== geoReq.current) return
        setF((x) => aplicarGeocodificacao(x, r, { lat, lon }))
        setGeo(r.identificado ? { estado: 'ok', msg: null } : { estado: 'nao_identificado', msg: r.motivo })
      } catch (e) {
        if (id === geoReq.current) setGeo({ estado: 'falhou', msg: e.message })
      }
    }, 900)
    return () => clearTimeout(t)
  }, [f.lat, f.lon, f.regiao, f.pais, tentativa])

  const mudarCoords = (lat, lon) => {
    const r = trocarLocalizacao(f, lat, lon, { nomeDemo: demo?.nome })
    setF(r.f)
    if (r.aviso) setAviso((a) => (a ? { ...r.aviso, de: a.de, nomeLimpo: a.nomeLimpo || r.aviso.nomeLimpo } : r.aviso))
    return r
  }
  const editarCoord = (k, v) => {
    const num = Number(v)
    if (v === '' || !Number.isFinite(num)) { set(k, v); return }
    const lat = k === 'lat' ? num : Number(f.lat)
    const lon = k === 'lon' ? num : Number(f.lon)
    if (coordsValidas(lat, lon)) mudarCoords(lat, lon)
    else set(k, v)
  }

  const recarregar = () => api.listarProps().then((r) => setSalvas(r.propriedades)).catch(() => {})

  const set = (k, v) => setF((x) => ({ ...x, [k]: v }))
  const setSolo = (k, v) => setF((x) => ({ ...x, solo: { ...x.solo, [k]: v } }))
  const setPrior = (k, v) => setF((x) => ({ ...x, prioridades: { ...x.prioridades, [k]: Number(v) } }))
  const setSlot = (i, k, v) => setF((x) => ({ ...x, rotacao_atual: x.rotacao_atual.map((s, j) => (j === i ? { ...s, [k]: k === 'cultura' ? v : Number(v) } : s)) }))
  const addSlot = () => setF((x) => ({ ...x, rotacao_atual: [...x.rotacao_atual, { cultura: 'feijao-caupi', ano: 1, mes: 3 }] }))
  const delSlot = (i) => setF((x) => ({ ...x, rotacao_atual: x.rotacao_atual.filter((_, j) => j !== i) }))
  const perm = f.culturas_permitidas || catalogo.map((c) => c.id)
  const togglePerm = (id) => {
    const nv = perm.includes(id) ? perm.filter((x) => x !== id) : [...perm, id]
    set('culturas_permitidas', nv.length === catalogo.length ? null : nv)
  }
  const escolherLocal = (lat, lon) => mudarCoords(lat, lon)
  const escolherLocalConhecido = (l) => {
    const r = mudarCoords(l.lat, l.lon)
    // nomes dos locais vêm da configuração do projeto (NASA1), não de inferência
    setF({ ...r.f, regiao: l.nome, pais: l.pais || (l.uf ? 'Brasil' : null), localidade_fonte: 'configuração do projeto (NASA1)' })
  }
  const setLocalManual = (k, v) => setF((x) => ({ ...x, [k]: v, localidade_fonte: FONTE_USUARIO }))

  const pendenteManejo = precisaRevisarManejo(f, demo, seloRevisao)
  const confirmarManejo = (marcou) => {
    const valor = marcou ? assinaturaManejo(f) : ''
    setSeloRevisao(valor)
    try { if (valor) localStorage.setItem(CHAVE_REVISAO_MANEJO, valor); else localStorage.removeItem(CHAVE_REVISAO_MANEJO) } catch { /* sem persistência */ }
  }

  const limpo = () => ({
    ...f,
    lat: Number(f.lat), lon: Number(f.lon), area_ha: numOuNull(f.area_ha),
    declividade_pct: numOuNull(f.declividade_pct), irrigacao_mm_ano: Number(f.irrigacao_mm_ano || 0),
    solo: { textura: f.solo?.textura || null, profundidade_cm: numOuNull(f.solo?.profundidade_cm),
      materia_organica_pct: numOuNull(f.solo?.materia_organica_pct), ph: numOuNull(f.solo?.ph) },
  })

  const rodar = async () => {
    setErro(null)
    if (!nomeValido(f)) { setErro(new Error('Dê um nome à propriedade antes de analisar.')); return }
    if (pendenteManejo) { setErro(new Error('Confirme que revisou os dados agrícolas para esta localização antes de analisar.')); return }
    if (!f.rotacao_atual.length) { setErro(new Error('Informe ao menos uma cultura na rotação atual.')); return }
    const p = limpo(); setProp(p); ir('dashboard'); analisar(p)
  }
  const salvar = async () => {
    setErro(null)
    if (!nomeValido(f)) { setErro(new Error('Dê um nome à propriedade antes de salvar.')); return }
    if (pendenteManejo) { setErro(new Error('Confirme que revisou os dados agrícolas para esta localização antes de salvar.')); return }
    try { const r = await api.salvarProp(limpo(), salvaId); setSalvaId(r.id); setMsg(`Propriedade salva (${r.nome}).`); recarregar() } catch (e) { setErro(e) }
  }
  const abrir = async (id) => { try { const r = await api.obterProp(id); setF(r.dados); setAviso(null); setSalvaId(id); setMsg(`Propriedade "${r.nome}" aberta.`) } catch (e) { setErro(e) } }
  const excluir = async (id) => { try { await api.excluirProp(id); if (id === salvaId) setSalvaId(null); recarregar() } catch (e) { setErro(e) } }

  const cobre = fontes?.filter((x) => x.status === 'integrado')

  return (
    <>
      <PageHeader title="Propriedade" actions={<>
        <Button variant="ghost" onClick={() => { setF(demo); setAviso(null); setSalvaId(null) }}>Restaurar demonstração</Button>
        <Button variant="ghost" onClick={salvar}>Salvar</Button>
        <Button onClick={rodar} disabled={carregando}>Analisar propriedade</Button>
      </>}>
        Escolha o local, informe as condições reais da fazenda e depois clique em “Analisar propriedade”. O clima vem da NASA; solo, culturas e práticas agrícolas precisam ser conferidos por você.
      </PageHeader>
      {msg && <div className="mb-4 rounded-md bg-field-soft px-4 py-2 text-sm text-ink">{msg}</div>}
      <ErrorBox error={erro} />
      {aviso && (
        <div className="mb-6 rounded-md border border-ochre/50 bg-[#fbf5ea] p-4 text-sm" role="status">
          <div className="font-semibold text-ink">Você mudou a localização da propriedade.</div>
          <p className="mt-1 text-[#5b4313]">
            Antes: {aviso.de.local} ({n(Number(aviso.de.lat), 3)}, {n(Number(aviso.de.lon), 3)}). Agora: {rotuloLocal(f)} ({n(Number(f.lat), 3)}, {n(Number(f.lon), 3)}).
            {aviso.revisar.length > 0 && <> Estes dados foram informados para o local anterior e podem não ser adequados à nova região: <b>{aviso.revisar.join('; ')}</b>. Revise-os antes de analisar.</>}
            {aviso.nomeLimpo && <> O nome demonstrativo foi removido: defina o nome desta propriedade.</>}
            {' '}A análise anterior não vale para este ponto.
          </p>
          <button className="mt-2 text-sm font-semibold text-ink underline" onClick={() => setAviso(null)}>Ocultar este aviso (confirmação agrícola abaixo permanece necessária)</button>
        </div>
      )}

      <div className={`mb-6 rounded-md border p-4 text-sm ${pendenteManejo ? 'border-ochre/50 bg-[#fbf5ea]' : 'border-field/30 bg-field-soft/40'}`} role="status">
        <h2 className="font-semibold text-ink">Conferência dos dados agrícolas para este local</h2>
        <p className="mt-1 text-stone">A NASA fornece dados climáticos regionais, mas não confirma o solo, o histórico de plantio, as culturas, os meses de semeadura nem a irrigação da sua propriedade. Ao mudar de país ou município, esses valores podem continuar iguais aos do cenário demonstrativo.</p>
        {pendenteManejo ? <label className="mt-3 flex cursor-pointer items-start gap-2 font-medium text-ink">
          <input type="checkbox" className="mt-1 accent-[#3F7D4E]" checked={false} onChange={(e) => confirmarManejo(e.target.checked)} aria-label="Confirmei os dados agrícolas deste local" />
          <span>Revisei solo, histórico, culturas, calendário de plantio e água disponível para estas coordenadas, ou reconheço que são dados demonstrativos e não representam uma fazenda real.</span>
        </label> : <p className="mt-2 text-sm font-semibold text-field">Dados agrícolas confirmados para esta configuração. Se alterar coordenadas ou dados agrícolas, confirme novamente.</p>}
      </div>
      <Section title="Localização">
        <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
          <div className="h-[360px] overflow-hidden rounded-md border border-line">
            <MapContainer center={[f.lat, f.lon]} zoom={5} style={{ height: '100%' }}>
              <TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <Picker lat={f.lat} lon={f.lon} onPick={escolherLocal} />
            </MapContainer>
          </div>
          <div className="space-y-3">
            <p className="text-sm text-stone">Clique no mapa ou digite as coordenadas (graus decimais).</p>
            <div className="rounded-md border border-line bg-white px-3 py-2 text-sm" aria-live="polite">
              <div className="font-medium text-ink">{rotuloLocal(f)}</div>
              <div className="text-xs text-stone">
                {f.regiao || f.pais ? `Fonte: ${f.localidade_fonte || 'não informada'}` :
                  geo.estado === 'buscando' || geo.estado === 'aguardando' ? 'Consultando OpenStreetMap Nominatim…' :
                  geo.estado === 'falhou' ? <>{geo.msg} Preencha país e região abaixo ou <button className="underline" onClick={() => setTentativa((t) => t + 1)}>tente novamente</button>.</> :
                  geo.estado === 'nao_identificado' ? 'Nenhum município encontrado para este ponto (ex.: mar ou área remota). Preencha manualmente se souber.' :
                  'Coordenadas mantidas; localidade ainda não identificada.'}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Campo label="Latitude"><input className={inp} type="number" step="0.0001" min="-90" max="90" value={f.lat} onChange={(e) => editarCoord('lat', e.target.value)} /></Campo>
              <Campo label="Longitude"><input className={inp} type="number" step="0.0001" min="-180" max="180" value={f.lon} onChange={(e) => editarCoord('lon', e.target.value)} /></Campo>
            </div>
            <div>
              <div className="mb-1 text-sm font-medium text-ink">Locais com dados já baixados (funcionam offline)</div>
              <div className="flex flex-wrap gap-1.5">
                {locais.map((l) => (
                  <button key={l.nome} onClick={() => escolherLocalConhecido(l)}
                    className="rounded border border-line bg-white px-2 py-1 text-xs hover:border-field">{l.nome}</button>
                ))}
              </div>
            </div>
            {cobre && (
              <div className="rounded-md border border-line bg-white p-3 text-xs">
                <div className="mb-1 font-semibold text-ink">Fontes para este ponto</div>
                {fontes.map((x) => (
                  <div key={x.id} className="flex justify-between gap-2 py-0.5">
                    <span className="text-stone">{x.nome.split(' (')[0]}</span>
                    <span>{!x.cobre_local ? <Badge color="#A23B2A">sem cobertura</Badge> : x.status === 'integrado' ? <Badge color="#3F7D4E">nos cálculos</Badge> : x.status === 'visual' ? <Badge color="#2F6690">visual</Badge> : <Badge>não integrado</Badge>}</span>
                  </div>
                ))}
                <div className="mt-1 text-stone">{fontes.find((x) => x.id === 'nasa_power')?.nota_local}</div>
              </div>
            )}
          </div>
        </div>
      </Section>

      <Section title="Dados gerais e solo">
        <div className="grid gap-4 md:grid-cols-3">
          <Campo label="Nome" hint={nomeValido(f) ? null : 'Obrigatório: defina o nome desta propriedade.'}>
            <input className={`${inp} ${nomeValido(f) ? '' : 'border-ochre'}`} value={f.nome} placeholder="ex.: Sítio Boa Vista" onChange={(e) => set('nome', e.target.value)} />
          </Campo>
          <Campo label="País" hint={f.localidade_fonte ? `Fonte: ${f.localidade_fonte}` : null}><input className={inp} value={f.pais || ''} placeholder={SEM_LOCAL} onChange={(e) => setLocalManual('pais', e.target.value)} /></Campo>
          <Campo label="Região / município"><input className={inp} value={f.regiao || ''} placeholder={SEM_LOCAL} onChange={(e) => setLocalManual('regiao', e.target.value)} /></Campo>
          <Campo label="Área (ha)"><input className={inp} type="number" min="0" step="0.1" value={f.area_ha ?? ''} onChange={(e) => set('area_ha', e.target.value)} /></Campo>
          <Campo label="Textura do solo">
            <select className={inp} value={f.solo?.textura || ''} onChange={(e) => setSolo('textura', e.target.value || null)}>
              <option value="">Não sei</option><option value="arenosa">Arenosa</option><option value="media">Média</option><option value="argilosa">Argilosa</option>
            </select>
          </Campo>
          <Campo label="Profundidade útil (cm)"><input className={inp} type="number" min="0" value={f.solo?.profundidade_cm ?? ''} onChange={(e) => setSolo('profundidade_cm', e.target.value)} /></Campo>
          <Campo label="Matéria orgânica (%)" hint="Da análise de solo, se houver."><input className={inp} type="number" min="0" step="0.1" value={f.solo?.materia_organica_pct ?? ''} onChange={(e) => setSolo('materia_organica_pct', e.target.value)} /></Campo>
          <Campo label="pH"><input className={inp} type="number" min="2" max="12" step="0.1" value={f.solo?.ph ?? ''} onChange={(e) => setSolo('ph', e.target.value)} /></Campo>
          <Campo label="Declividade (%)" hint="Deixe em branco para estimar com SRTM 90 m (exige internet).">
            <input className={inp} type="number" min="0" step="0.5" value={f.declividade_pct ?? ''} onChange={(e) => set('declividade_pct', e.target.value)} />
          </Campo>
        </div>
      </Section>

      <Section title="Água disponível">
        <div className="grid gap-4 md:grid-cols-3">
          <Campo label="Irrigação disponível (mm por ano)" hint="0 = sequeiro. 100 mm sobre 1 ha = 1.000 m³.">
            <input className={inp} type="number" min="0" step="10" value={f.irrigacao_mm_ano} onChange={(e) => set('irrigacao_mm_ano', e.target.value)} />
          </Campo>
          <Campo label="Fonte de água"><input className={inp} value={f.fonte_agua || ''} placeholder="ex.: cisterna, poço, açude" onChange={(e) => set('fonte_agua', e.target.value)} /></Campo>
        </div>
      </Section>

      <Section title="Rotação atual" aside="Horizonte de 2 anos; repete-se a cada ciclo de 24 meses.">
        <Panel>
          <table className="w-full text-sm">
            <thead><tr className="text-left text-stone"><th className="pb-2 font-medium">Cultura</th><th className="pb-2 font-medium">Ano</th><th className="pb-2 font-medium">Mês de semeadura</th><th /></tr></thead>
            <tbody>
              {f.rotacao_atual.map((s, i) => (
                <tr key={i} className="border-t border-line">
                  <td className="py-2 pr-2"><select className={inp} value={s.cultura} onChange={(e) => setSlot(i, 'cultura', e.target.value)}>
                    {catalogo.map((c) => <option key={c.id} value={c.id}>{c.nome} ({c.tipo}, {c.ciclo_dias} dias)</option>)}
                  </select></td>
                  <td className="py-2 pr-2"><select className={inp} value={s.ano} onChange={(e) => setSlot(i, 'ano', e.target.value)}><option value={1}>1</option><option value={2}>2</option></select></td>
                  <td className="py-2 pr-2"><select className={inp} value={s.mes} onChange={(e) => setSlot(i, 'mes', e.target.value)}>
                    {MESES.map((m, j) => <option key={m} value={j + 1}>{m}</option>)}
                  </select></td>
                  <td className="py-2 text-right"><button className="text-sm text-clay underline" onClick={() => delSlot(i)}>Remover</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3"><Button variant="ghost" onClick={addSlot}>Adicionar cultura</Button></div>
          <p className="mt-2 text-xs text-stone">Meses sem cultura são considerados pousio (solo descoberto).</p>
        </Panel>
        <div className="mt-4">
          <Campo label="Histórico de plantio (texto livre)"><textarea className={inp} rows={2} value={f.historico || ''} onChange={(e) => set('historico', e.target.value)} /></Campo>
        </div>
      </Section>

      <Section title="Culturas que podem entrar nas novas estratégias">
        <div className="flex flex-wrap gap-2">
          {catalogo.map((c) => (
            <label key={c.id} className={`flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm ${perm.includes(c.id) ? 'border-field bg-field-soft text-ink' : 'border-line text-stone'}`}>
              <input type="checkbox" checked={perm.includes(c.id)} onChange={() => togglePerm(c.id)} className="accent-[#3F7D4E]" />
              {c.nome}<span className="text-xs text-stone">{c.tipo === 'cobertura' ? 'cobertura' : ''}</span>
            </label>
          ))}
        </div>
      </Section>

      <Section title="Prioridades do agricultor" aside="Definem a estratégia D (equilíbrio). 0 = não importa, 5 = muito importante.">
        <div className="grid gap-4 md:grid-cols-5">
          {PRIORIDADES.map(([k, t]) => (
            <label key={k} className="block">
              <span className="text-sm font-medium text-ink">{t}</span>
              <input type="range" min="0" max="5" step="1" value={f.prioridades?.[k] ?? 1} onChange={(e) => setPrior(k, e.target.value)} className="mt-2 w-full accent-[#3F7D4E]" />
              <span className="num text-sm text-stone">{f.prioridades?.[k] ?? 1}</span>
            </label>
          ))}
        </div>
      </Section>

      <Section title="Propriedades salvas">
        {salvas.length === 0 ? <p className="text-sm text-stone">Nenhuma propriedade salva. Use "Salvar" para guardar esta configuração no banco local (SQLite).</p> : (
          <ul className="divide-y divide-line rounded-md border border-line bg-white">
            {salvas.map((s) => (
              <li key={s.id} className="flex items-center justify-between px-4 py-2 text-sm">
                <span><b className="text-ink">{s.nome}</b> <span className="text-stone">· atualizada em {new Date(s.atualizado_em).toLocaleString('pt-BR')}</span></span>
                <span className="flex gap-3"><button className="text-field underline" onClick={() => abrir(s.id)}>Abrir</button><button className="text-clay underline" onClick={() => excluir(s.id)}>Excluir</button></span>
              </li>
            ))}
          </ul>
        )}
      </Section>
      {pendenteManejo && <div className="mb-4 rounded-md border border-ochre/50 bg-[#fbf5ea] p-4 text-sm text-ink">
        <label className="flex cursor-pointer items-start gap-2">
          <input type="checkbox" className="mt-1 accent-[#3F7D4E]" checked={false} onChange={(e) => confirmarManejo(e.target.checked)} />
          <span><b>Antes de analisar:</b> confirmei os dados de solo, culturas, histórico, calendário e irrigação para este local, ou reconheço que são demonstrativos.</span>
        </label>
      </div>}
      <div className="flex justify-end"><Button onClick={rodar} disabled={carregando}>Analisar propriedade</Button></div>
    </>
  )
}
