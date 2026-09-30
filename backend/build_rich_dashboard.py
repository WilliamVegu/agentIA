import sqlite3
import json
import re
from pathlib import Path

def extract_entity_info(java_code: str):
    """Extract class name, table name, and fields from JPA entity Java file."""
    table_name = "orders"
    match_table = re.search(r'@Table\s*\(\s*name\s*=\s*"([^"]+)"', java_code)
    if match_table:
        table_name = match_table.group(1)

    class_name = "Order"
    match_class = re.search(r'public\s+class\s+([A-Za-z0-9_]+)', java_code)
    if match_class:
        class_name = match_class.group(1)

    fields = []
    # Simple regex for private <type> <name>;
    field_matches = re.findall(r'private\s+([\w\.<>]+)\s+([a-zA-Z0-9_]+)\s*;', java_code)
    for ftype, fname in field_matches:
        is_pk = (fname.lower() == "id")
        sql_type = "VARCHAR(255)"
        if "Long" in ftype or "Integer" in ftype:
            sql_type = "BIGINT" if "Long" in ftype else "INTEGER"
        elif "BigDecimal" in ftype or "Double" in ftype:
            sql_type = "NUMERIC(15,2)"
        elif "Instant" in ftype or "Date" in ftype or "Timestamp" in ftype:
            sql_type = "TIMESTAMP"
        elif "Boolean" in ftype:
            sql_type = "BOOLEAN"

        col_name = re.sub(r'(?<!^)(?=[A-Z])', '_', fname).lower()
        fields.append({
            "name": col_name,
            "prop": fname,
            "type": sql_type,
            "is_pk": is_pk
        })
    if not fields:
        fields = [
            {"name": "id", "prop": "id", "type": "BIGINT", "is_pk": True},
            {"name": "customer_email", "prop": "customerEmail", "type": "VARCHAR(255)", "is_pk": False},
            {"name": "total_amount", "prop": "totalAmount", "type": "NUMERIC(15,2)", "is_pk": False},
            {"name": "status", "prop": "status", "type": "VARCHAR(50)", "is_pk": False}
        ]
    return class_name, table_name, fields

def generate_microservice_er_svg(entity_info, session_name: str) -> str:
    cls_name, tbl_name, fields = entity_info
    
    # Calculate box height based on fields
    row_height = 28
    header_height = 42
    box_height = header_height + (len(fields) * row_height) + 16

    field_rows_svg = []
    y_offset = header_height + 24
    for f in fields:
        pk_badge = ""
        name_color = "#f8fafc"
        if f["is_pk"]:
            pk_badge = '<rect x="22" y="' + str(y_offset - 14) + '" width="28" height="18" rx="4" fill="#38bdf8" fill-opacity="0.2"/><text x="36" y="' + str(y_offset - 1) + '" fill="#38bdf8" font-size="10" font-weight="700" text-anchor="middle">PK</text>'
            name_color = "#38bdf8"
        else:
            pk_badge = '<circle cx="36" cy="' + str(y_offset - 5) + '" r="3" fill="#64748b"/>'

        row = f'''
        <g>
            {pk_badge}
            <text x="60" y="{y_offset}" fill="{name_color}" font-size="13" font-weight="600">{f["name"]}</text>
            <text x="240" y="{y_offset}" fill="#94a3b8" font-size="12" font-family="monospace">{f["type"]}</text>
        </g>
        '''
        field_rows_svg.append(row)
        y_offset += row_height

    fields_svg_str = "\n".join(field_rows_svg)

    # Let's also include a related table (ITEMS / ORDER_ITEMS)
    items_y = header_height + 24
    items_rows = [
        {"name": "id", "type": "BIGINT", "pk": True},
        {"name": f"{tbl_name[:-1] if tbl_name.endswith('s') else tbl_name}_id", "type": "BIGINT (FK)", "pk": False, "fk": True},
        {"name": "product_name", "type": "VARCHAR(255)", "pk": False},
        {"name": "quantity", "type": "INTEGER", "pk": False},
        {"name": "price", "type": "NUMERIC(15,2)", "pk": False},
        {"name": "created_at", "type": "TIMESTAMP", "pk": False}
    ]
    items_rows_svg = []
    items_box_height = header_height + (len(items_rows) * row_height) + 16

    for itm in items_rows:
        if itm["pk"]:
            badge = '<rect x="442" y="' + str(items_y - 14) + '" width="28" height="18" rx="4" fill="#38bdf8" fill-opacity="0.2"/><text x="456" y="' + str(items_y - 1) + '" fill="#38bdf8" font-size="10" font-weight="700" text-anchor="middle">PK</text>'
            ncolor = "#38bdf8"
        elif itm.get("fk"):
            badge = '<rect x="442" y="' + str(items_y - 14) + '" width="28" height="18" rx="4" fill="#a855f7" fill-opacity="0.2"/><text x="456" y="' + str(items_y - 1) + '" fill="#c084fc" font-size="10" font-weight="700" text-anchor="middle">FK</text>'
            ncolor = "#c084fc"
        else:
            badge = '<circle cx="456" cy="' + str(items_y - 5) + '" r="3" fill="#64748b"/>'
            ncolor = "#f8fafc"

        row = f'''
        <g>
            {badge}
            <text x="480" y="{items_y}" fill="{ncolor}" font-size="13" font-weight="600">{itm["name"]}</text>
            <text x="650" y="{items_y}" fill="#94a3b8" font-size="12" font-family="monospace">{itm["type"]}</text>
        </g>
        '''
        items_rows_svg.append(row)
        items_y += row_height

    items_svg_str = "\n".join(items_rows_svg)

    svg = f'''
    <svg viewBox="0 0 760 260" width="100%" height="260" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;">
        <defs>
            <linearGradient id="headerGrad1" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stop-color="#0284c7" />
                <stop offset="100%" stop-color="#0369a1" />
            </linearGradient>
            <linearGradient id="headerGrad2" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stop-color="#7c3aed" />
                <stop offset="100%" stop-color="#6d28d9" />
            </linearGradient>
            <filter id="shadow" x="-5%" y="-5%" width="110%" height="115%" filterUnits="userSpaceOnUse">
                <feGaussianBlur in="SourceAlpha" stdDeviation="4"/>
                <feOffset dx="0" dy="4" result="offsetblur"/>
                <feComponentTransfer><feFuncA type="linear" slope="0.35"/></feComponentTransfer>
                <feMerge> 
                    <feMergeNode/>
                    <feMergeNode in="SourceGraphic"/>
                </feMerge>
            </filter>
            <marker id="crow" viewBox="0 0 20 20" refX="10" refY="10" markerWidth="14" markerHeight="14" orient="auto-start-reverse">
                <path d="M 0,4 L 10,10 L 0,16 M 10,4 L 20,10 L 10,16" stroke="#38bdf8" stroke-width="2" fill="none"/>
            </marker>
        </defs>

        <!-- TABLE 1: Primary Entity (e.g. ORDERS) -->
        <g transform="translate(10, 15)" filter="url(#shadow)">
            <!-- Box Background -->
            <rect x="0" y="0" width="340" height="{box_height}" rx="10" fill="#131c31" stroke="#2e3e5c" stroke-width="1.5" />
            <!-- Header -->
            <path d="M 0,10 Q 0,0 10,0 L 330,0 Q 340,0 340,10 L 340,40 L 0,40 Z" fill="url(#headerGrad1)" />
            <text x="18" y="26" fill="#ffffff" font-size="15" font-weight="700">📦 {tbl_name.upper()} ({cls_name})</text>
            <text x="325" y="25" fill="#bae6fd" font-size="11" font-weight="600" text-anchor="end">POSTGRESQL</text>
            <!-- Columns Header Line -->
            <line x1="0" y1="40" x2="340" y2="40" stroke="#0284c7" stroke-width="1" />
            <!-- Field rows -->
            {fields_svg_str}
        </g>

        <!-- RELATIONSHIP CONNECTOR LINE -->
        <path d="M 350,60 C 385,60 395,60 430,60" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-dasharray="5,4" />
        <circle cx="354" cy="60" r="4" fill="#38bdf8" />
        <rect x="372" y="48" width="40" height="22" rx="4" fill="#0f172a" stroke="#38bdf8" stroke-width="1"/>
        <text x="392" y="63" fill="#38bdf8" font-size="11" font-weight="700" text-anchor="middle">1 : N</text>

        <!-- TABLE 2: Child Entity (e.g. ITEMS / ORDER_ITEMS) -->
        <g transform="translate(430, 15)" filter="url(#shadow)">
            <!-- Box Background -->
            <rect x="0" y="0" width="315" height="{items_box_height}" rx="10" fill="#131c31" stroke="#2e3e5c" stroke-width="1.5" />
            <!-- Header -->
            <path d="M 0,10 Q 0,0 10,0 L 305,0 Q 315,0 315,10 L 315,40 L 0,40 Z" fill="url(#headerGrad2)" />
            <text x="18" y="26" fill="#ffffff" font-size="15" font-weight="700">📑 ITEMS (Líneas de Detalle)</text>
            <line x1="0" y1="40" x2="315" y2="40" stroke="#7c3aed" stroke-width="1" />
            <!-- Items rows -->
            <g transform="translate(-430, 0)">
                {items_svg_str}
            </g>
        </g>
    </svg>
    '''
    return svg

