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
    # Se estiver logado, redireciona conforme o papel
    if session.get("user_id"):
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        elif session.get("role") == "barbeiro":
            return redirect(url_for("painel_barbeiro"))
        else:
            return redirect(url_for("agenda"))
    
    # Se não estiver logado, vai para a tela de login
    return redirect(url_for("login"))

@app.route("/selecionar_loja/<int:shop_id>")
def selecionar_loja(shop_id):
    # Rota mantida apenas para compatibilidade interna, se necessário
    # Mas o acesso direto não deve ser encorajado publicamente
    shop = storage.get_barbershop(shop_id)
    if shop:
        session["barbershop_id"] = shop["id"]
        session["barbershop_nome"] = shop["name"]
        session["barbershop_slug"] = shop["slug"]
    return redirect(url_for("agenda"))

@app.route("/b/<slug>")
def selecionar_loja_slug(slug):
    shop = storage.get_barbershop_by_slug(slug)
    if shop:
        session["barbershop_id"] = shop["id"]
        session["barbershop_nome"] = shop["name"]
        session["barbershop_slug"] = shop["slug"]
        return redirect(url_for("agenda"))
    return "Barbearia não encontrada", 404

@app.route("/login", methods=["GET", "POST"])
def login():
    erro = ""
    if request.method == "POST":
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")
        user = storage.verify_user(usuario, senha)
        if user:
            session["user_id"] = user["id"]
            session["usuario"] = user["username"]
            session["role"] = user["role"]
            
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

            # Carrega a barbearia do usuário na sessão
            u_full = storage.get_user_by_id(user["id"])
            if u_full and u_full["barbershop_id"]:
                shop = storage.get_barbershop(u_full["barbershop_id"])
                if shop:
                    session["barbershop_id"] = shop["id"]
                    session["barbershop_nome"] = shop["name"]
                    session["barbershop_slug"] = shop["slug"]
            
            if user["role"] == "barbeiro":
                return redirect(url_for("painel_barbeiro"))
            return redirect(url_for("agenda"))

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

def build_dias_from_db(year=None, month=None, barber_id=None, barbershop_id=None):
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
        
        slots = storage.get_availability(d, year=year, month=month, barber_id=barber_id, barbershop_id=barbershop_id)
        
        # Filtrar horários passados se for o dia atual
        if not is_past and current_date == today:
            now_time = datetime.now().strftime("%H:%M")
            # Disponível apenas se houver slot ativo, não tomado E futuro
            disponivel = any(s.get("available", True) and s["time"] > now_time for s in slots)
        else:
            disponivel = any(s.get("available", True) for s in slots)

        dias.append({
            "tipo": "dia",
            "numero": f"{d:02d}", 
            "raw_numero": d,
            "disponivel": disponivel,
            "passado": is_past
        })
        
    return {
        "dias": dias,
        "mes": month,
        "ano": year,
        "current_year": datetime.now().year,
        "mes_nome": f"{MESES[month-1]}",
        "meses_lista": MESES,
        "semana_header": ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    }

@app.route("/agenda")
def agenda():
    role = session.get("role")
    
    # Verifica barbearia selecionada
    barbershop_id = session.get("barbershop_id")
    if not barbershop_id:
        return redirect(url_for("home"))

    # Buscar dados da barbearia para pegar o telefone
    shop = storage.get_barbershop(barbershop_id)
    barbershop_phone = shop["phone"] if shop else None

    barber_id = None # Opcional: filtrar por barbeiro específico se houver seleção
    # Por enquanto, assume que agenda mostra disponibilidade da barbearia (todos ou default)
    
    barbearia_nome = session.get("barbershop_nome", "Barbearia")

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

    dados_cal = build_dias_from_db(year=ano, month=mes, barber_id=barber_id, barbershop_id=barbershop_id)
    return render_template("agenda.html", **dados_cal, barber_id=barber_id, barbearia_nome=barbearia_nome, barbershop_phone=barbershop_phone)

