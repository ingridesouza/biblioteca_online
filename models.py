from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# Tabela de associação para empréstimos (modelo explícito para PostgreSQL)
class Emprestimo(db.Model):
    __tablename__ = 'emprestimos'
    
    id = db.Column(db.Integer, primary_key=True, server_default=db.text("nextval('emprestimos_id_seq'::regclass)"))
    livro_id = db.Column(db.Integer, db.ForeignKey('livros.id'))
    membro_id = db.Column(db.Integer, db.ForeignKey('membros.id'))
    data_emprestimo = db.Column(db.DateTime, server_default=db.func.now())
    data_devolucao_prevista = db.Column(db.DateTime)
    data_devolucao = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='ativo')
    renovacoes = db.Column(db.Integer, server_default=db.text("0"))
    
    # Relacionamentos otimizados para PostgreSQL
    livro = db.relationship('Livro', back_populates='emprestimos')
    membro = db.relationship('Membro', back_populates='emprestimos')

class Livro(db.Model):
    __tablename__ = 'livros'
    
    id = db.Column(db.Integer, primary_key=True, server_default=db.text("nextval('livros_id_seq'::regclass)"))
    titulo = db.Column(db.String(100), nullable=False)
    autor = db.Column(db.String(100), nullable=False)
    status_emprestimo = db.Column(db.Boolean, server_default=db.text("false"))
    
    # Relacionamento unidirecional (mais eficiente no PostgreSQL)
    emprestimos = db.relationship('Emprestimo', back_populates='livro')

class Membro(db.Model, UserMixin):
    __tablename__ = 'membros'
    
    id = db.Column(db.Integer, primary_key=True, server_default=db.text("nextval('membros_id_seq'::regclass)"))
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    telefone = db.Column(db.String(20))
    senha_hash = db.Column(db.String(128))
    
    # Relacionamento unidirecional
    emprestimos = db.relationship('Emprestimo', back_populates='membro')

class Historico(db.Model):
    __tablename__ = 'historico'
    
    id = db.Column(db.Integer, primary_key=True, server_default=db.text("nextval('historico_id_seq'::regclass)"))
    acao = db.Column(db.String(50), nullable=False)
    livro_id = db.Column(db.Integer, db.ForeignKey('livros.id'))
    membro_id = db.Column(db.Integer, db.ForeignKey('membros.id'))
    data_hora = db.Column(db.DateTime, server_default=db.func.now())
    detalhes = db.Column(db.Text)
    
    # Relacionamentos otimizados
    livro = db.relationship('Livro', backref='historicos')
    membro = db.relationship('Membro', backref='historicos')