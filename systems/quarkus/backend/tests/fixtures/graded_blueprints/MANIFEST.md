# Graded blueprint corpus

A graded difficulty series for the microservice generator, meant to be swept from trivial to
very hard so the point where generation behaviour degrades can be located by bisection rather
than by guesswork. Twelve new blueprints, three per tier, each tier a visibly larger step than
the one below it.

All twelve load through the repository's own loader unchanged:
`ArchitectureBlueprint.model_validate(payload)` followed by
`app.services.spec_service.validate_blueprint(blueprint)` returns **0 warnings** for every file.

Unknown top-level keys (`blueprintId`, `tier`, `corpusRole`, `difficultyAxis`, `rationale`) are
ignored by the loader, exactly as in the existing corpora.

---

## Tier envelopes

| Tier | Entities | Attributes per entity | Stories | Scenarios | Operation set | Relationships |
|---|---|---|---|---|---|---|
| 1 — trivial | 1 | 3–5 | 1–2 | 2–3 | create + read | none |
| 2 — simple | 2 | 4–6 | 2–3 | 4–6 | create + read | exactly one foreign key |
| 3 — moderate | 3–4 | 6–10 | 3–5 | 6–12 | full CRUD | real, incl. at least one child-of-child, one validation-heavy entity |
| 4 — hard | 5–7 | 6–14, at least one entity with 10–14 | 6–8 | 12–20 | CRUD + collection reads | referential depth ≥ 3 hops, plus one layering/contract trap |

Visible step between adjacent tiers:

- **1 → 2**: a second entity appears, a foreign key appears, declared `validationRules` appear for
  the first time (tier 1 has none at all).
- **2 → 3**: `update` and `delete` appear for the first time, entity count rises to 3–4, a
  validation-heavy entity appears, scenario count roughly doubles.
- **3 → 4**: entity count rises to 5–7, referential depth goes to three hops
  (`Booking → RatePlan → Hotel → Destination`), at least one entity reaches 10–14 attributes, and
  every tier 4 file carries an explicit trap axis (nested names, type-mapping breadth, or
  cross-aggregate invariants).

## Graded blueprints

| File | Tier | Service | Entities | Attributes | Max/entity | Stories | Scenarios | Unhappy paths | The one thing that makes it that tier |
|---|---|---|---|---|---|---|---|---|---|
| [tier1-01.json](tier1-01.json) | 1 | todo-service | 1 | 3 | 3 | 1 | 2 | 0 | Floor of the scale: one entity, three attributes, no relationship, no validation rule. |
| [tier1-02.json](tier1-02.json) | 1 | tag-service | 1 | 4 | 4 | 2 | 2 | 0 | Adds a second story and a temporal attribute, so the per-story loop runs more than once. |
| [tier1-03.json](tier1-03.json) | 1 | bookmark-service | 1 | 5 | 5 | 2 | 3 | 0 | Widest trivial entity (five attributes, four Java types) and the full tier 1 scenario budget. |
| [tier2-01.json](tier2-01.json) | 2 | library-service | 2 | 11 | 6 | 2 | 4 | 2 | First foreign key (`Book.authorId → Author.id`) and first declared validation rules. |
| [tier2-02.json](tier2-02.json) | 2 | inventory-service | 2 | 11 | 6 | 3 | 5 | 3 | Adds a collection-returning read scoped by the foreign key and the empty-collection rule. |
| [tier2-03.json](tier2-03.json) | 2 | helpdesk-service | 2 | 11 | 6 | 3 | 6 | 4 | Top of tier 2: a format rule (`@Email`) and a service-level rejection for an unknown parent. |
| [tier3-01.json](tier3-01.json) | 3 | course-service | 3 | 21 | 8 | 4 | 9 | 5 | First CRUD tier: update and delete appear, and a two-level chain `Instructor ← Course ← Enrollment`. |
| [tier3-02.json](tier3-02.json) | 3 | expense-service | 4 | 30 | 10 | 5 | 11 | 7 | Four entities, two foreign keys on one child, and a 10-attribute validation-heavy claim with a status transition that only update can express. |
| [tier3-03.json](tier3-03.json) | 3 | parcel-service | 4 | 30 | 10 | 5 | 12 | 7 | Ceiling of tier 3: two chains into one aggregate (`Depot → Parcel → DeliveryAttempt`, `Recipient → Parcel`) and the full scenario budget. |
| [tier4-01.json](tier4-01.json) | 4 | fulfillment-service | 6 | 41 | 10 | 7 | 15 | 9 | **Trap axis — nested names / layering**: `Shipment`, `ShipmentItem`, `ShipmentItemAdjustment` share a prefix, tempting one controller per prefix or a service injected into a service instead of one repository per entity. |
| [tier4-02.json](tier4-02.json) | 4 | warranty-service | 5 | 41 | 14 | 6 | 14 | 8 | **Trap axis — contract/type mapping**: a 14-attribute entity spanning every type family, including `List<String>` and BigDecimal/Double and LocalDate/LocalDateTime pairs that map differently; tempts collapsing types or validating the transport object instead of the model. |
| [tier4-03.json](tier4-03.json) | 4 | travel-service | 6 | 46 | 12 | 8 | 18 | 10 | **Trap axis — cross-aggregate invariants**: a booking is valid only relative to a rate plan, its hotel and that hotel's cancellation policy, so the rule needs at least two loaded aggregates; tempts putting the invariant in the controller or calling the service's own HTTP endpoints. |

