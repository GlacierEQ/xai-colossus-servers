from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

REQUIRED_PATHS = (
    "src/rack_planner.py",
    "tests/test_rack_planner.py",
    "tests/test_portfolio_truth_surface.py",
    "scripts/ci/verify_portfolio_core.sh",
)

FORBIDDEN_STALE_CLAIMS = (
    "src/server_manager.py",
    "100,000+ GPU datacenters",
    "Rack topology discovery",
    "Hardware inventory tracking",
    "Automated node remediation",
    "Telemetry aggregation",
    "server_node_status()",
    "Fully connected to APEX Highway mesh",
    "99.9%+ cluster availability",
)


def test_readme_points_to_present_core_paths() -> None:
    text = README.read_text(encoding="utf-8")

    for relative_path in REQUIRED_PATHS:
        assert (ROOT / relative_path).exists(), relative_path
        assert relative_path in text


def test_readme_preserves_non_affiliation_and_scenario_boundaries() -> None:
    text = README.read_text(encoding="utf-8")

    assert "not affiliated with xAI" in text
    assert "not evidence of deployment" in text
    assert "deterministic scenario heuristic" in text
    assert "not an optimizer" in text
    assert "does not measure power" in text
    assert "does not authorize physical installation" in text


def test_readme_does_not_count_private_experiments_as_verified() -> None:
    text = README.read_text(encoding="utf-8")

    assert "0544f70c9a9cb3ac5c170bb308781716e2c00bd5" in text
    assert "7b12a0234041b316bad5c878733bc0a217aa9aaf" in text
    assert "not** counted as verified components" in text
    assert "No source is deleted or collapsed" in text


def test_stale_hardware_and_integration_claims_do_not_return() -> None:
    text = README.read_text(encoding="utf-8")

    for stale_claim in FORBIDDEN_STALE_CLAIMS:
        assert stale_claim not in text


def test_theatrical_answer_field_is_removed_from_public_planner() -> None:
    planner = (ROOT / "src" / "rack_planner.py").read_text(encoding="utf-8")

    assert "ANSWER = 42" not in planner
    assert '"answer"' not in planner
