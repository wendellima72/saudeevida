from flask import Flask, render_template, request, redirect, session, jsonify 
import os
import sqlite3 
from datetime import datetime

from agendamento import agendamento_bp
from chat import chat_bp
from pagamento import pagamento_bp

# ==================== CONFIGURAÇÃO INICIAL ====================
app = Flask(__name__)
app.secret_key = 'segredo123'

# Registro dos Blueprints
app.register_blueprint(agendamento_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(pagamento_bp)


# ==================== FUNÇÕES DO BANCO DE DADOS ====================

def conectar():
    """Conecta ao banco de dados SQLite"""
    return sqlite3.connect('banco.db')


def criar_banco():
    """Cria as tabelas do banco de dados se não existirem"""
    conn = conectar()
    cursor = conn.cursor()

    # Tabela de usuários
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        cpf TEXT UNIQUE,
        telefone TEXT UNIQUE,
        genero TEXT,
        nascimento TEXT,
        email TEXT UNIQUE,
        senha TEXT,
        tipo TEXT,
        plano TEXT,
        status_pagamento TEXT,
        data_criacao TEXT
    )
    ''')

    # Tabela de pagamentos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pagamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        plano TEXT,
        valor REAL,
        payment_id TEXT,
        status TEXT,
        data TEXT
    )
    ''')

    # Tabela de mensagens
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mensagens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        mensagem TEXT,
        remetente TEXT,
        data TEXT
    )
    ''')

    # Tabela de consultas (se não existir)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS consultas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        medico TEXT,
        especialidade TEXT,
        data TEXT,
        hora TEXT,
        status TEXT,
        tipo TEXT,
        unidade TEXT
    )
    ''')

    # Contas padrão do sistema (admin)
    contas = [
        ("Médico", "", "", "", "", "contamedico@gmail.com", "qwe123", "medico"),
        ("Financeiro", "", "", "", "", "contafinanceiro@gmail.com", "qwe123", "financeiro"),
        ("Suporte", "", "", "", "", "contasuporte@gmail.com", "qwe123", "suporte"),
    ]

    for conta in contas:
        try:
            cursor.execute('''
            INSERT INTO usuarios (nome, cpf, telefone, genero, nascimento, email, senha, tipo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', conta)
        except:
            pass

    conn.commit()
    conn.close()

# Executar criação do banco
criar_banco()


# ==================== ROTAS DE AUTENTICAÇÃO ====================

@app.route('/')
def home():
    """Página inicial - formulário de login"""
    return render_template('login.html')


@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    """Cadastra um novo usuário do tipo cliente com validação de unicidade"""
    dados = request.form

    conn = conectar()
    cursor = conn.cursor()

    # Verificar se o e-mail já existe
    cursor.execute("SELECT id FROM usuarios WHERE email = ?", (dados['email'],))
    if cursor.fetchone():
        conn.close()
        return "Este e-mail já está cadastrado!", 409

    # Verificar se o CPF já existe
    cursor.execute("SELECT id FROM usuarios WHERE cpf = ?", (dados['cpf'],))
    if cursor.fetchone():
        conn.close()
        return "Este CPF já está cadastrado!", 409

    # Verificar se o telefone já existe
    cursor.execute("SELECT id FROM usuarios WHERE telefone = ?", (dados['telefone'],))
    if cursor.fetchone():
        conn.close()
        return "Este telefone já está cadastrado!", 409

    try:
        cursor.execute('''
        INSERT INTO usuarios (nome, cpf, telefone, genero, nascimento, email, senha, tipo, data_criacao)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            dados['nome'],
            dados['cpf'],
            dados['telefone'],
            dados['genero'],
            dados['nascimento'],
            dados['email'],
            dados['senha'],
            'cliente',
            datetime.now().strftime("%d/%m/%Y")
        ))

        conn.commit()
        conn.close()
        return "Cadastro realizado com sucesso!", 200
        
    except Exception as e:
        conn.close()
        return f"Erro ao cadastrar: {str(e)}", 500