`Attributes` is the sum over all entities; `Max/entity` is the widest single entity.
`Unhappy paths` counts scenarios whose outcome is a refusal, a not-found, an inconsistency or an
empty collection.

## The existing corpora mapped onto the same scale

Read with the same envelopes as above, so all 27 blueprints are comparable in one place.

| File | Corpus | Mapped tier | Service | Entities | Attributes | Max/entity | Stories | Scenarios | Note on the mapping |
|---|---|---|---|---|---|---|---|---|---|
| minimal.json | baseline | 1 | notes-service | 1 | 2 | 2 | 1 | 1 | Below the tier 1 floor on every axis (two attributes, one scenario); the true minimum the schema accepts. |
| pair-a.json | baseline | 1 | invoice-service | 1 | 3 | 3 | 1 | 1 | Squarely tier 1. |
| pair-b.json | baseline | 1–2 | invoice-service | 1 | 3 | 3 | 1 | 4 | Scenario-only variant of pair-a: scenario count is tier 2, everything else is tier 1. |
| multi-entity.json | baseline | 2 | catalog-service | 2 | 8 | 4 | 2 | 4 | Two entities and tier 2 counts, but **no declared foreign key** — tier2-01 is the first blueprint here with a real relation. |
| constrained.json | baseline | 2 | member-service | 1 | 5 | 5 | 3 | 6 | One entity only, but six scenarios and a full validation vocabulary; sits at the top of tier 2 rather than in tier 3. |
| hard-04.json | hard | 4 | billing-service | 4 | 25 | 7 | 6 | 16 | Tier 4 envelope. |
| hard-05.json | hard | 4 | audit-service | 4 | 24 | 8 | 7 | 17 | Tier 4 envelope. |
| hard-06.json | hard | 4+ | subscription-service | 4 | 26 | 8 | 8 | 22 | Tier 4 in entities and attributes, but 22 scenarios exceed the tier 4 budget (12–20). |
| hard-02.json | hard | 4 | policy-service | 4 | 38 | 14 | 6 | 17 | Tier 4, including a 14-attribute entity and a collection attribute — same width axis as tier4-02. |
| hard-03.json | hard | 4 | order-service | 6 | 35 | 6 | 7 | 16 | Tier 4, prefix-colliding names — same layering axis as tier4-01. |
| hard-07.json | hard | 4 | billing-cycle-service | 5 | 33 | 9 | 8 | 18 | Tier 4 envelope. |
| hard-01.json | hard | 4 | logistics-service | 7 | 51 | 9 | 8 | 20 | Tier 4 at its exact ceiling (7 entities, 8 stories, 20 scenarios). |
| hard-08.json | hard | beyond 4 | clinic-service | 8 | 54 | 8 | 10 | 26 | Exceeds the tier 4 envelope on entities (8), stories (10) and scenarios (26). |
| hard-09.json | hard | beyond 4 | booking-service | 6 | 38 | 10 | 10 | 29 | Exceeds the tier 4 envelope on stories (10) and scenarios (29); invariant-heavy like tier4-03. |
| hard-10.json | hard | beyond 4 | identity-service | 5 | 32 | 7 | 10 | 26 | Exceeds the tier 4 envelope on stories (10) and scenarios (26). |

### What the mapping says

- The **graded set covers the baseline corpus comfortably**: tier 1 is at or below `pair-a`, and
  tier 2 envelops `multi-entity` and `constrained`.
- **Tier 4 is calibrated to the bulk of the hard corpus**: `hard-01`, `hard-02`, `hard-03`,
  `hard-04`, `hard-05` and `hard-07` land inside the tier 4 envelope, and tier4-01/02/03 reuse
  their three axes (nested names, attribute width, invariants/unhappy paths).
- **`hard-08`, `hard-09` and `hard-10` sit past the top of the graded scale** on story and
  scenario count. The graded series therefore ends where the existing hard corpus starts to
  overrun, not above it; a sweep that still passes all of tier 1–4 has not yet reached those
  three fixtures.

## How to sweep

1. Run the corpus in file order (`tier1-01` … `tier4-03`). The counts increase monotonically
   within each axis, so the first failure in order is the tier boundary.
2. To localise inside a tier, compare the three files: tier 1 by attribute width, tier 2 by
   scenario count, tier 3 by entity count, tier 4 by trap axis.
3. A generator that passes tier 1 and fails tier 2 is failing on relations, declared validation
   rules, or multiplicity — not on scale.
4. No network or model call is needed to consume this corpus; the files are inert JSON.
