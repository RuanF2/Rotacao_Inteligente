import test from 'node:test'
import assert from 'node:assert/strict'
import { assinaturaManejo, precisaRevisarManejo, avisoIndiceTermico } from './revisaoManejo.js'
const demo = { demonstrativa: true, lat: -9.015, lon: -42.6989, solo: { textura: 'arenosa' }, historico: 'demonstração', rotacao_atual: [{ cultura:'milho', ano:1, mes:1 }] }
test('demonstração no local original fica disponível', () => assert.equal(precisaRevisarManejo(demo,demo,''), false))
test('local novo requer confirmação explícita', () => { const p={...demo,lat:48.7,lon:2.3,demonstrativa:false}; assert.equal(precisaRevisarManejo(p,demo,''),true); assert.equal(precisaRevisarManejo(p,demo,assinaturaManejo(p)),false) })
test('alteração de solo, culturas, calendário ou coordenadas invalida confirmação', () => { const p={...demo, lat:48.7,lon:2.3,demonstrativa:false}; const s=assinaturaManejo(p); for (const q of [{...p,lat:48.8},{...p,solo:{textura:'argilosa'}},{...p,rotacao_atual:[{cultura:'trigo',ano:1,mes:1}]},{...p,historico:'novo'}]) assert.equal(precisaRevisarManejo(q,demo,s),true) })
test('nota do índice térmico separa calor regional de frio/geada',()=>{const x=avisoIndiceTermico(); assert.match(x,/35 °C/);assert.match(x,/geadas/)})