@app.route('/login', methods=['POST'])
def login():
    """Realiza login e redireciona conforme tipo de usuário"""
    email = request.form['email']
    senha = request.form['senha']

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute('''
    SELECT id, tipo, nome FROM usuarios WHERE email=? AND senha=?
    ''', (email, senha))

    user = cursor.fetchone()
    conn.close()

    if user:
        user_id = user[0]
        tipo = user[1]
        nome = user[2]
        session['usuario'] = email
        session['tipo'] = tipo
        session['user_id'] = user_id
        session['nome'] = nome

        if tipo == 'medico':
            return redirect('/medico')
        elif tipo == 'financeiro':
            return redirect('/financeiro')
        elif tipo == 'suporte':
            return redirect('/suporte')
        else:
            return redirect('/painel_cliente')

    return "Login inválido!", 401


@app.route('/logout')
def logout():
    """Remove os dados da sessão e faz logout"""
    session.clear()
    return redirect('/')


# ==================== ROTAS DE VERIFICAÇÃO DE UNICIDADE ====================

@app.route('/verificar_cpf', methods=['GET'])
def verificar_cpf():
    """Verifica se o CPF já está cadastrado"""
    cpf = request.args.get('valor')
    if not cpf:
        return jsonify({"exists": False})
    
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE cpf = ?", (cpf,))
    existe = cursor.fetchone() is not None
    conn.close()
    
    return jsonify({"exists": existe})


@app.route('/verificar_telefone', methods=['GET'])
def verificar_telefone():
    """Verifica se o telefone já está cadastrado"""
    telefone = request.args.get('valor')
    if not telefone:
        return jsonify({"exists": False})
    
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE telefone = ?", (telefone,))
    existe = cursor.fetchone() is not None
    conn.close()
    
    return jsonify({"exists": existe})


@app.route('/verificar_email', methods=['GET'])
def verificar_email():
    """Verifica se o e-mail já está cadastrado"""
    email = request.args.get('valor')
    if not email:
        return jsonify({"exists": False})
    
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
    existe = cursor.fetchone() is not None
    conn.close()
    
    return jsonify({"exists": existe})


# ==================== ROTAS DE PÁGINAS POR TIPO DE USUÁRIO ====================

@app.route('/painel_cliente')
def painel_cliente():
    """Painel do cliente (usuário comum)"""
    if 'tipo' not in session or session['tipo'] != 'cliente':
        return redirect('/')
    return render_template('painel_cliente.html')


@app.route('/medico')
def medico():
    """Painel do médico"""
    if 'tipo' not in session or session['tipo'] != 'medico':
        return redirect('/')
    return render_template('medico.html')


@app.route('/financeiro')
def financeiro():
    """Painel do financeiro"""
    if 'tipo' not in session or session['tipo'] != 'financeiro':
        return redirect('/')
    return render_template('financeiro.html')


@app.route('/suporte')
def suporte():
    """Dashboard do suporte com estatísticas e listagem"""
    if 'tipo' not in session or session['tipo'] != 'suporte':
        return redirect('/')

    conn = conectar()
    cursor = conn.cursor()

    # Total de clientes
    cursor.execute("SELECT COUNT(*) FROM usuarios WHERE tipo='cliente'")
    total_usuarios = cursor.fetchone()[0]

    hoje = datetime.now().strftime("%d/%m/%Y")

    # Consultas de hoje
    try:
        cursor.execute("SELECT COUNT(*) FROM consultas WHERE data = ?", (hoje,))
        consultas_hoje = cursor.fetchone()[0]
    except:
        consultas_hoje = 0

    # Total de mensagens
    try:
        cursor.execute("SELECT COUNT(*) FROM mensagens")
        total_mensagens = cursor.fetchone()[0]
    except:
        total_mensagens = 0

    # Lista de clientes
    cursor.execute("""
    SELECT id, nome, email, telefone, cpf, plano, genero, nascimento, status_pagamento, data_criacao
    FROM usuarios
    WHERE tipo='cliente'
    """)
    usuarios = cursor.fetchall()

    # Lista de consultas
    try:
        cursor.execute("""
        SELECT u.nome, c.medico, c.especialidade, c.data, c.status
        FROM consultas c
        JOIN usuarios u ON c.usuario_id = u.id
        ORDER BY c.data DESC
        """)
        consultas = cursor.fetchall()
    except:
        consultas = []

    conn.close()

    return render_template(
        'suporte.html',
        total_usuarios=total_usuarios,
        consultas_hoje=consultas_hoje,
        total_mensagens=total_mensagens,
        usuarios=usuarios,
        consultas=consultas
    )


