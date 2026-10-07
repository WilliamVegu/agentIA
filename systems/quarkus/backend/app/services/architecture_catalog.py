"""ArchitectureCatalog: named architecture profiles as data.

Each profile declares, declaratively, what the Scaffolder must produce: the module
layout ("capa X en proyecto Y"), the build tool, and the modules in dependency
order. This is the "catálogo de arquitecturas" from the reframing plan; adding a
new architecture is a data change, not a code change.
"""
from __future__ import annotations

from typing import Any, Dict, List


# Allowed libraries per capability, constrained to what the offline build can
# resolve from the pre-populated Maven cache. Anything else is a violation.
ALLOWED_DEPENDENCIES: Dict[str, List[str]] = {
    "web": ["spring-boot-starter-web", "spring-boot-starter-validation"],
    "persistence": ["spring-boot-starter-data-jpa", "h2", "postgresql"],
    "test": ["spring-boot-starter-test"],
}

ARCHITECTURE_PROFILES: Dict[str, Dict[str, Any]] = {
    "layered": {
        "modules": ["controller", "service", "repository", "model"],
        "build_tool": "maven",
        "description": "Clásica 4 capas unidireccional (Spring Boot)",
    },
    "hexagonal": {
        "modules": ["domain", "application", "infrastructure", "adapter-in/rest", "adapter-out/db"],
        "build_tool": "maven",
        "description": "Puertos y adaptadores; la infraestructura vive en sus adaptadores",
    },
    "hexagonal-ddd": {
        "modules": [
            "domain",
            "application",
            "infrastructure",
            "adapter-in/rest",
            "adapter-out/db",
            "bounded-contexts",
        ],
        "build_tool": "maven",
        "description": "Hexagonal + DDD: bounded contexts, agregados y value objects",
    },
}


def profile_names() -> List[str]:
    return list(ARCHITECTURE_PROFILES.keys())


def get_profile(name: str) -> Dict[str, Any]:
    if name not in ARCHITECTURE_PROFILES:
        raise KeyError(f"Unknown architecture profile: {name!r}. Known: {profile_names()}")
    return ARCHITECTURE_PROFILES[name]


def modules_for(name: str) -> List[str]:
    return list(get_profile(name)["modules"])


def build_tool_for(name: str) -> str:
    return get_profile(name)["build_tool"]