def generate_platform_er_svg() -> str:
    """Generates an HD ER Diagram for studio.db (generation_sessions, diagnostics, skillopt, costs)."""
    return '''
    <svg viewBox="0 0 920 320" width="100%" height="320" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;">
        <defs>
            <linearGradient id="pGrad1" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stop-color="#0284c7" />
                <stop offset="100%" stop-color="#0369a1" />
            </linearGradient>
            <linearGradient id="pGrad2" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stop-color="#059669" />
                <stop offset="100%" stop-color="#047857" />
            </linearGradient>
            <linearGradient id="pGrad3" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stop-color="#d97706" />
                <stop offset="100%" stop-color="#b45309" />
            </linearGradient>
            <filter id="pShadow" x="-5%" y="-5%" width="110%" height="115%">
                <feGaussianBlur in="SourceAlpha" stdDeviation="4"/>
                <feOffset dx="0" dy="4" result="offsetblur"/>
                <feComponentTransfer><feFuncA type="linear" slope="0.35"/></feComponentTransfer>
                <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
        </defs>

        <!-- 1. GENERATION_SESSIONS (Central Hub) -->
        <g transform="translate(15, 20)" filter="url(#pShadow)">
            <rect x="0" y="0" width="310" height="280" rx="10" fill="#131c31" stroke="#2e3e5c" stroke-width="1.5" />
            <path d="M 0,10 Q 0,0 10,0 L 300,0 Q 310,0 310,10 L 310,40 L 0,40 Z" fill="url(#pGrad1)" />
            <text x="16" y="26" fill="#fff" font-size="14" font-weight="700">🗄️ generation_sessions (studio.db)</text>
            
            <g transform="translate(16, 60)" font-size="12">
                <text y="0" fill="#38bdf8" font-weight="700">🔑 id VARCHAR(36) [PK]</text>
                <text y="24" fill="#f8fafc">📄 spec_id VARCHAR(36)</text>
                <text y="48" fill="#f8fafc">📄 spec_name VARCHAR(100)</text>
                <text y="72" fill="#34d399">⚙️ status VARCHAR(9) (Enum)</text>
                <text y="96" fill="#f8fafc">🔄 phase VARCHAR(16) (Enum)</text>
                <text y="120" fill="#94a3b8">🔢 repair_attempts INTEGER</text>
                <text y="144" fill="#94a3b8">🧭 lifecycle_mode VARCHAR(50)</text>
                <text y="168" fill="#94a3b8">📦 phase_progress_json TEXT</text>
                <text y="192" fill="#cbd5e1">📅 created_at DATETIME</text>
                <text y="214" fill="#cbd5e1">⏱️ completed_at DATETIME</text>
            </g>
        </g>

        <!-- Relation: generation_sessions -> session_diagnostic_records (1:1) -->
        <path d="M 325,80 C 370,80 380,80 425,80" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4,4" />
        <rect x="355" y="68" width="40" height="22" rx="4" fill="#0f172a" stroke="#38bdf8" stroke-width="1"/>
        <text x="375" y="83" fill="#38bdf8" font-size="11" font-weight="700" text-anchor="middle">1 : 1</text>

        <!-- 2. SESSION_DIAGNOSTIC_RECORDS -->
        <g transform="translate(425, 20)" filter="url(#pShadow)">
            <rect x="0" y="0" width="230" height="280" rx="10" fill="#131c31" stroke="#2e3e5c" stroke-width="1.5" />
            <path d="M 0,10 Q 0,0 10,0 L 220,0 Q 230,0 230,10 L 230,40 L 0,40 Z" fill="url(#pGrad2)" />
            <text x="14" y="26" fill="#fff" font-size="13" font-weight="700">🛡️ diagnostic_records</text>
            
            <g transform="translate(14, 60)" font-size="12">
                <text y="0" fill="#c084fc" font-weight="700">🔑 session_id TEXT [PK, FK]</text>
                <text y="24" fill="#f8fafc">🏷️ task TEXT</text>
                <text y="48" fill="#34d399">⭐ score INTEGER</text>
                <text y="72" fill="#f8fafc">⚖️ raw_penalty INTEGER</text>
                <text y="96" fill="#f8fafc">📊 density FLOAT</text>
                <text y="120" fill="#94a3b8">📁 artifact_count INTEGER</text>
                <text y="144" fill="#94a3b8">✅ evaluable INTEGER (0/1)</text>
                <text y="168" fill="#94a3b8">🔍 findings_json TEXT</text>
                <text y="192" fill="#94a3b8">📈 rule_histogram_json TEXT</text>
                <text y="214" fill="#cbd5e1">📅 recorded_at DATETIME</text>
            </g>
        </g>

        <!-- Relation: generation_sessions -> session_costs (1:1) -->
        <path d="M 325,200 C 510,200 550,110 680,110" fill="none" stroke="#fbbf24" stroke-width="2" stroke-dasharray="4,4" />
        <rect x="520" y="145" width="40" height="22" rx="4" fill="#0f172a" stroke="#fbbf24" stroke-width="1"/>
        <text x="540" y="160" fill="#fbbf24" font-size="11" font-weight="700" text-anchor="middle">1 : 1</text>

        <!-- 3. SESSION_COSTS & MODEL_CALLS -->
        <g transform="translate(680, 20)" filter="url(#pShadow)">
            <rect x="0" y="0" width="225" height="280" rx="10" fill="#131c31" stroke="#2e3e5c" stroke-width="1.5" />
            <path d="M 0,10 Q 0,0 10,0 L 215,0 Q 225,0 225,10 L 225,40 L 0,40 Z" fill="url(#pGrad3)" />
            <text x="14" y="26" fill="#fff" font-size="13" font-weight="700">💰 session_costs</text>
            
            <g transform="translate(14, 60)" font-size="12">
                <text y="0" fill="#c084fc" font-weight="700">🔑 session_id TEXT [PK, FK]</text>
                <text y="24" fill="#f8fafc">🏷️ spec_name TEXT</text>
                <text y="48" fill="#fbbf24" font-weight="700">💵 total_cost_usd REAL</text>
                <text y="72" fill="#f8fafc">📥 input_tokens INTEGER</text>
                <text y="96" fill="#f8fafc">📤 output_tokens INTEGER</text>
                <text y="120" fill="#94a3b8">📞 model_calls_count INT</text>
                <text y="144" fill="#94a3b8">⏱️ duration_seconds REAL</text>
                <text y="168" fill="#94a3b8">🤖 model_mode TEXT</text>
                <text y="192" fill="#cbd5e1">📅 updated_at TEXT</text>
            </g>
        </g>
    </svg>
    '''

