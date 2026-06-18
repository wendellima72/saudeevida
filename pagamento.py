from flask import Blueprint, request, render_template, redirect, session, jsonify, url_for
import mercadopago
import sqlite3
from datetime import datetime
import json

pagamento_bp = Blueprint('pagamento', __name__)

# ==================== CONFIGURAÇÃO ====================
# TOKEN DE PRODUÇÃO - Coloque seu Access Token real aqui
# IMPORTANTE: Use variável de ambiente em produção!
MERCADO_PAGO_ACCESS_TOKEN = "APP_USR-2058425028825147-033112-d5c027476bc8db1990b7f37dc135c7de-3304688103"

# Inicializar SDK do Mercado Pago
sdk = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)


# ==================== FUNÇÕES AUXILIARES ====================

def conectar():
    return sqlite3.connect('banco.db')


def get_usuario_logado():
    """Retorna os dados do usuário logado"""
    if 'usuario' not in session:
        return None
    
    email = session['usuario']
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, email FROM usuarios WHERE email = ?", (email,))
    usuario = cursor.fetchone()
    conn.close()
    
    if usuario:
        return {"id": usuario[0], "nome": usuario[1], "email": usuario[2]}
    return None


def salvar_pagamento(user_id, plano, valor, payment_id, status, payment_method):
    """Salva o pagamento no banco de dados"""
    conn = conectar()
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pagamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plano TEXT,
        valor REAL,
        payment_id TEXT,
        status TEXT,
        payment_method TEXT,
        data TEXT
    )
    ''')
    
    cursor.execute('''
    INSERT INTO pagamentos (user_id, plano, valor, payment_id, status, payment_method, data)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, plano, valor, payment_id, status, payment_method, datetime.now().strftime("%d/%m/%Y %H:%M")))
    
    conn.commit()
    conn.close()


def atualizar_plano_usuario(user_id, plano):
    """Atualiza o plano do usuário no banco"""
    conn = conectar()
    cursor = conn.cursor()
    
    # Verificar se a coluna plano existe, se não, adicionar
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN plano TEXT")
    except:
        pass
    
    cursor.execute("UPDATE usuarios SET plano = ? WHERE id = ?", (plano, user_id))
    conn.commit()
    conn.close()


# ==================== PLANOS DISPONÍVEIS ====================

PLANOS = {
    "basico": {"nome": "Plano Básico", "valor": 1.90, "descricao": "Consultas básicas ilimitadas"},
    "medio": {"nome": "Plano Médio", "valor": 3.90, "descricao": "Consultas com especialistas"},
    "premium": {"nome": "Plano Premium", "valor": 4.90, "descricao": "Acesso total a todos os serviços"}
}


# ==================== ROTAS ====================

@pagamento_bp.route('/planos')
def planos():
    """Exibe a página de planos"""
    if 'usuario' not in session:
        return redirect('/')
    
    usuario = get_usuario_logado()
    return render_template('planos.html', planos=PLANOS, usuario=usuario)


@pagamento_bp.route('/criar_pagamento', methods=['POST'])
def criar_pagamento():
    """Cria um pagamento no Mercado Pago"""
    if 'usuario' not in session:
        return jsonify({"erro": "Usuário não logado"}), 401
    
    usuario = get_usuario_logado()
    plano_key = request.form.get('plano')
    metodo_pagamento = request.form.get('metodo_pagamento')  # pix ou cartao
    
    if plano_key not in PLANOS:
        return jsonify({"erro": "Plano inválido"}), 400
    
    plano = PLANOS[plano_key]
    valor = plano["valor"]
    
    # Criar preferência de pagamento
    preference_data = {
        "items": [
            {
                "title": plano["nome"],
                "description": plano["descricao"],
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": valor
            }
        ],
        "payer": {
            "email": usuario["email"],
            "name": usuario["nome"]
        },
        "back_urls": {
            "success": "https://hospitalsystem-prfu.onrender.com/pagamento_sucesso",
            "failure": "https://hospitalsystem-prfu.onrender.com/pagamento_erro",
            "pending": "https://hospitalsystem-prfu.onrender.com/pagamento_pendente"
        },
        "auto_return": "approved",
        "notification_url": "https://hospitalsystem-prfu.onrender.com/webhook_pagamento"
    }
    
    # Se for PIX, configurar especificamente
    if metodo_pagamento == 'pix':
        preference_data["payment_methods"] = {
            "excluded_payment_methods": [],
            "excluded_payment_types": [{"id": "credit_card"}, {"id": "debit_card"}],
            "installments": 1
        }
    
    try:
        # Criar preferência
        preference_response = sdk.preference().create(preference_data)
        preference = preference_response["response"]
        
        # Salvar informações do pagamento pendente
        conn = conectar()
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pagamentos_pendentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plano TEXT,
            valor REAL,
            preference_id TEXT,
            status TEXT,
            data TEXT
        )
        ''')
        
        cursor.execute('''
        INSERT INTO pagamentos_pendentes (user_id, plano, valor, preference_id, status, data)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (usuario["id"], plano_key, valor, preference["id"], "pendente", datetime.now().strftime("%d/%m/%Y %H:%M")))
        
        conn.commit()
        conn.close()
        
        # Retornar o link de pagamento
        return jsonify({
            "sucesso": True,
            "init_point": preference["init_point"],
            "sandbox_init_point": preference.get("sandbox_init_point", preference["init_point"]),
            "preference_id": preference["id"]
        })
        
    except Exception as e:
        print(f"Erro ao criar pagamento: {e}")
        return jsonify({"erro": str(e)}), 500


