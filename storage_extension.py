
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

def set_slot_active(slot_id, active=1):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE availability SET active=? WHERE id=?", (active, slot_id))
    conn.commit()
    conn.close()