# ==================== ROTAS DE PÁGINAS PÚBLICAS ====================

@app.route('/agendamentos')
def agendamentos():
    """Página de agendamentos do cliente"""
    if 'usuario' not in session:
        return redirect('/')
    return render_template('agendamentos.html')


@app.route('/planos')
def planos():
    """Página de planos de assinatura"""
    if 'usuario' not in session:
        return redirect('/')
    return render_template('planos.html')


@app.route('/trabalhe_conosco')
def trabalhe():
    """Página de trabalho conosco"""
    return render_template('trabalhe_conosco.html')


@app.route('/contato')
def contato():
    """Página de contato / suporte"""
    return render_template('contato.html')


# ==================== ROTAS DE GERENCIAMENTO DE USUÁRIOS (SUPORTE) ====================

@app.route('/criar_usuario', methods=['GET', 'POST'])
def criar_usuario():
    """Cria um novo usuário (cliente, médico, financeiro ou suporte)"""
    if 'tipo' not in session or session['tipo'] != 'suporte':
        return redirect('/')
    
    if request.method == 'POST':
        nome = request.form['nome']
        cpf = request.form['cpf']
        telefone = request.form['telefone']
        genero = request.form['genero']
        nascimento = request.form['nascimento']
        email = request.form['email']
        senha = request.form['senha']
        tipo = request.form['tipo']
        
        conn = conectar()
        cursor = conn.cursor()
        
        # Verificar duplicatas
        cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            return redirect('/criar_usuario?erro=Email já existe!')
        
        cursor.execute("SELECT id FROM usuarios WHERE cpf = ?", (cpf,))
        if cursor.fetchone():
            conn.close()
            return redirect('/criar_usuario?erro=CPF já existe!')
        
        cursor.execute("SELECT id FROM usuarios WHERE telefone = ?", (telefone,))
        if cursor.fetchone():
            conn.close()
            return redirect('/criar_usuario?erro=Telefone já existe!')
        
        try:
            cursor.execute('''
            INSERT INTO usuarios (nome, cpf, telefone, genero, nascimento, email, senha, tipo, data_criacao)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nome, cpf, telefone, genero, nascimento, email, senha, tipo, datetime.now().strftime("%d/%m/%Y")))
            
            conn.commit()
            conn.close()
            return redirect('/suporte?msg=Usuário criado com sucesso!')
        except:
            conn.close()
            return redirect('/criar_usuario?erro=Erro ao criar usuário!')
    
    return render_template('criar_usuario.html')


@app.route('/editar_usuario/<int:user_id>', methods=['GET', 'POST'])
def editar_usuario(user_id):
    """Edita os dados de um usuário existente"""
    if 'tipo' not in session or session['tipo'] != 'suporte':
        return redirect('/')
    
    conn = conectar()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        cpf = request.form['cpf']
        telefone = request.form['telefone']
        genero = request.form['genero']
        nascimento = request.form['nascimento']
        email = request.form['email']
        tipo = request.form['tipo']
        
        # Verificar duplicatas ignorando o próprio usuário
        cursor.execute("SELECT id FROM usuarios WHERE email = ? AND id != ?", (email, user_id))
        if cursor.fetchone():
            conn.close()
            return redirect(f'/editar_usuario/{user_id}?erro=Email já existe!')
        
        cursor.execute("SELECT id FROM usuarios WHERE cpf = ? AND id != ?", (cpf, user_id))
        if cursor.fetchone():
            conn.close()
            return redirect(f'/editar_usuario/{user_id}?erro=CPF já existe!')
        
        cursor.execute("SELECT id FROM usuarios WHERE telefone = ? AND id != ?", (telefone, user_id))
        if cursor.fetchone():
            conn.close()
            return redirect(f'/editar_usuario/{user_id}?erro=Telefone já existe!')
        
        cursor.execute('''
        UPDATE usuarios 
        SET nome=?, cpf=?, telefone=?, genero=?, nascimento=?, email=?, tipo=?
        WHERE id=?
        ''', (nome, cpf, telefone, genero, nascimento, email, tipo, user_id))
        
        conn.commit()
        conn.close()
        return redirect('/suporte?msg=Usuário atualizado com sucesso!')
    
    cursor.execute("SELECT id, nome, cpf, telefone, genero, nascimento, email, tipo FROM usuarios WHERE id=?", (user_id,))
    usuario = cursor.fetchone()
    conn.close()
    
    return render_template('editar_usuario.html', usuario=usuario)


@app.route('/deletar_usuario/<int:user_id>')
def deletar_usuario(user_id):
    """Remove um usuário do sistema"""
    if 'tipo' not in session or session['tipo'] != 'suporte':
        return redirect('/')
    
    conn = conectar()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM usuarios WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    
    return redirect('/suporte?msg=Usuário deletado com sucesso!')


@app.route('/usuario_senha/<int:user_id>')
def usuario_senha(user_id):
    """Retorna a senha do usuário (apenas para suporte)"""
    if 'tipo' not in session or session['tipo'] != 'suporte':
        return jsonify({"senha": ""})
    
    conn = conectar()
    cursor = conn.cursor()
    
    cursor.execute("SELECT senha FROM usuarios WHERE id=?", (user_id,))
    resultado = cursor.fetchone()
    conn.close()
    
    if resultado:
        return jsonify({"senha": resultado[0]})
    return jsonify({"senha": ""})


# ==================== ROTAS DE BUSCA E PERFIL ====================

@app.route('/buscar_usuario')
def buscar_usuario():
    """Busca usuário por nome, email ou CPF e redireciona para o perfil"""
    termo = request.args.get('q')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id FROM usuarios
    WHERE nome LIKE ? OR email LIKE ? OR cpf LIKE ?
    LIMIT 1
    """, (f"%{termo}%", f"%{termo}%", f"%{termo}%"))

    user = cursor.fetchone()
    conn.close()

    if user:
        return redirect(f"/perfil_visualizar/{user[0]}")
    else:
        return redirect('/suporte')


# ==================== PERFIL DO USUÁRIO LOGADO ====================
@app.route('/meu_perfil')
def meu_perfil():
    """Exibe o perfil do próprio usuário logado"""
    if 'user_id' not in session:
        return redirect('/')
    
    user_id = session['user_id']
    
    conn = conectar()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT id, nome, email, telefone, cpf, genero, nascimento, plano, status_pagamento, data_criacao, tipo
    FROM usuarios WHERE id=?
    """, (user_id,))
    usuario = cursor.fetchone()
    
    # Buscar consultas do usuário
    try:
        cursor.execute("""
        SELECT id, medico, especialidade, data, hora, status
        FROM consultas
        WHERE usuario_id=?
        ORDER BY data DESC
        """, (user_id,))
        consultas = cursor.fetchall()
    except:
        consultas = []
    
    conn.close()
    
    return render_template("meu_perfil.html", usuario=usuario, consultas=consultas)


# ==================== PERFIL DE OUTRO USUÁRIO (APENAS SUPORTE) ====================
@app.route('/perfil_visualizar/<int:user_id>')
def perfil_visualizar(user_id):
    """Exibe o perfil completo de um usuário (apenas para suporte)"""
    if 'tipo' not in session or session['tipo'] != 'suporte':
        return redirect('/')
    
    if 'user_id' not in session:
        return redirect('/')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, nome, email, telefone, cpf, genero, nascimento, plano, status_pagamento, data_criacao, tipo
    FROM usuarios WHERE id=?
    """, (user_id,))
    usuario = cursor.fetchone()

    if not usuario:
        conn.close()
        return "Usuário não encontrado", 404

    try:
        cursor.execute("""
        SELECT id, medico, especialidade, data, hora, status
        FROM consultas
        WHERE usuario_id=?
        ORDER BY data DESC
        """, (user_id,))
        consultas = cursor.fetchall()
    except:
        consultas = []

    conn.close()

    return render_template("visualizar_perfil.html", usuario=usuario, consultas=consultas)



# ==================== EDITAR PERFIL ====================

@app.route('/editar_perfil', methods=['POST'])
def editar_perfil():
    """Salva as alterações do perfil do usuário"""
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    nome = request.form.get('nome', '').strip()
    telefone = request.form.get('telefone', '').strip()
    genero = request.form.get('genero', '').strip()
    nascimento = request.form.get('nascimento', '').strip()

    if not nome:
        return redirect('/meu_perfil')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE usuarios
        SET nome=?, telefone=?, genero=?, nascimento=?
        WHERE id=?
    """, (nome, telefone, genero, nascimento, user_id))

    conn.commit()
    conn.close()

    # Atualiza nome na sessão
    session['nome'] = nome

    return redirect('/meu_perfil')


# ==================== ALTERAR SENHA ====================

@app.route('/alterar_senha', methods=['POST'])
def alterar_senha():
    """Altera a senha do usuário logado"""
    if 'user_id' not in session:
        return redirect('/')

    from flask_bcrypt import Bcrypt
    bcrypt_local = Bcrypt(app)

    user_id = session['user_id']
    senha_atual = request.form.get('senha_atual', '')
    nova_senha = request.form.get('nova_senha', '')
    confirmar = request.form.get('confirmar_senha', '')

    if nova_senha != confirmar or len(nova_senha) < 6:
        return redirect('/meu_perfil')

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT senha FROM usuarios WHERE id=?", (user_id,))
    usuario = cursor.fetchone()

    if not usuario or not bcrypt_local.check_password_hash(usuario[0], senha_atual):
        conn.close()
        return redirect('/meu_perfil')

    nova_hash = bcrypt_local.generate_password_hash(nova_senha).decode('utf-8')
    cursor.execute("UPDATE usuarios SET senha=? WHERE id=?", (nova_hash, user_id))
    conn.commit()
    conn.close()

    return redirect('/meu_perfil')


# ==================== API CHATBASE ====================

# ==================== NOTIFICAÇÕES CORRIGIDAS ====================

@app.route('/notificacoes')
def notificacoes():
    """Retorna notificações do usuário logado"""
    if 'user_id' not in session:
        return jsonify([])

    user_id = session['user_id']
    
    try:
        conn = conectar()
        cursor = conn.cursor()

        # Buscar consultas do usuário nos próximos 7 dias
        cursor.execute("""
            SELECT id, medico, especialidade, data, hora, status, tipo
            FROM consultas
            WHERE usuario_id = ?
            AND status != 'Cancelado'
            AND date(data) >= date('now')
            AND date(data) <= date('now', '+7 days')
            ORDER BY data ASC, hora ASC
        """, (user_id,))
        proximas = cursor.fetchall()

        # Buscar consultas com status atualizado recentemente
        cursor.execute("""
            SELECT id, medico, especialidade, data, hora, status, tipo
            FROM consultas
            WHERE usuario_id = ?
            AND status IN ('Confirmado', 'Finalizado')
            ORDER BY id DESC
            LIMIT 5
        """, (user_id,))
        atualizadas = cursor.fetchall()

        conn.close()

        notifs = []

        for c in proximas:
            notifs.append({
                'id': c[0],
                'tipo': 'proxima',
                'icone': 'fa-calendar-check',
                'cor': '#1c9fd3',
                'titulo': 'Consulta em breve',
                'mensagem': f'{c[1]} — {c[3]} às {c[4]}',
                'data': c[3]
            })

        for c in atualizadas:
            if c[5] == 'Confirmado':
                notifs.append({
                    'id': c[0],
                    'tipo': 'confirmada',
                    'icone': 'fa-circle-check',
                    'cor': '#10b981',
                    'titulo': 'Consulta confirmada!',
                    'mensagem': f'{c[1]} — {c[3]} às {c[4]}',
                    'data': c[3]
                })
            elif c[5] == 'Finalizado':
                notifs.append({
                    'id': c[0],
                    'tipo': 'finalizada',
                    'icone': 'fa-star',
                    'cor': '#f59e0b',
                    'titulo': 'Consulta finalizada',
                    'mensagem': f'Como foi sua consulta com {c[1]}?',
                    'data': c[3]
                })

        # Remove duplicatas
        vistos = set()
        unicos = []
        for n in notifs:
            chave = f"{n['id']}-{n['tipo']}"
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(n)

        return jsonify(unicos[:8])

    except Exception as e:
        print(f'Erro em /notificacoes: {e}')
        return jsonify([])  # Retorna array vazio em caso de erro


# ==================== ROTA DE AGENDAMENTO ====================

@app.route('/agendar', methods=['POST'])
def agendar_consulta():
    """Rota para agendar uma nova consulta"""
    if 'user_id' not in session:
        return redirect('/')
    
    # Pegar dados do formulário
    nome = request.form.get('nome')
    tipo = request.form.get('tipo')
    unidade = request.form.get('unidade')
    especialidade = request.form.get('especialidade')
    medico = request.form.get('medico')
    data = request.form.get('data')
    hora = request.form.get('hora')
    
    # Validar dados
    if not all([nome, tipo, unidade, especialidade, medico, data, hora]):
        return "Dados incompletos!", 400
    
    try:
        conn = conectar()
        cursor = conn.cursor()
        
        # Verificar se já existe consulta no mesmo horário para este médico
        cursor.execute("""
            SELECT id FROM consultas 
            WHERE medico = ? AND data = ? AND hora = ? AND status != 'Cancelado'
        """, (medico, data, hora))
        
        if cursor.fetchone():
            conn.close()
            return "Horário já ocupado!", 409
        
        # Inserir no banco
        cursor.execute('''
        INSERT INTO consultas (usuario_id, medico, especialidade, data, hora, status, tipo, unidade)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user_id'],
            medico,
            especialidade,
            data,
            hora,
            'Aguardando',  # Status inicial
            tipo,
            unidade
        ))
        
        conn.commit()
        conn.close()
        
        return redirect('/agendamentos?sucesso=true')
        
    except Exception as e:
        print(f'Erro ao agendar: {e}')
        return "Erro ao agendar consulta", 500


