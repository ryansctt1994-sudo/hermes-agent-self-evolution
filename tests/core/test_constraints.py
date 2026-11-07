"""Tests for constraint validators."""

import sys
from pathlib import Path

import pytest
from evolution.core.constraints import ConstraintValidator
from evolution.core.config import EvolutionConfig


@pytest.fixture
def validator(tmp_path):
    # Constraint checks don't touch the hermes-agent checkout, so point the
    # config at a temp dir instead of requiring a real install.
    config = EvolutionConfig(hermes_agent_path=tmp_path)
    return ConstraintValidator(config)


class TestSizeConstraints:
    def test_skill_under_limit(self, validator):
        result = validator._check_size("x" * 1000, "skill")
        assert result.passed

    def test_skill_over_limit(self, validator):
        result = validator._check_size("x" * 20_000, "skill")
        assert not result.passed
        assert "exceeded" in result.message

    def test_tool_description_under_limit(self, validator):
        result = validator._check_size("Search files by content", "tool_description")
        assert result.passed

    def test_tool_description_over_limit(self, validator):
        result = validator._check_size("x" * 600, "tool_description")
        assert not result.passed


class TestGrowthConstraints:
    def test_acceptable_growth(self, validator):
        baseline = "x" * 1000
        evolved = "x" * 1100  # 10% growth
        result = validator._check_growth(evolved, baseline, "skill")
        assert result.passed

    def test_excessive_growth(self, validator):
        baseline = "x" * 1000
        evolved = "x" * 1300  # 30% growth
        result = validator._check_growth(evolved, baseline, "skill")
        assert not result.passed

    def test_shrinkage_is_ok(self, validator):
        baseline = "x" * 1000
        evolved = "x" * 800  # 20% smaller
        result = validator._check_growth(evolved, baseline, "skill")
        assert result.passed


class TestNonEmpty:
    def test_non_empty_passes(self, validator):
        result = validator._check_non_empty("some content")
        assert result.passed

    def test_empty_fails(self, validator):
        result = validator._check_non_empty("")
        assert not result.passed

    def test_whitespace_only_fails(self, validator):
        result = validator._check_non_empty("   \n  ")
        assert not result.passed


class TestSkillStructure:
    def test_valid_skill(self, validator):
        skill = "---\nname: test-skill\ndescription: A test skill\n---\n\n# Test\nContent here"
        result = validator._check_skill_structure(skill)
        assert result.passed

    def test_missing_frontmatter(self, validator):
        skill = "# Test\nContent without frontmatter"
        result = validator._check_skill_structure(skill)
        assert not result.passed

    def test_missing_name(self, validator):
        skill = "---\ndescription: A test skill\n---\n\n# Test"
        result = validator._check_skill_structure(skill)
        assert not result.passed

    def test_missing_description(self, validator):
        skill = "---\nname: test-skill\n---\n\n# Test"
        result = validator._check_skill_structure(skill)
        assert not result.passed


class TestValidateAll:
    def test_valid_skill_passes_all(self, validator):
        skill = "---\nname: test\ndescription: Test skill\n---\n\n# Procedure\n1. Do thing"
        results = validator.validate_all(skill, "skill")
        assert all(r.passed for r in results)

    def test_empty_skill_fails(self, validator):
        results = validator.validate_all("", "skill")
        failed = [r for r in results if not r.passed]
        assert len(failed) > 0


SKILL_REL = Path("skills") / "demo" / "SKILL.md"
GOOD_SKILL = "---\nname: demo\ndescription: Demo skill\n---\n\n# Procedure\n1. Do thing\n"


@pytest.fixture
def fake_hermes(tmp_path):
    """A minimal hermes-agent checkout whose own test checks the skill file."""
    repo = tmp_path / "hermes-agent"
    (repo / SKILL_REL.parent).mkdir(parents=True)
    (repo / SKILL_REL).write_text(GOOD_SKILL)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_skills.py").write_text(
        "from pathlib import Path\n"
        "def test_skill_has_frontmatter():\n"
        f"    text = Path({str(SKILL_REL)!r}).read_text()\n"
        "    assert text.startswith('---') and 'BROKEN' not in text\n"
    )
    return repo


class TestTestSuiteGate:
    """--run-tests: hermes-agent's suite runs on a scratch copy with the artifact in place."""

    def test_passing_artifact_passes(self, validator, fake_hermes):
        result = validator.run_test_suite_with_artifact(fake_hermes, SKILL_REL, GOOD_SKILL, python=sys.executable)
        assert result.passed, result.details

    def test_breaking_artifact_fails(self, validator, fake_hermes):
        result = validator.run_test_suite_with_artifact(fake_hermes, SKILL_REL, GOOD_SKILL + "BROKEN\n", python=sys.executable)
        assert not result.passed
        assert result.constraint_name == "test_suite"

    def test_real_checkout_is_never_modified(self, validator, fake_hermes):
        before = {p: p.read_bytes() for p in fake_hermes.rglob("*") if p.is_file()}
        validator.run_test_suite_with_artifact(fake_hermes, SKILL_REL, GOOD_SKILL + "BROKEN\n", python=sys.executable)
        after = {p: p.read_bytes() for p in fake_hermes.rglob("*") if p.is_file()}
        assert after == before

    @pytest.mark.parametrize("bad", [Path("..") / "outside.md", Path("/etc/passwd")])
    def test_paths_outside_the_repo_are_refused(self, validator, fake_hermes, bad):
        result = validator.run_test_suite_with_artifact(fake_hermes, bad, GOOD_SKILL, python=sys.executable)
        assert not result.passed and "inside the repo" in result.message

    def test_missing_artifact_is_refused(self, validator, fake_hermes):
        result = validator.run_test_suite_with_artifact(
            fake_hermes, Path("skills") / "nope" / "SKILL.md", GOOD_SKILL, python=sys.executable
        )
        assert not result.passed and "not found" in result.message

    def test_missing_interpreter_fails_closed(self, validator, fake_hermes):
        result = validator.run_test_suite_with_artifact(fake_hermes, SKILL_REL, GOOD_SKILL, python="no-such-python-xyz")
        assert not result.passed
