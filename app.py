from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Livro, Membro, Emprestimo
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from dateutil import parser
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from sqlalchemy import or_
from models import Historico
import smtplib
from email.mime.text import MIMEText
from itsdangerous.url_safe import URLSafeTimedSerializer as Serializer

load_dotenv()

app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Usando postgresql do Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace(
    "postgresql://", 
    "postgresql+psycopg2://"
) + "?sslmode=require"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.secret_key = os.getenv('FLASK_SECRET_KEY')

app.config.update(
    MAIL_SERVER=os.getenv('MAIL_SERVER'),
    MAIL_PORT=int(os.getenv('MAIL_PORT')),
    MAIL_USE_TLS=os.getenv('MAIL_USE_TLS').lower() == 'true',
    MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
    MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
    MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER')
)



db.init_app(app)

with app.app_context():
    db.create_all()



def verificar_atrasos():
    with app.app_context():
        emprestimos = Emprestimo.query.filter_by(status='ativo').all()
        for emprestimo in emprestimos:
            if datetime.now() > emprestimo.data_devolucao_prevista:
                emprestimo.status = 'atrasado'
                
                historico = Historico(
                    acao='atraso',
                    livro_id=emprestimo.livro_id,
                    membro_id=emprestimo.membro_id,
                    detalhes=f'Empréstimo atrasado desde {emprestimo.data_devolucao_prevista.strftime("%d/%m/%Y")}'
                )
                
                db.session.add(historico)
                
                if emprestimo.membro.email:
                    try:
                        msg = MIMEText(f"""
                        Prezado(a) {emprestimo.membro.nome},
                        
                        O livro "{emprestimo.livro.titulo}" está com devolução atrasada desde {emprestimo.data_devolucao_prevista.strftime('%d/%m/%Y')}.
                        
                        Por favor, regularize sua situação o mais breve possível.
                        
                        Atenciosamente,
                        Biblioteca Digital
                        """)
                        
                        msg['Subject'] = '[Biblioteca] Aviso de atraso na devolução'
                        msg['From'] = app.config['MAIL_USERNAME']
                        msg['To'] = emprestimo.membro.email
                        
                        with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
                            server.starttls()
                            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
                            server.send_message(msg)
                            
                    except Exception as e:
                        app.logger.error(f'Erro ao enviar e-mail: {str(e)}')
                
                db.session.commit()




@app.route('/')
def index():
    total_livros = Livro.query.count()
    total_membros = Membro.query.count()
    total_emprestimos = Emprestimo.query.filter_by(data_devolucao=None).count()
    
    return render_template('index.html',
                         total_livros=total_livros,
                         total_membros=total_membros,
                         total_emprestimos=total_emprestimos)

@app.route('/livros')
def listar_livros():
    livros = Livro.query.all()
    return render_template('livros.html', livros=livros)

@app.route('/livros/adicionar', methods=['GET', 'POST'])
def adicionar_livro():
    if request.method == 'POST':
        titulo = request.form['titulo']
        autor = request.form['autor']
        
        if not titulo or not autor:
            flash('Preencha todos os campos obrigatórios!', 'danger')
            return redirect(url_for('adicionar_livro'))
        
        try:
            novo_livro = Livro(titulo=titulo, autor=autor)
            db.session.add(novo_livro)
            db.session.commit()
            flash(f'Livro "{novo_livro.titulo}" cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_livros'))
        except Exception as e:
            db.session.rollback()
            flash('Erro ao cadastrar livro!', 'danger')
            return redirect(url_for('adicionar_livro'))
    
    return render_template('adicionar_livro.html')

@app.route('/livros/pesquisar', methods=['GET'])
def pesquisar_livros():
    termo = request.args.get('termo', '')
    
    if termo:
        livros = Livro.query.filter(
            (Livro.titulo.ilike(f'%{termo}%')) | 
            (Livro.autor.ilike(f'%{termo}%')) | 
            (Livro.id == termo if termo.isdigit() else False)
        ).all()
    else:
        livros = []
    
    return render_template('livros.html', livros=livros, termo_pesquisa=termo)

@app.route('/membros')
def listar_membros():
    membros = Membro.query.all()
    return render_template('membros.html', membros=membros)