@pagamento_bp.route('/criar_pagamento_direto', methods=['POST'])
def criar_pagamento_direto():
    """
    Cria pagamento direto via API (PIX ou Cartão)
    Útil para checkout dentro do próprio site
    """
    if 'usuario' not in session:
        return jsonify({"erro": "Usuário não logado"}), 401
    
    usuario = get_usuario_logado()
    dados = request.get_json()
    
    plano_key = dados.get('plano')
    metodo = dados.get('metodo')  # pix ou cartao
    cartao_dados = dados.get('cartao', {}) if metodo == 'cartao' else None
    
    if plano_key not in PLANOS:
        return jsonify({"erro": "Plano inválido"}), 400
    
    plano = PLANOS[plano_key]
    valor = plano["valor"]
    
    # Preparar dados do pagamento
    payment_data = {
        "transaction_amount": valor,
        "description": plano["nome"],
        "payment_method_id": "pix" if metodo == 'pix' else "master",
        "payer": {
            "email": usuario["email"],
            "first_name": usuario["nome"].split()[0] if usuario["nome"] else usuario["nome"],
            "identification": {
                "type": "CPF",
                "number": "19119119100"  # CPF de exemplo
            }
        }
    }
    
    # Se for cartão, adicionar dados do cartão
    if metodo == 'cartao' and cartao_dados:
        payment_data.update({
            "token": cartao_dados.get('token'),
            "installments": cartao_dados.get('installments', 1),
            "payment_method_id": cartao_dados.get('payment_method_id', 'master'),
            "issuer_id": cartao_dados.get('issuer_id')
        })
    
    try:
        # Criar pagamento
        payment_response = sdk.payment().create(payment_data)
        payment = payment_response["response"]
        
        # Salvar no banco
        salvar_pagamento(
            user_id=usuario["id"],
            plano=plano["nome"],
            valor=valor,
            payment_id=payment.get("id"),
            status=payment.get("status"),
            payment_method=metodo
        )
        
        # Se aprovado, atualizar plano do usuário
        if payment.get("status") == "approved":
            atualizar_plano_usuario(usuario["id"], plano["nome"])
        
        return jsonify({
            "sucesso": True,
            "status": payment.get("status"),
            "payment_id": payment.get("id"),
            "qr_code": payment.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code_base64"),
            "qr_code_text": payment.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code")
        })
        
    except Exception as e:
        print(f"Erro ao criar pagamento: {e}")
        return jsonify({"erro": str(e)}), 500


@pagamento_bp.route('/webhook_pagamento', methods=['POST'])
def webhook_pagamento():
    """Webhook para receber notificações do Mercado Pago"""
    try:
        data = request.get_json()
        
        if data and data.get("type") == "payment":
            payment_id = data["data"]["id"]
            
            # Buscar informações do pagamento
            payment_response = sdk.payment().get(payment_id)
            payment = payment_response["response"]
            
            # Atualizar status no banco
            conn = conectar()
            cursor = conn.cursor()
            
            # Buscar pagamento pendente pelo payment_id
            cursor.execute("SELECT user_id, plano FROM pagamentos_pendentes WHERE preference_id = ?", (payment.get("preference_id"),))
            pendente = cursor.fetchone()
            
            if pendente:
                user_id, plano_key = pendente
                
                # Atualizar status do pagamento
                salvar_pagamento(
                    user_id=user_id,
                    plano=PLANOS.get(plano_key, {}).get("nome", plano_key),
                    valor=payment.get("transaction_amount", 0),
                    payment_id=payment_id,
                    status=payment.get("status"),
                    payment_method=payment.get("payment_method_id", "desconhecido")
                )
                
                # Se aprovado, atualizar plano do usuário
                if payment.get("status") == "approved":
                    atualizar_plano_usuario(user_id, PLANOS.get(plano_key, {}).get("nome", plano_key))
            
            conn.close()
        
        return jsonify({"sucesso": True}), 200
        
    except Exception as e:
        print(f"Erro no webhook: {e}")
        return jsonify({"erro": str(e)}), 500


@pagamento_bp.route('/pagamento_sucesso')
def pagamento_sucesso():
    """Página de sucesso após pagamento"""
    return render_template('pagamento_sucesso.html')


@pagamento_bp.route('/pagamento_erro')
def pagamento_erro():
    """Página de erro no pagamento"""
    return render_template('pagamento_erro.html')


@pagamento_bp.route('/pagamento_pendente')
def pagamento_pendente():
    """Página de pagamento pendente"""
    return render_template('pagamento_pendente.html')


@pagamento_bp.route('/status_pagamento/<preference_id>')
def status_pagamento(preference_id):
    """Verifica status do pagamento por preference_id"""
    if 'usuario' not in session:
        return jsonify({"erro": "Não autorizado"}), 401
    
    conn = conectar()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT status, plano, valor FROM pagamentos_pendentes 
    WHERE preference_id = ?
    ''', (preference_id,))
    
    resultado = cursor.fetchone()
    conn.close()
    
    if resultado:
        return jsonify({
            "status": resultado[0],
            "plano": resultado[1],
            "valor": resultado[2]
        })
    
    return jsonify({"status": "nao_encontrado"}), 404