@app.route("/horarios/<int:dia>")
def horarios(dia):
    ano = request.args.get("ano", type=int)
    mes = request.args.get("mes", type=int)
    barbershop_id = session.get("barbershop_id")
    # barber_id = storage.get_default_barber_id() # Não usar mais default global
    
    if not barbershop_id:
        return jsonify({"error": "no_shop_selected"}), 400

    slots = storage.get_availability(dia, year=ano, month=mes, barber_id=None, barbershop_id=barbershop_id)
    
    # Filtrar horários passados se for hoje
    try:
        current_date = datetime(ano, mes, dia).date()
        if current_date == datetime.now().date():
            now_time = datetime.now().strftime("%H:%M")
            horarios_disponiveis = [s["time"] for s in slots if s.get("available", True) and s["time"] > now_time]
        elif current_date < datetime.now().date():
             horarios_disponiveis = [] # Dia passado não tem horários
        else:
             horarios_disponiveis = [s["time"] for s in slots if s.get("available", True)]
    except ValueError:
        horarios_disponiveis = []

    return jsonify({"dia": dia, "horarios": horarios_disponiveis, "detalhes": slots})

@app.route("/reservar", methods=["POST"])
def reservar():
    if "usuario" not in session:
        public_client = storage.get_or_create_public_client()
        user_id = public_client["id"]
    else:
        user_id = session.get("user_id")
        
    barbershop_id = session.get("barbershop_id")
    if not barbershop_id:
        return jsonify({"success": False, "error": "no_shop_selected"})

    # aceita tanto form quanto JSON
    dia = request.form.get("dia") or (request.json and request.json.get("dia"))
    horario = request.form.get("horario") or (request.json and request.json.get("horario"))
    service = request.form.get("service") or (request.json and request.json.get("service"))
    ano = request.form.get("ano") or (request.json and request.json.get("ano"))
    mes = request.form.get("mes") or (request.json and request.json.get("mes"))
    
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
        pass 

    if not service:
        service = "corte de cabelo"

    customer_name = request.form.get("customer_name") or (request.json and request.json.get("customer_name"))

    ok = storage.create_booking(user_id, dia, horario, service, year=year, month=month, customer_phone=None, barber_id=None, customer_name=customer_name, barbershop_id=barbershop_id)
    if ok:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "slot_taken"})

