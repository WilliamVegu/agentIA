"""Tests for the naming-conventions rule (levantando_observaciones item 5)."""
from app.services.conformance_diagnostics import (
    RULE_NAMING_CONVENTION,
    check_naming_conventions,
    diagnose,
)

ENTITY = "src/main/java/com/corp/x/model/entity/%s.java"
DTO = "src/main/java/com/corp/x/model/dto/%s.java"


def ids(violations):
    return [v.rule_id for v in violations]


def test_entity_pascal_singular_clean():
    files = {ENTITY % "Order": "@Entity\npublic class Order { private Long id; }"}
    assert check_naming_conventions(files) == []


def test_entity_plural_flagged():
    files = {ENTITY % "Orders": "@Entity\npublic class Orders { private Long id; }"}
    v = check_naming_conventions(files)
    assert RULE_NAMING_CONVENTION in ids(v)


def test_entity_not_pascal_flagged():
    files = {ENTITY % "order": "@Entity\npublic class order { private Long id; }"}
    v = check_naming_conventions(files)
    assert RULE_NAMING_CONVENTION in ids(v)


def test_plural_allowlist_not_flagged():
    files = {ENTITY % "Address": "@Entity\npublic class Address { private Long id; }"}
    assert check_naming_conventions(files) == []


def test_dto_without_suffix_flagged():
    files = {DTO % "Order": "public record Order(String id) {}"}
    v = check_naming_conventions(files)
    assert RULE_NAMING_CONVENTION in ids(v)


def test_dto_with_request_suffix_clean():
    files = {DTO % "OrderRequest": "public record OrderRequest(String id) {}"}
    assert check_naming_conventions(files) == []


def test_field_snake_case_flagged():
    files = {ENTITY % "Order": "@Entity\npublic class Order { private Long customer_id; }"}
    v = check_naming_conventions(files)
    assert RULE_NAMING_CONVENTION in ids(v)


def test_field_camel_case_clean():
    files = {ENTITY % "Order": "@Entity\npublic class Order { private Long customerId; }"}
    assert check_naming_conventions(files) == []


def test_constants_exempt():
    files = {ENTITY % "Order": "@Entity\npublic class Order { private static final long serialVersionUID = 1L; }"}
    assert check_naming_conventions(files) == []


def test_naming_surfaces_in_diagnose():
    files = {
        "pom.xml": "<project></project>",
        ENTITY % "Orders": "@Entity\npublic class Orders { private Long customer_id; }",
    }
    report = diagnose(files)
    assert RULE_NAMING_CONVENTION in report.rule_histogram