@app.route('/membros/adicionar', methods=['GET', 'POST'])
def adicionar_membro():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form.get('email', '')
        telefone = request.form.get('telefone', '')
        
        if not nome:
            flash('O nome é obrigatório!', 'danger')
            return redirect(url_for('adicionar_membro'))
        
        try:
            novo_membro = Membro(nome=nome)
            if email:
                novo_membro.email = email
            if telefone:
                novo_membro.telefone = telefone
                
            db.session.add(novo_membro)
            db.session.commit()
            flash(f'Membro "{novo_membro.nome}" cadastrado com sucesso!', 'success')
            return redirect(url_for('listar_membros'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar membro: {str(e)}', 'danger')
            return redirect(url_for('adicionar_membro'))
    
    return render_template('adicionar_membro.html')


@app.route('/membros/deletar/<int:membro_id>', methods=['POST'])
def deletar_membro(membro_id):
    membro = Membro.query.get_or_404(membro_id)
    
    if Emprestimo.query.filter_by(membro_id=membro_id, data_devolucao=None).count() > 0:
        flash('Não é possível deletar membro com empréstimos ativos!', 'danger')
        return redirect(url_for('listar_membros'))
    
    try:
        Historico.query.filter_by(membro_id=membro_id).update({'membro_id': None})
        
        novo_historico = Historico(
            acao='exclusao_membro',
            detalhes=f'Membro "{membro.nome}" (ID: {membro_id}) deletado do sistema'
        )
        
        db.session.add(novo_historico)
        db.session.delete(membro)
        db.session.commit()
        
        flash(f'Membro "{membro.nome}" deletado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao deletar membro: {str(e)}', 'danger')
    
    return redirect(url_for('listar_membros'))

@app.route('/emprestimos')
def listar_emprestimos():
    emprestimos = Emprestimo.query.filter_by(data_devolucao=None).all()
    return render_template('emprestimos.html', emprestimos=emprestimos)

@app.route('/historico')
def ver_historico():
    page = request.args.get('page', 1, type=int)
    query = request.args.get('query', '')
    
    if query:
        historico_query = Historico.query.join(Membro).join(Livro).filter(
            or_(
                Membro.nome.ilike(f'%{query}%'),
                Livro.titulo.ilike(f'%{query}%'),
                Historico.acao.ilike(f'%{query}%'),
                Historico.detalhes.ilike(f'%{query}%')
            )
        )
    else:
        historico_query = Historico.query
    
    pagination = historico_query.order_by(Historico.data_hora.desc()).paginate(
        page=page, 
        per_page=10,
        error_out=False
    )
    
    return render_template('historico.html', 
                        historico=pagination.items,
                        pagination=pagination)

@app.route('/emprestimos/renovar/<int:emprestimo_id>')
def renovar_emprestimo(emprestimo_id):
    emprestimo = Emprestimo.query.get_or_404(emprestimo_id)
    
    if emprestimo.status != 'ativo':
        flash('Este empréstimo não pode ser renovado!', 'danger')
        return redirect(url_for('listar_emprestimos'))
    
    if datetime.now() + timedelta(days=15) > emprestimo.data_devolucao_prevista + timedelta(days=15):
        flash('Limite máximo de renovação atingido!', 'warning')
        return redirect(url_for('listar_emprestimos'))
    
    try:
        novo_historico = Historico(
            acao='renovacao',
            livro_id=emprestimo.livro_id,
            membro_id=emprestimo.membro_id,
            detalhes=f'Renovado até {(emprestimo.data_devolucao_prevista + timedelta(days=15)).strftime("%d/%m/%Y")}'
        )
        
        emprestimo.data_devolucao_prevista += timedelta(days=15)
        emprestimo.renovacoes += 1
        
        db.session.add(novo_historico)
        db.session.commit()
        
        flash('Empréstimo renovado com sucesso por mais 15 dias!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao renovar empréstimo: {str(e)}', 'danger')
    
    return redirect(url_for('listar_emprestimos'))


@app.route('/emprestimos/novo', methods=['GET', 'POST'])
def novo_emprestimo():
    if request.method == 'POST':
        livro_id = request.form['livro_id']
        membro_id = request.form['membro_id']
        data_prevista = request.form.get('data_devolucao_prevista')
        
        try:
            livro = Livro.query.get(livro_id)
            membro = Membro.query.get(membro_id)
            
            if not livro or not membro:
                flash('Livro ou membro não encontrado!', 'danger')
                return redirect(url_for('novo_emprestimo'))
                
            if livro.status_emprestimo:
                flash(f'O livro "{livro.titulo}" já está emprestado!', 'warning')
                return redirect(url_for('novo_emprestimo'))
            
            data_devolucao_prevista = parser.parse(data_prevista) if data_prevista else datetime.now() + timedelta(days=14)
            
            novo_emprestimo = Emprestimo(
                livro_id=livro.id,
                membro_id=membro.id,
                data_emprestimo=datetime.now(),
                data_devolucao_prevista=data_devolucao_prevista,
                status='ativo'
            )
            
            livro.status_emprestimo = True
            
            novo_historico = Historico(
                acao='emprestimo',
                livro_id=livro.id,
                membro_id=membro.id,
                detalhes=f'Devolução prevista para {data_devolucao_prevista.strftime("%d/%m/%Y")}'
            )
            
            db.session.add(novo_emprestimo)
            db.session.add(novo_historico)
            db.session.commit()
            
            flash(f'Empréstimo registrado com sucesso para {membro.nome}!', 'success')
            return redirect(url_for('listar_emprestimos'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao registrar empréstimo: {str(e)}', 'danger')
            return redirect(url_for('novo_emprestimo'))
    
    livros_disponiveis = Livro.query.filter_by(status_emprestimo=False).all()
    membros = Membro.query.all()
    return render_template(
        'novo_emprestimo.html',
        livros=livros_disponiveis,
        membros=membros,
        date=datetime.now().date(),
        timedelta=timedelta
    )

@app.route('/emprestimos/devolver/<int:emprestimo_id>', methods=['POST'])
def devolver_livro(emprestimo_id):
    emprestimo = Emprestimo.query.get(emprestimo_id)
    
    if emprestimo:
        livro = Livro.query.get(emprestimo.livro_id)
        membro = Membro.query.get(emprestimo.membro_id)
        
        livro.status_emprestimo = False
        emprestimo.data_devolucao = datetime.now()
        emprestimo.status = 'finalizado'
        
        novo_historico = Historico(
            acao='devolucao',
            livro_id=emprestimo.livro_id,
            membro_id=emprestimo.membro_id,
            detalhes=f'Devolvido em {datetime.now().strftime("%d/%m/%Y")}'
        )
        
        db.session.add(novo_historico)
        db.session.commit()
        
        flash(f'O livro "{livro.titulo}" foi devolvido pelo membro "{membro.nome}".', 'success')
    else:
        flash('Empréstimo não encontrado.', 'danger')
    
    return redirect(url_for('listar_emprestimos'))


atexit.register(lambda: scheduler.shutdown())
if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=verificar_atrasos, trigger='interval', days=1)
    scheduler.start()
    app.run(debug=True)
