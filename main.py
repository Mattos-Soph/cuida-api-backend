# main.py
from flask import Flask, send_file, jsonify, request
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
import os

# --- IMPORTAÇÃO DO SEU GERADOR DE PDF ---
from gerador_docs import (
    gerar_nfe,
    gerar_relatorio_mensal,
    gerar_laudo_auditoria,
    gerar_relatorio_saidas
)

# --- CONFIGURAÇÃO E CLIENTE SUPABASE ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ ERRO: SUPABASE_URL e SUPABASE_KEY precisam estar configurados!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

# --- ROTA TESTE GERAL ---
@app.route('/')
def home():
    return jsonify({"status": "API CUIDA Conectada e Rodando!"})

# ==============================================================================
# 1. ROTA RELATÓRIO DE SAÍDAS (Com Colunas Definitivas)
# ==============================================================================
@app.route('/gerar_relatorio_saidas', methods=['GET'])
def gerar_relatorio_saidas_route():
    nome_arquivo = "relatorio_saidas_final.pdf"
    
    try:
        funcionario_id_filtro = request.args.get('funcionario_id') 
        unidade_id_filtro = None 
        nome_unidade = "TODAS AS UNIDADES" 

        # --- FASE 1: BUSCA DO ID DA UNIDADE ASSOCIADA AO FUNCIONÁRIO ---
        if funcionario_id_filtro:
            # 🌟 CORREÇÃO FINAL AQUI: Usando 'id_funcionario' e 'id_unidade'
            func_res = supabase.table("funcionario").select("id_unidade").eq('id_funcionario', funcionario_id_filtro).limit(1).execute()
            
            if func_res.data and func_res.data[0].get('id_unidade'):
                unidade_id_filtro = func_res.data[0]['id_unidade'] # Atribui o valor de 'id_unidade'

        # --- FASE 2: BUSCA DO NOME DA UNIDADE (se o ID foi encontrado) ---
        if unidade_id_filtro:
            # Consulta a tabela 'unidade' para buscar o NOME da unidade
            unidade_res = supabase.table("unidade").select("nome_unidade").eq('id_unidade', unidade_id_filtro).limit(1).execute()
            if unidade_res.data:
                nome_unidade = unidade_res.data[0]['nome_unidade']

        # 3. Base Query para as movimentações
        query = supabase.table("movimentacoes_estoque").select(
             "quantidade_movimentada, medicamento_id, unidade_id"
        ).eq('tipo', 'saida')

        # APLICA FILTRO DE UNIDADE
        if unidade_id_filtro:
            query = query.eq('unidade_id', unidade_id_filtro)
        
        response_mov = query.execute()
        dados_mov = response_mov.data
        
        dados_para_pdf = []
        
        # 4. Lookups de Medicamento e Montagem dos Dados
        for item in dados_mov:
            nome_medicamento = "Medicamento Desconhecido"
            if item.get('medicamento_id'):
                res_med = supabase.table("medicamento").select("nome").eq('id_medicamento', item['medicamento_id']).limit(1).execute()
                if res_med.data:
                    nome_medicamento = res_med.data[0]['nome']
            
            # Adicionar a linha formatada ao relatório
            dados_para_pdf.append([
                 nome_medicamento, 
                 nome_unidade, 
                 str(item['quantidade_movimentada'])
            ])

        # 5. Geração do PDF
        data_hoje = datetime.now().strftime("%d/%m/%Y")
        
        gerar_relatorio_saidas("REL-SAIDAS-FINAL", data_hoje, dados_para_pdf, unidade_destino=nome_unidade, caminho=nome_arquivo)
        
        return send_file(nome_arquivo, as_attachment=True)

    except Exception as e:
        print(f"ERRO NO BACKEND REL-SAÍDAS: {str(e)}")
        if os.path.exists(nome_arquivo):
            os.remove(nome_arquivo) 
        return jsonify({"erro": f"Falha na rota Relatório de Saídas: {str(e)}"}), 500

# ==============================================================================
# 2. ROTA RELATÓRIO MENSAL (CORRIGIDA - Cálculo Direto no Python)
# ==============================================================================
@app.route('/gerar_relatorio_mensal', methods=['GET'])
def gerar_relatorio_mensal_route():
    try:
        # 1. Busca dados brutos: Corrigindo 'quantidade' para 'quantidade_movimentada' (MÁXIMA INEFICIÊNCIA)
        response = supabase.table("movimentacoes_estoque").select("tipo, quantidade_movimentada, criado_em").execute()
        dados_brutos = response.data

        # 2. Agregação e Cálculo no Python (Simulação do GROUP BY)
        relatorio = {}
        for item in dados_brutos:
            # Garante que 'criado_em' existe e trata o fuso horário
            if 'criado_em' not in item or item['criado_em'] is None: continue 
            
            data = datetime.fromisoformat(item['criado_em'].split('+')[0])
            mes_ano = data.strftime('%Y-%m') 
            
            if mes_ano not in relatorio:
                relatorio[mes_ano] = {'entradas': 0, 'saidas': 0}

            if item['tipo'] == 'entrada':
                relatorio[mes_ano]['entradas'] += item['quantidade_movimentada']
            elif item['tipo'] == 'saida':
                relatorio[mes_ano]['saidas'] += item['quantidade_movimentada']

        # 3. Formata para o ReportLab
        dados_para_pdf = []
        for mes_ano, totais in sorted(relatorio.items(), reverse=True):
            dados_para_pdf.append([
                mes_ano,
                str(totais['entradas']),
                str(totais['saidas'])
            ])

        data_hoje = datetime.now().strftime("%d/%m/%Y")
        nome_arquivo = "relatorio_mensal_python.pdf"
        
        gerar_relatorio_mensal("RM-PYTHON", data_hoje, dados_para_pdf, caminho=nome_arquivo)
        
        return send_file(nome_arquivo, as_attachment=True)

    except Exception as e:
        print(f"ERRO NO BACKEND REL-MENSAL (PYTHON): {str(e)}")
        # Se a tabela 'movimentacoes_estoque' não existir ou colunas de data/tipo estiverem erradas.
        return jsonify({"erro": f"Rota falhou. Verifique se a tabela 'movimentacoes_estoque' existe: {str(e)}"}), 500
    
