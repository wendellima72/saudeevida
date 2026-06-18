from flask import Blueprint, request, render_template, redirect, session, jsonify
import sqlite3
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

chat_bp = Blueprint('chat', __name__)

# ==================== FUNÇÕES DO BANCO ====================

def criar_tabelas_chat():
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER,
        usuario_nome TEXT,
        usuario_email TEXT,
        motivo TEXT,
        status TEXT DEFAULT 'aberto',
        data_abertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_fechamento TIMESTAMP,
        feedback_estrelas INTEGER,
        feedback_comentario TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mensagens_chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        remetente TEXT,
        mensagem TEXT,
        data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()

criar_tabelas_chat()

# ==================== FUNÇÕES DE EMAIL ====================

def enviar_email_cliente(destinatario, assunto, mensagem):
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
        print(f"Email enviado para {destinatario}")
    except Exception as e:
        print(f"Erro ao enviar email: {e}")

def notificar_abertura_ticket(email, nome, motivo, ticket_id):
    assunto = f"Atendimento aberto - Ticket #{ticket_id}"
    mensagem = f"""
    <h2>Olá {nome}!</h2>
    <p>Seu atendimento foi aberto com sucesso.</p>
    <p><strong>Motivo:</strong> {motivo}</p>
    <p>Em breve um de nossos atendentes responderá.</p>
    <p>Você pode acompanhar seu atendimento clicando <a href="http://127.0.0.1:5000/chat_cliente">aqui</a>.</p>
    <br>
    <p>Atenciosamente,<br>Equipe Saúde & Vida</p>
    """
    enviar_email_cliente(email, assunto, mensagem)

def notificar_resposta_suporte(email, nome, ticket_id):
    assunto = f"Nova resposta no atendimento #{ticket_id}"
    mensagem = f"""
    <h2>Olá {nome}!</h2>
    <p>O suporte respondeu seu atendimento.</p>
    <p>Clique <a href="http://127.0.0.1:5000/ver_chat/{ticket_id}">aqui</a> para visualizar a resposta.</p>
    <br>
    <p>Atenciosamente,<br>Equipe Saúde & Vida</p>
    """
    enviar_email_cliente(email, assunto, mensagem)

def notificar_fechamento_ticket(email, nome, ticket_id, estrelas=None):
    assunto = f"Atendimento finalizado - Ticket #{ticket_id}"
    estrelas_html = ""
    if estrelas:
        estrelas_html = f"<p>Sua avaliação: {'⭐' * int(estrelas)}</p>"
    mensagem = f"""
    <h2>Olá {nome}!</h2>
    <p>Seu atendimento #{ticket_id} foi finalizado.</p>
    {estrelas_html}
    <p>Agradecemos pelo contato!</p>
    <br>
    <p>Atenciosamente,<br>Equipe Saúde & Vida</p>
    """
    enviar_email_cliente(email, assunto, mensagem)

# ==================== ROTAS DO CLIENTE ====================

