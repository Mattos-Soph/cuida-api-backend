import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.units import cm
import qrcode
import io

# ==============================================================================
# FUNÇÃO PRINCIPAL (A MÁQUINA DE PDF)
# ==============================================================================
# 🌟 CORREÇÃO 1: Adicionado 'subtitulo_extra=None' na assinatura da função
def gerar_documento_base(titulo_doc, referencia, data, conteudo, caminho_salvar, subtitulo_extra=None):
    """
    Função genérica que monta o layout padrão da Prefeitura de Marília.
    """
    
    # Gera ID único para rastreio interno
    doc_id = f"DOC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    base_url = "http://sistema.saude.marilia.gov.br/documentos"

    # --- GERAÇÃO DO QR CODE (EM MEMÓRIA, SEM ARQUIVO TEMPORÁRIO) ---
    qr = qrcode.make(f"{base_url}/{doc_id}")
    qr_buffer = io.BytesIO()
    qr.save(qr_buffer, format='PNG')
    qr_buffer.seek(0) # Volta o ponteiro para o início da memória
    imagem_qr = Image(qr_buffer, width=2.5 * cm, height=2.5 * cm)

    # --- SETUP DO DOCUMENTO ---
    doc = SimpleDocTemplate(
        caminho_salvar,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
    )

    elementos = []
    estilos = getSampleStyleSheet()

    # --- ESTILOS PERSONALIZADOS ---
    estilo_titulo = ParagraphStyle("titulo", parent=estilos["Heading1"], alignment=TA_CENTER, fontSize=18, spaceAfter=20)
    estilo_subtitulo = ParagraphStyle("subtitulo", parent=estilos["Heading2"], alignment=TA_CENTER, fontSize=14, spaceAfter=15)
    estilo_normal = ParagraphStyle("normal", parent=estilos["Normal"], alignment=TA_LEFT, fontSize=12, spaceAfter=12)
    estilo_data = ParagraphStyle("data", parent=estilos["Normal"], alignment=TA_RIGHT, fontSize=11, spaceAfter=20)
    estilo_rodape = ParagraphStyle("rodape", parent=estilos["Normal"], alignment=TA_CENTER, fontSize=9, textColor=colors.grey)

    # --- CABEÇALHO (LOGO E TÍTULOS) ---
    if os.path.exists("logo_marilia.png"):
        logo = Image("logo_marilia.png", width=3 * cm, height=3 * cm)
        logo.hAlign = "CENTER"
        elementos.append(logo)

    elementos.append(Paragraph("Prefeitura Municipal de Marília", estilo_titulo))
    elementos.append(Paragraph("Secretaria Municipal de Saúde", estilo_subtitulo))
    elementos.append(Paragraph(titulo_doc, estilo_subtitulo))
    
    # 🌟 CORREÇÃO 2: Exibir o nome da unidade (subtítulo extra)
    if subtitulo_extra:
        elementos.append(Paragraph(f"Unidade de Filtro: <b>{subtitulo_extra}</b>", estilo_normal))
        
    elementos.append(Paragraph(f"Referência: {referencia}", estilo_normal))
    elementos.append(Paragraph(f"Data de Emissão: {data}", estilo_data))

    # --- CORPO (TABELA OU TEXTO) ---
    if isinstance(conteudo, list):
        # Se for lista, desenha Tabela
        # 🌟 CORREÇÃO 3: Largura ajustada para caber o nome do medicamento
        tabela = Table(conteudo, colWidths=[9.5 * cm, 3.5 * cm, 2.0 * cm]) 
        tabela.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004080")), # Azul Prefeitura
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]), # Zebrado
            ])
        )
        elementos.append(tabela)
    else:
        # Se for string, desenha Texto (ex: Laudo)
        elementos.append(Paragraph(conteudo, estilo_normal))

    elementos.append(Spacer(1, 40))

    # --- RODAPÉ (QR CODE + INFO) ---
    rodape_dados = [[
        imagem_qr,
        Paragraph(f"<b>Autenticidade:</b> {doc_id}<br/>Documento oficial gerado pelo Sistema CUIDA.", estilo_rodape)
    ]]
    
    rodape_tabela = Table(rodape_dados, colWidths=[3 * cm, 12 * cm])
    rodape_tabela.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "LEFT"),
    ]))
    elementos.append(rodape_tabela)

    # --- BUILD (GERAR ARQUIVO) ---
    # Função auxiliar para desenhar a borda da página
    def desenhar_margem(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#DDDDDD"))
        canvas.setLineWidth(1)
        canvas.rect(1.0 * cm, 1.0 * cm, A4[0] - 2.0 * cm, A4[1] - 2.0 * cm)
        canvas.restoreState()

    doc.build(elementos, onFirstPage=desenhar_margem, onLaterPages=desenhar_margem)
    print(f"✅ PDF Gerado: {caminho_salvar}")


# ==============================================================================
# FUNÇÕES ESPECÍFICAS (INTERFACES PARA A API)
# ==============================================================================

def gerar_nfe(referencia, data, itens, caminho="nfe.pdf"):
    # Cabeçalho da tabela
    conteudo = [["Produto", "Lote", "Qtd."]] + itens
    gerar_documento_base("Nota Fiscal Eletrônica (NF-e)", referencia, data, conteudo, caminho)

def gerar_relatorio_mensal(referencia, data, valores, caminho="relatorio_mensal.pdf"):
    conteudo = [["Mês", "Entradas", "Saídas"]] + valores
    gerar_documento_base("Relatório Mensal de Estoque", referencia, data, conteudo, caminho)

def gerar_laudo_auditoria(referencia, data, texto, caminho="laudo_auditoria.pdf"):
    # Laudo geralmente é texto corrido, não tabela
    gerar_documento_base("Laudo de Auditoria Técnica", referencia, data, texto, caminho)

# 🌟 CORREÇÃO FINAL: Adicionado 'unidade_destino=None' para ser usado como subtítulo extra
def gerar_relatorio_saidas(referencia, data, saidas, unidade_destino=None, caminho="relatorio_saidas.pdf"):
    conteudo = [["Medicamento", "Unidade Destino", "Qtd. Enviada"]] + saidas
    # Chamando a base com o nome da unidade para o cabeçalho
    gerar_documento_base("Relatório de Saídas e Movimentação", referencia, data, conteudo, caminho, subtitulo_extra=unidade_destino)