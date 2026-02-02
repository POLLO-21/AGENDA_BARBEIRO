import os
import calendar
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import storage

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "dev_secret"
storage.init_db()

@app.route("/")
def home():
    if session.get("role") == "barbeiro":
        return redirect(url_for("painel_barbeiro"))
    return redirect(url_for("agenda"))

@app.route("/login", methods=["GET", "POST"])
def login():
    erro = ""
    if request.method == "POST":
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")
        user = storage.verify_user(usuario, senha)
        if user and user["role"] == "barbeiro":
            session["user_id"] = user["id"]
            session["usuario"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("painel_barbeiro"))

        erro = "Usuário ou senha inválidos"
    return render_template("login.html", erro=erro)

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("usuario", None)
    session.pop("role", None)
    return redirect(url_for("login"))

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

def build_dias_from_db(year=None, month=None, barber_id=None):
    if year is None or month is None:
        now = datetime.now()
        year = now.year
        month = now.month
    # Detalhes do mês
    num_days = calendar.monthrange(year, month)[1]
    # weekday: 0=Segunda, 6=Domingo
    first_weekday = calendar.monthrange(year, month)[0]
    
    # Ajuste para grid começar no Domingo (0)
    start_offset = (first_weekday + 1) % 7
    dias = []
    for _ in range(start_offset):
        dias.append({"tipo": "vazio"})
        
    today = datetime.now().date()
    
    for d in range(1, num_days + 1):
        current_date = datetime(year, month, d).date()
        is_past = current_date < today
        
        slots = storage.get_availability(d, year=year, month=month, barber_id=barber_id)
        disponivel = any(s.get("available", True) for s in slots)
        dias.append({
            "tipo": "dia",
            "numero": d, 
            "disponivel": disponivel,
            "passado": is_past
        })
        
    return {
        "dias": dias,
        "mes": month,
        "ano": year,
        "current_year": datetime.now().year,
        "mes_nome": f"{MESES[month-1]}/{year}",
        "meses_lista": MESES,
        "semana_header": ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    }

@app.route("/agenda")
def agenda():
    role = session.get("role")
    
    barber_id = storage.get_default_barber_id()
    barbearia_nome = "Barbearia"
    if barber_id:
        u = storage.get_user_by_id(barber_id)
        if u:
            barbearia_nome = (u['barbearia_nome'] if 'barbearia_nome' in u.keys() else None) or u['username'].capitalize()

    if role == "cliente" or role is None:
        mes = None
        ano = None
    else:
        try:
            mes = int(request.args.get("mes")) if request.args.get("mes") else None
            ano = int(request.args.get("ano")) if request.args.get("ano") else None
        except ValueError:
            mes = None
            ano = None

    dados_cal = build_dias_from_db(year=ano, month=mes, barber_id=barber_id)
    return render_template("agenda.html", **dados_cal, barber_id=barber_id, barbearia_nome=barbearia_nome)

@app.route("/horarios/<int:dia>")
def horarios(dia):
    ano = request.args.get("ano", type=int)
    mes = request.args.get("mes", type=int)
    barber_id = storage.get_default_barber_id()

    slots = storage.get_availability(dia, year=ano, month=mes, barber_id=barber_id)
    horarios_disponiveis = [s["time"] for s in slots if s.get("available", True)]
    return jsonify({"dia": dia, "horarios": horarios_disponiveis, "detalhes": slots})

@app.route("/reservar", methods=["POST"])
def reservar():
    if "usuario" not in session:
        public_client = storage.get_or_create_public_client()
        user_id = public_client["id"]
    else:
        user_id = session.get("user_id")
    # aceita tanto form quanto JSON
    dia = request.form.get("dia") or (request.json and request.json.get("dia"))
    horario = request.form.get("horario") or (request.json and request.json.get("horario"))
    service = request.form.get("service") or (request.json and request.json.get("service"))
    ano = request.form.get("ano") or (request.json and request.json.get("ano"))
    mes = request.form.get("mes") or (request.json and request.json.get("mes"))
    barber_id = storage.get_default_barber_id()

    try:
        dia = int(dia)
    except:
        return jsonify({"success": False, "error": "invalid_day"})
    
    year = None
    month = None
    try:
        if ano is not None:
            year = int(ano)
        if mes is not None:
            month = int(mes)
    except:
        year = None
        month = None

    if not horario:
        return jsonify({"success": False, "error": "invalid_time"})

    # Validação de data passada
    try:
        booking_date = datetime(year, month, dia).date()
        if booking_date < datetime.now().date():
             return jsonify({"success": False, "error": "past_date"})
    except:
        pass # Se der erro na data, deixa passar e falhará mais tarde ou será tratado

    if not service:
        service = "corte de cabelo"

    customer_phone = request.form.get("customer_phone") or (request.json and request.json.get("customer_phone"))
    customer_name = request.form.get("customer_name") or (request.json and request.json.get("customer_name"))

    ok = storage.create_booking(user_id, dia, horario, service, year=year, month=month, customer_phone=customer_phone, barber_id=barber_id, customer_name=customer_name)
    if ok:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "slot_taken"})

