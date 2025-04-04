from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import current_app
import smtplib
from email.mime.text import MIMEText

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)  # Armazena hash da senha
    is_admin = db.Column(db.Boolean, default=False)

    def __init__(self, username, password, is_admin=False):
        self.username = username
        self.set_password(password)
        self.is_admin = is_admin

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<Usuario {self.username} {'(Admin)' if self.is_admin else ''}>"

class Livro(db.Model):
    __tablename__ = 'livros'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    autor = db.Column(db.String(100), nullable=False)
    status_emprestimo = db.Column(db.Boolean, default=False)
    
    # Relacionamentos
    emprestimos = db.relationship('Emprestimo', back_populates='livro')

    def __init__(self, titulo, autor, status_emprestimo=False):
        self.titulo = titulo
        self.autor = autor
        self.status_emprestimo = status_emprestimo
    
    def __repr__(self):
        status = 'Disponível' if not self.status_emprestimo else 'Indisponível'
        return f"{self.titulo} (ID: {self.id}) - Autor: {self.autor}, Empréstimo: {status}"

class Membro(db.Model):
    __tablename__ = 'membros'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    
    # Relacionamentos
    emprestimos = db.relationship('Emprestimo', back_populates='membro')
    
    def __init__(self, nome, email=None, telefone=None):
        self.nome = nome
        self.email = email
        self.telefone = telefone
    
    def __repr__(self):
        return f"{self.nome} (ID: {self.id})"

class Historico(db.Model):
    __tablename__ = 'historico'
    
    id = db.Column(db.Integer, primary_key=True)
    acao = db.Column(db.String(50), nullable=False)
    livro_id = db.Column(db.Integer, db.ForeignKey('livros.id'))
    membro_id = db.Column(db.Integer, db.ForeignKey('membros.id'))
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    detalhes = db.Column(db.String(200))
    
    # Relacionamentos
    livro = db.relationship('Livro', backref='historicos')
    membro = db.relationship('Membro', backref='historicos')

class Emprestimo(db.Model):
    __tablename__ = 'emprestimos'
    
    id = db.Column(db.Integer, primary_key=True)
    livro_id = db.Column(db.Integer, db.ForeignKey('livros.id'), nullable=False)
    membro_id = db.Column(db.Integer, db.ForeignKey('membros.id'), nullable=False)
    data_emprestimo = db.Column(db.DateTime, default=datetime.utcnow)
    data_devolucao_prevista = db.Column(db.DateTime)
    data_devolucao = db.Column(db.DateTime)
    renovacoes = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='ativo')
    
    # Relacionamentos
    livro = db.relationship('Livro', back_populates='emprestimos')
    membro = db.relationship('Membro', back_populates='emprestimos')
    
    def verificar_atraso(self):
        if self.status == 'ativo' and datetime.now() > self.data_devolucao_prevista:
            self.status = 'atrasado'
            db.session.commit()
            self.enviar_lembrete()
            return True
        return False
    
    def enviar_lembrete(self):
        if not self.membro.email:
            return False
        try:
            msg = MIMEText(f"""
            Prezado(a) {self.membro.nome},
            
            O livro "{self.livro.titulo}" está com devolução atrasada desde {self.data_devolucao_prevista.strftime('%d/%m/%Y')}.
            
            Por favor, regularize sua situação o mais breve possível.
            
            Atenciosamente,
            Biblioteca Digital
            """)
            msg['Subject'] = f'[Biblioteca] Atraso na devolução do livro'
            msg['From'] = current_app.config['MAIL_USERNAME']
            msg['To'] = self.membro.email
            with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT']) as server:
                server.starttls()
                server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
                server.send_message(msg)
            return True
        except Exception as e:
            current_app.logger.error(f'Erro ao enviar e-mail: {str(e)}')
            return False