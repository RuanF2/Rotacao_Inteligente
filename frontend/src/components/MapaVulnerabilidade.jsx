import { useEffect, useMemo, useState } from 'react'
import { CircleMarker, LayerGroup, LayersControl, MapContainer, Marker, Popup, Rectangle, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import { CLASSE_COR, n } from '../lib/format'

const pin = L.divIcon({
  className: '',
  html: '<div style="width:18px;height:18px;border-radius:50% 50% 50% 0;background:#12352A;transform:rotate(-45deg);border:3px solid white;box-shadow:0 1px 4px rgba(0,0,0,.4)"></div>',
  iconSize: [18, 18], iconAnchor: [9, 18],
})

/** Célula aproximada da grade MERRA-2 usada pelo NASA POWER (0,5° × 0,625°). */
export function celulaPower(lat, lon) {
  const clat = Math.round(lat / 0.5) * 0.5
  const clon = Math.round(lon / 0.625) * 0.625
  return [[clat - 0.25, clon - 0.3125], [clat + 0.25, clon + 0.3125]]
}

function Recentrar({ lat, lon }) {
  const map = useMap()
  useEffect(() => { map.setView([lat, lon], map.getZoom()) }, [lat, lon]) // eslint-disable-line
  return null
}

function Clique({ onPick }) {
  useMapEvents({ click: (e) => onPick && onPick(e.latlng.lat, e.latlng.lng) })
  return null
}

function dataPadrao(diasAtras) {
  const d = new Date(Date.now() - diasAtras * 86400000)
  return d.toISOString().slice(0, 10)
}

export default function MapaVulnerabilidade({ lat, lon, pontos = [], camadas, onPick, height = 460, zoom = 6, nome }) {
  const [data, setData] = useState(dataPadrao(20))
  const [falhaTiles, setFalhaTiles] = useState(false)
  const gibs = useMemo(() => {
    if (!camadas) return []
    return Object.entries(camadas.camadas).map(([k, c]) => ({
      k, nome: c.nome, desc: c.descricao,
      url: camadas.url_modelo.replace('{layer}', c.id).replace('{time}', data).replace('{tile_matrix_set}', c.tile_matrix_set),
      maxNative: Number(c.tile_matrix_set.match(/Level(\d+)/)?.[1] || 6),
    }))
  }, [camadas, data])
  const cel = celulaPower(lat, lon)
  return (
    <div>
      <div className="no-print mb-2 flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2 text-stone">
          Data das camadas de satélite
          <input type="date" value={data} max={dataPadrao(1)} onChange={(e) => { setData(e.target.value); setFalhaTiles(false) }}
            className="rounded border border-line px-2 py-1 text-ink" />
        </label>
        <span className="text-xs text-stone">Use o seletor de camadas no canto do mapa. Camadas NASA GIBS são apenas visuais.</span>
      </div>
      <div className="overflow-hidden rounded-md border border-line" style={{ height }}>
        <MapContainer center={[lat, lon]} zoom={zoom} style={{ height: '100%', width: '100%' }} scrollWheelZoom>
          <Recentrar lat={lat} lon={lon} />
          {onPick && <Clique onPick={onPick} />}
          <LayersControl position="topright">
            <LayersControl.BaseLayer checked name="Mapa (OpenStreetMap)">
              <TileLayer attribution="&copy; OpenStreetMap" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            </LayersControl.BaseLayer>
            <LayersControl.BaseLayer name="Imagem de satélite (Esri)">
              <TileLayer attribution="Esri, Maxar, Earthstar Geographics" url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
            </LayersControl.BaseLayer>
            {gibs.map((g) => (
              <LayersControl.Overlay key={g.k + data} name={`${g.nome} — NASA GIBS (visual)`}>
                <TileLayer url={g.url} opacity={0.7} maxNativeZoom={g.maxNative} maxZoom={14}
                  attribution="NASA EOSDIS GIBS" eventHandlers={{ tileerror: () => setFalhaTiles(true) }} />
              </LayersControl.Overlay>
            ))}
            <LayersControl.Overlay checked name="Vulnerabilidade climática (pontos NASA POWER)">
              <LayerGroup>
                {pontos.filter((p) => p.vulnerabilidade != null).map((p) => (
                  <CircleMarker key={p.nome} center={[p.lat, p.lon]} radius={11}
                    pathOptions={{ color: 'white', weight: 2, fillColor: CLASSE_COR[p.classe_vulnerabilidade], fillOpacity: 0.9 }}>
                    <Popup>
                      <div className="text-sm">
                        <b>{p.nome}</b><br />
                        Vulnerabilidade climática: {n(p.vulnerabilidade, 2)} ({p.classe_vulnerabilidade})<br />
                        Chuva anual: {n(p.precipitacao_anual_mm)} mm · Aridez {n(p.indice_aridez, 2)} ({p.classe_aridez})<br />
                        Dias Tmax ≥ 35 °C: {n(p.dias_calor)} · GWETROOT (modelo): {n(p.gwetroot, 2)}<br />
                        Índice de Fournier: {n(p.indice_fournier)}<br />
                        <i>{p.nota}</i>
                      </div>
                    </Popup>
                  </CircleMarker>
                ))}
              </LayerGroup>
            </LayersControl.Overlay>
            <LayersControl.Overlay checked name="Célula NASA POWER (≈50 km)">
              <Rectangle bounds={cel} pathOptions={{ color: '#2F6690', weight: 1.5, dashArray: '5 4', fillOpacity: 0.05 }}>
                <Tooltip sticky>Os dados climáticos representam esta célula da grade, não o talhão.</Tooltip>
              </Rectangle>
            </LayersControl.Overlay>
          </LayersControl>
          <Marker position={[lat, lon]} icon={pin}>
            <Popup>{nome || 'Propriedade'}<br />{n(lat, 4)}, {n(lon, 4)}</Popup>
          </Marker>
        </MapContainer>
      </div>
      {falhaTiles && (
        <p className="mt-2 text-sm text-ochre">Algumas imagens do NASA GIBS não carregaram para {data} (sem internet, sem passagem do satélite ou data ainda não processada). Tente outra data.</p>
      )}
      <div className="mt-2 flex flex-wrap gap-3 text-xs text-stone">
        {['baixa', 'moderada', 'alta', 'crítica'].map((c) => (
          <span key={c} className="flex items-center gap-1"><span className="h-3 w-3 rounded-full" style={{ background: CLASSE_COR[c] }} />{c}</span>
        ))}
        <span>Pontos: índice climático calculado onde há série NASA POWER em cache (sem declividade nem manejo).</span>
      </div>
    </div>
  )
}
