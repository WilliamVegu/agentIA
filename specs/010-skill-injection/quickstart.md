# Quickstart & Validation Guide: Skill Injection Pilot Assets

**Feature**: Finalize Skill Domain Set and Author Seed Skill Documents  
**Branch**: `010-skill-injection`  

---

## 1. Overview of Artifacts to Validate

| Artifact | Location | Expected Content |
| :--- | :--- | :--- |
| **Domain Triage Catalog** | `specs/010-skill-injection/domains.md` | Finalized triage of all 5 domains citing Task 0 numbers. |
| **Seed Skills** | `backend/app/resources/skills/*.md` | `layer_architecture.md`, `exception_handling.md`, `mockito_tests.md`. |
| **Deterministic Fixer Spec** | `specs/010-skill-injection/fixers.md` | Complete engineering spec for `jakarta_namespace` and `maven_pom`. |
| **Executive Summary** | `specs/010-skill-injection/task1-summary.md` | Survival tallies, token stats, and resolutions to the 3 decisions. |

---

## 2. Validation Checklist

### A. Format & Linter Checks
Run the automated skill validator script (authored in task execution):
```bash
python3 backend/scripts/validate_seed_skills.py
```

*Expected Verification*:
- [ ] Each skill file has `# Title`.
- [ ] Each skill file has `## Granularity` (`task-level` or `event-driven`).
- [ ] Each skill file has `## When to apply` with zero instance-specific literals.
- [ ] Each skill file has ordered numbered rules starting with imperative verbs.
- [ ] Each skill file contains an empty `<!-- SLOW_UPDATE_START -->` / `<!-- SLOW_UPDATE_END -->` block.
- [ ] Each skill file contains < 500 tokens.
- [ ] The entire set contains < 2,000 tokens combined.

### B. Domain Triage Integrity
- [ ] 5 domains evaluated (`jakarta_namespace`, `layer_architecture`, `exception_handling`, `maven_pom`, `mockito_tests`).
- [ ] Exact numbers cited from `reports/009-historical-baseline.md` (e.g., 28 verified, 16 blocked, 4 failed).
- [ ] Zero domains left unclassified.

### C. Decision Resolutions
- [ ] Decision 1 (Dual representation) explicitly resolved with technical rationale.
- [ ] Decision 2 (Task-level vs event-driven granularity) explicitly assigned per domain.
- [ ] Decision 3 (Pilot viability threshold) verified against minimum survival criteria.
