from app.services.generated_code_fixes import fix_invalid_type_constraints


def test_numeric_record_component_never_removes_annotated_string_component():
    source="""public record Entry(
    @NotBlank @Email String email,
    @NotNull @Positive java.math.BigDecimal balance,
    @NotNull java.time.Instant bookedAt
) {}"""
    fixed,changes=fix_invalid_type_constraints(source)
    assert fixed==source
    assert changes==[]


def test_invalid_inline_record_constraint_preserves_its_component():
    fixed,changes=fix_invalid_type_constraints('public record Entry(@NotBlank java.util.UUID entryId) {}')
    assert '@NotBlank' not in fixed
    assert 'java.util.UUID entryId' in fixed
    assert changes