# ==================== ROTA DE CANCELAMENTO DE CONSULTA ====================

@app.route('/cancelar_consulta', methods=['POST'])
def cancelar_consulta():
    """Cancela uma consulta existente"""
    if 'user_id' not in session:
        return redirect('/')
    
    consulta_id = request.form.get('id')
    user_id = session['user_id']
    
    if not consulta_id:
        return redirect('/agendamentos')
    
    try:
        conn = conectar()
        cursor = conn.cursor()
        
        # Verificar se a consulta pertence ao usuário
        cursor.execute("""
            SELECT id FROM consultas 
            WHERE id = ? AND usuario_id = ?
        """, (consulta_id, user_id))
        
        if not cursor.fetchone():
            conn.close()
            return "Consulta não encontrada", 404
        
        # Cancelar a consulta
        cursor.execute("""
            UPDATE consultas 
            SET status = 'Cancelado' 
            WHERE id = ?
        """, (consulta_id,))
        
        conn.commit()
        conn.close()
        
        return redirect('/agendamentos?cancelado=true')
        
    except Exception as e:
        print(f'Erro ao cancelar consulta: {e}')
        return "Erro ao cancelar consulta", 500


@app.route('/marcar_notif_lidas', methods=['POST'])
def marcar_notif_lidas():
    """Marca notificações como lidas (salva no localStorage via JS)"""
    return jsonify({'ok': True})