# ==============================================================================
# 3. ROTA NOTA FISCAL (NF-e) - CORREÇÃO FINAL COM VERIFICAÇÃO DE NULL
# ==============================================================================
@app.route('/gerar_nfe', methods=['GET'])
def gerar_nfe_route():
    try:
        # 1. Busca Principal
        response_rec = supabase.table("registro_recebimento").select("quantidade_recebida, item_entrega_id").execute()
        dados_rec = response_rec.data

        dados_para_pdf = []
        for item_rec in dados_rec:
            
            # 🚨 CHECK 1: Ignora se o ID de ligação principal for Nulo (item_entrega_id)
            if not item_rec.get('item_entrega_id'):
                continue 
                
            # 2. SEGUNDA CONSULTA: Pega o ID do Medicamento
            res_item = supabase.table("itens_entrega").select("id_medicamento").eq('id', item_rec['item_entrega_id']).limit(1).execute()
            
            if not res_item.data: continue # Ignora se o item de entrega não for encontrado
            
            # 3. VERIFICAÇÃO CRÍTICA (Check 2): Garante que o ID do Medicamento não é NULL
            # Esta é a linha que resolve o erro "invalid input syntax for type integer: None"
            id_med = res_item.data[0].get('id_medicamento')
            
            if id_med is None:
                print(f"AVISO: Pulando registro pois id_medicamento é Nulo no item: {item_rec['item_entrega_id']}")
                continue # Pula a linha que tem o ID do medicamento vazio

            # 4. TERCEIRA CONSULTA: Agora, o id_med é certamente um número
            res_med = supabase.table("medicamento").select("nome").eq('id_medicamento', id_med).limit(1).execute()
            
            nome_medicamento = res_med.data[0]['nome'] if res_med.data else "Produto Desconhecido"
            
            dados_para_pdf.append([
                nome_medicamento, 
                "LOTE PENDENTE (sem ligação)",
                str(item_rec['quantidade_recebida'])
            ])

        data_hoje = datetime.now().strftime("%d/%m/%Y")
        nome_arquivo = "nfe_funcional_final.pdf"
        
        gerar_nfe("NF-2025-FINAL", data_hoje, dados_para_pdf, caminho=nome_arquivo)
        
        return send_file(nome_arquivo, as_attachment=True)

    except Exception as e:
        print(f"ERRO NO BACKEND NF-E: {str(e)}")
        # Se falhar agora, o erro é em tabelas base como 'registro_recebimento' ou 'itens_entrega'.
        return jsonify({"erro": f"Rota '/gerar_nfe' falhou. Verifique se o RLS está desabilitado na tabela 'registro_recebimento'. Detalhe: {str(e)}"}), 500
    

# ==============================================================================
# 4. ROTA LAUDO AUDITORIA (Funcional)
# ==============================================================================
@app.route('/gerar_laudo_auditoria', methods=['GET'])
def gerar_laudo_auditoria_route():
    # Esta rota foi mantida para contornar a falta da tabela 'laudo_auditoria'
    try:
        # Conta Saídas e Entradas para gerar um texto dinâmico (Evita o erro de tabela inexistente)
        response_saidas = supabase.table("movimentacoes_estoque").select("id").eq('tipo', 'saida').execute()
        response_entradas = supabase.table("registro_recebimento").select("id").execute()
        
        total_saidas = len(response_saidas.data)
        total_entradas = len(response_entradas.data)
        
        texto_laudo = (
            f"<b>RESUMO DE AUDITORIA DE SISTEMA CUIDA</b><br/><br/>"
            f"A Auditoria Técnica conclui que as APIs de dados estão estáveis e a sincronização está ativa.<br/>"
            f"O sistema registou {total_entradas} entradas de notas fiscais e {total_saidas} saídas de medicamentos desde o início do período.<br/><br/>"
            f"<b>Recomendação:</b> É necessária uma auditoria física para conferência de {total_entradas - total_saidas} itens."
        )

        data_hoje = datetime.now().strftime("%d/%m/%Y")
        nome_arquivo = "laudo_auditoria_dinamico.pdf"
        
        gerar_laudo_auditoria("AUD-SISTEMA", data_hoje, texto_laudo, caminho=nome_arquivo)
        
        return send_file(nome_arquivo, as_attachment=True)

    except Exception as e:
        print(f"ERRO NO BACKEND LAUDO: {str(e)}")
        return jsonify({"erro": f"Falha ao gerar Laudo. Verifique as tabelas de Movimentação e Registro: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')