#!/usr/bin/env python3
"""Build the executed-test-case matrix from the JUnit reports.

The matrix is generated from machine-readable results rather than written by hand, so it
can never disagree with what the suites actually did. Every row is a test that really ran,
with the outcome the runner reported.

Usage (from the repository root, after running both suites with --junitxml):

    .venv/bin/python docs/entrega_qe/build_matriz.py
"""

from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENTREGA = ROOT / "reports" / "qe" / "entrega"
OUT = ROOT / "docs" / "entrega_qe"

# ---------------------------------------------------------------------------
# Flujo assignment. Ordered: the first pattern that matches a test's file wins.
# Kept as data so the classification is auditable and easy to correct.
# ---------------------------------------------------------------------------
FLOWS: list[tuple[str, str]] = [
    ("F0", "Autenticación y sesión de operador"),
    ("F1", "Ingesta y validación de especificación (blueprints)"),
    ("F2", "Requisitos → Historias BDD"),
    ("F3", "Diseño arquitectónico"),
    ("F4", "Modelos de dominio y esquema SQL"),
    ("F5", "Generación de código y síntesis de pruebas"),
    ("F6", "Sandbox hermético y auto-reparación acotada"),
    ("F7", "Auditoría de seguridad y Quality Gate"),
    ("F8", "DevOps: manifiestos, contenedores y despliegue local"),
    ("F9", "Exportación, artefactos y publicación Git"),
    ("F10", "Orquestación Auto-Pilot y ciclo de vida de la sesión"),
    ("F11", "Trazabilidad de costos y telemetría"),
    ("F12", "Playground de API en vivo"),
    ("FT", "Transversal: interfaz, tema, contratos de servicio"),
]

FLOW_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"auth"), "F0"),
    (re.compile(r"specification|routes_spec|entry_point"), "F1"),
    (re.compile(r"requirements"), "F2"),
    (re.compile(r"architecture"), "F3"),
    (re.compile(r"models_sql|model_sql|schema|slice_test"), "F4"),
    (re.compile(r"routes_tests|test_analysis|generated_code|code_generation"), "F5"),
    (re.compile(r"sandbox|repair|environment_repair|docker_runner"), "F6"),
    (re.compile(r"security|injection"), "F7"),
    (re.compile(r"devops|deploy|deployment_identity"), "F8"),
    (re.compile(r"publish|git|artifact|export"), "F9"),
    (re.compile(r"orchestrator|pipeline|lifecycle|session|outdated|sessions_api"), "F10"),
    (re.compile(r"cost|mlflow|pricing|recording"), "F11"),
    (re.compile(r"playground"), "F12"),
]


def flow_of(file_name: str) -> str:
    lowered = file_name.lower()
    for pattern, flow in FLOW_MAP:
        if pattern.search(lowered):
            return flow
    return "FT"


def parse_junit(path: Path, suite: str) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"missing {path}; run the suites with --junitxml first")
    tree = ET.parse(path)
    rows: list[dict] = []
    for case in tree.iter("testcase"):
        classname = case.get("classname") or ""
        name = case.get("name") or ""
        source = classname or ""
        outcome = "PASS"
        detail = ""
        for child in case:
            tag = child.tag.lower()
            if tag == "failure":
                outcome = "FAIL"
                detail = (child.get("message") or "").strip().replace("\n", " ")[:180]
            elif tag == "error":
                outcome = "ERROR"
                detail = (child.get("message") or "").strip().replace("\n", " ")[:180]
            elif tag == "skipped":
                outcome = "SKIP"
                detail = (child.get("message") or "").strip().replace("\n", " ")[:180]
        file_name = Path(source).name if source else Path(name.split(" > ")[0]).name
        rows.append(
            {
                "suite": suite,
                "flow": flow_of(file_name),
                "archivo": source or file_name,
                "caso": name,
                "resultado": outcome,
                "segundos": case.get("time") or "0",
                "detalle": detail,
            }
        )
    return rows


