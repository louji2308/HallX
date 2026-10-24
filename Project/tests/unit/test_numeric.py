from hallx.validation.numeric import (
    check_numeric_consistency,
    extract_numbers,
    parse_declared,
)


def test_matching_number_and_unit_passes() -> None:
    assert (
        check_numeric_consistency(
            "The retention period is 30 days.",
            "Retention is 30 days.",
            ["30 days"],
        )
        == ()
    )


def test_declared_value_missing_from_quote_fails() -> None:
    mismatches = check_numeric_consistency(
        "The retention period is 90 days.",
        "The retention period is 30 days.",
        ["90 days"],
    )
    assert {mismatch.kind for mismatch in mismatches} >= {
        "DECLARED_NOT_IN_QUOTE",
        "CLAIM_NUMBER_NOT_IN_QUOTE",
    }


def test_unit_mismatch_fails() -> None:
    mismatches = check_numeric_consistency(
        "The retention period is 90 days.",
        "The retention period is 90 months.",
        ["90 days"],
    )
    assert mismatches


def test_extract_numbers_normalizes_separators_and_percent() -> None:
    values = extract_numbers("1,200 users and 3.5% growth")
    assert values[0].key() == ("1200", "users")
    assert values[1].key() == ("3.5", "percent")


def test_parse_declared() -> None:
    parsed = parse_declared("30 days")
    assert parsed is not None
    assert parsed.key() == ("30", "days")
