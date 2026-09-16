"""
app.py

Life Dashboard - applicazione personale per tracciare dieta, spese e
statistiche di vita quotidiana.

Avvio:
    python app.py

L'app gira in locale su http://127.0.0.1:5000
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import date, datetime, timedelta
import database

app = Flask(__name__)

# Categorie di spesa disponibili in tutta l'app.
EXPENSE_CATEGORIES = [
    "Food", "Transport", "University", "Gym",
    "Entertainment", "Technology", "Shopping", "Other"
]

# Categorie di entrata (separate dalle spese: hanno senso diverso).
INCOME_CATEGORIES = [
    "Salary", "Allowance", "Freelance", "Gift", "Refund", "Other"
]

MEALS = ["Breakfast", "Lunch", "Dinner", "Snack"]

# Giorni della settimana nell'ordine usato da date.weekday() (0=Lunedì).
WEEKDAYS_IT = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def today_str():
    return date.today().isoformat()


def get_settings():
    conn = database.get_connection()
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    conn.close()
    return dict(row)


def get_daily_nutrition_totals(day):
    """Somma calorie/proteine/carbo/grassi per un dato giorno."""
    conn = database.get_connection()
    row = conn.execute("""
        SELECT
            COALESCE(SUM(calories), 0) AS calories,
            COALESCE(SUM(protein), 0) AS protein,
            COALESCE(SUM(carbs), 0) AS carbs,
            COALESCE(SUM(fats), 0) AS fats
        FROM food_entries WHERE date = ?
    """, (day,)).fetchone()
    conn.close()
    return dict(row)


def get_daily_expense_total(day):
    """Totale delle sole spese (type='expense') per un dato giorno."""
    conn = database.get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date = ? AND type = 'expense'",
        (day,)
    ).fetchone()
    conn.close()
    return row["total"]


def get_month_expense_total(year_month):
    """Totale delle sole spese nel mese 'YYYY-MM'."""
    conn = database.get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date LIKE ? AND type = 'expense'",
        (year_month + "%",)
    ).fetchone()
    conn.close()
    return row["total"]


def get_month_income_total(year_month):
    """Totale delle sole entrate nel mese 'YYYY-MM'."""
    conn = database.get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date LIKE ? AND type = 'income'",
        (year_month + "%",)
    ).fetchone()
    conn.close()
    return row["total"]


def get_top_category(year_month):
    """Categoria di spesa (non entrata) con il totale più alto nel mese."""
    conn = database.get_connection()
    row = conn.execute("""
        SELECT category, SUM(amount) AS total
        FROM expenses
        WHERE date LIKE ? AND type = 'expense'
        GROUP BY category
        ORDER BY total DESC
        LIMIT 1
    """, (year_month + "%",)).fetchone()
    conn.close()
    return row["category"] if row else None


def get_latest_weight():
    conn = database.get_connection()
    row = conn.execute(
        "SELECT weight_kg FROM weight_entries ORDER BY date DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["weight_kg"] if row else None


def get_today_stats(day):
    conn = database.get_connection()
    row = conn.execute("SELECT * FROM daily_stats WHERE date = ?", (day,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def get_university_settings():
    conn = database.get_connection()
    row = conn.execute("SELECT * FROM university_settings WHERE id = 1").fetchone()
    conn.close()
    return dict(row)


def get_passed_exams():
    """Tutti gli esami con status='passed', cioè quelli con un voto registrato."""
    conn = database.get_connection()
    rows = conn.execute(
        "SELECT * FROM exams WHERE status = 'passed' ORDER BY exam_date DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def calculate_weighted_average(passed_exams):
    """
    Media ponderata per CFU, come richiesto dal sistema universitario italiano:
    media = somma(voto * cfu) / somma(cfu)
    Gli esami con lode (30 e lode) contano come 30 nella media numerica
    (convenzione standard italiana: la lode non alza il voto numerico,
    è un riconoscimento aggiuntivo che conta a parte per la discussione di laurea).
    Restituisce None se non ci sono ancora esami superati (media non calcolabile).
    """
    if not passed_exams:
        return None

    total_weighted = sum(e["grade"] * e["cfu"] for e in passed_exams)
    total_cfu = sum(e["cfu"] for e in passed_exams)

    if total_cfu == 0:
        return None

    return total_weighted / total_cfu


def calculate_graduation_projection(average, uni_settings):
    """
    Stima del voto di laurea in 110, sistema italiano.
    Formula standard usata dalla maggior parte degli atenei:
        base_110 = media_in_30 * (110 / 30)
    A questo si sommano punti tesi e punti bonus (attività extra,
    Erasmus, tempi di laurea, ecc. - variano da ateneo ad ateneo,
    per questo sono impostabili manualmente).
    Il risultato è arrotondato all'intero più vicino e mai superiore a 110.
    Restituisce None se la media non è disponibile.
    """
    if average is None:
        return None

    base_110 = average * (110 / 30)
    projected = base_110 + uni_settings["thesis_points"] + uni_settings["bonus_points"]
    projected = min(projected, 110)
    return round(projected, 1)


def get_upcoming_exams():
    conn = database.get_connection()
    rows = conn.execute("""
        SELECT * FROM exams
        WHERE status = 'planned' AND exam_date IS NOT NULL
        ORDER BY exam_date ASC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weekly_schedule():
    """Restituisce l'orario raggruppato per giorno della settimana (0=Lunedì)."""
    conn = database.get_connection()
    rows = conn.execute(
        "SELECT * FROM class_schedule ORDER BY day_of_week, start_time"
    ).fetchall()
    conn.close()

    schedule_by_day = {i: [] for i in range(7)}
    for r in rows:
        schedule_by_day[r["day_of_week"]].append(dict(r))
    return schedule_by_day


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    day = today_str()
    settings = get_settings()
    nutrition = get_daily_nutrition_totals(day)
    stats = get_today_stats(day)
    weight = get_latest_weight()

    year_month = day[:7]
    money_today = get_daily_expense_total(day)
    money_month = get_month_expense_total(year_month)
    income_month = get_month_income_total(year_month)
    net_month = income_month - money_month
    top_category = get_top_category(year_month)

    # Dati per i grafici degli ultimi 14 giorni.
    conn = database.get_connection()
    since = (date.today() - timedelta(days=13)).isoformat()

    weight_rows = conn.execute(
        "SELECT date, weight_kg FROM weight_entries WHERE date >= ? ORDER BY date",
        (since,)
    ).fetchall()

    study_rows = conn.execute(
        "SELECT date, study_hours FROM daily_stats WHERE date >= ? ORDER BY date",
        (since,)
    ).fetchall()

    calorie_rows = conn.execute("""
        SELECT date, SUM(calories) AS calories
        FROM food_entries WHERE date >= ?
        GROUP BY date ORDER BY date
    """, (since,)).fetchall()

    expense_rows = conn.execute("""
        SELECT date, SUM(amount) AS total
        FROM expenses WHERE date >= ? AND type = 'expense'
        GROUP BY date ORDER BY date
    """, (since,)).fetchall()
    conn.close()

    charts = {
        "weight": {"labels": [r["date"] for r in weight_rows],
                   "values": [r["weight_kg"] for r in weight_rows]},
        "study": {"labels": [r["date"] for r in study_rows],
                  "values": [r["study_hours"] for r in study_rows]},
        "calories": {"labels": [r["date"] for r in calorie_rows],
                     "values": [r["calories"] for r in calorie_rows]},
        "expenses": {"labels": [r["date"] for r in expense_rows],
                     "values": [r["total"] for r in expense_rows]},
    }

    return render_template(
        "dashboard.html",
        today=day,
        nutrition=nutrition,
        settings=settings,
        stats=stats,
        weight=weight,
        money_today=money_today,
        money_month=money_month,
        net_month=net_month,
        top_category=top_category,
        charts=charts,
    )