# ==================== CHATBASE JWT TOKEN ====================

@app.route('/chatbase_token')
def chatbase_token():
    """Gera token JWT para autenticar usuario no Chatbase (Private mode)"""
    if 'usuario' not in session:
        return jsonify({'erro': 'Nao autorizado'}), 401

    import jwt as pyjwt

    secret = 'e8nfpfhgw172l3vh6svwg15t753qodye'

    payload = {
        'user_id': str(session.get('user_id', '')),
        'email': session.get('usuario', ''),
    }

    token = pyjwt.encode(payload, secret, algorithm='HS256')
    return jsonify({'token': token})


# ==================== CHAT I.A. (GROQ) ====================

@app.route('/chat_ia', methods=['POST'])
def chat_ia():
    """Rota que chama a API do Groq pelo backend"""
    if 'usuario' not in session:
        return jsonify({'erro': 'Não autorizado'}), 401

    import urllib.request
    import json as json_lib

    dados = request.get_json()
    historico = dados.get('historico', [])


    SYSTEM_PROMPT = """Você é o assistente virtual do Centro Médico Saúde & Vida, um sistema hospitalar online.
Responda SOMENTE perguntas relacionadas ao hospital: agendamentos, consultas, planos de saúde, especialidades médicas, exames, unidades, horários e dúvidas gerais sobre o sistema.
Se a pergunta não tiver relação com saúde ou o sistema, diga educadamente que só pode ajudar com assuntos do hospital.
Seja sempre simpático, objetivo e profissional. Responda em português.
Informações do sistema:
- Unidades: Centro (Rua Barão do Rio Branco, 845), Aldeota (Av. Dom Luís, 2300), Parangaba
- Horário: Seg-Sex 08h-18h | Sáb 08h-12h
- Especialidades: Clínica Geral, Cardiologia, Dermatologia, Ortopedia, Pediatria, Neurologia, Ginecologia
- Para agendar: acesse a aba Agendamentos no menu
- Planos disponíveis na aba Planos
- WhatsApp de suporte: (85) 99139-3370"""

    # Monta mensagens no formato OpenAI
    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    for msg in historico:
        role = msg.get('role', 'user')
        content = msg.get('parts', [{}])[0].get('text', '') if 'parts' in msg else msg.get('content', '')
        messages.append({'role': role, 'content': content})

    body = json_lib.dumps({
        'model': 'llama-3.1-8b-instant',
        'messages': messages,
        'max_tokens': 1024,
        'temperature': 0.7
    }).encode('utf-8')

    try:
        req = urllib.request.Request(
            GROQ_URL,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {GROQ_KEY}'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json_lib.loads(resp.read().decode('utf-8'))

        resposta = data['choices'][0]['message']['content']
        return jsonify({'resposta': resposta})

    except Exception as e:
        print(f'Erro Groq: {e}')
        return jsonify({'erro': str(e)}), 500


# ==================== INICIALIZAÇÃO DO SERVIDOR ====================

if __name__ == "__main__":
    # Pega a porta da variável de ambiente (Render define isso automaticamente)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
