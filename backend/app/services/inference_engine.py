"""InferenceEngine: blueprint (with its input interface) -> ArchitecturePlan.

Deterministic rules, no model calls. Each decision records a human-readable reason
so the plan is auditable and debuggable. Preferences on the input interface win
when valid; otherwise the engine infers from the throughput/data/integration
signals. This is the "inferir extensiones / librerías / tipo de DB" step of the
reframing.
"""
from __future__ import annotations

from typing import List, Optional

from app.models.architecture_plan import ArchitecturePlan
from app.models.blueprint import ArchitectureBlueprint, InputInterface
from app.services import architecture_catalog as catalog


def _pick(value: Optional[str], allowed: List[str]) -> Optional[str]:
    """Return value if it is in allowed, else None."""
    if value is None:
        return None
    return value if value in allowed else None


def infer_architecture(blueprint: ArchitectureBlueprint) -> ArchitecturePlan:
    iface: Optional[InputInterface] = blueprint.inputInterface

    reasons: List[str] = []

    # --- 1. Profile ("primero la arquitectura") ---
    preference = _pick(iface.architecturePreference if iface else None, catalog.profile_names())
    if preference:
        profile = preference
        reasons.append(f"arquitectura elegida explícitamente: {profile}")
    else:
        integrations = (iface.integrations if iface else []) or []
        data_needs = (iface.dataNeeds if iface else []) or []
        consistency = (iface.consistency if iface else "strong")
        has_integrations = bool(integrations) and "none" not in integrations
        if has_integrations or "document" in data_needs or consistency == "eventual":
            profile = "hexagonal"
            reasons.append(
                "se infiere hexagonal: integraciones/eventualidad sugieren puertos y adaptadores"
            )
        else:
            profile = "layered"
            reasons.append("se infiere layered: caso CRUD sin integraciones")

    # --- 2. Build tool (elegible) ---
    build_pref = _pick(iface.buildToolPreference if iface else None, ["maven", "gradle"])
    build_tool = build_pref or catalog.build_tool_for(profile)
    if build_pref:
        reasons.append(f"build tool elegido explícitamente: {build_tool}")

    # --- 3. Database type (volumen + necesidades de datos) ---
    if iface is None:
        # Sin interfaz de entrada: se mantiene el databaseMode del blueprint (no rompe
        # el comportamiento actual, que genera Postgres por defecto).
        database_type = "postgresql" if blueprint.databaseMode.lower().startswith("postgres") else "h2"
        reasons.append(f"sin interfaz de entrada; se mantiene {database_type} del blueprint")
    else:
        data_needs = iface.dataNeeds or []
        volume = iface.requestVolume or "low"

        if "document" in data_needs:
            # Document store no está en la lista blanca offline; degradar con nota.
            database_type = "postgresql"
            reasons.append(
                "dataNeeds incluye 'document'; no hay store documental offline — se degrada a postgresql"
            )
        elif volume == "high":
            database_type = "postgresql"
            reasons.append("volumen alto -> base relacional duradera (postgresql)")
        elif volume == "medium":
            database_type = "postgresql"
            reasons.append("volumen medio -> base relacional durable (postgresql)")
        else:
            database_type = "h2"
            reasons.append("volumen bajo -> base en memoria (h2) para build hermético")

    # --- 4. Libraries (inferir librerías, dentro de la lista blanca) ---
    libraries = list(catalog.ALLOWED_DEPENDENCIES["web"])  # web + validation siempre
    libraries.append("spring-boot-starter-data-jpa")
    libraries.append(database_type)  # driver h2 o postgresql
    libraries.extend(catalog.ALLOWED_DEPENDENCIES["test"])

    if "cache" in data_needs:
        reasons.append("dataNeeds incluye 'cache': sin librería en lista blanca offline — omitida")

    # --- 5. Modules ("capa X en proyecto Y") ---
    modules = catalog.modules_for(profile)

    return ArchitecturePlan(
        profile=profile,
        buildTool=build_tool,
        databaseType=database_type,
        modules=modules,
        libraries=libraries,
        reasons=reasons,
    )