@app.route("/register_barber", methods=["GET", "POST"])
def register_barber():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")
        barbearia_nome = request.form.get("barbearia")
        phone = request.form.get("phone")
        # email removido conforme solicitação
        address = request.form.get("address")
        
        if storage.get_user_by_username(usuario):
            return render_template("register_barber.html", erro="Usuário já existe")

        # Verificações adicionais de unicidade (Barbearia e Telefone)
        conn = storage.get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM barbershops WHERE name = ?", (barbearia_nome,))
        if cur.fetchone():
            conn.close()
            return render_template("register_barber.html", erro="Nome da barbearia já existe")

        cur.execute("SELECT id FROM barbershops WHERE phone = ?", (phone,))
        if cur.fetchone():
            conn.close()
            return render_template("register_barber.html", erro="Telefone já cadastrado em uma barbearia")

        cur.execute("SELECT id FROM users WHERE phone = ?", (phone,))
        if cur.fetchone():
            conn.close()
            return render_template("register_barber.html", erro="Telefone já vinculado a um usuário")
            
        # Cria a barbearia
        # Gerar slug simples
        slug = barbearia_nome.lower().replace(" ", "-")
        
        # Check slug uniqueness (basic)
        cur.execute("SELECT id FROM barbershops WHERE slug=?", (slug,))
        if cur.fetchone():
            slug = f"{slug}-{datetime.now().strftime('%S')}"
            
        cur.execute("INSERT INTO barbershops(name, slug, phone, address) VALUES(?,?,?,?)", (barbearia_nome, slug, phone, None))
        shop_id = cur.lastrowid
        conn.commit()
        conn.close()

        storage.create_user(usuario, senha, role="barbeiro", barbearia_nome=barbearia_nome, phone=phone, barbershop_id=shop_id, email=None)
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
        phone = request.form.get("phone")
        
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
            storage.update_user_profile(user_id, username=novo_usuario, password=nova_senha if nova_senha else None, barbearia_nome=nova_barbearia, phone=phone, address=None)
            if novo_usuario:
                session["usuario"] = novo_usuario
            if nova_barbearia:
                session["barbershop_nome"] = nova_barbearia
            return redirect(url_for("painel_barbeiro"))
    
    # Carregar dados da barbearia se existir
    shop_data = None
    if u["barbershop_id"]:
        shop_data = storage.get_barbershop(u["barbershop_id"])

    return render_template("perfil.html", usuario=u, shop=shop_data, erro=erro)


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
        # Usa customer_name se existir, senão usa username (do cadastro ou "Cliente")
        nome_cliente = r["customer_name"] if r["customer_name"] else r["username"]
        agendamentos_hoje.append({
            "id": r["id"],
            "cliente": nome_cliente,
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
        nome_cliente = r["customer_name"] if r["customer_name"] else r["username"]
        dados.append({
            "id": r["id"],
            "cliente": nome_cliente,
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
        dia_display = f"{dia_id:02d}/{mes:02d}/{ano}"
    else:
        dia_display = f"{dia_id:02d}"

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

@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    # Verifica se é admin
    role = session.get("role")
    if role != "admin":
        return redirect(url_for("agenda"))
        
    shops = storage.get_all_barbershops_with_stats()
    return render_template("admin_dashboard.html", shops=shops)

@app.route("/admin/barbershop/<int:shop_id>", methods=["GET", "POST"])
def admin_barbershop_details(shop_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))
    
    shop = storage.get_barbershop(shop_id)
    if not shop:
        return redirect(url_for("admin_dashboard"))
        
    users = storage.get_users_by_barbershop(shop_id)
    # Tenta encontrar o usuário principal (primeiro barbeiro)
    main_user = next((u for u in users if u["role"] == "barbeiro"), None)

    if request.method == "POST":
        name = request.form.get("name")
        slug = request.form.get("slug")
        phone = request.form.get("phone")
        address = request.form.get("address")
        
        # Dados do usuário
        username = request.form.get("username")
        password = request.form.get("password")
        
        # Check slug uniqueness if changed
        if slug != shop["slug"]:
            existing = storage.get_barbershop_by_slug(slug)
            if existing and existing["id"] != shop_id:
                return render_template("admin_barbershop_details.html", shop=shop, users=users, main_user=main_user, erro="Slug já existe")
        
        storage.update_barbershop(shop_id, name, slug, phone, address)
        
        # Atualizar usuário se fornecido e se existir um usuário principal
        if main_user and username:
            storage.update_user_profile(main_user["id"], username=username, password=password if password else None)
            
        return redirect(url_for("admin_barbershop_details", shop_id=shop_id))
        
    return render_template("admin_barbershop_details.html", shop=shop, users=users, main_user=main_user)

@app.route("/admin/barbershop/<int:shop_id>/delete", methods=["POST"])
def admin_delete_barbershop(shop_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))
        
    storage.delete_barbershop(shop_id)
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/barbershop/<int:shop_id>/toggle_status", methods=["POST"])
def admin_toggle_barbershop_status(shop_id):
    if "user_id" not in session or session.get("role") != "admin":
        return redirect(url_for("login"))
        
    storage.toggle_barbershop_status(shop_id)
    return redirect(url_for("admin_barbershop_details", shop_id=shop_id))

@app.route("/setup_admin_secret_123")
def setup_admin():
    # Rota secreta temporária para criar o primeiro admin
    # Em produção, remover ou proteger melhor
    ok = storage.create_admin("admin", "admin123")
    if ok:
        return "Admin criado com sucesso: admin / admin123"
    return "Admin já existe ou erro."

if __name__ == "__main__":
    # host='0.0.0.0' permite acesso da rede local (necessário para teste real via celular)
    app.run(debug=True, host='0.0.0.0')
