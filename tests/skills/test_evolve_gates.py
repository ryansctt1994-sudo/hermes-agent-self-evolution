"""evolve() end to end with DSPy stubbed out: no network, no API keys.

Covers the constraint step and the --run-tests gate as evolve() wires them,
against a throwaway hermes-agent checkout whose own test rejects a skill
containing the word BROKEN.
"""

import json
import os
import sys
import types
from pathlib import Path

import pytest

from evolution.skills import evolve_skill as es

SKILL = "---\nname: demo\ndescription: Demo skill\n---\n\n# Procedure\n1. Do thing\n"
GOOD_BODY = "# Procedure\n1. Do the thing"
BROKEN_BODY = "# Procedure\n1. BROKEN"


class FakeModule:
    def __init__(self, skill_text):
        self.skill_text = skill_text

    def __call__(self, task_input):
        return types.SimpleNamespace(output="ok")


class FakeDataset:
    all_examples = [object()] * 3
    train = val = holdout = [object()]

    def to_dspy_examples(self, split):
        return [types.SimpleNamespace(task_input="task")]


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_dspy(evolved_body):
    class GEPA:
        def __init__(self, **kwargs):
            pass

        def compile(self, module, **kwargs):
            return FakeModule(evolved_body)

    return types.SimpleNamespace(
        LM=lambda model: object(),
        configure=lambda **kwargs: None,
        GEPA=GEPA,
        context=lambda **kwargs: _NullContext(),
    )


@pytest.fixture
def hermes(tmp_path, monkeypatch):
    repo = tmp_path / "hermes-agent"
    (repo / "skills" / "demo").mkdir(parents=True)
    (repo / "skills" / "demo" / "SKILL.md").write_text(SKILL)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_skill.py").write_text(
        "from pathlib import Path\n"
        "def test_skill_not_broken():\n"
        "    assert 'BROKEN' not in Path('skills/demo/SKILL.md').read_text()\n"
    )
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)  # evolve() writes output/ relative to the cwd
    # No default hermes-agent anywhere: hermes_repo= must be what evolve() uses.
    monkeypatch.delenv("HERMES_AGENT_REPO", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    # The gate runs `python -m pytest`; make `python` resolve to this interpreter.
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setattr(es, "SkillModule", FakeModule)
    monkeypatch.setattr(es, "skill_fitness_metric", lambda example, pred: 0.5)
    monkeypatch.setattr(es.GoldenDatasetLoader, "load", staticmethod(lambda path: FakeDataset()))
    return repo, work


def run(monkeypatch, repo, body, run_tests):
    monkeypatch.setattr(es, "dspy", fake_dspy(body))
    es.evolve("demo", iterations=1, eval_source="golden", dataset_path="unused",
              hermes_repo=str(repo), run_tests=run_tests)


def metrics(work):
    found = list((work / "output" / "demo").glob("*/metrics.json"))
    return json.loads(found[0].read_text()) if found else None


def test_a_well_formed_evolved_skill_passes_the_constraint_step(monkeypatch, hermes):
    # The skill body has no frontmatter; the structure check must see the reassembled file.
    repo, work = hermes
    run(monkeypatch, repo, GOOD_BODY, run_tests=False)
    m = metrics(work)
    assert m is not None, "evolve() stopped at the constraint step"
    assert m["constraints_passed"] is True
    assert m["test_suite_passed"] is None


def test_run_tests_passes_a_good_skill(monkeypatch, hermes):
    repo, work = hermes
    run(monkeypatch, repo, GOOD_BODY, run_tests=True)
    m = metrics(work)
    assert m is not None and m["test_suite_passed"] is True


def test_run_tests_blocks_a_skill_that_breaks_hermes_tests(monkeypatch, hermes):
    repo, work = hermes
    run(monkeypatch, repo, BROKEN_BODY, run_tests=True)
    assert metrics(work) is None
    assert "BROKEN" in (work / "output" / "demo" / "evolved_FAILED.md").read_text()


def test_without_run_tests_the_suite_is_not_consulted(monkeypatch, hermes):
    repo, work = hermes
    run(monkeypatch, repo, BROKEN_BODY, run_tests=False)
    m = metrics(work)
    assert m is not None and m["test_suite_passed"] is None


def test_the_real_checkout_is_never_written(monkeypatch, hermes):
    repo, _ = hermes
    before = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    run(monkeypatch, repo, BROKEN_BODY, run_tests=True)
    run(monkeypatch, repo, GOOD_BODY, run_tests=True)
    after = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    assert after == before
