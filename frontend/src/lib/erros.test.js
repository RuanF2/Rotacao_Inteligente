import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretarErro } from './erros.js'

test('diagnóstico de inviabilidade mantém verificações sem inventar causa', () => {
  const diagnostico = { tipo: 'sem_estrategia_viavel', titulo: 'Nenhuma rotação viável foi encontrada',
    verificacoes: [{ codigo: 'janela_termica', resultado: 'bloqueio_confirmado', detalhe: '12 de 12 meses' }] }
  const erro = interpretarErro({ detail: { mensagem: 'Busca sem soluções', diagnostico } }, 422)
  assert.equal(erro.message, 'Busca sem soluções')
  assert.deepEqual(erro.diagnostico, diagnostico)
})

test('erro HTTP anterior continua legível e sem diagnóstico inventado', () => {
  const erro = interpretarErro({ detail: 'Falha de conexão' }, 503)
  assert.equal(erro.message, 'Falha de conexão')
  assert.equal(erro.diagnostico, undefined)
})

test('422 do Pydantic continua exibindo campos', () => {
  const erro = interpretarErro({ detail: [{ loc: ['body', 'lat'], msg: 'campo inválido' }] }, 422)
  assert.match(erro.message, /lat: campo inválido/)
})
