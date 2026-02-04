import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

def _db_path():
    url = os.getenv("DATABASE_URL", "sqlite:///agenda.db")
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    return url

def create_admin(username, password):
    conn = get_conn()
    cur = conn.cursor()
    # Verifica se já existe
    cur.execute("SELECT id FROM users WHERE username=?", (username,))
    if cur.fetchone():
        conn.close()
        return False
    
    pwd_hash = generate_password_hash(password)
    cur.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, pwd_hash, "admin")
    )
    conn.commit()
    conn.close()
    return True

def get_all_barbershops_with_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM barbershops")
    shops = cur.fetchall()
    
    # Mês/Ano atual para filtro
    now = datetime.now()
    
    results = []
    for shop in shops:
        sid = shop["id"]
        # Count barbers
        cur.execute("SELECT COUNT(*) c FROM users WHERE barbershop_id=? AND role='barbeiro'", (sid,))
        barbers_count = cur.fetchone()["c"]
        
        # Count bookings (somente do mês atual)
        cur.execute("SELECT COUNT(*) c FROM bookings WHERE barbershop_id=? AND month=? AND year=?", (sid, now.month, now.year))
        bookings_count = cur.fetchone()["c"]
        
        results.append({
            "id": sid,
            "name": shop["name"],
            "slug": shop["slug"],
            "barbers_count": barbers_count,
            "bookings_count": bookings_count
        })
    conn.close()
    return results

