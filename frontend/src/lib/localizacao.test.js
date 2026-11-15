// Executar: npm test   (node --test, sem dependências extras)
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  SEM_LOCAL, FONTE_USUARIO, aplicarGeocodificacao, analiseCorresponde, coordsIguais, nomeValido, rotuloLocal, trocarLocalizacao,
} from './localizacao.js'

const DEMO = {
  nome: 'Sítio Demonstrativo Serra da Capivara', lat: -9.015, lon: -42.69889, regiao: 'São Raimundo Nonato – PI (semiárido)',
  pais: 'Brasil', localidade_fonte: 'configuração do projeto', demonstrativa: true, declividade_pct: null, irrigacao_mm_ano: 0,
  solo: { textura: 'arenosa', profundidade_cm: 60 }, rotacao_atual: [{ cultura: 'milho', ano: 1, mes: 1 }],
  historico: 'Milho todo ano', culturas_permitidas: null,
}

test('trocar para a França descarta município/região/país anteriores', () => {
  const { f, aviso } = trocarLocalizacao(DEMO, 47.01, 5.768, { nomeDemo: DEMO.nome })
  assert.equal(f.lat, 47.01)
  assert.equal(f.lon, 5.768)
  assert.equal(f.regiao, null)
  assert.equal(f.pais, null)
  assert.equal(f.localidade_fonte, null)
  assert.equal(f.demonstrativa, false)
  assert.equal(rotuloLocal(f), SEM_LOCAL)
  assert.equal(aviso.de.local, 'São Raimundo Nonato – PI (semiárido), Brasil')
})

test('nome demonstrativo é limpo; nome de propriedade real é preservado', () => {
  const demo = trocarLocalizacao(DEMO, 47.01, 5.768, { nomeDemo: DEMO.nome })
  assert.equal(demo.f.nome, '')
  assert.equal(demo.aviso.nomeLimpo, true)
  assert.equal(nomeValido(demo.f), false)
  const real = { ...DEMO, nome: 'Fazenda Boa Esperança', demonstrativa: false }
  const r = trocarLocalizacao(real, 47.01, 5.768, { nomeDemo: DEMO.nome })
  assert.equal(r.f.nome, 'Fazenda Boa Esperança')
  assert.equal(r.aviso.nomeLimpo, false)
})

test('demonstração renomeada pelo usuário mantém o nome digitado', () => {
  const renomeada = { ...DEMO, nome: 'Fazenda Boa Esperança' }   // ainda marcada como demonstrativa
  const { f, aviso } = trocarLocalizacao(renomeada, 41.6, -93.6, { nomeDemo: DEMO.nome })
  assert.equal(f.nome, 'Fazenda Boa Esperança')
  assert.equal(aviso.nomeLimpo, false)
})

test('aviso lista solo, culturas/calendário e histórico do local anterior', () => {
  const { aviso } = trocarLocalizacao(DEMO, 47.01, 5.768)
  assert.ok(aviso.revisar.includes('dados de solo'))
  assert.ok(aviso.revisar.some((x) => x.startsWith('culturas e calendário')))
  assert.ok(aviso.revisar.includes('histórico de plantio'))
})

test('mesma coordenada não gera troca nem aviso; coordenada inválida é ignorada', () => {
  assert.equal(trocarLocalizacao(DEMO, -9.015, -42.69889).aviso, null)
  const inval = trocarLocalizacao(DEMO, 120, 5)
  assert.equal(inval.aviso, null)
  assert.equal(inval.f, DEMO)
})

test('troca de localização também descarta declividade informada para o terreno anterior', () => {
  const { f, aviso } = trocarLocalizacao({ ...DEMO, declividade_pct: 12 }, 47.01, 5.768)
  assert.equal(f.declividade_pct, null)
  assert.ok(aviso.revisar.includes('declividade'))
})

const GEO_OK = { identificado: true, municipio: 'Dijon', regiao: 'Bourgogne-Franche-Comté', pais: 'França', fonte: 'OpenStreetMap Nominatim' }

test('geocodificação bem-sucedida preenche localidade com a fonte', () => {
  const { f } = trocarLocalizacao(DEMO, 47.01, 5.768)
  const g = aplicarGeocodificacao(f, GEO_OK, { lat: 47.01, lon: 5.768 })
  assert.equal(g.regiao, 'Dijon – Bourgogne-Franche-Comté')
  assert.equal(g.pais, 'França')
  assert.equal(g.localidade_fonte, 'OpenStreetMap Nominatim')
})

test('falha ou ponto sem endereço mantém "Localização não identificada"', () => {
  const { f } = trocarLocalizacao(DEMO, 47.01, 5.768)
  assert.equal(aplicarGeocodificacao(f, null, { lat: 47.01, lon: 5.768 }), f)
  const mar = aplicarGeocodificacao(f, { identificado: false, municipio: null, pais: null }, { lat: 47.01, lon: 5.768 })
  assert.equal(rotuloLocal(mar), SEM_LOCAL)
})

test('resposta atrasada de outra coordenada é descartada', () => {
  const { f } = trocarLocalizacao(DEMO, 47.01, 5.768)
  const depois = trocarLocalizacao(f, 48.5, 2.3).f
  assert.equal(aplicarGeocodificacao(depois, GEO_OK, { lat: 47.01, lon: 5.768 }), depois)
})

test('local digitado pelo usuário não é sobrescrito pela geocodificação', () => {
  const { f } = trocarLocalizacao(DEMO, 47.01, 5.768)
  const digitado = { ...f, regiao: 'Minha comuna', pais: 'França', localidade_fonte: FONTE_USUARIO }
  assert.equal(aplicarGeocodificacao(digitado, GEO_OK, { lat: 47.01, lon: 5.768 }), digitado)
})

test('análise só é exibida para as mesmas coordenadas da propriedade ativa', () => {
  const analise = { propriedade: { lat: -9.015, lon: -42.69889 } }
  assert.equal(analiseCorresponde(analise, DEMO), true)
  assert.equal(analiseCorresponde(analise, { ...DEMO, lat: 47.01, lon: 5.768 }), false)
  assert.equal(analiseCorresponde(null, DEMO), false)
})

test('persistência: o JSON salvo/restaurado mantém a nova localização sem metadados antigos', () => {
  const { f } = trocarLocalizacao(DEMO, 47.01, 5.768)
  const salvo = JSON.parse(JSON.stringify(f))
  assert.ok(coordsIguais(salvo, { lat: 47.01, lon: 5.768 }))
  assert.equal(salvo.regiao, null)
  assert.equal(rotuloLocal(salvo), SEM_LOCAL)
})