@chat_bp.route('/chat_cliente')
def chat_cliente():
    if 'usuario' not in session:
        return redirect('/')
    
    usuario_email = session.get('usuario')
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, motivo, status, substr(data_abertura, 1, 16) as data_abertura
        FROM tickets 
        WHERE usuario_email = ?
        ORDER BY data_abertura DESC
    """, (usuario_email,))
    
    tickets = cursor.fetchall()
    conn.close()
    
    return render_template('chat_cliente.html', tickets=tickets)

@chat_bp.route('/abrir_ticket', methods=['POST'])
def abrir_ticket():
    if 'usuario' not in session:
        return redirect('/')
    
    usuario_email = session.get('usuario')
    usuario_nome = session.get('usuario_nome')
    motivo = request.form.get('motivo')
    mensagem_inicial = request.form.get('mensagem')
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, status FROM tickets 
        WHERE usuario_email = ? AND status != 'fechado'
    """, (usuario_email,))
    
    ticket_existente = cursor.fetchone()
    
    if ticket_existente:
        conn.close()
        return redirect(f'/ver_chat/{ticket_existente[0]}')
    
    cursor.execute("SELECT id, nome FROM usuarios WHERE email = ?", (usuario_email,))
    user = cursor.fetchone()
    usuario_id = user[0] if user else None
    nome_real = user[1] if user else usuario_nome
    
    cursor.execute("""
        INSERT INTO tickets (usuario_id, usuario_nome, usuario_email, motivo, status)
        VALUES (?, ?, ?, ?, 'aberto')
    """, (usuario_id, nome_real, usuario_email, motivo))
    
    ticket_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO mensagens_chat (ticket_id, remetente, mensagem)
        VALUES (?, 'cliente', ?)
    """, (ticket_id, mensagem_inicial))
    
    conn.commit()
    conn.close()
    
    notificar_abertura_ticket(usuario_email, nome_real, motivo, ticket_id)
    
    return redirect(f'/ver_chat/{ticket_id}')

@chat_bp.route('/ver_chat/<int:ticket_id>')
def ver_chat(ticket_id):
    if 'usuario' not in session:
        return redirect('/')
    
    usuario_email = session.get('usuario')
    tipo_usuario = session.get('tipo')
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    if tipo_usuario == 'suporte':
        cursor.execute("""
            SELECT id, motivo, status, usuario_nome
            FROM tickets 
            WHERE id = ?
        """, (ticket_id,))
    else:
        cursor.execute("""
            SELECT id, motivo, status, usuario_nome
            FROM tickets 
            WHERE id = ? AND usuario_email = ?
        """, (ticket_id, usuario_email))
    
    ticket = cursor.fetchone()
    
    if not ticket:
        conn.close()
        if tipo_usuario == 'suporte':
            return redirect('/suporte')
        return redirect('/chat_cliente')
    
    cursor.execute("""
        SELECT remetente, mensagem, 
               strftime('%d/%m/%Y %H:%M', datetime(data_envio, 'localtime')) as data_envio
        FROM mensagens_chat 
        WHERE ticket_id = ? 
        ORDER BY id ASC
    """, (ticket_id,))
    
    mensagens = cursor.fetchall()
    conn.close()
    
    return render_template('chat_conversa.html', ticket=ticket, mensagens=mensagens)

@chat_bp.route('/enviar_mensagem_cliente', methods=['POST'])
def enviar_mensagem_cliente():
    if 'usuario' not in session:
        return jsonify({"erro": "Não autorizado"}), 401
    
    ticket_id = request.form.get('ticket_id')
    mensagem = request.form.get('mensagem')
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO mensagens_chat (ticket_id, remetente, mensagem)
        VALUES (?, 'cliente', ?)
    """, (ticket_id, mensagem))
    
    cursor.execute("""
        UPDATE tickets SET status = 'aguardando_suporte' WHERE id = ?
    """, (ticket_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({"sucesso": True})

@chat_bp.route('/buscar_mensagens/<int:ticket_id>')
def buscar_mensagens(ticket_id):
    if 'usuario' not in session:
        return jsonify([])
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT remetente, mensagem, 
               strftime('%d/%m/%Y %H:%M', datetime(data_envio, 'localtime')) as data_envio
        FROM mensagens_chat 
        WHERE ticket_id = ? 
        ORDER BY id ASC
    """, (ticket_id,))
    
    mensagens = cursor.fetchall()
    conn.close()
    
    resultado = []
    for m in mensagens:
        resultado.append({
            "remetente": m[0],
            "mensagem": m[1],
            "data_envio": m[2] if m[2] else ''
        })
    
    return jsonify(resultado)

@chat_bp.route('/fechar_ticket_cliente/<int:ticket_id>', methods=['POST'])
def fechar_ticket_cliente(ticket_id):
    if 'usuario' not in session:
        return redirect('/')
    
    feedback_estrelas = request.form.get('estrelas')
    feedback_comentario = request.form.get('comentario')
    usuario_email = session.get('usuario')
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT usuario_nome FROM tickets WHERE id = ? AND usuario_email = ?", (ticket_id, usuario_email))
    ticket_info = cursor.fetchone()
    
    cursor.execute("""
        UPDATE tickets 
        SET status = 'fechado', 
            data_fechamento = CURRENT_TIMESTAMP,
            feedback_estrelas = ?,
            feedback_comentario = ?
        WHERE id = ? AND usuario_email = ?
    """, (feedback_estrelas, feedback_comentario, ticket_id, usuario_email))
    
    conn.commit()
    conn.close()
    
    if ticket_info:
        notificar_fechamento_ticket(usuario_email, ticket_info[0], ticket_id, feedback_estrelas)
    
    return redirect('/chat_cliente')

# ==================== ROTAS DO SUPORTE ====================

@chat_bp.route('/suporte_chat')
def suporte_chat():
    if session.get('tipo') != 'suporte':
        return redirect('/')
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    # Buscar tickets com status traduzidos
    cursor.execute("""
        SELECT t.id, u.nome, t.usuario_email, t.motivo, t.status, 
               substr(t.data_abertura, 1, 16) as data_abertura
        FROM tickets t
        LEFT JOIN usuarios u ON t.usuario_email = u.email
        WHERE t.status != 'fechado'
        ORDER BY 
            CASE t.status 
                WHEN 'aguardando_suporte' THEN 1
                WHEN 'aberto' THEN 2
                WHEN 'aguardando_cliente' THEN 3
            END,
            t.data_abertura ASC
    """)
    
    tickets = cursor.fetchall()
    conn.close()
    
    tickets_com_nome = []
    for t in tickets:
        nome = t[1] if t[1] else 'Cliente'
        # Traduzir status para exibição
        status_exibicao = t[4]
        if status_exibicao == 'aguardando_suporte':
            status_exibicao = 'Aguardando Suporte'
        elif status_exibicao == 'aguardando_cliente':
            status_exibicao = 'Aguardando Cliente'
        elif status_exibicao == 'aberto':
            status_exibicao = 'Aberto'
        
        tickets_com_nome.append((t[0], nome, t[2], t[3], status_exibicao, t[5], t[4]))
    
    return render_template('suporte_chat_lista.html', tickets=tickets_com_nome)

@chat_bp.route('/enviar_mensagem_suporte', methods=['POST'])
def enviar_mensagem_suporte():
    if session.get('tipo') != 'suporte':
        return jsonify({"erro": "Não autorizado"}), 401
    
    ticket_id = request.form.get('ticket_id')
    mensagem = request.form.get('mensagem')
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT usuario_email, usuario_nome FROM tickets WHERE id = ?", (ticket_id,))
    ticket_info = cursor.fetchone()
    
    cursor.execute("""
        INSERT INTO mensagens_chat (ticket_id, remetente, mensagem)
        VALUES (?, 'suporte', ?)
    """, (ticket_id, mensagem))
    
    cursor.execute("""
        UPDATE tickets SET status = 'aguardando_cliente' WHERE id = ?
    """, (ticket_id,))
    
    conn.commit()
    conn.close()
    
    if ticket_info:
        notificar_resposta_suporte(ticket_info[0], ticket_info[1], ticket_id)
    
    return jsonify({"sucesso": True})

@chat_bp.route('/fechar_ticket_suporte/<int:ticket_id>', methods=['POST'])
def fechar_ticket_suporte(ticket_id):
    if session.get('tipo') != 'suporte':
        return redirect('/')
    
    estrelas = request.form.get('estrelas', '0')
    comentario = request.form.get('comentario', '')
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT usuario_email, usuario_nome FROM tickets WHERE id = ?", (ticket_id,))
    ticket_info = cursor.fetchone()
    
    cursor.execute("""
        UPDATE tickets 
        SET status = 'fechado', 
            data_fechamento = CURRENT_TIMESTAMP,
            feedback_estrelas = ?,
            feedback_comentario = ?
        WHERE id = ?
    """, (estrelas, comentario, ticket_id))
    
    conn.commit()
    conn.close()
    
    if ticket_info:
        notificar_fechamento_ticket(ticket_info[0], ticket_info[1], ticket_id, estrelas)
    
    return jsonify({"sucesso": True})

@chat_bp.route('/estatisticas_chat')
def estatisticas_chat():
    if session.get('tipo') != 'suporte':
        return jsonify({"total_mensagens": 0, "total_pendentes": 0})
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    # Total de mensagens
    cursor.execute("SELECT COUNT(*) FROM mensagens_chat")
    total_mensagens = cursor.fetchone()[0]
    
    # Total de tickets aguardando suporte (PENDENTES)
    cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'aguardando_suporte'")
    total_pendentes = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        "total_mensagens": total_mensagens,
        "total_pendentes": total_pendentes
    })

@chat_bp.route('/verificar_ticket_ativo')
def verificar_ticket_ativo():
    if 'usuario' not in session:
        return jsonify({"tem_ticket_aberto": False})
    
    usuario_email = session.get('usuario')
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id FROM tickets 
        WHERE usuario_email = ? AND status != 'fechado'
    """, (usuario_email,))
    
    ticket = cursor.fetchone()
    conn.close()
    
    return jsonify({"tem_ticket_aberto": ticket is not None})

@chat_bp.route('/ver_chat_suporte/<int:ticket_id>')
def ver_chat_suporte(ticket_id):
    if session.get('tipo') != 'suporte':
        return redirect('/')
    
    conn = sqlite3.connect('banco.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, usuario_nome, usuario_email, motivo, status 
        FROM tickets WHERE id = ?
    """, (ticket_id,))
    
    ticket = cursor.fetchone()
    
    if not ticket:
        conn.close()
        return redirect('/suporte_chat')
    
    # Buscar nome real do cliente
    cursor.execute("SELECT nome FROM usuarios WHERE email = ?", (ticket[2],))
    user = cursor.fetchone()
    
    if user and user[0]:
        nome_real = user[0]
    else:
        nome_real = ticket[1] if ticket[1] else 'Cliente'
    
    ticket = (ticket[0], nome_real, ticket[2], ticket[3], ticket[4])
    
    cursor.execute("""
        SELECT remetente, mensagem, 
               strftime('%d/%m/%Y %H:%M', datetime(data_envio, 'localtime')) as data_envio
        FROM mensagens_chat 
        WHERE ticket_id = ? 
        ORDER BY id ASC
    """, (ticket_id,))
    
    mensagens = cursor.fetchall()
    conn.close()
    
    return render_template('suporte_chat_conversa.html', ticket=ticket, mensagens=mensagens)