# ---------------------------------------------------------------------------
# DIET
# ---------------------------------------------------------------------------

@app.route("/diet")
def diet():
    day = request.args.get("date", today_str())
    settings = get_settings()
    nutrition = get_daily_nutrition_totals(day)

    conn = database.get_connection()
    entries = conn.execute(
        "SELECT * FROM food_entries WHERE date = ? ORDER BY id", (day,)
    ).fetchall()
    conn.close()

    # Raggruppa le voci per pasto, mantenendo l'ordine definito in MEALS.
    entries_by_meal = {meal: [] for meal in MEALS}
    for e in entries:
        entries_by_meal.setdefault(e["meal"], []).append(e)

    return render_template(
        "diet.html",
        day=day,
        meals=MEALS,
        entries_by_meal=entries_by_meal,
        nutrition=nutrition,
        settings=settings,
    )


@app.route("/diet/add", methods=["POST"])
def add_food():
    conn = database.get_connection()
    conn.execute("""
        INSERT INTO food_entries (date, meal, food_name, quantity, calories, protein, carbs, fats)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        request.form["date"],
        request.form["meal"],
        request.form["food_name"],
        request.form.get("quantity", ""),
        float(request.form.get("calories") or 0),
        float(request.form.get("protein") or 0),
        float(request.form.get("carbs") or 0),
        float(request.form.get("fats") or 0),
    ))
    conn.commit()
    conn.close()
    return redirect(url_for("diet", date=request.form["date"]))


@app.route("/diet/delete/<int:entry_id>", methods=["POST"])
def delete_food(entry_id):
    day = request.form.get("date", today_str())
    conn = database.get_connection()
    conn.execute("DELETE FROM food_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("diet", date=day))


@app.route("/weight")
def weight_page():
    conn = database.get_connection()
    entries = conn.execute(
        "SELECT * FROM weight_entries ORDER BY date DESC"
    ).fetchall()
    conn.close()
    # Convertito in dict così il template può passarlo a |tojson per il grafico.
    entries = [dict(r) for r in entries]
    return render_template("weight.html", entries=entries, today=today_str())


@app.route("/weight/add", methods=["POST"])
def add_weight():
    conn = database.get_connection()
    # INSERT OR REPLACE: un solo peso per giorno, se rifai l'inserimento
    # per la stessa data aggiorna invece di duplicare.
    conn.execute("""
        INSERT INTO weight_entries (date, weight_kg)
        VALUES (?, ?)
        ON CONFLICT(date) DO UPDATE SET weight_kg = excluded.weight_kg
    """, (request.form["date"], float(request.form["weight_kg"])))
    conn.commit()
    conn.close()
    return redirect(url_for("weight_page"))


@app.route("/weight/delete/<int:entry_id>", methods=["POST"])
def delete_weight(entry_id):
    conn = database.get_connection()
    conn.execute("DELETE FROM weight_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("weight_page"))


# ---------------------------------------------------------------------------
# MONEY
# ---------------------------------------------------------------------------

@app.route("/money")
def money():
    settings = get_settings()
    day = today_str()
    year_month = day[:7]
    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()

    conn = database.get_connection()

    total_today = get_daily_expense_total(day)

    total_week = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date >= ? AND type = 'expense'",
        (week_start,)
    ).fetchone()["total"]

    total_month = get_month_expense_total(year_month)
    income_month = get_month_income_total(year_month)
    net_month = income_month - total_month

    total_all = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE type = 'expense'"
    ).fetchone()["total"]

    income_all = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE type = 'income'"
    ).fetchone()["total"]

    by_category = conn.execute("""
        SELECT category, SUM(amount) AS total
        FROM expenses WHERE date LIKE ? AND type = 'expense'
        GROUP BY category ORDER BY total DESC
    """, (year_month + "%",)).fetchall()
    by_category = [dict(r) for r in by_category]

    # Filtri opzionali per la lista dei movimenti: mese, categoria e tipo
    # (spesa/entrata/tutti). Il filtro categoria mostra sia le categorie di
    # spesa sia quelle di entrata, il template le distingue visivamente.
    filter_category = request.args.get("category", "")
    filter_month = request.args.get("month", year_month)
    filter_type = request.args.get("type", "")

    query = "SELECT * FROM expenses WHERE date LIKE ?"
    params = [filter_month + "%"]
    if filter_category:
        query += " AND category = ?"
        params.append(filter_category)
    if filter_type:
        query += " AND type = ?"
        params.append(filter_type)
    query += " ORDER BY date DESC, id DESC"

    movements = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "money.html",
        settings=settings,
        expense_categories=EXPENSE_CATEGORIES,
        income_categories=INCOME_CATEGORIES,
        total_today=total_today,
        total_week=total_week,
        total_month=total_month,
        income_month=income_month,
        net_month=net_month,
        total_all=total_all,
        income_all=income_all,
        by_category=by_category,
        movements=movements,
        filter_category=filter_category,
        filter_month=filter_month,
        filter_type=filter_type,
        today=day,
    )


@app.route("/money/add", methods=["POST"])
def add_expense():
    movement_type = request.form.get("type", "expense")
    if movement_type not in ("expense", "income"):
        movement_type = "expense"

    conn = database.get_connection()
    conn.execute("""
        INSERT INTO expenses (date, amount, category, description, type)
        VALUES (?, ?, ?, ?, ?)
    """, (
        request.form["date"],
        float(request.form["amount"]),
        request.form["category"],
        request.form.get("description", ""),
        movement_type,
    ))
    conn.commit()
    conn.close()
    return redirect(url_for("money"))


@app.route("/money/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    conn = database.get_connection()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("money"))


# ---------------------------------------------------------------------------
# LIFE STATS
# ---------------------------------------------------------------------------

@app.route("/life-stats")
def life_stats():
    day = request.args.get("date", today_str())
    today_data = get_today_stats(day)

    conn = database.get_connection()
    since = (date.today() - timedelta(days=29)).isoformat()
    history = conn.execute(
        "SELECT * FROM daily_stats WHERE date >= ? ORDER BY date DESC",
        (since,)
    ).fetchall()
    conn.close()

    charts = {
        "labels": [r["date"] for r in reversed(history)],
        "sleep": [r["sleep_hours"] for r in reversed(history)],
        "study": [r["study_hours"] for r in reversed(history)],
        "reading": [r["reading_minutes"] for r in reversed(history)],
        "gym": [r["gym"] for r in reversed(history)],
    }

    return render_template(
        "life_stats.html",
        day=day,
        today_data=today_data,
        history=history,
        charts=charts,
    )


@app.route("/life-stats/add", methods=["POST"])
def add_life_stats():
    day = request.form["date"]

    def parse_float(field):
        val = request.form.get(field)
        return float(val) if val else None

    def parse_int(field):
        val = request.form.get(field)
        return int(val) if val else None

    conn = database.get_connection()
    conn.execute("""
        INSERT INTO daily_stats (date, sleep_hours, study_hours, reading_minutes, water_liters, gym, steps, mood)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            sleep_hours = excluded.sleep_hours,
            study_hours = excluded.study_hours,
            reading_minutes = excluded.reading_minutes,
            water_liters = excluded.water_liters,
            gym = excluded.gym,
            steps = excluded.steps,
            mood = excluded.mood
    """, (
        day,
        parse_float("sleep_hours"),
        parse_float("study_hours"),
        parse_float("reading_minutes"),
        parse_float("water_liters"),
        1 if request.form.get("gym") == "on" else 0,
        parse_int("steps"),
        parse_int("mood"),
    ))
    conn.commit()
    conn.close()
    return redirect(url_for("life_stats", date=day))


@app.route("/life-stats/delete/<date_str>", methods=["POST"])
def delete_life_stats(date_str):
    conn = database.get_connection()
    conn.execute("DELETE FROM daily_stats WHERE date = ?", (date_str,))
    conn.commit()
    conn.close()
    return redirect(url_for("life_stats"))


# ---------------------------------------------------------------------------
# UNIVERSITY (libretto esami + orario lezioni + proiezione voto di laurea)
# ---------------------------------------------------------------------------

@app.route("/university")
def university():
    uni_settings = get_university_settings()
    passed_exams = get_passed_exams()
    upcoming_exams = get_upcoming_exams()

    average = calculate_weighted_average(passed_exams)
    total_cfu_done = sum(e["cfu"] for e in passed_exams) if passed_exams else 0
    cfu_remaining = max(uni_settings["total_cfu_required"] - total_cfu_done, 0)

    # Quanto manca all'obiettivo di media: ha senso solo se esiste già
    # una media reale (almeno un esame superato) E se l'utente ha
    # impostato un obiettivo. Altrimenti mostriamo "—" invece di un
    # numero fuorviante (es. non diciamo "ti mancano 28 punti" partendo da 0).
    target_average = uni_settings["target_average"]
    average_gap = None
    if average is not None and target_average is not None:
        average_gap = round(target_average - average, 2)

    graduation_projection = calculate_graduation_projection(average, uni_settings)

    schedule = get_weekly_schedule()

    return render_template(
        "university.html",
        uni_settings=uni_settings,
        passed_exams=passed_exams,
        upcoming_exams=upcoming_exams,
        average=average,
        target_average=target_average,
        average_gap=average_gap,
        total_cfu_done=total_cfu_done,
        cfu_remaining=cfu_remaining,
        graduation_projection=graduation_projection,
        schedule=schedule,
        weekdays=WEEKDAYS_IT,
        today=today_str(),
    )


@app.route("/university/exam/add", methods=["POST"])
def add_exam():
    """
    Aggiunge un esame. Se viene fornito un voto, lo status è 'passed'
    (esame superato); altrimenti resta 'planned' (data prevista, in attesa).
    """
    grade_raw = request.form.get("grade", "").strip()
    honors = 1 if request.form.get("honors") == "on" else 0
    status = "passed" if grade_raw else "planned"

    conn = database.get_connection()
    conn.execute("""
        INSERT INTO exams (name, cfu, status, exam_date, grade, honors, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        request.form["name"],
        float(request.form["cfu"]),
        status,
        request.form.get("exam_date") or None,
        int(grade_raw) if grade_raw else None,
        honors,
        request.form.get("notes", ""),
    ))
    conn.commit()
    conn.close()
    return redirect(url_for("university"))