def write_coverage() -> None:
    """Emit the measured coverage, so the report cannot quote a stale figure.

    The codebase moved under this campaign (a concurrent session added ~2,100 statements),
    so the per-module percentages are re-read from the coverage report on every build
    rather than remembered from the day the tests were written.
    """
    path = ENTREGA / "coverage.json"
    if not path.exists():
        (OUT / "cobertura_generada.tex").write_text(
            "% coverage.json no encontrado\n", encoding="utf-8")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    totals = data["totals"]
    priority = [
        ("services/docker_service.py", "F8"),
        ("api/routes_session.py", "F10"),
        ("services/lifecycle_service.py", "F10"),
        ("services/pipeline_runner.py", "F10"),
        ("services/auth_service.py", "F0"),
    ]
    lines = [
        "% GENERADO POR docs/entrega_qe/build_matriz.py -- no editar a mano.",
        f"\\newcommand{{\\QEcover}}{{{totals['percent_covered']:.1f}}}",
        f"\\newcommand{{\\QEstmts}}{{{totals['num_statements']:,}}}".replace(",", "\\,"),
        f"\\newcommand{{\\QEmissed}}{{{totals['missing_lines']:,}}}".replace(",", "\\,"),
        r"\begin{center}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"\textbf{Módulo} & \textbf{Flujo} & \textbf{Cobertura} & \textbf{Sin cubrir} \\",
        r"\midrule",
    ]
    for module, flow in priority:
        entry = data["files"].get(f"backend/app/{module}")
        if not entry:
            continue
        summary = entry["summary"]
        name = module.replace("_", r"\_")
        pct = f"{summary['percent_covered']:.1f}\\,\\%"
        lines.append(f"\\code{{{name}}} & {flow} & \\textbf{{{pct}}} & {summary['missing_lines']} \\\\")
    lines += [
        r"\midrule",
        f"\\textbf{{Total del backend}} & & \\textbf{{\\QEcover\\,\\%}} & \\textbf{{\\QEmissed}} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{center}",
        "",
    ]
    (OUT / "cobertura_generada.tex").write_text("\n".join(lines), encoding="utf-8")
    print(f"cobertura: {totals['percent_covered']:.1f}% ({totals['missing_lines']} sin cubrir)")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = parse_junit(ENTREGA / "junit-backend.xml", "backend")
    rows += parse_junit(ENTREGA / "junit-frontend.xml", "frontend")

    # Stable, human-usable identifiers: F6-014 etc., grouped by flow.
    counters: Counter[str] = Counter()
    for row in sorted(rows, key=lambda r: (r["flow"], r["archivo"], r["caso"])):
        counters[row["flow"]] += 1
        row["id"] = f"{row['flow']}-{counters[row['flow']]:03d}"

    columns = ["id", "flow", "suite", "archivo", "caso", "resultado", "segundos", "detalle"]
    with (OUT / "matriz_casos_de_prueba.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: r["id"]))

    totals = Counter(r["resultado"] for r in rows)
    by_flow: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        by_flow[row["flow"]][row["resultado"]] += 1

    summary = {
        "total": len(rows),
        "por_resultado": dict(totals),
        "por_suite": dict(Counter(r["suite"] for r in rows)),
        "por_flujo": {
            code: {"titulo": dict(FLOWS)[code], "total": sum(c.values()), **dict(c)}
            for code, c in sorted(by_flow.items())
        },
    }
    (OUT / "resumen_ejecucion.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    write_latex(summary, rows)
    write_coverage()

    print(f"casos: {len(rows)}  resultados: {dict(totals)}")
    for code, c in sorted(by_flow.items()):
        title = dict(FLOWS)[code]
        print(f"  {code:3} {sum(c.values()):4}  pass={c['PASS']:4} fail={c['FAIL']:3}  {title}")


def _esc(text: str) -> str:
    for old, new in (("\\", r"\textbackslash{}"), ("_", r"\_"), ("&", r"\&"),
                     ("%", r"\%"), ("#", r"\#"), ("$", r"\$")):
        text = text.replace(old, new)
    # Test names and failure messages are long tokens with no spaces: without an explicit
    # break opportunity they run straight into the margin.
    for old, new in ((r"\_", "\\_\\allowbreak{}"), (".", ".\\allowbreak{}"),
                     (")", ")\\allowbreak{}"), ("/", "/\\allowbreak{}"),
                     (",", ",\\allowbreak{}")):
        text = text.replace(old, new)
    return text


def write_latex(summary: dict, rows: list[dict]) -> None:
    """Emit the results tables as LaTeX, generated from the same data as the CSV.

    Generated rather than typed: a hand-written results table is a second source of truth,
    and the first thing it does is disagree with the evidence.
    """
    total = summary["total"]
    res = summary["por_resultado"]
    suite = summary["por_suite"]
    files = len({r["archivo"] for r in rows})
    macros = [
        "% GENERADO POR docs/entrega_qe/build_matriz.py -- no editar a mano.",
        f"\\newcommand{{\\QEtot}}{{{total}}}",
        f"\\newcommand{{\\QEpass}}{{{res.get('PASS', 0)}}}",
        f"\\newcommand{{\\QEfail}}{{{res.get('FAIL', 0) + res.get('ERROR', 0)}}}",
        f"\\newcommand{{\\QEskip}}{{{res.get('SKIP', 0)}}}",
        f"\\newcommand{{\\QEbackend}}{{{suite.get('backend', 0)}}}",
        f"\\newcommand{{\\QEfrontend}}{{{suite.get('frontend', 0)}}}",
        f"\\newcommand{{\\QEfiles}}{{{files}}}",
        f"\\newcommand{{\\QEflows}}{{{len(summary['por_flujo'])}}}",
    ]
    # Written separately so the report can use the numbers in its preamble-level summary
    # before the tables themselves are input further down.
    (OUT / "metricas_generadas.tex").write_text("\n".join(macros) + "\n", encoding="utf-8")

    lines = [
        r"\begin{center}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"\textbf{Resultado} & \textbf{Casos} & \textbf{\%} & \\",
        r"\midrule",
    ]
    for key, label in (("PASS", "Correctos (PASS)"), ("FAIL", "Fallidos (FAIL)"),
                       ("ERROR", "Errores"), ("SKIP", "Omitidos (SKIP)")):
        count = res.get(key, 0)
        if not count and key in ("ERROR",):
            continue
        lines.append(f"{label} & {count} & {100.0 * count / total:.1f} & \\\\")
    lines += [
        r"\midrule",
        f"\\textbf{{Total ejecutado}} & \\textbf{{{total}}} & \\textbf{{100{{,}}0}} & \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{center}",
        "",
        r"\begin{center}",
        r"\begin{longtable}{p{1.1cm} p{6.6cm} r r r}",
        r"\toprule",
        r"\textbf{Flujo} & \textbf{Nombre} & \textbf{Casos} & \textbf{PASS} & \textbf{FAIL} \\",
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        r"\textbf{Flujo} & \textbf{Nombre} & \textbf{Casos} & \textbf{PASS} & \textbf{FAIL} \\",
        r"\midrule",
        r"\endhead",
    ]
    for code, data in summary["por_flujo"].items():
        fail = data.get("FAIL", 0) + data.get("ERROR", 0)
        name = _esc(data["titulo"]).replace("→", r"$\rightarrow$")
        lines.append(f"\\textbf{{{code}}} & {name} & {data['total']} & {data.get('PASS', 0)} & {fail} \\\\")
    lines += [r"\bottomrule", r"\end{longtable}", r"\end{center}", ""]

    failing = [r for r in rows if r["resultado"] in ("FAIL", "ERROR")]
    if failing:
        lines += [
            r"\noindent\textbf{Casos no superados en la última ejecución:}",
            r"\begin{center}",
            r"\footnotesize",
            r"\begin{longtable}{>{\raggedright\arraybackslash}p{1.5cm} >{\raggedright\arraybackslash}p{9.4cm}}",
            r"\toprule",
            r"\textbf{ID} & \textbf{Motivo reportado por el ejecutor} \\",
            r"\midrule",
            r"\endfirsthead",
            r"\toprule",
            r"\textbf{ID} & \textbf{Motivo reportado por el ejecutor} \\",
            r"\midrule",
            r"\endhead",
        ]
        for row in failing[:60]:
            # Truncate BEFORE escaping. Slicing escaped text can cut a LaTeX command in
            # half and produce an undefined control sequence at compile time.
            reason = (row["detalle"] or "--")[:110]
            det = _esc(reason)
            lines.append(f"\\code{{{row['id']}}} & {det} \\\\")
        lines += [r"\bottomrule", r"\end{longtable}", r"\end{center}", ""]

    (OUT / "resultados_generados.tex").write_text("\n".join(lines), encoding="utf-8")



if __name__ == "__main__":
    main()
