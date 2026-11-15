import test from 'node:test'
import assert from 'node:assert/strict'
import { ROTULO_PERDA_AGUA, ROTULO_INDICE_AGUA_FRIO, haExposicaoTermica, requerAlertaAgronomico, ausenciaPerdaHidricaNaoGaranteSeguranca } from './interpretacao.js'

test('perda hídrica explicita escopo, e indice hidrico inclui temperatura', () => {
  assert.match(ROTULO_PERDA_AGUA, /falta de água/)
  assert.match(ROTULO_INDICE_AGUA_FRIO, /térmica/)
})

test('frio/geada deve gerar alerta mesmo quando perda hidrica é zero', () => {
  const avaliacao = { restricoes: { viavel: false }, slots: [{ nome: 'Milho', fracao_dias_frio: 0.84, perda_rendimento_media: 0 }] }
  assert.equal(haExposicaoTermica(avaliacao), true)
  assert.equal(requerAlertaAgronomico(avaliacao), true)
  assert.equal(ausenciaPerdaHidricaNaoGaranteSeguranca(avaliacao), true)
})

test('calor elevado também dispara alerta sem inventar perda', () => {
  assert.equal(requerAlertaAgronomico({restricoes:{viavel:true},slots:[{fracao_dias_calor:0.3, perda_rendimento_media:0}]}),true)
})

test('rotação sem exposicao ou restricoes violadas nao recebe alerta falso', () => {
  const a={restricoes:{viavel:true},slots:[{fracao_dias_calor:0,fracao_dias_frio:0,perda_rendimento_media:0}]}
  assert.equal(requerAlertaAgronomico(a),false)
  assert.equal(ausenciaPerdaHidricaNaoGaranteSeguranca(a),false)
})