@app.route("/register_barber", methods=["GET", "POST"])
def register_barber():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")
        barbearia = request.form.get("barbearia")
        
        if storage.get_user_by_username(usuario):
            return render_template("register_barber.html", erro="Usuário já existe")
            
        storage.create_user(usuario, senha, role="barbeiro", barbearia_nome=barbearia)
        return redirect(url_for("login"))
        
    return render_template("register_barber.html")

@app.route("/perfil", methods=["GET", "POST"])
def perfil():
    if "user_id" not in session or session.get("role") != "barbeiro":
        return redirect(url_for("login"))
        
    user_id = session["user_id"]
    u = storage.get_user_by_id(user_id)
    erro = None
    
    if request.method == "POST":
        novo_usuario = request.form.get("usuario")
        senha_atual = request.form.get("senha_atual")
        nova_senha = request.form.get("senha_nova")
        confirmar_senha = request.form.get("senha_confirmar")
        nova_barbearia = request.form.get("barbearia")
        
        if novo_usuario and novo_usuario != u["username"]:
            existente = storage.get_user_by_username(novo_usuario)
            if existente and existente["id"] != user_id:
                erro = "Já existe um usuário com esse nome"
        
        if not erro and (nova_senha or confirmar_senha):
            if not senha_atual:
                erro = "Informe a senha atual para alterar a senha"
            else:
                valido = storage.verify_user(u["username"], senha_atual)
                if not valido:
                    erro = "Senha atual incorreta"
                elif nova_senha != confirmar_senha:
                    erro = "Nova senha e confirmação não conferem"
        
        if not erro:
            storage.update_user_profile(user_id, username=novo_usuario, password=nova_senha if nova_senha else None, barbearia_nome=nova_barbearia)
            if novo_usuario:
                session["usuario"] = novo_usuario
            return redirect(url_for("painel_barbeiro"))
    
    return render_template("perfil.html", usuario=u, erro=erro)


@app.route("/me/agendamentos")
def meus_agendamentos():
    if "usuario" not in session:
        return redirect(url_for("login"))
    user_id = session.get("user_id")
    rows = storage.get_bookings_by_user(user_id)
    return render_template("meus_agendamentos.html", bookings=rows)

def user_owns_booking(user_id, booking_id):
    rows = storage.get_bookings_by_user(user_id)
    return any(r["id"] == booking_id for r in rows)

@app.route("/cancelar", methods=["POST"])
def cancelar():
    if "usuario" not in session:
        return jsonify({"success": False, "error": "login_required"}), 401

    booking_id = request.form.get("booking_id") or (request.json and request.json.get("booking_id"))
    try:
        booking_id = int(booking_id)
    except:
        return jsonify({"success": False, "error": "invalid_id"})

    role = session.get("role")
    user_id = session.get("user_id")

    if role == "barbeiro" or user_owns_booking(user_id, booking_id):
        storage.cancel_booking(booking_id)
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "not_allowed"}), 403

@app.route("/painel_barbeiro")
def painel_barbeiro():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") != "barbeiro":
        return redirect(url_for("agenda"))

    bookings = storage.get_all_bookings_with_usernames(barber_id=session["user_id"])
    try:
        mes = int(request.args.get("mes")) if request.args.get("mes") else None
        ano = int(request.args.get("ano")) if request.args.get("ano") else None
    except ValueError:
        mes = None
        ano = None
    
    dados_cal = build_dias_from_db(year=ano, month=mes, barber_id=session["user_id"])

    # Buscar agendamentos de HOJE
    now = datetime.now()
    agendamentos_hoje_rows = storage.get_bookings_by_day_with_usernames(now.day, now.year, now.month, barber_id=session["user_id"])
    agendamentos_hoje = []
    for r in agendamentos_hoje_rows:
        agendamentos_hoje.append({
            "id": r["id"],
            "cliente": r["username"],
            "phone": r["customer_phone"],
            "time": r["time"],
            "status": r["status"],
            "service": r["service"] or "corte de cabelo"
        })

    return render_template("painel_barbeiro.html", bookings=bookings, agendamentos_hoje=agendamentos_hoje, **dados_cal)

@app.route("/api/dia/<int:dia>/agendamentos")
def api_agendamentos_dia(dia):
    if "user_id" not in session or session.get("role") != "barbeiro":
        return jsonify({"success": False, "error": "not_allowed"}), 403
    ano = request.args.get("ano", type=int)
    mes = request.args.get("mes", type=int)
    rows = storage.get_bookings_by_day_with_usernames(dia, year=ano, month=mes, barber_id=session["user_id"])
    dados = []
    for r in rows:
        dados.append({
            "id": r["id"],
            "cliente": r["username"],
            "phone": r["customer_phone"],
            "time": r["time"],
            "status": r["status"],
            "service": r["service"] or "corte de cabelo"
        })
    return jsonify({"success": True, "dia": dia, "agendamentos": dados})