@app.route("/university/exam/delete/<int:exam_id>", methods=["POST"])
def delete_exam(exam_id):
    conn = database.get_connection()
    conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("university"))


@app.route("/university/schedule/add", methods=["POST"])
def add_schedule_slot():
    conn = database.get_connection()
    conn.execute("""
        INSERT INTO class_schedule (course_name, day_of_week, start_time, end_time, location)
        VALUES (?, ?, ?, ?, ?)
    """, (
        request.form["course_name"],
        int(request.form["day_of_week"]),
        request.form["start_time"],
        request.form["end_time"],
        request.form.get("location", ""),
    ))
    conn.commit()
    conn.close()
    return redirect(url_for("university"))


@app.route("/university/schedule/delete/<int:slot_id>", methods=["POST"])
def delete_schedule_slot(slot_id):
    conn = database.get_connection()
    conn.execute("DELETE FROM class_schedule WHERE id = ?", (slot_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("university"))


@app.route("/university/settings/update", methods=["POST"])
def update_university_settings():
    target_raw = request.form.get("target_average", "").strip()

    conn = database.get_connection()
    conn.execute("""
        UPDATE university_settings
        SET target_average = ?, total_cfu_required = ?, thesis_points = ?, bonus_points = ?
        WHERE id = 1
    """, (
        float(target_raw) if target_raw else None,
        float(request.form["total_cfu_required"]),
        float(request.form.get("thesis_points") or 0),
        float(request.form.get("bonus_points") or 0),
    ))
    conn.commit()
    conn.close()
    return redirect(url_for("university"))


# ---------------------------------------------------------------------------
# HISTORY (vista unificata, utile per revisione generale)
# ---------------------------------------------------------------------------

@app.route("/history")
def history():
    conn = database.get_connection()
    food = conn.execute(
        "SELECT * FROM food_entries ORDER BY date DESC, id DESC LIMIT 50"
    ).fetchall()
    expenses = conn.execute(
        "SELECT * FROM expenses ORDER BY date DESC, id DESC LIMIT 50"
    ).fetchall()
    stats = conn.execute(
        "SELECT * FROM daily_stats ORDER BY date DESC LIMIT 50"
    ).fetchall()
    weights = conn.execute(
        "SELECT * FROM weight_entries ORDER BY date DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return render_template(
        "history.html", food=food, expenses=expenses, stats=stats, weights=weights
    )


# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------

@app.route("/settings")
def settings_page():
    return render_template("settings.html", settings=get_settings())


@app.route("/settings/update", methods=["POST"])
def update_settings():
    conn = database.get_connection()
    conn.execute("""
        UPDATE settings
        SET calorie_target = ?, protein_target = ?, currency = ?
        WHERE id = 1
    """, (
        float(request.form["calorie_target"]),
        float(request.form["protein_target"]),
        request.form["currency"],
    ))
    conn.commit()
    conn.close()
    return redirect(url_for("settings_page"))


# ---------------------------------------------------------------------------
# Avvio
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    database.init_db()
    app.run(debug=True)
else:
    # Assicura che il DB esista anche se l'app viene avviata con `flask run`.
    database.init_db()
