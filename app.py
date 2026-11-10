import os
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, abort

app = Flask(__name__)

APP_SECRET = os.environ.get("APP_SECRET", "MeinSuperGeheimerSchluessel2026")
DATABASE_URL = os.environ.get("DATABASE_URL")

WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

def get_db_connection():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL Umgebungsvariable ist nicht gesetzt!")
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL:
        return
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS auftraege (
                    id VARCHAR(16) PRIMARY KEY,
                    datum VARCHAR(10) NOT NULL,
                    kunde TEXT NOT NULL,
                    telefon TEXT,
                    aufgabe TEXT,
                    material TEXT,
                    bezahlt BOOLEAN DEFAULT FALSE
                );
            """)
            conn.commit()

# --- SICHERHEITS-PRÜFUNG ---
@app.before_request
def pruefe_zugang():
    if request.path == "/ping":
        return None

    token_in_url = request.args.get("login")
    if token_in_url == APP_SECRET:
        return None

    gespeichertes_cookie = request.cookies.get("handwerker_auth")
    if gespeichertes_cookie == APP_SECRET:
        return None

    abort(403, description="Zugriff verweigert. Bitte öffne die App einmalig mit deinem geheimen Schlüssel.")

@app.after_request
def setze_auth_cookie(response):
    token_in_url = request.args.get("login")
    if token_in_url == APP_SECRET:
        response.set_cookie("handwerker_auth", APP_SECRET, max_age=63072000, httponly=True, samesite="Lax")
    return response

@app.route("/ping")
def ping():
    return "OK", 200

# --- DATENBANK-FUNKTIONEN ---
def lade_daten():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM auftraege ORDER BY datum ASC;")
                return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print("DB Fehler beim Laden:", e)
        return []

def erstelle_tages_kopf(ziel_tag, heute):
    tage_diff = (ziel_tag - heute).days
    wochentag = WOCHENTAGE[ziel_tag.weekday()]
    datum_str = ziel_tag.strftime("%d.%m.%Y")
    
    if tage_diff == 0:
        return f"🔥 HEUTE – {wochentag}, {datum_str}"
    elif tage_diff == 1:
        return f"⚡ MORGEN – {wochentag}, {datum_str}"
    elif tage_diff == -1:
        return f"Gestern – {wochentag}, {datum_str}"
    else:
        return f"{wochentag}, {datum_str}"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Handwerker Planer</title>
    <style>
        :root {
            --bg: #0b1120;
            --card-bg: #1e293b;
            --primary: #3b82f6;
            --success-border: #10b981;
            --danger-border: #ef4444;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        html { scroll-behavior: smooth; }
        body { background-color: var(--bg); color: var(--text); padding: 12px; padding-bottom: 90px; }
        
        #top { padding-top: 4px; }
        
        .header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
        .header h1 { font-size: 1.3rem; font-weight: 800; color: #fff; }
        
        .filter-container {
            position: sticky; top: 0; z-index: 100; background: var(--bg); padding: 8px 0; margin-bottom: 14px;
        }
        .zeit-filter {
            display: flex; gap: 6px; background: #1e293b; padding: 5px; border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3); border: 1px solid #334155;
        }
        .zeit-filter a {
            flex: 1; text-align: center; text-decoration: none; padding: 9px 2px; font-size: 0.8rem; font-weight: 700;
            color: var(--text-muted); border-radius: 8px; transition: background 0.2s;
        }
        .zeit-filter a.active { background: var(--primary); color: #fff; }

        .overdue-section {
            background: rgba(185, 28, 28, 0.15); border: 2px solid #ef4444; border-radius: 14px; padding: 14px; margin-bottom: 20px;
        }
        .overdue-title { color: #f87171; font-size: 1rem; font-weight: 800; margin-bottom: 10px; }

        .card-form { 
            background: var(--card-bg); border-radius: 14px; padding: 16px; margin-bottom: 22px; 
            border: 1px solid #334155; box-shadow: 0 4px 14px rgba(0,0,0,0.4);
        }
        .card-form h2 { font-size: 1.15rem; margin-bottom: 12px; color: var(--accent); }
        .form-group { margin-bottom: 10px; }
        label { display: block; font-size: 0.8rem; font-weight: 700; margin-bottom: 4px; color: var(--text-muted); }
        input[type="text"], input[type="date"], input[type="tel"] {
            width: 100%; padding: 13px; border: 1px solid #475569; background: #0b1120; color: #fff;
            border-radius: 9px; font-size: 1.05rem;
        }
        .checkbox-group { display: flex; align-items: center; gap: 10px; margin: 14px 0; font-size: 1rem; font-weight: 600; }
        .checkbox-group input { width: 22px; height: 22px; accent-color: #10b981; }
        
        .btn-submit {
            width: 100%; background: var(--primary); color: white; border: none; padding: 15px;
            border-radius: 9px; font-size: 1.1rem; font-weight: 700; cursor: pointer;
        }
        .btn-cancel {
            display: block; text-align: center; margin-top: 10px; color: var(--text-muted); text-decoration: none; font-size: 0.9rem;
        }

        .day-group { margin-bottom: 18px; }
        .day-header {
            font-size: 1.05rem; font-weight: 800; padding: 8px 12px; background: #1e293b;
            color: #f1f5f9; border-radius: 9px; margin-bottom: 8px; border-left: 5px solid var(--primary);
            display: flex; justify-content: space-between; align-items: center;
        }
        .day-header.heute { border-left-color: #f59e0b; background: #283548; }
        .day-header.vergangen { border-left-color: #64748b; background: #1a2234; color: #94a3b8; }

        .free-day-card {
            border: 2px dashed #334155; border-radius: 12px; padding: 14px; text-align: center;
            background: rgba(30, 41, 59, 0.4); margin-bottom: 8px;
        }
        .free-day-text { font-size: 0.95rem; font-weight: 700; color: #10b981; margin-bottom: 6px; }
        .btn-book-free {
            display: inline-block; background: #334155; color: #93c5fd; text-decoration: none;
            padding: 8px 16px; border-radius: 7px; font-size: 0.85rem; font-weight: 700;
        }

        .order-card {
            background: var(--card-bg); border-radius: 14px; padding: 16px; margin-bottom: 10px;
            border: 2px solid #334155; box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }
        .order-card.paid { border-color: var(--success-border); background: linear-gradient(180deg, #1e293b 0%, #064e3b25 100%); }
        .order-card.unpaid { border-color: var(--danger-border); background: linear-gradient(180deg, #1e293b 0%, #450a0a25 100%); }
        
        .order-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .customer-name { font-size: 1.25rem; font-weight: 800; color: #fff; }
        
        .status-dot { font-size: 0.9rem; font-weight: 700; padding: 4px 10px; border-radius: 20px; }
        .status-dot.paid { background: #065f46; color: #34d399; border: 1px solid #10b981; }
        .status-dot.unpaid { background: #7f1d1d; color: #f87171; border: 1px solid #ef4444; }

        .block-info {
            background: #0b1120; border-radius: 9px; padding: 12px; margin-bottom: 8px; border: 1px solid #334155;
        }
        .block-title { font-size: 0.75rem; font-weight: 800; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px; }
        .block-content { font-size: 1.05rem; font-weight: 600; color: #e2e8f0; line-height: 1.35; }
        .block-material { color: #facc15; font-weight: 700; }

        .phone-button {
            display: flex; align-items: center; justify-content: center; gap: 8px;
            width: 100%; background: #2563eb; color: #fff; padding: 13px;
            border-radius: 9px; text-decoration: none; font-size: 1.05rem; font-weight: 700; margin: 10px 0;
        }

        .card-actions { display: flex; gap: 8px; margin-top: 12px; }
        .btn-act {
            flex: 1; padding: 11px; border-radius: 8px; font-weight: 700; font-size: 0.85rem;
            text-align: center; text-decoration: none; border: none; cursor: pointer;
        }
        .btn-toggle-status { background: #334155; color: #fff; border: 1px solid #475569; }
        .btn-edit { background: #f59e0b; color: #000; }
        .btn-del { background: #450a0a; color: #f87171; border: 1px solid #7f1d1d; }
    </style>
</head>
<body>

    <div id="top"></div>

    <div class="header">
        <h1>🛠️ Handwerker Planer</h1>
        <a href="#formular" style="color: var(--primary); text-decoration: none; font-weight: 700; font-size: 0.95rem;">+ Neuer Termin</a>
    </div>

    <div class="filter-container">
        <div class="zeit-filter">
            <a href="/?modus=archiv#top" class="{{ 'active' if modus == 'archiv' else '' }}">📁 Archiv</a>
            <a href="/?wochen=2&modus=zukunft#top" class="{{ 'active' if modus == 'zukunft' and ausgewaehlte_wochen == 2 else '' }}">2 Wo.</a>
            <a href="/?wochen=4&modus=zukunft#top" class="{{ 'active' if modus == 'zukunft' and ausgewaehlte_wochen == 4 else '' }}">4 Wo.</a>
            <a href="/?wochen=8&modus=zukunft#top" class="{{ 'active' if modus == 'zukunft' and ausgewaehlte_wochen == 8 else '' }}">8 Wo.</a>
            <a href="/?wochen=12&modus=zukunft#top" class="{{ 'active' if modus == 'zukunft' and ausgewaehlte_wochen == 12 else '' }}">12 Wo.</a>
        </div>
    </div>

    {% if ueberfaellig and modus != 'archiv' %}
    <div class="overdue-section">
        <div class="overdue-title">
            ⚠️ Achtung: {{ ueberfaellig|length }} unbezahlte Aufträge aus vergangenen Tagen!
        </div>
        {% for e in ueberfaellig %}
        <div class="order-card unpaid" style="margin-bottom: 8px;">
            <div class="order-top">
                <div>
                    <div class="customer-name">{{ e.kunde }}</div>
                    <div style="font-size: 0.85rem; color: #f87171; font-weight: 700;">📅 Fällig war am: {{ e.datum }}</div>
                </div>
                <div class="status-dot unpaid">🔴 Offen</div>
            </div>

            {% if e.telefon %}
            <a class="phone-button" href="tel:{{ e.telefon }}">📞 Nachhaken: {{ e.telefon }}</a>
            {% endif %}

            <div class="card-actions">
                <a href="/toggle/{{ e.id }}?wochen={{ ausgewaehlte_wochen }}&modus={{ modus }}" class="btn-act btn-toggle-status">
                    Geld ist da! (🟢)
                </a>
                <a href="/bearbeiten/{{ e.id }}?wochen={{ ausgewaehlte_wochen }}&modus={{ modus }}#formular" class="btn-act btn-edit">
                    ✏️
                </a>
            </div>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    <div class="calendar-list">
        {% for tag in tage_liste %}
            <div class="day-group">
                <div class="day-header {{ 'heute' if tag.ist_heute else ('vergangen' if tag.ist_vergangenheit else '') }}">
                    <span>{{ tag.titel }}</span>
                    {% if tag.eintraege|length > 0 %}
                        <span style="font-size: 0.8rem; background: var(--primary); padding: 2px 8px; border-radius: 12px;">{{ tag.eintraege|length }}</span>
                    {% endif %}
                </div>

                {% if tag.eintraege|length == 0 %}
                    <div class="free-day-card">
                        <div class="free-day-text">🟢 FREI – Keine Termine</div>
                        <a href="/?vorauswahl_datum={{ tag.iso }}&wochen={{ ausgewaehlte_wochen }}&modus={{ modus }}#formular" class="btn-book-free">
                            + Termin planen
                        </a>
                    </div>
                {% else %}
                    {% for e in tag.eintraege %}
                    <div class="order-card {{ 'paid' if e.bezahlt else 'unpaid' }}">
                        <div class="order-top">
                            <div class="customer-name">{{ e.kunde }}</div>
                            <div class="status-dot {{ 'paid' if e.bezahlt else 'unpaid' }}">
                                {{ '🟢 Bezahlt' if e.bezahlt else '🔴 Offen' }}
                            </div>
                        </div>

                        {% if e.telefon %}
                        <a class="phone-button" href="tel:{{ e.telefon }}">
                            📞 {{ e.telefon }} anrufen
                        </a>
                        {% endif %}

                        <div class="block-info">
                            <div class="block-title">Tätigkeit</div>
                            <div class="block-content">{{ e.aufgabe if e.aufgabe else 'Keine Beschreibung' }}</div>
                        </div>

                        <div class="block-info">
                            <div class="block-title">Material</div>
                            <div class="block-content block-material">{{ e.material if e.material else '–' }}</div>
                        </div>

                        <div class="card-actions">
                            <a href="/toggle/{{ e.id }}?wochen={{ ausgewaehlte_wochen }}&modus={{ modus }}" class="btn-act btn-toggle-status">
                                {{ 'Auf 🔴 setzen' if e.bezahlt else 'Auf 🟢 setzen' }}
                            </a>
                            <a href="/bearbeiten/{{ e.id }}?wochen={{ ausgewaehlte_wochen }}&modus={{ modus }}#formular" class="btn-act btn-edit">
                                ✏️ Ändern
                            </a>
                            <a href="/loeschen/{{ e.id }}?wochen={{ ausgewaehlte_wochen }}&modus={{ modus }}" class="btn-act btn-del" onclick="return confirm('Termin für {{ e.kunde }} wirklich löschen?');">
                                🗑️
                            </a>
                        </div>
                    </div>
                    {% endfor %}
                {% endif %}
            </div>
        {% endfor %}
    </div>

    <div class="card-form" id="formular">
        <h2>{{ '✏️ Termin bearbeiten' if edit_eintrag else '➕ Termin eintragen' }}</h2>
        <form action="{{ '/speichern/' + edit_eintrag.id if edit_eintrag else '/neu' }}" method="POST">
            <input type="hidden" name="wochen" value="{{ ausgewaehlte_wochen }}">
            <input type="hidden" name="modus" value="{{ modus }}">
            
            <div class="form-group">
                <label>Datum des Termins</label>
                <input type="date" name="datum" value="{{ edit_eintrag.datum if edit_eintrag else vorauswahl_datum }}" required>
            </div>
            
            <div class="form-group">
                <label>Kundenname</label>
                <input type="text" name="kunde" value="{{ edit_eintrag.kunde if edit_eintrag else '' }}" placeholder="z.B. Müller, Hauptstr. 4" required>
            </div>
            
            <div class="form-group">
                <label>Telefonnummer</label>
                <input type="tel" name="telefon" value="{{ edit_eintrag.telefon if edit_eintrag else '' }}" placeholder="0171 1234567">
            </div>
            
            <div class="form-group">
                <label>Tätigkeit</label>
                <input type="text" name="aufgabe" value="{{ edit_eintrag.aufgabe if edit_eintrag else '' }}" placeholder="z.B. Heizungswartung">
            </div>
            
            <div class="form-group">
                <label>Material</label>
                <input type="text" name="material" value="{{ edit_eintrag.material if edit_eintrag else '' }}" placeholder="z.B. Dichtungssatz">
            </div>
            
            <div class="checkbox-group">
                <input type="checkbox" id="bezahlt" name="bezahlt" {{ 'checked' if edit_eintrag and edit_eintrag.bezahlt else '' }}>
                <label for="bezahlt" style="margin:0; color:inherit;">Rechnung bezahlt? (🟢)</label>
            </div>
            
            <button type="submit" class="btn-submit">
                {{ 'Änderungen speichern' if edit_eintrag else '+ Termin speichern' }}
            </button>

            {% if edit_eintrag %}
                <a href="/?wochen={{ ausgewaehlte_wochen }}&modus={{ modus }}#top" class="btn-cancel">Abbrechen</a>
            {% endif %}
        </form>
    </div>

    <script>
        if (window.location.hash === '#top') {
            window.scrollTo(0, 0);
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    daten = lade_daten()
    wochen = request.args.get("wochen", default=2, type=int)
    modus = request.args.get("modus", default="zukunft", type=str)
    vorauswahl_datum = request.args.get("vorauswahl_datum", default="", type=str)

    heute = date.today()
    heute_iso = heute.strftime("%Y-%m-%d")

    ueberfaellig = [e for e in daten if e.get("datum", "") < heute_iso and not e.get("bezahlt", False)]
    ueberfaellig.sort(key=lambda x: x.get("datum", ""), reverse=True)

    tage_liste = []
    termine_map = {}
    for e in daten:
        d = e.get("datum", "")
        if d not in termine_map:
            termine_map[d] = []
        termine_map[d].append(e)

    if modus == "archiv":
        vergangene_tage = [d for d in sorted(termine_map.keys()) if d < heute_iso]
        vergangene_tage.sort(reverse=True)
        for d in vergangene_tage:
            try:
                z_tag = datetime.strptime(d, "%Y-%m-%d").date()
                tage_liste.append({
                    "iso": d,
                    "titel": erstelle_tages_kopf(z_tag, heute),
                    "ist_heute": False,
                    "ist_vergangenheit": True,
                    "eintraege": termine_map.get(d, [])
                })
            except Exception:
                pass
    else:
        tage_gesamt = wochen * 7
        for i in range(tage_gesamt):
            aktueller_tag = heute + timedelta(days=i)
            iso_str = aktueller_tag.strftime("%Y-%m-%d")
            tage_liste.append({
                "iso": iso_str,
                "titel": erstelle_tages_kopf(aktueller_tag, heute),
                "ist_heute": (i == 0),
                "ist_vergangenheit": False,
                "eintraege": termine_map.get(iso_str, [])
            })

    return render_template_string(
        HTML_TEMPLATE,
        tage_liste=tage_liste,
        ausgewaehlte_wochen=wochen,
        modus=modus,
        ueberfaellig=ueberfaellig,
        vorauswahl_datum=vorauswahl_datum,
        edit_eintrag=None
    )

@app.route("/bearbeiten/<eintrag_id>")
def bearbeiten(eintrag_id):
    daten = lade_daten()
    wochen = request.args.get("wochen", default=2, type=int)
    modus = request.args.get("modus", default="zukunft", type=str)
    edit_eintrag = next((e for e in daten if e.get("id") == eintrag_id), None)

    heute = date.today()
    heute_iso = heute.strftime("%Y-%m-%d")

    ueberfaellig = [e for e in daten if e.get("datum", "") < heute_iso and not e.get("bezahlt", False)]
    ueberfaellig.sort(key=lambda x: x.get("datum", ""), reverse=True)

    tage_liste = []
    termine_map = {}
    for e in daten:
        d = e.get("datum", "")
        if d not in termine_map:
            termine_map[d] = []
        termine_map[d].append(e)

    if modus == "archiv":
        vergangene_tage = [d for d in sorted(termine_map.keys()) if d < heute_iso]
        vergangene_tage.sort(reverse=True)
        for d in vergangene_tage:
            try:
                z_tag = datetime.strptime(d, "%Y-%m-%d").date()
                tage_liste.append({
                    "iso": d,
                    "titel": erstelle_tages_kopf(z_tag, heute),
                    "ist_heute": False,
                    "ist_vergangenheit": True,
                    "eintraege": termine_map.get(d, [])
                })
            except Exception:
                pass
    else:
        tage_gesamt = wochen * 7
        for i in range(tage_gesamt):
            aktueller_tag = heute + timedelta(days=i)
            iso_str = aktueller_tag.strftime("%Y-%m-%d")
            tage_liste.append({
                "iso": iso_str,
                "titel": erstelle_tages_kopf(aktueller_tag, heute),
                "ist_heute": (i == 0),
                "ist_vergangenheit": False,
                "eintraege": termine_map.get(iso_str, [])
            })

    return render_template_string(
        HTML_TEMPLATE,
        tage_liste=tage_liste,
        ausgewaehlte_wochen=wochen,
        modus=modus,
        ueberfaellig=ueberfaellig,
        vorauswahl_datum="",
        edit_eintrag=edit_eintrag
    )

@app.route("/neu", methods=["POST"])
def neu():
    wochen = request.form.get("wochen", default="2")
    modus = request.form.get("modus", default="zukunft")
    e_id = str(uuid.uuid4())[:8]
    datum = request.form.get("datum", "")
    kunde = request.form.get("kunde", "")
    telefon = request.form.get("telefon", "")
    aufgabe = request.form.get("aufgabe", "")
    material = request.form.get("material", "")
    bezahlt = True if request.form.get("bezahlt") else False

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO auftraege (id, datum, kunde, telefon, aufgabe, material, bezahlt)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (e_id, datum, kunde, telefon, aufgabe, material, bezahlt))
            conn.commit()

    return redirect(url_for("index", wochen=wochen, modus=modus) + "#top")

@app.route("/speichern/<eintrag_id>", methods=["POST"])
def speichern(eintrag_id):
    wochen = request.form.get("wochen", default="2")
    modus = request.form.get("modus", default="zukunft")
    datum = request.form.get("datum", "")
    kunde = request.form.get("kunde", "")
    telefon = request.form.get("telefon", "")
    aufgabe = request.form.get("aufgabe", "")
    material = request.form.get("material", "")
    bezahlt = True if request.form.get("bezahlt") else False

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE auftraege
                SET datum=%s, kunde=%s, telefon=%s, aufgabe=%s, material=%s, bezahlt=%s
                WHERE id=%s;
            """, (datum, kunde, telefon, aufgabe, material, bezahlt, eintrag_id))
            conn.commit()

    return redirect(url_for("index", wochen=wochen, modus=modus) + "#top")

@app.route("/toggle/<eintrag_id>")
def toggle(eintrag_id):
    wochen = request.args.get("wochen", default=2, type=int)
    modus = request.args.get("modus", default="zukunft", type=str)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE auftraege
                SET bezahlt = NOT bezahlt
                WHERE id = %s;
            """, (eintrag_id,))
            conn.commit()

    return redirect(url_for("index", wochen=wochen, modus=modus))

@app.route("/loeschen/<eintrag_id>")
def loeschen(eintrag_id):
    wochen = request.args.get("wochen", default=2, type=int)
    modus = request.args.get("modus", default="zukunft", type=str)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM auftraege WHERE id = %s;", (eintrag_id,))
            conn.commit()

    return redirect(url_for("index", wochen=wochen, modus=modus) + "#top")

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
