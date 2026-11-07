# 🧬 Hermes Agent Self-Evolution

**Evolutionary self-improvement for [Hermes Agent](https://github.com/NousResearch/hermes-agent).**

Hermes Agent Self-Evolution uses DSPy + GEPA (Genetic-Pareto Prompt Evolution) to automatically evolve and optimize Hermes Agent's skills, tool descriptions, system prompts, and code — producing measurably better versions through reflective evolutionary search.

**No GPU training required.** Everything operates via API calls — mutating text, evaluating results, and selecting the best variants. ~$2-10 per optimization run.

## How It Works

```
Read current skill/prompt/tool ──► Generate eval dataset
                                        │
                                        ▼
                                   GEPA Optimizer ◄── Execution traces
                                        │                    ▲
                                        ▼                    │
                                   Candidate variants ──► Evaluate
                                        │
                                   Constraint gates (tests, size limits, benchmarks)
                                        │
                                        ▼
                                   Best variant ──► PR against hermes-agent
```

GEPA reads execution traces to understand *why* things fail (not just that they failed), then proposes targeted improvements. ICLR 2026 Oral, MIT licensed.

## Quick Start

```bash
# Install
git clone https://github.com/NousResearch/hermes-agent-self-evolution.git
cd hermes-agent-self-evolution
pip install -e ".[dev]"

# Point at your hermes-agent repo
export HERMES_AGENT_REPO=~/.hermes/hermes-agent

# Evolve a skill (synthetic eval data)
python -m evolution.skills.evolve_skill \
    --skill github-code-review \
    --iterations 10 \
    --eval-source synthetic

# Or use real session history from Claude Code, Copilot, and Hermes
python -m evolution.skills.evolve_skill \
    --skill github-code-review \
    --iterations 10 \
    --eval-source sessiondb
```

## What It Optimizes

| Phase | Target | Engine | Status |
|-------|--------|--------|--------|
| **Phase 1** | Skill files (SKILL.md) | DSPy + GEPA | ✅ Implemented |
| **Phase 2** | Tool descriptions | DSPy + GEPA | 🔲 Planned |
| **Phase 3** | System prompt sections | DSPy + GEPA | 🔲 Planned |
| **Phase 4** | Tool implementation code | Darwinian Evolver | 🔲 Planned |
| **Phase 5** | Continuous improvement loop | Automated pipeline | 🔲 Planned |

## Engines

| Engine | What It Does | License |
|--------|-------------|---------|
| **[DSPy](https://github.com/stanfordnlp/dspy) + [GEPA](https://github.com/gepa-ai/gepa)** | Reflective prompt evolution — reads execution traces, proposes targeted mutations | MIT |
| **[Darwinian Evolver](https://github.com/imbue-ai/darwinian_evolver)** | Code evolution with Git-based organisms | AGPL v3 (external CLI only) |

## Guardrails

What the code enforces on an evolved skill today, and what it doesn't:

| Guardrail | Status | Where |
|---|---|---|
| Size limit (skills ≤15KB) | Enforced | `ConstraintValidator._check_size` |
| Growth limit (≤20% over the baseline) | Enforced | `ConstraintValidator._check_growth` |
| Non-empty, with `name` and `description` frontmatter | Enforced | `ConstraintValidator.validate_all` |
| hermes-agent's test suite passes 100% | Enforced **only with `--run-tests`**. The suite runs on a scratch copy of hermes-agent with the evolved skill in place; the real checkout is never written | `ConstraintValidator.run_test_suite_with_artifact` |
| Caching compatibility (no mid-conversation changes) | Design rule, not checked in code | — |
| Semantic preservation (no drift from the original purpose) | Design rule, not checked in code | — |
| Human review, never a direct commit | Process. The pipeline writes results to `output/` and never opens a pull request or writes to hermes-agent | — |

A variant that fails an enforced check is saved as `output/<skill>/evolved_FAILED.md` and not reported as an improvement.

## Phase 1 report

`reports/phase1_validation_report.pdf` (March 2026) records one end-to-end run on one held-out example (0.408 → 0.569). Its numbers are written into `generate_report.py`, not read from a metrics file, and its roadmap row said "Validated ✓". The generator now says "Prototype run"; the committed PDF predates that change and was not regenerated, so it keeps its original date and wording.

## Full Plan

See [PLAN.md](PLAN.md) for the complete architecture, evaluation data strategy, constraints, benchmarks integration, and phased timeline.

## License

MIT — © 2026 Nous Research
