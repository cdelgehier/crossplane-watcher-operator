import pytest

from cwo.notifier import compute_hash, format_comment

# ---------------------------------------------------------------------------
# format_comment
# ---------------------------------------------------------------------------


def test_format_comment_contains_resource_identity(sample_conditions):
    result = format_comment(
        "XStackVM", "monapp-vm", "eu1-dev-monapp", "abc123", sample_conditions, {}
    )
    assert "XStackVM/monapp-vm" in result
    assert "eu1-dev-monapp" in result
    assert "abc123" in result


@pytest.mark.parametrize(
    "conditions, expected_emoji, expected_type",
    [
        (
            [{"type": "Ready", "status": "True", "reason": "Available", "message": ""}],
            "✅",
            "Ready",
        ),
        (
            [{"type": "Synced", "status": "True", "reason": "ReconcileSuccess", "message": ""}],
            "✅",
            "Synced",
        ),
        (
            [{"type": "Ready", "status": "False", "reason": "ReconcilePending", "message": ""}],
            "⏳",
            "Ready",
        ),
        (
            [{"type": "Ready", "status": "False", "reason": "ReconcileError", "message": "err"}],
            "❌",
            "Ready",
        ),
        (
            [{"type": "Synced", "status": "False", "reason": "ReconcileError", "message": ""}],
            "⚠️",
            "Synced",
        ),
        (
            [{"type": "CustomCondition", "status": "Unknown", "reason": "Checking", "message": ""}],
            "🔵",
            "CustomCondition",
        ),
    ],
)
def test_format_comment_emoji(conditions, expected_emoji, expected_type):
    result = format_comment("XStackVM", "monapp-vm", "ns", "sha", conditions, {})
    assert f"{expected_emoji} {expected_type}" in result


@pytest.mark.parametrize("kind", ["XStackVM", "XS3Bucket", "XSecurityGroup"])
def test_format_comment_various_kinds(kind, sample_conditions):
    result = format_comment(kind, "my-res", "ns", "sha", sample_conditions, {})
    assert kind in result


def test_format_comment_error_message_appears_in_table(error_conditions):
    result = format_comment("XStackVM", "monapp-vm", "ns", "abc123", error_conditions, {})
    assert "terraform apply failed" in result


def test_format_comment_full_status_is_collapsible(sample_conditions):
    result = format_comment(
        "XStackVM", "monapp-vm", "ns", "abc123", sample_conditions, {"ready": True}
    )
    assert "<details>" in result
    assert "<summary>Full status</summary>" in result


def test_format_comment_full_status_contains_yaml_fields(sample_conditions):
    status = {"atProvider": {"instanceId": "i-1234"}}
    result = format_comment("XStackVM", "monapp-vm", "ns", "abc123", sample_conditions, status)
    assert "instanceId" in result
    assert "i-1234" in result


def test_format_comment_empty_conditions_renders_placeholder():
    result = format_comment("XStackVM", "monapp-vm", "ns", "abc123", [], {})
    assert "—" in result


# ---------------------------------------------------------------------------
# compute_hash
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "conditions_a, conditions_b, should_match",
    [
        # same state → same hash
        (
            [{"type": "Ready", "status": "True", "reason": "Available", "message": ""}],
            [{"type": "Ready", "status": "True", "reason": "Available", "message": ""}],
            True,
        ),
        # different status → different hash
        (
            [{"type": "Ready", "status": "True", "reason": "Available", "message": ""}],
            [{"type": "Ready", "status": "False", "reason": "ReconcilePending", "message": ""}],
            False,
        ),
        # different reason → different hash
        (
            [{"type": "Ready", "status": "False", "reason": "ReconcilePending", "message": ""}],
            [{"type": "Ready", "status": "False", "reason": "ReconcileError", "message": ""}],
            False,
        ),
        # different message → same hash (anti-spam: messages are ignored)
        (
            [
                {
                    "type": "Ready",
                    "status": "True",
                    "reason": "Available",
                    "message": "done at 10:00",
                }
            ],
            [
                {
                    "type": "Ready",
                    "status": "True",
                    "reason": "Available",
                    "message": "done at 11:00",
                }
            ],
            True,
        ),
        # non-Ready/Synced condition added → same hash (ignored)
        (
            [{"type": "Ready", "status": "True", "reason": "Available", "message": ""}],
            [
                {"type": "Ready", "status": "True", "reason": "Available", "message": ""},
                {
                    "type": "CustomCondition",
                    "status": "Unknown",
                    "reason": "Checking",
                    "message": "",
                },
            ],
            True,
        ),
    ],
)
def test_compute_hash_comparison(conditions_a, conditions_b, should_match):
    if should_match:
        assert compute_hash(conditions_a) == compute_hash(conditions_b)
    else:
        assert compute_hash(conditions_a) != compute_hash(conditions_b)


def test_compute_hash_returns_12_char_string(sample_conditions):
    h = compute_hash(sample_conditions)
    assert isinstance(h, str)
    assert len(h) == 12


def test_compute_hash_empty_conditions_is_stable():
    assert compute_hash([]) == compute_hash([])


def test_compute_hash_order_of_conditions_does_not_matter():
    a = [
        {"type": "Ready", "status": "True", "reason": "Available", "message": ""},
        {"type": "Synced", "status": "True", "reason": "ReconcileSuccess", "message": ""},
    ]
    b = list(reversed(a))
    assert compute_hash(a) == compute_hash(b)
