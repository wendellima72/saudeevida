from flask import Blueprint, request, render_template, redirect, session, jsonify
import sqlite3
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

agendamento_bp = Blueprint('agendamento', __name__)

# ---------------------------
# CRIAR TABELA CONSULTAS
# ---------------------------
def criar_tabela():
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS consultas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        email TEXT,
        tipo TEXT,
        especialidade TEXT,
        medico TEXT,
        data TEXT,
        hora TEXT,
        unidade TEXT,
        status TEXT
    )
    ''')

    conn.commit()
    conn.close()

criar_tabela()

# ---------------------------
# TABELAS MÉDICAS CORRIGIDAS
# ---------------------------
def criar_tabelas_medicas():
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prontuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paciente_email TEXT,
        paciente_nome TEXT,
        medico TEXT,
        observacoes TEXT,
        diagnostico TEXT,
        prescricao TEXT,
        data TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exames (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        paciente_email TEXT,
        paciente_nome TEXT,
        medico TEXT,
        exame TEXT,
        detalhes TEXT,
        data TEXT
    )
    """)

    conn.commit()
    conn.close()

criar_tabelas_medicas()

# ---------------------------
# CONFIG LINK
# ---------------------------
link_sistema = "http://127.0.0.1:5000/painel_cliente"

# ---------------------------
# EMAIL (APENAS CONSULTAS)
# ---------------------------
def enviar_email(destinatario, assunto, mensagem):
    remetente = "wenddel.lima@aluno.ce.gov.br"
    senha = "tydd cmdp nidx dtfh"

    msg = MIMEText(mensagem, 'html')
    msg['Subject'] = assunto
    msg['From'] = remetente
    msg['To'] = destinatario

    try:
        servidor = smtplib.SMTP('smtp.gmail.com', 587)
        servidor.starttls()
        servidor.login(remetente, senha)
        servidor.sendmail(remetente, destinatario, msg.as_string())
        servidor.quit()
        print("EMAIL ENVIADO")
    except Exception as e:
        print("ERRO:", e)

# ---------------------------
# EMAILS CONSULTA
# ---------------------------
def email_agendado(email, nome, data, hora, medico, tipo):
    mensagem = f"""
    <h2>Consulta Agendada</h2>
    <p>Olá, {nome}</p>
    <p>Data: {data} às {hora}</p>
    <p>Médico: {medico}</p>
    """
    enviar_email(email, "Consulta Agendada", mensagem)

def email_cancelado(email, nome, data, hora):
    mensagem = f"""
    <h2>Consulta Cancelada</h2>
    <p>Olá, {nome}</p>
    <p>Data: {data} às {hora}</p>
    """
    enviar_email(email, "Consulta Cancelada", mensagem)

def email_finalizado(email, nome, data, medico):
    mensagem = f"""
    <h2>Consulta Finalizada</h2>
    <p>Consulta com {medico} finalizada.</p>
    """
    enviar_email(email, "Consulta Finalizada", mensagem)

# ---------------------------
# AGENDAR CONSULTA
# ---------------------------
@agendamento_bp.route('/agendar', methods=['POST'])
def agendar():

    if 'usuario' not in session:
        return redirect('/')

    nome = request.form.get('nome')
    email = session['usuario']
    tipo = request.form.get('tipo')
    especialidade = request.form.get('especialidade')
    medico = request.form.get('medico')
    data = request.form.get('data')
    hora = request.form.get('hora')
    unidade = request.form.get('unidade')

    hoje = datetime.now().strftime("%Y-%m-%d")
    if data < hoje:
        return "Não pode agendar em datas passadas!"

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM consultas 
    WHERE medico=? AND data=? AND hora=? AND status != 'Cancelado'
    """, (medico, data, hora))

    if cursor.fetchone():
        conn.close()
        return "Horário já ocupado!"

    cursor.execute("""
    INSERT INTO consultas (nome, email, tipo, especialidade, medico, data, hora, unidade, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (nome, email, tipo, especialidade, medico, data, hora, unidade, "Aguardando"))

    conn.commit()
    conn.close()

    email_agendado(email, nome, data, hora, medico, tipo)

    return redirect('/agendamentos')

# ---------------------------
# PACIENTE
# ---------------------------
@agendamento_bp.route('/agendamentos')
def pagina_agendamentos():

    if 'usuario' not in session:
        return redirect('/')

    email = session['usuario']

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("""
    SELECT * FROM consultas
    WHERE email=? AND status != 'Finalizado' AND status != 'Cancelado'
    """, (email,))
    consultas = cursor.fetchall()

    cursor.execute("""
    SELECT * FROM consultas
    WHERE email=? AND (status='Finalizado' OR status='Cancelado')
    """, (email,))
    historico = cursor.fetchall()

    cursor.execute("""
    SELECT * FROM prontuarios 
    WHERE paciente_email=? 
    ORDER BY id DESC
    """, (email,))
    prontuarios = cursor.fetchall()

    cursor.execute("""
    SELECT * FROM exames 
    WHERE paciente_email=? 
    ORDER BY id DESC
    """, (email,))
    exames = cursor.fetchall()

    conn.close()

    return render_template('agendamentos.html',
        consultas=consultas,
        historico=historico,
        prontuarios=prontuarios,
        exames=exames
    )

# ---------------------------
# MÉDICO
# ---------------------------
@agendamento_bp.route('/medico')
def pagina_medico():

    if session.get('tipo') != 'medico':
        return redirect('/')

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM consultas WHERE status != 'Finalizado' AND status != 'Cancelado'")
    consultas = cursor.fetchall()

    cursor.execute("SELECT * FROM consultas WHERE status='Finalizado'")
    historico = cursor.fetchall()

    cursor.execute("SELECT DISTINCT nome, email FROM consultas WHERE status != 'Finalizado' AND status != 'Cancelado'")
    pacientes = cursor.fetchall()

    conn.close()

    return render_template('medico.html',
        consultas=consultas,
        historico=historico,
        pacientes=pacientes
    )

# ---------------------------
# SALVAR PRONTUÁRIO
# ---------------------------
@agendamento_bp.route('/salvar_prontuario', methods=['POST'])
def salvar_prontuario():

    if session.get('tipo') != 'medico':
        return redirect('/')

    paciente_nome = request.form.get('paciente_nome')
    paciente_email = request.form.get('paciente_email')

    obs = request.form.get('observacoes')
    diag = request.form.get('diagnostico')
    pres = request.form.get('prescricao')

    medico = session.get('usuario_nome')
    data = datetime.now().strftime("%d/%m/%Y %H:%M")

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO prontuarios 
    (paciente_email, paciente_nome, medico, observacoes, diagnostico, prescricao, data)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (paciente_email, paciente_nome, medico, obs, diag, pres, data))

    conn.commit()
    conn.close()

    return redirect('/medico')


# ---------------------------
# SOLICITAR EXAME
# ---------------------------
@agendamento_bp.route('/solicitar_exame', methods=['POST'])
def solicitar_exame():

    if session.get('tipo') != 'medico':
        return redirect('/')

    paciente_nome = request.form.get('paciente_nome')
    paciente_email = request.form.get('paciente_email')

    exame = request.form.get('exame')
    detalhes = request.form.get('detalhes')

    medico = session.get('usuario_nome')
    data = datetime.now().strftime("%d/%m/%Y %H:%M")

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO exames 
    (paciente_email, paciente_nome, medico, exame, detalhes, data)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (paciente_email, paciente_nome, medico, exame, detalhes, data))

    conn.commit()
    conn.close()

    return redirect('/medico')

# ---------------------------
# ATUALIZAR STATUS
# ---------------------------
@agendamento_bp.route('/atualizar_status', methods=['POST'])
def atualizar_status():

    if session.get('tipo') != 'medico':
        return "Acesso negado"

    id = request.form.get('id')
    status = request.form.get('status')

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("SELECT email, nome, data, medico FROM consultas WHERE id=?", (id,))
    dados = cursor.fetchone()

    cursor.execute("UPDATE consultas SET status=? WHERE id=?", (status, id))

    conn.commit()
    conn.close()

    if status == "Finalizado":
        email_finalizado(dados[0], dados[1], dados[2], dados[3])

    return redirect('/medico')

# ---------------------------
# CANCELAR CONSULTA
# ---------------------------
@agendamento_bp.route('/cancelar_consulta', methods=['POST'])
def cancelar_consulta():

    if session.get('tipo') != 'cliente':
        return redirect('/')

    id_consulta = request.form.get('id')

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("SELECT email, nome, data, hora FROM consultas WHERE id=?", (id_consulta,))
    dados = cursor.fetchone()

    cursor.execute("UPDATE consultas SET status='Cancelado' WHERE id=?", (id_consulta,))

    conn.commit()
    conn.close()

    email_cancelado(dados[0], dados[1], dados[2], dados[3])

    return redirect('/agendamentos')


# ---------------------------
# SUPORTE - PÁGINA PRINCIPAL
# ---------------------------
@agendamento_bp.route('/suporte')
def pagina_suporte():

    if 'usuario' not in session:
        return redirect('/')

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    # Busca todos usuários
    cursor.execute("""
        SELECT id, nome, email, tipo, telefone, cpf, plano, genero 
        FROM usuarios 
        ORDER BY nome
    """)
    usuarios = cursor.fetchall()

    # Busca TODAS as consultas com nome do paciente
    cursor.execute("""
        SELECT c.id, u.nome, c.medico, c.especialidade, c.data, c.status, c.hora
        FROM consultas c
        JOIN usuarios u ON c.email = u.email
        ORDER BY c.data DESC, c.hora DESC
    """)
    consultas = cursor.fetchall()

    # Estatísticas
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    total_usuarios = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM consultas WHERE data = date('now')")
    consultas_hoje = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM consultas WHERE status = 'Finalizado'")
    total_finalizadas = cursor.fetchone()[0]

    conn.close()

    return render_template('suporte.html',
        usuarios=usuarios,
        consultas=consultas,
        total_usuarios=total_usuarios,
        consultas_hoje=consultas_hoje,
        total_mensagens=0,
        total_finalizadas=total_finalizadas
    )


# ---------------------------
# TODAS CONSULTAS (API)
# ---------------------------
@agendamento_bp.route('/todas_consultas')
def todas_consultas():

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT u.nome, c.medico, c.especialidade, c.data, c.status, c.hora, c.id
        FROM consultas c
        JOIN usuarios u ON c.email = u.email
        ORDER BY c.data DESC, c.hora DESC
    """)

    consultas = cursor.fetchall()
    conn.close()

    return jsonify(consultas)


# ---------------------------
# CONSULTAS POR USUÁRIO (API)
# ---------------------------
@agendamento_bp.route('/consultas_usuario/<int:usuario_id>')
def consultas_usuario(usuario_id):

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    # Primeiro pega o email do usuário
    cursor.execute("SELECT email FROM usuarios WHERE id = ?", (usuario_id,))
    usuario = cursor.fetchone()

    if not usuario:
        return jsonify([])

    email = usuario[0]

    # Busca consultas do usuário específico
    cursor.execute("""
        SELECT id, medico, especialidade, data, status, hora
        FROM consultas
        WHERE email = ?
        ORDER BY data DESC, hora DESC
    """, (email,))

    consultas = cursor.fetchall()
    conn.close()

    # Retorna os dados
    resultado = []
    for c in consultas:
        resultado.append({
            "id": c[0],
            "medico": c[1],
            "especialidade": c[2],
            "data": c[3],
            "status": c[4],
            "hora": c[5]
        })

    return jsonify(resultado)

# ---------------------------
# PESQUISAR USUÁRIOS (AJAX)
# ---------------------------
@agendamento_bp.route('/pesquisar_usuarios')
def pesquisar_usuarios():

    if 'usuario' not in session:
        return jsonify([])

    termo = request.args.get('q', '')

    if len(termo) < 2:
        return jsonify([])

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome, email, tipo, telefone, cpf, plano, genero
        FROM usuarios
        WHERE nome LIKE ? OR email LIKE ? OR cpf LIKE ?
        ORDER BY nome
        LIMIT 50
    """, (f'%{termo}%', f'%{termo}%', f'%{termo}%'))

    usuarios = cursor.fetchall()
    conn.close()

    return jsonify(usuarios)

# ---------------------------
# DETALHES DO USUÁRIO
# ---------------------------
@agendamento_bp.route('/usuario_detalhes/<int:usuario_id>')
def usuario_detalhes(usuario_id):

    if 'usuario' not in session:
        return jsonify({"erro": "Não autorizado"}), 401

    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome, email, tipo, telefone, cpf, plano, genero
        FROM usuarios
        WHERE id = ?
    """, (usuario_id,))

    usuario = cursor.fetchone()
    conn.close()

    if usuario:
        return jsonify({
            "id": usuario[0],
            "nome": usuario[1],
            "email": usuario[2],
            "tipo": usuario[3],
            "telefone": usuario[4] if usuario[4] else '---',
            "cpf": usuario[5] if usuario[5] else '---',
            "plano": usuario[6] if usuario[6] else 'Sem plano',
            "genero": usuario[7] if usuario[7] else '---'
        })
    else:
        return jsonify({"erro": "Usuário não encontrado"}), 404