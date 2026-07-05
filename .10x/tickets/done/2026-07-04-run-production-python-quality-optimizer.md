Status: done
Created: 2026-07-04
Updated: 2026-07-04

# Run Production Python Quality Optimizer

## Scope

Run the complete attached Production Python Quality Optimizer procedure for `atlassian-md-export`, using non-mutating tool execution unless a check reveals an issue that must be fixed in source.

For each check that reports an issue, repair the smallest source-owned cause, then rerun all checks from the beginning through the repaired check before continuing.

Initial known issue: `ty check src tests` reports local type-narrowing diagnostics in `src/atlassian_md_export/indexes.py`, `src/atlassian_md_export/operations.py`, and `src/atlassian_md_export/writer.py`.

## Acceptance Criteria

- Every check in the attached procedure is either run successfully, run with findings that are fixed and rechecked, or explicitly recorded as unavailable/skipped with the reason and non-uv/external tool status.
- Required issue remediation preserves runtime behavior, CLI contracts, Markdown output semantics, and state/manifest semantics.
- Hard gates do not regress: Ruff, `ty`, Mypy, tests, Semgrep, dependency audit, and secret scanning must either pass or be explicitly unavailable with no claim of passing.
- For every source fix, all checks from the beginning through the failing check are rerun before proceeding.
- Final evidence records exact commands, outcomes, limits, and unavailable tools.

## Explicit Exclusions

- Do not run `uv sync`, update `uv.lock`, or change dependency metadata.
- Do not add type ignores or broad `Any` casts.
- Do not change public CLI behavior, export schemas, Markdown rendering semantics, or cleanup authority semantics.
- Do not remediate unrelated quality findings unless they directly block the acceptance criteria above.
- Do not initialize Tach, create baselines, add Semgrep config, or add coverage/benchmark baselines. CI/config files remained out of scope except for the Semgrep-reported mutable GitHub Actions references, which were pinned to full SHAs under the user's explicit instruction to address every check issue.
- Do not print secrets if a secret scanner reports findings.

## Blockers

None.

## Progress And Notes

- 2026-07-04: Formatter drift was corrected separately as trivial canonicalization with `uv run --no-sync ruff format --no-cache src tests`.
- 2026-07-04: Baseline post-format checks passed for Ruff, Mypy, and Pytest. `ty` reported 9 diagnostics:
  - `src/atlassian_md_export/indexes.py:469` `dict(item)` over `Mapping`.
  - `src/atlassian_md_export/operations.py:2782` `_list` return narrowing.
  - `src/atlassian_md_export/operations.py:2786` `_dict_list` return narrowing.
  - `src/atlassian_md_export/writer.py:1346`, `1349`, `1610`, `1629`, `1653`, and `1659` mapping/object narrowing around `_json_object`.
- 2026-07-04: The local `.venv` console scripts have stale shebangs from the old path `/Users/alexanderbut/code_projects/work/atlassian-md-export/.venv/bin/python3`; verification can use `.venv/bin/python -m ...` or `PYTHONPATH=src .venv/bin/python -m pytest` without syncing.
- 2026-07-04: User explicitly expanded authorization: run the entire attached procedure; for each check with an issue, address it and rerun all checks up to that point.
- 2026-07-04: Completed optimizer procedure. Final hard gates passed where runnable: Ruff, `ty`, Mypy, targeted/full pytest, coverage, Semgrep default/security-audit, `uv audit`, OSV-Scanner, and Gitleaks. CodeQL unavailable because no system binary is installed; Tach/Hypothesis/benchmarks/profilers skipped for recorded reasons.
- 2026-07-04: Remediated check findings: type narrowing, production/test complexity, coverage for new shared payload helpers, actionable duplicate helpers, Deptry first-party classification, Semgrep SQL construction findings, and mutable GitHub Actions references.
- 2026-07-04: Evidence recorded in `.10x/evidence/2026-07-04-production-python-quality-optimizer.md`.
- 2026-07-04: Closure review recorded in `.10x/reviews/2026-07-04-production-python-quality-optimizer-review.md` with verdict `pass`.

## Evidence Expectations

Record the exact command outputs in a new `.10x/evidence/` record before closure. At minimum include:

- discovery commands from Phase 0
- Ruff format/lint checks
- `ty check src tests`
- Mypy
- Tach status
- Pytest fast/full loop
- Coverage
- Radon
- Complexipy
- Vulture
- jscpd
- Deptry
- pydoclint
- Semgrep
- CodeQL status
- `uv audit`
- OSV-Scanner status
- Gitleaks status
- benchmark/profiler applicability

Evidence satisfied by `.10x/evidence/2026-07-04-production-python-quality-optimizer.md`.

Known project-local invocations:

- `env PYTHONPATH=src uv run --no-project --no-cache --with ty ty check src tests`
- `uv run --no-sync ruff check --no-cache src tests`
- `uv run --no-sync ruff format --check --no-cache src tests`
- `.venv/bin/python -m mypy --no-incremental src tests`
- `env PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider`

## References

- `.10x/knowledge/atlassian-md-export-sync-and-field-semantics.md`
- `.10x/specs/atlassian-md-export-cli-config.md`
- `.10x/specs/jira-export-api-sync.md`
- `.10x/specs/jira-issue-markdown-output.md`
- `.10x/specs/jira-attachments-index-clean-verify.md`
- `.10x/specs/confluence-cli-config.md`
- `.10x/specs/confluence-export-api-sync.md`
- `.10x/specs/confluence-page-markdown-output.md`
- `.10x/specs/confluence-attachments-index-clean-verify.md`
- `.10x/specs/adf-markdown-rendering.md`