# === ROTAS PARA EDIÇÃO/EXCLUSÃO ===
# Observação: Estas rotas verificam role == 'barbeiro' antes de permitir ação.

@app.route('/editar_dia/<int:dia_id>', methods=['GET', 'POST'])
def editar_dia(dia_id):
    if "role" not in session or session.get("role") != "barbeiro":
        return redirect(url_for("agenda"))

    # Pega mês/ano da URL
    try:
        mes = int(request.args.get("mes")) if request.args.get("mes") else None
        ano = int(request.args.get("ano")) if request.args.get("ano") else None
    except ValueError:
        mes = None
        ano = None

    slots = storage.get_availability(dia_id, year=ano, month=mes, barber_id=session["user_id"])
    
    # Se ano/mes foram passados, formata para exibição
    if mes and ano:
        dia_display = f"{dia_id}/{mes:02d}/{ano}"
    else:
        dia_display = str(dia_id)

    dia = {
        "numero": dia_display, 
        "raw_numero": dia_id,
        "disponivel": any(s.get("available", False) for s in slots),
        "mes": mes,
        "ano": ano
    }

    if request.method == "POST":
        # Se for post de edição de número (não recomendado, mas existe)
        return redirect(url_for("painel_barbeiro", mes=mes, ano=ano))

    return render_template("editar_dia.html", dia=dia, slots=slots)

@app.route('/excluir_dia/<int:dia_id>', methods=['POST'])
def excluir_dia(dia_id):
    if "role" not in session or session.get("role") != "barbeiro":
        return redirect(url_for("agenda"))

    mes = request.args.get("mes", type=int)
    ano = request.args.get("ano", type=int)

    storage.set_day_active(dia_id, 0, year=ano, month=mes, barber_id=session["user_id"])
    return redirect(url_for("painel_barbeiro", mes=mes, ano=ano))

@app.route('/restaurar_dia/<int:dia_id>', methods=['POST'])
def restaurar_dia(dia_id):
    if "role" not in session or session.get("role") != "barbeiro":
        return redirect(url_for("agenda"))
        
    mes = request.args.get("mes", type=int)
    ano = request.args.get("ano", type=int)

    storage.restore_day_availability(dia_id, year=ano, month=mes, barber_id=session["user_id"])
    return redirect(url_for("painel_barbeiro", mes=mes, ano=ano))

@app.route('/editar_horario/<int:horario_id>', methods=['GET', 'POST'])
def editar_horario(horario_id):
    if "role" not in session or session.get("role") != "barbeiro":
        return redirect(url_for("agenda"))

    horario_row = storage.get_horario_by_id(horario_id)
    if not horario_row:
        return redirect(url_for("painel_barbeiro"))

    # Converte row em dict-like para o template
    horario = {"id": horario_row["id"], "time": horario_row["time"], "available": (horario_row["active"] == 1)}

    if request.method == "POST":
        novo_horario = request.form.get("time")
        disponivel = True if request.form.get("available") in ("1", "on", "true", "True") else False
        storage.update_horario(horario_id, novo_horario, disponivel)
        return redirect(url_for("painel_barbeiro"))

    return render_template("editar_horario.html", horario=horario)

@app.route('/excluir_horario/<int:horario_id>', methods=['POST'])
def excluir_horario(horario_id):
    if "role" not in session or session.get("role") != "barbeiro":
        return redirect(url_for("agenda"))

    # Marca o horário (slot) como inativo em availability
    horario_row = storage.get_horario_by_id(horario_id)
    if horario_row:
        # atualiza para ativo = 0
        storage.update_horario(horario_id, horario_row["time"], False)
    # Tenta voltar para a página anterior com os mesmos parâmetros se possível
    # Mas como o referer pode ser complexo, voltamos para painel ou tentamos deduzir.
    # O ideal seria receber dia/mes/ano no form.
    return redirect(request.referrer or url_for("painel_barbeiro"))

@app.route('/ativar_horario/<int:horario_id>', methods=['POST'])
def ativar_horario(horario_id):
    if "role" not in session or session.get("role") != "barbeiro":
        return redirect(url_for("agenda"))
    storage.set_slot_active(horario_id, 1)
    return redirect(request.referrer or url_for("painel_barbeiro"))

@app.route('/liberar_horario_dia', methods=['POST'])
def liberar_horario_dia():
    if "role" not in session or session.get("role") != "barbeiro":
        return redirect(url_for("agenda"))
    
    day = request.form.get("day")
    time = request.form.get("time")
    month = request.form.get("month")
    year = request.form.get("year")
    slot_id = request.form.get("slot_id")

    if day and time and month and year:
        storage.cancel_booking_by_details(int(day), time, int(year), int(month))
    
    # Também garante que o slot esteja ativo na tabela availability
    if slot_id:
        storage.set_slot_active(int(slot_id), 1)

    return redirect(request.referrer or url_for("painel_barbeiro"))

if __name__ == "__main__":
    # host='0.0.0.0' permite acesso da rede local (necessário para teste real via celular)
    app.run(debug=True, host='0.0.0.0')