def get_conn():
    p = _db_path()
    conn = sqlite3.connect(p, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_legacy_data():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username='barbeiro'")
    row = cur.fetchone()
    if row:
        uid = row["id"]
        cur.execute("UPDATE availability SET barber_id=? WHERE barber_id IS NULL", (uid,))
        cur.execute("UPDATE bookings SET barber_id=? WHERE barber_id IS NULL", (uid,))
        conn.commit()
    conn.close()

def get_default_barber_id():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username='barbeiro'")
    row = cur.fetchone()
    if row:
        uid = row["id"]
        conn.close()
        return uid
    cur.execute("SELECT id FROM users WHERE role='barbeiro' ORDER BY id LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row["id"] if row else None

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    here = os.path.dirname(__file__)
    sql_path = os.path.join(here, "migrations.sql")
    with open(sql_path, "r", encoding="utf-8") as f:
        cur.executescript(f.read())
    conn.commit()
    cur.execute("PRAGMA table_info(bookings)")
    cols = [r["name"] for r in cur.fetchall()]
    if "service" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN service TEXT DEFAULT 'corte de cabelo'")
        conn.commit()
    if "year" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN year INTEGER")
    if "month" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN month INTEGER")
    if "customer_phone" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN customer_phone TEXT")
    if "customer_name" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN customer_name TEXT")
    if "barber_id" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN barber_id INTEGER")
    if "barbershop_id" not in cols:
        cur.execute("ALTER TABLE bookings ADD COLUMN barbershop_id INTEGER")

    cur.execute("PRAGMA table_info(availability)")
    acols = [r["name"] for r in cur.fetchall()]
    if "barber_id" not in acols:
        cur.execute("ALTER TABLE availability ADD COLUMN barber_id INTEGER")
    if "month" not in acols:
        cur.execute("ALTER TABLE availability ADD COLUMN month INTEGER")
    if "year" not in acols:
        cur.execute("ALTER TABLE availability ADD COLUMN year INTEGER")
    if "barbershop_id" not in acols:
        cur.execute("ALTER TABLE availability ADD COLUMN barbershop_id INTEGER")

    # Criar tabela barbershops se não existir
    cur.execute("""
        CREATE TABLE IF NOT EXISTS barbershops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            phone TEXT,
            address TEXT
        )
    """)
    
    # Garantir colunas na tabela barbershops (migração)
    cur.execute("PRAGMA table_info(barbershops)")
    bcols = [r["name"] for r in cur.fetchall()]
    if "phone" not in bcols:
        cur.execute("ALTER TABLE barbershops ADD COLUMN phone TEXT")
    if "address" not in bcols:
        cur.execute("ALTER TABLE barbershops ADD COLUMN address TEXT")

    cur.execute("PRAGMA table_info(users)")
    ucols = [r["name"] for r in cur.fetchall()]
    if "barbearia_nome" not in ucols:
        cur.execute("ALTER TABLE users ADD COLUMN barbearia_nome TEXT")
    if "phone" not in ucols:
        cur.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    if "barbershop_id" not in ucols:
        cur.execute("ALTER TABLE users ADD COLUMN barbershop_id INTEGER")
    if "email" not in ucols:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")

    # Indices para performance com muitas barbearias
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bookings_shop ON bookings(barbershop_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_shop ON users(barbershop_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_avail_shop ON availability(barbershop_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_avail_date ON availability(year, month, day)")

    # Criar barbearia padrão se não existir
    cur.execute("SELECT COUNT(*) c FROM barbershops")
    if cur.fetchone()["c"] == 0:
        cur.execute("INSERT INTO barbershops (name, slug, phone) VALUES (?, ?, ?)", 
                   ("Minha Barbearia", "minha-barbearia", "00000000000"))
        bs_id = cur.lastrowid
        # Migrar dados existentes para a barbearia padrão
        cur.execute("UPDATE users SET barbershop_id=? WHERE barbershop_id IS NULL", (bs_id,))
        cur.execute("UPDATE bookings SET barbershop_id=? WHERE barbershop_id IS NULL", (bs_id,))
        cur.execute("UPDATE availability SET barbershop_id=? WHERE barbershop_id IS NULL", (bs_id,))
        conn.commit()

    if ("year" not in cols) or ("month" not in cols):
        now = datetime.now()
        cur.execute("UPDATE bookings SET year=? WHERE year IS NULL", (now.year,))
        cur.execute("UPDATE bookings SET month=? WHERE month IS NULL", (now.month,))
        conn.commit()
    
    conn.close()
    
    # Run migration in a separate connection to avoid locking issues if any
    migrate_legacy_data()
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) c FROM availability")
    if cur.fetchone()["c"] == 0:
        # Se não tem nada, seed default (talvez para um barbeiro criado agora?)
        # Mas seed_default_availability não recebe barber_id...
        # Vamos deixar quieto por enquanto, create_user cuida disso.
        # Ou se for o primeiro run limpo:
        pass 
    conn.close()

def generate_default_times():
    times = []
    # Manhã: 08:00 às 10:30 (fecha às 11:00)
    for h in range(8, 11): # 8, 9, 10
        times.append(f"{h:02d}:00")
        times.append(f"{h:02d}:30")
            
    # Tarde: 13:00 às 18:30 (fecha às 19:00)
    for h in range(13, 19): # 13, 14, 15, 16, 17, 18
        times.append(f"{h:02d}:00")
        times.append(f"{h:02d}:30")
    return times

def seed_default_availability(conn):
    times = generate_default_times()
    cur = conn.cursor()
    # Cria disponibilidade para dias 1 a 31
    for day in range(1,32):
        for t in times:
            cur.execute("INSERT INTO availability(day,time,active) VALUES(?,?,1)", (day,t))
    conn.commit()

def reset_availability():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM availability")
    conn.commit()
    seed_default_availability(conn)
    conn.close()

def get_barbershops():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM barbershops ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_barbershop(shop_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM barbershops WHERE id=?", (shop_id,))
    row = cur.fetchone()
    conn.close()
    return row

def get_barbershop_by_slug(slug):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM barbershops WHERE slug=?", (slug,))
    row = cur.fetchone()
    conn.close()
    return row

def update_barbershop(shop_id, name, slug, phone, address):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE barbershops SET name=?, slug=?, phone=?, address=? WHERE id=?", 
                (name, slug, phone, address, shop_id))
    conn.commit()
    conn.close()

def get_users_by_barbershop(shop_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE barbershop_id=?", (shop_id,))
    rows = cur.fetchall()
    conn.close()
    return rows

def delete_barbershop(shop_id):
    conn = get_conn()
    cur = conn.cursor()
    # Delete related data
    cur.execute("DELETE FROM bookings WHERE barbershop_id=?", (shop_id,))
    cur.execute("DELETE FROM availability WHERE barbershop_id=?", (shop_id,))
    cur.execute("DELETE FROM users WHERE barbershop_id=?", (shop_id,))
    cur.execute("DELETE FROM barbershops WHERE id=?", (shop_id,))
    conn.commit()
    conn.close()

def create_user(username, password, role="cliente", barbearia_nome=None, phone=None, barbershop_id=None, email=None):
    conn = get_conn()
    cur = conn.cursor()
    ph = generate_password_hash(password)
    
    # Se não foi passado barbershop_id, tenta pegar o primeiro (default)
    if barbershop_id is None:
        cur.execute("SELECT id FROM barbershops LIMIT 1")
        row = cur.fetchone()
        if row:
            barbershop_id = row["id"]

    cur.execute("INSERT INTO users(username,password_hash,role,barbearia_nome,phone,barbershop_id,email) VALUES(?,?,?,?,?,?,?)", 
               (username,ph,role,barbearia_nome,phone,barbershop_id,email))
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    if role == "barbeiro":
        seed_availability_for_barber(user_id)
    return user_id

def update_user_profile(user_id, username=None, password=None, barbearia_nome=None, phone=None, address=None):
    conn = get_conn()
    cur = conn.cursor()
    
    # Se houver atualização de nome de barbearia, atualizar também na tabela barbershops
    if barbearia_nome or phone or address:
        cur.execute("SELECT barbershop_id FROM users WHERE id=?", (user_id,))
        row = cur.fetchone()
        if row and row["barbershop_id"]:
            shop_id = row["barbershop_id"]
            
            # Construir query dinâmica para barbershops
            shop_fields = []
            shop_params = []
            if barbearia_nome:
                shop_fields.append("name=?")
                shop_params.append(barbearia_nome)
            if phone:
                shop_fields.append("phone=?")
                shop_params.append(phone)
            if address:
                shop_fields.append("address=?")
                shop_params.append(address)
            
            if shop_fields:
                shop_params.append(shop_id)
                cur.execute(f"UPDATE barbershops SET {', '.join(shop_fields)} WHERE id=?", tuple(shop_params))

    fields = []
    params = []
    if username:
        fields.append("username=?")
        params.append(username)
    if password:
        fields.append("password_hash=?")
        params.append(generate_password_hash(password))
    if barbearia_nome:
        fields.append("barbearia_nome=?")
        params.append(barbearia_nome)
    
    if fields:
        params.append(user_id)
        cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", tuple(params))
        
    conn.commit()
    conn.close()

def seed_availability_for_barber(barber_id):
    conn = get_conn()
    cur = conn.cursor()
    times = generate_default_times()
    for day in range(1,32):
        for t in times:
            cur.execute("INSERT INTO availability(day,time,active,barber_id) VALUES(?,?,1,?)", (day,t,barber_id))
    conn.commit()
    conn.close()

def get_user_by_username(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    return row

def get_user_by_id(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def verify_user(username, password):
    u = get_user_by_username(username)
    if not u:
        return None
    if check_password_hash(u["password_hash"], password):
        return {"id": u["id"], "username": u["username"], "role": u["role"]}
    return None

def ensure_daily_slots(conn, day, month, year, barber_id, barbershop_id=None):
    cur = conn.cursor()
    # Verifica se já existem slots para este dia/mês/ano/barbeiro/barbearia
    query = "SELECT COUNT(*) c FROM availability WHERE day=? AND month=? AND year=?"
    params = [day, month, year]
    
    if barber_id is None:
        query += " AND barber_id IS NULL"
    else:
        query += " AND barber_id=?"
        params.append(barber_id)
    
    if barbershop_id is None:
        query += " AND barbershop_id IS NULL"
    else:
        query += " AND barbershop_id=?"
        params.append(barbershop_id)
        
    cur.execute(query, tuple(params))
    count = cur.fetchone()["c"]
    
    if count == 0:
        # Se não existe, cria os slots padrão
        times = generate_default_times()
        for t in times:
            insert_sql = "INSERT INTO availability(day, month, year, time, active, barber_id, barbershop_id) VALUES(?, ?, ?, ?, 1, ?, ?)"
            cur.execute(insert_sql, (day, month, year, t, barber_id, barbershop_id))
        conn.commit()

def get_availability(day, year=None, month=None, barber_id=None, barbershop_id=None):
    if year is None or month is None:
        now = datetime.now()
        if year is None: year = now.year
        if month is None: month = now.month

    conn = get_conn()
    
    # Se barbershop_id não for passado, tenta inferir do barber_id ou pegar default?
    # Melhor deixar explícito. Se None, pode misturar dados.
    
    # Garante que existem slots para este dia específico
    ensure_daily_slots(conn, day, month, year, barber_id, barbershop_id)
    
    cur = conn.cursor()
    
    query_avail = "SELECT id, time, active FROM availability WHERE day=? AND month=? AND year=?"
    params_avail = [day, month, year]
    
    if barber_id is None:
        query_avail += " AND barber_id IS NULL"
    else:
        query_avail += " AND barber_id=?"
        params_avail.append(barber_id)
    
    if barbershop_id is None:
        query_avail += " AND barbershop_id IS NULL"
    else:
        query_avail += " AND barbershop_id=?"
        params_avail.append(barbershop_id)
        
    query_avail += " ORDER BY time"
    
    cur.execute(query_avail, tuple(params_avail))
    avail_rows = cur.fetchall()

    # Busca agendamentos confirmados para marcar como ocupado
    query_book = "SELECT time FROM bookings WHERE day=? AND status='confirmado' AND year=? AND month=?"
    params_book = [day, year, month]
    
    if barber_id is None:
        query_book += " AND barber_id IS NULL"
    else:
        query_book += " AND barber_id=?"
        params_book.append(barber_id)
    
    if barbershop_id is None:
        query_book += " AND barbershop_id IS NULL"
    else:
        query_book += " AND barbershop_id=?"
        params_book.append(barbershop_id)

    cur.execute(query_book, tuple(params_book))
    taken_rows = cur.fetchall()
    taken_times = {row["time"] for row in taken_rows}
    
    slots = []
    for r in avail_rows:
        is_taken = r["time"] in taken_times
        slots.append({
            "id": r["id"], 
            "time": r["time"], 
            "available": (r["active"] == 1 and not is_taken),
            "active": (r["active"] == 1),
            "is_taken": is_taken
        })
    
    conn.close()
    return slots

def is_slot_taken(day, time, year=None, month=None, barber_id=None, barbershop_id=None):
    conn = get_conn()
    cur = conn.cursor()
    query = "SELECT COUNT(*) c FROM bookings WHERE day=? AND time=? AND status='confirmado'"
    params = [day, time]
    
    if year is not None and month is not None:
        query += " AND year=? AND month=?"
        params.extend([year, month])
        
    if barber_id is None:
        query += " AND barber_id IS NULL"
    else:
        query += " AND barber_id=?"
        params.append(barber_id)
        
    if barbershop_id is None:
        query += " AND barbershop_id IS NULL"
    else:
        query += " AND barbershop_id=?"
        params.append(barbershop_id)
        
    cur.execute(query, tuple(params))
    c = cur.fetchone()["c"]
    conn.close()
    return c > 0

def create_booking(user_id, day, time, service="corte de cabelo", year=None, month=None, customer_phone=None, barber_id=None, customer_name=None, barbershop_id=None):
    if year is None or month is None:
        now = datetime.now()
        if year is None:
            year = now.year
        if month is None:
            month = now.month
    if is_slot_taken(day, time, year, month, barber_id, barbershop_id):
        return False
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO bookings(user_id,day,month,year,time,status,created_at,service,customer_phone,customer_name,barber_id,barbershop_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (user_id, day, month, year, time, "confirmado", datetime.now(), service, customer_phone, customer_name, barber_id, barbershop_id)
    )
    conn.commit()
    conn.close()
    return True

def get_bookings_by_user(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM bookings WHERE user_id=? AND status='confirmado' "
        "ORDER BY year DESC, month DESC, day DESC, time",
        (user_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def get_bookings_by_day_with_usernames(day, year=None, month=None, barber_id=None, barbershop_id=None):
    conn = get_conn()
    cur = conn.cursor()
    base_sql = """
        SELECT b.id, b.user_id, b.day, b.month, b.year, b.time, b.status, b.created_at, b.service, b.customer_phone, u.username
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE b.day=? AND b.status='confirmado'
    """
    params = [day]
    if year is not None and month is not None:
        base_sql += " AND b.year=? AND b.month=?"
        params.extend([year, month])
    
    if barber_id is None:
        base_sql += " AND b.barber_id IS NULL"
    else:
        base_sql += " AND b.barber_id=?"
        params.append(barber_id)
        
    if barbershop_id is None:
        base_sql += " AND b.barbershop_id IS NULL"
    else:
        base_sql += " AND b.barbershop_id=?"
        params.append(barbershop_id)
        
    base_sql += " ORDER BY b.time"
    cur.execute(base_sql, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return rows

def cancel_booking(booking_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE bookings SET status='cancelado' WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()

def get_all_bookings_with_usernames(barber_id=None, barbershop_id=None):
    conn = get_conn()
    cur = conn.cursor()
    sql = """
        SELECT b.id, b.user_id, b.day, b.month, b.year, b.time, b.status, b.created_at, b.service, b.customer_phone, b.customer_name, u.username
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        WHERE b.status='confirmado'
    """
    params = []
    if barber_id is None:
        sql += " AND b.barber_id IS NULL"
    else:
        sql += " AND b.barber_id=?"
        params.append(barber_id)
    
    if barbershop_id is None:
        sql += " AND b.barbershop_id IS NULL"
    else:
        sql += " AND b.barbershop_id=?"
        params.append(barbershop_id)
        
    sql += " ORDER BY b.year DESC, b.month DESC, b.day DESC, b.time"
    
    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return rows

# NOVOS MÉTODOS para editar horários e dias:

def get_horario_by_id(horario_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM availability WHERE id=?", (horario_id,))
    row = cur.fetchone()
    conn.close()
    return row

def update_horario(horario_id, time, available):
    conn = get_conn()
    cur = conn.cursor()
    active = 1 if available else 0
    cur.execute("UPDATE availability SET time=?, active=? WHERE id=?", (time, active, horario_id))
    conn.commit()
    conn.close()

def get_dia_by_id(dia_id):
    # This is slightly tricky because "dia_id" usually refers to a day number (1-31) in the old schema
    # But here we probably pass the day number. 
    # However, if we are editing "Day 5", which Month/Year?
    # The current 'editar_dia' route uses 'dia_id' as the day number.
    # We should probably update the route to pass month/year too.
    # For now, let's keep it simple or see how it's used.
    pass

def update_dia(dia_id, novo_dia):
    # Deprecated or needs update to handle month/year
    pass

# compatibilidade
def get_db_connection():
    return get_conn()

def cancel_booking_by_details(day, time, year, month):
    conn = get_conn()
    cur = conn.cursor()
    # Find booking id
    cur.execute(
        "SELECT id FROM bookings WHERE day=? AND time=? AND year=? AND month=? AND status='confirmado'",
        (day, time, year, month)
    )
    row = cur.fetchone()
    if row:
        booking_id = row["id"]
        cur.execute("UPDATE bookings SET status='cancelado' WHERE id=?", (booking_id,))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def get_or_create_public_client():
    username = "Cliente"
    u = get_user_by_username(username)
    if not u:
        create_user(username, "publico", role="cliente")
        u = get_user_by_username(username)
    return u

def set_slot_active(slot_id, active=1):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE availability SET active=? WHERE id=?", (active, slot_id))
    conn.commit()
    conn.close()

def set_day_active(day, active, year=None, month=None, barber_id=None, barbershop_id=None):
    if year is None or month is None:
        now = datetime.now()
        if year is None: year = now.year
        if month is None: month = now.month
        
    conn = get_conn()
    ensure_daily_slots(conn, day, month, year, barber_id, barbershop_id)
    cur = conn.cursor()
    
    query = "UPDATE availability SET active=? WHERE day=? AND month=? AND year=?"
    params = [active, day, month, year]
    
    if barber_id is None:
        query += " AND barber_id IS NULL"
    else:
        query += " AND barber_id=?"
        params.append(barber_id)
        
    if barbershop_id is None:
        query += " AND barbershop_id IS NULL"
    else:
        query += " AND barbershop_id=?"
        params.append(barbershop_id)
        
    cur.execute(query, tuple(params))
    conn.commit()
    conn.close()

def restore_day_availability(day, year=None, month=None, barber_id=None, barbershop_id=None):
    if year is None or month is None:
        now = datetime.now()
        if year is None: year = now.year
        if month is None: month = now.month

    conn = get_conn()
    ensure_daily_slots(conn, day, month, year, barber_id, barbershop_id)
    cur = conn.cursor()
    
    query = "UPDATE availability SET active=1 WHERE day=? AND month=? AND year=?"
    params = [day, month, year]
    
    if barber_id is None:
        query += " AND barber_id IS NULL"
    else:
        query += " AND barber_id=?"
        params.append(barber_id)
        
    if barbershop_id is None:
        query += " AND barbershop_id IS NULL"
    else:
        query += " AND barbershop_id=?"
        params.append(barbershop_id)
        
    cur.execute(query, tuple(params))
    conn.commit()
    conn.close()
