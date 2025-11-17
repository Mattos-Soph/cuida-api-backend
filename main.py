# main.py
from flask import Flask, send_file, jsonify
from datetime import datetime
from gerador_docs import (
    gerar_nfe,
    gerar_relatorio_mensal,
    gerar_laudo_auditoria,
    gerar_relatorio_saidas
)
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# --- CONFIGURAÇÃO DO SUPABASE ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ ERRO: SUPABASE_URL e SUPABASE_KEY precisam estar no arquivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

# --- ROTA TESTE ---
@app.route('/')
def home():
    return jsonify({"status": "API CUIDA Conectada e Rodando!"})

# ==============================================================================
# 1. ROTA RELATÓRIO DE ESTOQUE (Antigo Relatório de Saídas)
# ==============================================================================
@app.route('/gerar_relatorio_saidas', methods=['GET'])
def gerar_relatorio_saidas_route():
    try:
        # 1. Busca dados reais no banco
        response = supabase.table("estoque_medicamentos").select("*").execute()
        dados_banco = response.data 

        # 2. Formata para o ReportLab 
        dados_para_pdf = []
        for item in dados_banco:
            linha = [
                item['nome'],           
                item['unidade'],        
                str(item['quantidade']) 
            ]
            dados_para_pdf.append(linha)

        # 3. Gera o PDF
        data_hoje = datetime.now().strftime("%d/%m/%Y")
        nome_arquivo = "relatorio_estoque_real.pdf"
        
        # CORREÇÃO AQUI: Passando 'caminho=nome_arquivo'
        gerar_relatorio_saidas("REL-ESTOQUE-DB", data_hoje, dados_para_pdf, caminho=nome_arquivo)
        
        return send_file(nome_arquivo, as_attachment=True)

    except Exception as e:
        return jsonify({"erro": f"Falha ao gerar PDF: {str(e)}"}), 500

# ==============================================================================
# 2. ROTA RELATÓRIO MENSAL
# ==============================================================================
@app.route('/gerar_relatorio_mensal', methods=['GET'])
def gerar_relatorio_mensal_route():
    try:
        response = supabase.table("relatorio_mensal").select("*").execute()
        dados_banco = response.data

        # Formata: [Mês, Entradas, Saídas]
        dados_para_pdf = []
        for item in dados_banco:
            dados_para_pdf.append([
                item['mes'],
                str(item['entradas']),
                str(item['saidas'])
            ])

        data_hoje = datetime.now().strftime("%d/%m/%Y")
        gerar_relatorio_mensal("RM-2025-DB", data_hoje, dados_para_pdf)
        
        return send_file("relatorio_mensal.pdf", as_attachment=True)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# ==============================================================================
# 3. ROTA NOTA FISCAL (NF-e)
# ==============================================================================
@app.route('/gerar_nfe', methods=['GET'])
def gerar_nfe_route():
    try:
        # Pega dados da tabela 'nfe'
        response = supabase.table("nfe").select("*").execute()
        dados_banco = response.data

        # Formata: [Produto, Lote, Qtd] (Ajuste conforme seu layout pede)
        dados_para_pdf = []
        for item in dados_banco:
            dados_para_pdf.append([
                item['produto'],
                item['lote'],
                str(item['quantidade'])
            ])

        data_hoje = datetime.now().strftime("%d/%m/%Y")
        gerar_nfe("NF-2025-AUTO", data_hoje, dados_para_pdf)
        
        return send_file("nfe.pdf", as_attachment=True)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500


if __name__ == '__main__':
    # '0.0.0.0' permite que o celular/emulador acesse o PC
    app.run(debug=True, host='0.0.0.0')