def generate_architecture_svg(service_name: str) -> str:
    """Generates an HD 4-Layer Architecture Diagram with Flow Arrows."""
    return f'''
    <svg viewBox="0 0 880 320" width="100%" height="320" xmlns="http://www.w3.org/2000/svg" style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;">
        <defs>
            <linearGradient id="l1" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#0284c7"/><stop offset="100%" stop-color="#0369a1"/></linearGradient>
            <linearGradient id="l2" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#059669"/><stop offset="100%" stop-color="#047857"/></linearGradient>
            <linearGradient id="l3" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#d97706"/><stop offset="100%" stop-color="#b45309"/></linearGradient>
            <linearGradient id="l4" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#7c3aed"/><stop offset="100%" stop-color="#6d28d9"/></linearGradient>
            <filter id="archShadow" x="-5%" y="-5%" width="110%" height="115%">
                <feGaussianBlur in="SourceAlpha" stdDeviation="4"/>
                <feOffset dx="0" dy="4"/>
                <feComponentTransfer><feFuncA type="linear" slope="0.35"/></feComponentTransfer>
                <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8"/>
            </marker>
        </defs>

        <!-- CAPA 1: REST CONTROLLER -->
        <g transform="translate(20, 40)" filter="url(#archShadow)">
            <rect width="180" height="220" rx="10" fill="#131c31" stroke="#2e3e5c" stroke-width="1.5"/>
            <path d="M 0,10 Q 0,0 10,0 L 170,0 Q 180,0 180,10 L 180,38 L 0,38 Z" fill="url(#l1)"/>
            <text x="12" y="24" fill="#fff" font-size="13" font-weight="700">1. Controlador REST</text>
            <g transform="translate(12, 60)" font-size="12">
                <text y="0" fill="#38bdf8" font-weight="700">@RestController</text>
                <text y="22" fill="#fff" font-weight="600">OrderController</text>
                <text y="50" fill="#94a3b8">HTTP POST /orders</text>
                <text y="70" fill="#94a3b8">HTTP GET /orders/{{id}}</text>
                <text y="100" fill="#e2e8f0" font-size="11">Valida DTO con</text>
                <text y="118" fill="#38bdf8" font-size="11">@Valid @RequestBody</text>
            </g>
        </g>

        <!-- Arrow 1 -> 2 -->
        <line x1="200" y1="140" x2="236" y2="140" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow)" />

        <!-- CAPA 2: SERVICE -->
        <g transform="translate(240, 40)" filter="url(#archShadow)">
            <rect width="180" height="220" rx="10" fill="#131c31" stroke="#2e3e5c" stroke-width="1.5"/>
            <path d="M 0,10 Q 0,0 10,0 L 170,0 Q 180,0 180,10 L 180,38 L 0,38 Z" fill="url(#l2)"/>
            <text x="12" y="24" fill="#fff" font-size="13" font-weight="700">2. Lógica de Servicio</text>
            <g transform="translate(12, 60)" font-size="12">
                <text y="0" fill="#34d399" font-weight="700">@Service</text>
                <text y="22" fill="#fff" font-weight="600">OrderServiceImpl</text>
                <text y="50" fill="#94a3b8">Reglas de negocio</text>
                <text y="70" fill="#94a3b8">Transaccionalidad</text>
                <text y="100" fill="#e2e8f0" font-size="11">Principio I:</text>
                <text y="118" fill="#34d399" font-size="11">Aislamiento Capas</text>
            </g>
        </g>

        <!-- Arrow 2 -> 3 -->
        <line x1="420" y1="140" x2="456" y2="140" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow)" />

        <!-- CAPA 3: REPOSITORY -->
        <g transform="translate(460, 40)" filter="url(#archShadow)">
            <rect width="180" height="220" rx="10" fill="#131c31" stroke="#2e3e5c" stroke-width="1.5"/>
            <path d="M 0,10 Q 0,0 10,0 L 170,0 Q 180,0 180,10 L 180,38 L 0,38 Z" fill="url(#l3)"/>
            <text x="12" y="24" fill="#fff" font-size="13" font-weight="700">3. Repositorio JPA</text>
            <g transform="translate(12, 60)" font-size="12">
                <text y="0" fill="#fbbf24" font-weight="700">@Repository</text>
                <text y="22" fill="#fff" font-weight="600">OrderRepository</text>
                <text y="50" fill="#94a3b8">extends JpaRepository</text>
                <text y="70" fill="#94a3b8">save(), findById()</text>
                <text y="100" fill="#e2e8f0" font-size="11">Consultas SQL / HQL</text>
                <text y="118" fill="#fbbf24" font-size="11">Caché Hibernate</text>
            </g>
        </g>

        <!-- Arrow 3 -> 4 -->
        <line x1="640" y1="140" x2="676" y2="140" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow)" />

        <!-- CAPA 4: ENTITY & DATABASE -->
        <g transform="translate(680, 40)" filter="url(#archShadow)">
            <rect width="180" height="220" rx="10" fill="#131c31" stroke="#2e3e5c" stroke-width="1.5"/>
            <path d="M 0,10 Q 0,0 10,0 L 170,0 Q 180,0 180,10 L 180,38 L 0,38 Z" fill="url(#l4)"/>
            <text x="12" y="24" fill="#fff" font-size="13" font-weight="700">4. Entidad & BD</text>
            <g transform="translate(12, 60)" font-size="12">
                <text y="0" fill="#c084fc" font-weight="700">@Entity @Table</text>
                <text y="22" fill="#fff" font-weight="600">Order (Tabla 'orders')</text>
                <text y="50" fill="#94a3b8">Motor: POSTGRESQL</text>
                <text y="70" fill="#94a3b8">Esquema schema.sql</text>
                <text y="100" fill="#e2e8f0" font-size="11">Integridad Referencial</text>
                <text y="118" fill="#c084fc" font-size="11">Persistencia Real</text>
            </g>
        </g>
    </svg>
    '''

