import sqlite3
import json
from pathlib import Path

def export_db():
    db_path = Path("backend/studio.db")
    if not db_path.exists():
        print("studio.db not found")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all tables
    tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    
    data = {}
    for table in tables:
        rows = cur.execute(f"SELECT * FROM {table}").fetchall()
        data[table] = [dict(r) for r in rows]

    # Save JSON
    json_path = Path("backend/studio_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Exported JSON to {json_path}")

    # Generate HTML Viewer
    sessions = data.get("generation_sessions", [])
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Visor de Base de Datos - AgentIA Studio</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 24px;
        }}
        h1 {{
            color: #38bdf8;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 24px;
            margin-bottom: 8px;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 9999px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-completed {{ background: #065f46; color: #34d399; }}
        .badge-queued {{ background: #854d0e; color: #fde047; }}
        .badge-running {{ background: #1e40af; color: #93c5fd; }}
        .card {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            font-size: 14px;
        }}
        th, td {{
            text-align: left;
            padding: 12px 14px;
            border-bottom: 1px solid #334155;
        }}
        th {{
            background: #0f172a;
            color: #94a3b8;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.05em;
        }}
        tr:hover td {{
            background: #273549;
        }}
        code {{
            background: #0f172a;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            color: #38bdf8;
            font-size: 12px;
        }}
        .highlight {{
            border: 2px solid #38bdf8 !important;
            background: rgba(56, 189, 248, 0.05);
        }}
        .subtitle {{
            color: #94a3b8;
            margin-bottom: 24px;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <h1>🗄️ Visor de Base de Datos (studio.db)</h1>
    <div class="subtitle">Registros actuales en <code>backend/studio.db</code> • Tabla: <strong>generation_sessions</strong></div>

    <div class="card">
        <table>
            <thead>
                <tr>
                    <th>Microservicio</th>
                    <th>Estado</th>
                    <th>Fase</th>
                    <th>ID de Sesión</th>
                    <th>Modo</th>
                    <th>Fecha Creación</th>
                </tr>
            </thead>
            <tbody>
    """
    for s in sessions:
        is_ceviche = s.get("spec_name") == "ceviche"
        status_cls = "badge-completed" if s.get("status") == "COMPLETED" else "badge-queued"
        row_cls = "class='highlight'" if is_ceviche else ""
        html += f"""
                <tr {row_cls}>
                    <td><strong>{'⚡ ' if is_ceviche else ''}{s.get('spec_name')}</strong></td>
                    <td><span class="badge {status_cls}">{s.get('status')}</span></td>
                    <td><code>{s.get('phase')}</code></td>
                    <td><code>{s.get('id')}</code></td>
                    <td>{s.get('lifecycle_mode')}</td>
                    <td>{s.get('created_at')}</td>
                </tr>
        """
    html += """
            </tbody>
        </table>
    </div>
</body>
</html>
    """

    html_path = Path("backend/view_database.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Exported HTML viewer to {html_path}")

if __name__ == "__main__":
    export_db()
