import { useEffect, useState } from 'react'
import { marked } from 'marked'
import { api } from '../lib/api'
import { AnaliseGate, Button, ErrorBox, Loader, PageHeader } from '../components/ui'
import { analiseCorresponde } from '../lib/localizacao'

// O relatório contém textos digitados pelo usuário: HTML bruto é exibido como texto, nunca interpretado.
marked.use({ renderer: { html({ text }) { return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') } } })

export default function Relatorio(props) {
  const { prop, analise } = props
  const [md, setMd] = useState(null)
  const [erro, setErro] = useState(null)
  const [carregando, setCarregando] = useState(false)

  const gerar = async () => {
    setCarregando(true); setErro(null)
    try { setMd(await api.relatorio(prop)) } catch (e) { setErro(e) } finally { setCarregando(false) }
  }
  useEffect(() => { setMd(null); if (analiseCorresponde(analise, prop)) gerar() }, [analise, prop]) // eslint-disable-line

  const baixar = () => {
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `relatorio-${(prop.nome || 'propriedade').toLowerCase().replace(/[^a-z0-9]+/g, '-')}.md`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <>
      <PageHeader title="Relatório" actions={md && <>
        <Button variant="ghost" onClick={baixar}>Baixar Markdown</Button>
        <Button onClick={() => window.print()}>Imprimir ou salvar PDF</Button>
      </>}>
        Documento com a propriedade, as fontes usadas, as condições ambientais, as estratégias comparadas, riscos e limitações.
      </PageHeader>
      <AnaliseGate {...props}><></></AnaliseGate>
      <ErrorBox error={erro} onRetry={gerar} />
      {carregando && <Loader text="Montando o relatório…" />}
      {md && !carregando && (
        <article className="prose-rel rounded-md border border-line bg-white p-8 print:border-0 print:p-0" dangerouslySetInnerHTML={{ __html: marked.parse(md) }} />
      )}
    </>
  )
}