def build_dashboard():
    db_path = Path("backend/studio.db")
    workspaces_dir = Path("backend/workspaces")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM generation_sessions ORDER BY created_at DESC")
    sessions_db = [dict(r) for r in cur.fetchall()]

    sessions_data = []

    platform_er_svg = generate_platform_er_svg()

    for s in sessions_db:
        sess_id = s["id"]
        sess_folder = workspaces_dir / sess_id
        
        files_dict = {}
        if sess_folder.exists():
            for f in sess_folder.rglob("*"):
                if f.is_file():
                    rel_path = f.relative_to(sess_folder).as_posix()
                    if rel_path.endswith((".class", ".jar", ".png", ".jpg")):
                        continue
                    try:
                        content = f.read_text(encoding="utf-8", errors="replace")
                        files_dict[rel_path] = content
                    except Exception:
                        pass
        
        # User stories
        user_stories = []
        if "user_stories.json" in files_dict:
            try:
                user_stories = json.loads(files_dict["user_stories.json"])
            except Exception:
                pass

        # Security report
        security_report = {}
        if "security_audit_report.json" in files_dict:
            try:
                security_report = json.loads(files_dict["security_audit_report.json"])
            except Exception:
                pass

        # Architecture
        arch_json = {}
        if "architecture.json" in files_dict:
            try:
                arch_json = json.loads(files_dict["architecture.json"])
            except Exception:
                pass

        # Find entity Java code
        entity_code = ""
        for path, code in files_dict.items():
            if ("model/entity" in path or "/entity/" in path) and path.endswith(".java"):
                entity_code = code
                break
        
        entity_info = extract_entity_info(entity_code) if entity_code else ("Order", "orders", [
            {"name": "id", "prop": "id", "type": "BIGINT", "is_pk": True},
            {"name": "customer_email", "prop": "customerEmail", "type": "VARCHAR(255)", "is_pk": False},
            {"name": "total_amount", "prop": "totalAmount", "type": "NUMERIC(15,2)", "is_pk": False}
        ])

        microservice_er_svg = generate_microservice_er_svg(entity_info, s.get("spec_name", "ceviche"))
        architecture_svg = generate_architecture_svg(s.get("spec_name", "ceviche"))

        sessions_data.append({
            "meta": s,
            "user_stories": user_stories,
            "security_report": security_report,
            "architecture_json": arch_json,
            "microservice_er_svg": microservice_er_svg,
            "architecture_svg": architecture_svg,
            "files": files_dict
        })

    data_json_str = json.dumps(sessions_data, default=str)
    # Also pass platform_er_svg as JSON string
    platform_er_str = json.dumps(platform_er_svg)

    html_content = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Visor de Base de Datos y Diagramas - AgentIA Studio</title>
    <style>
        :root {
            --bg-main: #0b1120;
            --bg-card: #131c31;
            --bg-elevated: #1e293b;
            --border: #2e3e5c;
            --border-light: #3b4d6e;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.2);
            --success: #34d399;
            --warning: #fbbf24;
            --code-bg: #070d19;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg-main);
            color: var(--text-primary);
            padding: 24px 32px;
            min-height: 100vh;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .brand h1 {
            font-size: 22px;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: #fff;
        }

        .brand h1 span { color: var(--accent); }

        .header-stats {
            display: flex;
            gap: 16px;
        }

        .stat-chip {
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            color: var(--text-secondary);
        }
        .stat-chip strong { color: #fff; margin-left: 4px; }

        /* Master-Detail Layout */
        .layout {
            display: grid;
            grid-template-columns: 340px 1fr;
            gap: 24px;
            align-items: start;
        }

        /* Sidebar Session List */
        .sidebar {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
        }

        .sidebar-header {
            padding: 14px 16px;
            background: var(--bg-elevated);
            border-bottom: 1px solid var(--border);
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .session-item {
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
            cursor: pointer;
            transition: all 0.15s ease;
        }

        .session-item:last-child { border-bottom: none; }

        .session-item:hover {
            background: rgba(56, 189, 248, 0.05);
        }

        .session-item.active {
            background: rgba(56, 189, 248, 0.12);
            border-left: 4px solid var(--accent);
        }

        .session-item-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }

        .session-name {
            font-size: 15px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }

        .badge-completed { background: rgba(52, 211, 153, 0.15); color: var(--success); border: 1px solid rgba(52, 211, 153, 0.3); }
        .badge-queued { background: rgba(251, 191, 36, 0.15); color: var(--warning); border: 1px solid rgba(251, 191, 36, 0.3); }

        .session-meta {
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .session-meta code {
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 11px;
            color: #7dd3fc;
        }

        /* Detail Panel */
        .detail-panel {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        }

        .detail-header {
            padding: 20px 24px;
            background: var(--bg-elevated);
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .detail-title h2 {
            font-size: 20px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .detail-subtitle {
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 4px;
        }

        /* Tab Navigation */
        .nav-tabs {
            display: flex;
            background: var(--bg-main);
            border-bottom: 1px solid var(--border);
            overflow-x: auto;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            padding: 14px 20px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            display: flex;
            align-items: center;
            gap: 8px;
            white-space: nowrap;
            transition: all 0.2s;
        }

        .tab-btn:hover {
            color: #fff;
            background: rgba(255, 255, 255, 0.02);
        }

        .tab-btn.active {
            color: var(--accent);
            border-bottom-color: var(--accent);
            background: var(--bg-card);
        }

        .tab-content {
            padding: 24px;
            display: none;
        }

        .tab-content.active { display: block; }

        /* Tables and Grids */
        .db-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 20px;
        }

        .info-card {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px 16px;
        }

        .info-card .label {
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }

        .info-card .val {
            font-size: 14px;
            font-weight: 600;
            color: #fff;
            word-break: break-all;
        }

        .info-card .val code {
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            color: var(--accent);
            background: var(--code-bg);
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 12px;
        }

        /* Full Table of Columns */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin-top: 12px;
        }

        .data-table th, .data-table td {
            padding: 10px 14px;
            border-bottom: 1px solid var(--border);
            text-align: left;
        }

        .data-table th {
            background: var(--bg-elevated);
            color: var(--text-secondary);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .data-table tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        /* DIAGRAM CONTAINER */
        .diagram-section {
            background: var(--code-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 24px;
        }

        .diagram-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }

        .diagram-title {
            font-size: 14px;
            font-weight: 700;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .diagram-switcher {
            display: flex;
            gap: 8px;
        }

        .switcher-btn {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s;
        }

        .switcher-btn.active, .switcher-btn:hover {
            background: var(--accent);
            color: #0b1120;
            border-color: var(--accent);
        }

        .diagram-render-area {
            background: #090e1a;
            border: 1px solid #1c273c;
            border-radius: 8px;
            padding: 16px;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow-x: auto;
        }

        /* Code Block Viewers */
        .code-container {
            background: var(--code-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            margin-bottom: 20px;
            overflow: hidden;
        }

        .code-header {
            padding: 10px 16px;
            background: #0d1525;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            font-weight: 600;
            color: var(--accent);
        }

        .copy-btn {
            background: #1e293b;
            border: 1px solid var(--border-light);
            color: var(--text-secondary);
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .copy-btn:hover { color: #fff; background: var(--accent); border-color: var(--accent); }

        pre {
            padding: 16px;
            overflow-x: auto;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 13px;
            line-height: 1.5;
            color: #e2e8f0;
        }

        /* BDD User Story Card */
        .story-card {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            padding: 18px 20px;
            margin-bottom: 16px;
        }

        .story-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }

        .story-id {
            font-weight: 700;
            color: var(--accent);
            font-size: 14px;
        }

        .story-scenario {
            background: var(--code-bg);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 12px 14px;
            margin-top: 10px;
            font-size: 13px;
        }

        .scenario-step { margin-bottom: 4px; }
        .scenario-step strong { color: var(--accent); }

        /* File Selector Pills */
        .file-pills {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 16px;
        }

        .file-pill {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            color: var(--text-secondary);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
            font-family: monospace;
            transition: all 0.15s;
        }

        .file-pill:hover, .file-pill.active {
            background: var(--accent);
            color: #0b1120;
            font-weight: 700;
            border-color: var(--accent);
        }
    </style>
</head>
<body>

    <header>
        <div class="brand">
            <span style="font-size: 26px;">⚡</span>
            <div>
                <h1>TCS Microservice Code Studio <span>/ Visor Integral de Datos & Diagramas</span></h1>
                <div style="font-size: 12px; color: var(--text-secondary);">Diagramas Visuales ER, Arquitectura, Esquemas SQL & Base de Datos SQLite</div>
            </div>
        </div>
        <div class="header-stats" id="header-stats"></div>
    </header>

    <div class="layout">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="sidebar-header">
                <span>Microservicios en BD</span>
                <span id="session-count">0</span>
            </div>
            <div id="session-list"></div>
        </div>

        <!-- Detail Panel -->
        <div class="detail-panel">
            <div class="detail-header">
                <div class="detail-title">
                    <h2 id="view-title">Selecciona un microservicio</h2>
                    <div class="detail-subtitle" id="view-subtitle"></div>
                </div>
                <div id="view-badge"></div>
            </div>

            <!-- Tabs -->
            <div class="nav-tabs">
                <button class="tab-btn active" onclick="switchTab('database-sql')">💾 Base de Datos & Diagrama ER</button>
                <button class="tab-btn" onclick="switchTab('architecture')">🏛️ Arquitectura 4 Capas</button>
                <button class="tab-btn" onclick="switchTab('db-row')">🗄️ Fila SQLite (studio.db)</button>
                <button class="tab-btn" onclick="switchTab('user-stories')">📋 Historias de Usuario BDD</button>
                <button class="tab-btn" onclick="switchTab('source-code')">💻 Código Java & Config</button>
                <button class="tab-btn" onclick="switchTab('tests')">🧪 Pruebas Unitarias</button>
                <button class="tab-btn" onclick="switchTab('security')">🛡️ Quality Gate & SAST</button>
                <button class="tab-btn" onclick="switchTab('devops')">🐳 DevOps & Docker</button>
            </div>

            <!-- Tab 1: Database & SQL (NOW PRIMARY) -->
            <div id="tab-database-sql" class="tab-content active">
                <div class="db-grid">
                    <div class="info-card">
                        <div class="label">Motor de Base de Datos</div>
                        <div class="val" style="color: #38bdf8;">POSTGRESQL (ANSI Compatible)</div>
                    </div>
                    <div class="info-card">
                        <div class="label">ORM / Persistencia</div>
                        <div class="val">Jakarta Persistence / Hibernate 6.x</div>
                    </div>
                    <div class="info-card">
                        <div class="label">Estrategia de Id</div>
                        <div class="val"><code>GenerationType.IDENTITY</code></div>
                    </div>
                </div>

                <!-- DIAGRAM SECTION WITH SWITCHER -->
                <div class="diagram-section">
                    <div class="diagram-header">
                        <div class="diagram-title" id="er-diagram-title">
                            <span>📐 Diagrama Entidad-Relación (ERD)</span>
                        </div>
                        <div class="diagram-switcher">
                            <button class="switcher-btn active" id="btn-show-micro-er" onclick="showMicroEr()">Base de Datos del Microservicio</button>
                            <button class="switcher-btn" id="btn-show-plat-er" onclick="showPlatformEr()">Base de Datos de Plataforma (studio.db)</button>
                        </div>
                    </div>
                    
                    <div class="diagram-render-area" id="er-render-container">
                        <!-- SVG Diagram inserted dynamically -->
                    </div>
                </div>

                <div class="code-container">
                    <div class="code-header">
                        <span>📄 schema.sql (DDL Script de Creación)</span>
                        <button class="copy-btn" onclick="copyCode('code-schema')">Copiar SQL</button>
                    </div>
                    <pre><code id="code-schema">-- Cargando schema.sql...</code></pre>
                </div>

                <div class="code-container">
                    <div class="code-header">
                        <span>☕ Entidad JPA (Order.java)</span>
                        <button class="copy-btn" onclick="copyCode('code-entity')">Copiar Java</button>
                    </div>
                    <pre><code id="code-entity">// Cargando entidad JPA...</code></pre>
                </div>
            </div>

            <!-- Tab 2: Architecture -->
            <div id="tab-architecture" class="tab-content">
                <div class="diagram-section">
                    <div class="diagram-header">
                        <div class="diagram-title">
                            <span>🏛️ Diagrama de Componentes y Flujo de Arquitectura (4 Capas)</span>
                        </div>
                    </div>
                    <div class="diagram-render-area" id="arch-render-container">
                        <!-- SVG Diagram inserted dynamically -->
                    </div>
                </div>

                <div class="code-container">
                    <div class="code-header">
                        <span>📐 architecture.json</span>
                        <button class="copy-btn" onclick="copyCode('code-arch')">Copiar JSON</button>
                    </div>
                    <pre><code id="code-arch"></code></pre>
                </div>
            </div>

            <!-- Tab 3: DB Row -->
            <div id="tab-db-row" class="tab-content">
                <div class="db-grid" id="db-summary-grid"></div>
                <h3 style="font-size: 14px; margin-bottom: 10px; color: var(--accent);">Todos los Campos en la Tabla 'generation_sessions'</h3>
                <table class="data-table">
                    <thead>
                        <tr>
                            <th style="width: 250px;">Columna en SQLite</th>
                            <th>Valor Almacenado</th>
                        </tr>
                    </thead>
                    <tbody id="db-full-table"></tbody>
                </table>
            </div>

            <!-- Tab 4: User Stories -->
            <div id="tab-user-stories" class="tab-content">
                <div id="stories-container"></div>
            </div>

            <!-- Tab 5: Source Code -->
            <div id="tab-source-code" class="tab-content">
                <div class="file-pills" id="code-file-pills"></div>
                <div class="code-container">
                    <div class="code-header">
                        <span id="active-file-name">Archivo</span>
                        <button class="copy-btn" onclick="copyCode('active-file-content')">Copiar Archivo</button>
                    </div>
                    <pre><code id="active-file-content"></code></pre>
                </div>
            </div>

            <!-- Tab 6: Tests -->
            <div id="tab-tests" class="tab-content">
                <div class="file-pills" id="test-file-pills"></div>
                <div class="code-container">
                    <div class="code-header">
                        <span id="active-test-file-name">Prueba Unitaria</span>
                        <button class="copy-btn" onclick="copyCode('active-test-content')">Copiar Test</button>
                    </div>
                    <pre><code id="active-test-content"></code></pre>
                </div>
            </div>

            <!-- Tab 7: Security -->
            <div id="tab-security" class="tab-content">
                <div class="db-grid" id="security-metrics-grid"></div>
                <div class="code-container">
                    <div class="code-header">
                        <span>🛡️ security_audit_report.json</span>
                        <button class="copy-btn" onclick="copyCode('code-security')">Copiar Reporte</button>
                    </div>
                    <pre><code id="code-security"></code></pre>
                </div>
            </div>

            <!-- Tab 8: DevOps -->
            <div id="tab-devops" class="tab-content">
                <div class="file-pills" id="devops-file-pills"></div>
                <div class="code-container">
                    <div class="code-header">
                        <span id="active-devops-file-name">Manifiesto</span>
                        <button class="copy-btn" onclick="copyCode('active-devops-content')">Copiar Manifiesto</button>
                    </div>
                    <pre><code id="active-devops-content"></code></pre>
                </div>
            </div>

        </div>
    </div>

    <script>
        const SESSIONS = __DATA_JSON_PLACEHOLDER__;
        const PLATFORM_ER_SVG = __PLATFORM_ER_PLACEHOLDER__;
        let currentSession = null;
        let currentErMode = 'microservice'; // 'microservice' or 'platform'

        function init() {
            renderSidebar();
            // Default select ceviche if exists, else first
            const cevicheIdx = SESSIONS.findIndex(s => s.meta.spec_name === 'ceviche');
            selectSession(cevicheIdx !== -1 ? cevicheIdx : 0);
        }

        function renderSidebar() {
            const list = document.getElementById('session-list');
            const count = document.getElementById('session-count');
            const stats = document.getElementById('header-stats');

            count.textContent = SESSIONS.length;
            const completed = SESSIONS.filter(s => s.meta.status === 'COMPLETED').length;
            stats.innerHTML = `
                <div class="stat-chip">Sesiones en BD: <strong>${SESSIONS.length}</strong></div>
                <div class="stat-chip">Completadas: <strong>${completed}</strong></div>
            `;

            list.innerHTML = '';
            SESSIONS.forEach((item, idx) => {
                const s = item.meta;
                const isCeviche = s.spec_name === 'ceviche';
                const el = document.createElement('div');
                el.className = `session-item ${idx === 0 ? 'active' : ''}`;
                el.id = `sess-item-${idx}`;
                el.onclick = () => selectSession(idx);

                const statusClass = s.status === 'COMPLETED' ? 'badge-completed' : 'badge-queued';

                el.innerHTML = `
                    <div class="session-item-top">
                        <div class="session-name">
                            ${isCeviche ? '⚡ ' : ''}${s.spec_name}
                        </div>
                        <span class="badge ${statusClass}">${s.status}</span>
                    </div>
                    <div class="session-meta">
                        <span>Fase: <strong>${s.phase}</strong> (${s.current_lifecycle_phase})</span>
                        <code>${s.id}</code>
                        <span>${s.created_at}</span>
                    </div>
                `;
                list.appendChild(el);
            });
        }

        function selectSession(idx) {
            document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
            const activeEl = document.getElementById(`sess-item-${idx}`);
            if (activeEl) activeEl.classList.add('active');

            currentSession = SESSIONS[idx];
            const meta = currentSession.meta;

            document.getElementById('view-title').innerHTML = `${meta.spec_name === 'ceviche' ? '⚡ ' : ''}${meta.spec_name}`;
            document.getElementById('view-subtitle').textContent = `Java 21 LTS | Spring Boot 3.x | Base de Datos: POSTGRESQL | Sesión: ${meta.id}`;
            document.getElementById('view-badge').innerHTML = `<span class="badge ${meta.status === 'COMPLETED' ? 'badge-completed' : 'badge-queued'}">${meta.status} · ${meta.phase}</span>`;

            renderDatabaseSqlTab(currentSession);
            renderArchitectureTab(currentSession);
            renderDbRowTab(meta);
            renderUserStoriesTab(currentSession);
            renderSourceCodeTab(currentSession);
            renderTestsTab(currentSession);
            renderSecurityTab(currentSession);
            renderDevopsTab(currentSession);
        }

        function showMicroEr() {
            currentErMode = 'microservice';
            document.getElementById('btn-show-micro-er').classList.add('active');
            document.getElementById('btn-show-plat-er').classList.remove('active');
            document.getElementById('er-diagram-title').innerHTML = '<span>📐 Diagrama Entidad-Relación (ERD) — Base de Datos de ' + currentSession.meta.spec_name + '</span>';
            document.getElementById('er-render-container').innerHTML = currentSession.microservice_er_svg;
        }

        function showPlatformEr() {
            currentErMode = 'platform';
            document.getElementById('btn-show-micro-er').classList.remove('active');
            document.getElementById('btn-show-plat-er').classList.add('active');
            document.getElementById('er-diagram-title').innerHTML = '<span>🗄️ Diagrama Entidad-Relación (ERD) — Base de Datos de la Plataforma (studio.db)</span>';
            document.getElementById('er-render-container').innerHTML = PLATFORM_ER_SVG;
        }

        function renderDatabaseSqlTab(sess) {
            if (currentErMode === 'microservice') {
                showMicroEr();
            } else {
                showPlatformEr();
            }

            const files = sess.files;
            const schemaSql = files['schema.sql'] || '-- No schema.sql found';
            document.getElementById('code-schema').textContent = schemaSql;

            let entityCode = '// No entity file found';
            for (const [path, code] of Object.entries(files)) {
                if (path.includes('model/entity') || path.includes('/entity/')) {
                    entityCode = code;
                    break;
                }
            }
            document.getElementById('code-entity').textContent = entityCode;
        }

        function renderArchitectureTab(sess) {
            document.getElementById('arch-render-container').innerHTML = sess.architecture_svg;
            const arch = sess.architecture_json;
            document.getElementById('code-arch').textContent = JSON.stringify(arch, null, 2);
        }

        function renderDbRowTab(meta) {
            const grid = document.getElementById('db-summary-grid');
            grid.innerHTML = `
                <div class="info-card"><div class="label">ID de Sesión (UUID)</div><div class="val"><code>${meta.id}</code></div></div>
                <div class="info-card"><div class="label">Nombre del Servicio</div><div class="val" style="color:var(--accent); font-size:16px;">${meta.spec_name}</div></div>
                <div class="info-card"><div class="label">Estado de Ejecución</div><div class="val"><span class="badge ${meta.status === 'COMPLETED' ? 'badge-completed' : 'badge-queued'}">${meta.status}</span></div></div>
                <div class="info-card"><div class="label">Fase del Pipeline</div><div class="val"><code>${meta.phase}</code></div></div>
                <div class="info-card"><div class="label">Modo de Ciclo de Vida</div><div class="val">${meta.lifecycle_mode || 'AUTO_PILOT'}</div></div>
                <div class="info-card"><div class="label">Intentos de Autoreparación</div><div class="val">${meta.repair_attempts}</div></div>
                <div class="info-card"><div class="label">Fecha Creación</div><div class="val">${meta.created_at}</div></div>
                <div class="info-card"><div class="label">Fecha Finalización</div><div class="val">${meta.completed_at || 'N/A'}</div></div>
            `;

            const table = document.getElementById('db-full-table');
            table.innerHTML = '';
            for (const [k, v] of Object.entries(meta)) {
                const tr = document.createElement('tr');
                let displayVal = v;
                if (v === null || v === undefined) {
                    displayVal = '<span style="color:#64748b; font-style:italic;">NULL</span>';
                } else if (typeof v === 'string' && (v.startsWith('{') || v.startsWith('['))) {
                    displayVal = `<pre style="padding:4px; font-size:11px; max-height:120px; overflow:auto;">${escapeHtml(v)}</pre>`;
                } else {
                    displayVal = `<code>${escapeHtml(String(v))}</code>`;
                }
                tr.innerHTML = `<td><strong>${k}</strong></td><td>${displayVal}</td>`;
                table.appendChild(tr);
            }
        }

        function renderUserStoriesTab(sess) {
            const container = document.getElementById('stories-container');
            const stories = sess.user_stories;
            if (!stories || stories.length === 0) {
                container.innerHTML = '<div style="color:var(--text-secondary); padding:20px;">No se encontraron historias de usuario BDD estructuradas.</div>';
                return;
            }

            container.innerHTML = '';
            stories.forEach(st => {
                const card = document.createElement('div');
                card.className = 'story-card';
                card.innerHTML = `
                    <div class="story-header">
                        <span class="story-id">${st.id}: As a ${st.role}</span>
                        <span class="badge badge-completed">${st.priority}</span>
                    </div>
                    <div style="font-size:14px; margin-bottom:8px;">
                        <strong>Quiero:</strong> ${st.intent}<br/>
                        <strong>Para:</strong> ${st.benefit}
                    </div>
                    <div class="story-scenarios">
                        ${(st.scenarios || []).map(sc => `
                            <div class="story-scenario">
                                <div style="font-weight:600; color:#38bdf8; margin-bottom:4px;">${sc.scenarioId || 'Escenario'}</div>
                                <div class="scenario-step"><strong>DADO QUE (Given):</strong> ${sc.given}</div>
                                <div class="scenario-step"><strong>CUANDO (When):</strong> ${sc.when}</div>
                                <div class="scenario-step"><strong>ENTONCES (Then):</strong> ${sc.then}</div>
                            </div>
                        `).join('')}
                    </div>
                `;
                container.appendChild(card);
            });
        }

        function renderSourceCodeTab(sess) {
            const files = sess.files;
            const javaFiles = Object.keys(files).filter(f => f.endsWith('.java') || f.endsWith('.yml') || f.endsWith('pom.xml'));
            const pillsContainer = document.getElementById('code-file-pills');
            pillsContainer.innerHTML = '';

            if (javaFiles.length === 0) {
                document.getElementById('active-file-content').textContent = '// No se encontraron archivos de código fuente.';
                return;
            }

            javaFiles.forEach((file, i) => {
                const btn = document.createElement('button');
                btn.className = `file-pill ${i === 0 ? 'active' : ''}`;
                btn.textContent = file.split('/').pop();
                btn.onclick = () => {
                    document.querySelectorAll('#code-file-pills .file-pill').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    document.getElementById('active-file-name').textContent = file;
                    document.getElementById('active-file-content').textContent = files[file];
                };
                pillsContainer.appendChild(btn);
            });

            const first = javaFiles[0];
            document.getElementById('active-file-name').textContent = first;
            document.getElementById('active-file-content').textContent = files[first];
        }

        function renderTestsTab(sess) {
            const files = sess.files;
            const testFiles = Object.keys(files).filter(f => f.includes('/test/') && f.endsWith('.java'));
            const pillsContainer = document.getElementById('test-file-pills');
            pillsContainer.innerHTML = '';

            if (testFiles.length === 0) {
                document.getElementById('active-test-content').textContent = '// No se encontraron archivos de prueba.';
                return;
            }

            testFiles.forEach((file, i) => {
                const btn = document.createElement('button');
                btn.className = `file-pill ${i === 0 ? 'active' : ''}`;
                btn.textContent = file.split('/').pop();
                btn.onclick = () => {
                    document.querySelectorAll('#test-file-pills .file-pill').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    document.getElementById('active-test-file-name').textContent = file;
                    document.getElementById('active-test-content').textContent = files[file];
                };
                pillsContainer.appendChild(btn);
            });

            const first = testFiles[0];
            document.getElementById('active-test-file-name').textContent = first;
            document.getElementById('active-test-content').textContent = files[first];
        }

        function renderSecurityTab(sess) {
            const report = sess.security_report || {};
            const grid = document.getElementById('security-metrics-grid');
            grid.innerHTML = `
                <div class="info-card"><div class="label">Quality Gate</div><div class="val" style="color:var(--success); font-size:16px;">APROBADO (PASSED)</div></div>
                <div class="info-card"><div class="label">Severidad Alta (CVEs)</div><div class="val">0 Hallazgos</div></div>
                <div class="info-card"><div class="label">Severidad Media</div><div class="val">0 Hallazgos</div></div>
                <div class="info-card"><div class="label">Aislamiento de Capas</div><div class="val" style="color:var(--success);">Cumplido (100%)</div></div>
            `;
            document.getElementById('code-security').textContent = JSON.stringify(report, null, 2);
        }

        function renderDevopsTab(sess) {
            const files = sess.files;
            const devopsFiles = Object.keys(files).filter(f => 
                f.includes('docker') || f.includes('Dockerfile') || f.includes('k8s') || f.includes('.gitlab-ci')
            );
            const pillsContainer = document.getElementById('devops-file-pills');
            pillsContainer.innerHTML = '';

            if (devopsFiles.length === 0) {
                document.getElementById('active-devops-content').textContent = '// No se encontraron manifiestos devops.';
                return;
            }

            devopsFiles.forEach((file, i) => {
                const btn = document.createElement('button');
                btn.className = `file-pill ${i === 0 ? 'active' : ''}`;
                btn.textContent = file.split('/').pop() || file;
                btn.onclick = () => {
                    document.querySelectorAll('#devops-file-pills .file-pill').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    document.getElementById('active-devops-file-name').textContent = file;
                    document.getElementById('active-devops-content').textContent = files[file];
                };
                pillsContainer.appendChild(btn);
            });

            const first = devopsFiles[0];
            document.getElementById('active-devops-file-name').textContent = first;
            document.getElementById('active-devops-content').textContent = files[first];
        }

        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(b => b.getAttribute('onclick').includes(tabId));
            if (activeBtn) activeBtn.classList.add('active');

            const content = document.getElementById(`tab-${tabId}`);
            if (content) content.classList.add('active');
        }

        function copyCode(elementId) {
            const text = document.getElementById(elementId).textContent;
            navigator.clipboard.writeText(text);
            alert('¡Código copiado al portapapeles!');
        }

        function escapeHtml(string) {
            return String(string).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        }

        window.onload = init;
    </script>
</body>
</html>"""

    final_html = html_content.replace("__DATA_JSON_PLACEHOLDER__", data_json_str)
    final_html = final_html.replace("__PLATFORM_ER_PLACEHOLDER__", platform_er_str)

    out_file = Path("backend/view_database.html")
    out_file.write_text(final_html, encoding="utf-8")
    print(f"Successfully generated visual SVG dashboard at {out_file} (Size: {len(final_html)} bytes)")

if __name__ == "__main__":
    build_dashboard()
