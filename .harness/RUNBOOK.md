# Codex Runbook

This runbook is the default workflow for long-running Codex development on this project.

## Start Of Each Session

Read these files first:

1. `.harness/PROJECT_GOAL.md`
2. `.harness/STATE.md`
3. `.harness/BACKLOG.md`
4. `.harness/DECISIONS.md`
5. `.harness/RELEASE_CRITERIA.md`

Then inspect the relevant code for the selected task.

## Task Selection

- Pick exactly one P0 or P1 task unless the user explicitly chooses another task.
- Continue any `[~]` in-progress task before taking a new `[ ]` task.
- Prefer tasks that improve verifiability or contributor onboarding.
- Keep the slice small enough to complete in one Codex turn when possible.
- Mark the selected task `[~]` before editing and `[x]` only after verification passes.

## Decomposition Gate

Before editing for a selected task, decide whether it is small enough for one Codex turn.

Split the task in `.harness/BACKLOG.md` before implementation when any of these are true:

- Acceptance spans multiple independent modules or workflows.
- Verification would require several unrelated smoke/manual checks.
- The task needs a schema or architecture boundary before feature work.
- A partial implementation would leave the project hard to resume safely.

When splitting:

- Replace the broad task with smaller P0/P1 tasks, or add child tasks directly below it.
- Preserve the original task's `Goal` as the parent intent.
- Give each new task its own `Goal`, `Acceptance`, and `Verification`.
- Update `.harness/STATE.md` with the chosen next slice.
- Only then mark one concrete slice `[~]` and start editing.

## Before Editing

- Check the current working tree shape with `rg --files` or targeted file reads.
- Preserve user changes. Do not revert unrelated files.
- Confirm whether local services are already running before starting new ones.
- For frontend changes, plan to verify in the browser.

## Implementation Rules

- Follow existing code style and standard-library-first approach.
- Add or update tests for backend behavior.
- Use focused smoke scripts for runtime behavior.
- Keep docs and harness state in sync with implementation changes.
- Avoid adding a frontend build system until the static console becomes a clear bottleneck.

## Verification

Run the narrowest relevant set first, then the general harness check:

```bash
python3 -m unittest
node --check online_obs/static/app.js
scripts/dev_check.sh
```

For runtime tasks, run one or more smoke scripts:

```bash
scripts/smoke_rtmp.sh
scripts/smoke_upload_file.sh
```

## End Of Each Session

Update:

- `.harness/STATE.md`
- `.harness/BACKLOG.md`
- `.harness/DECISIONS.md` if architecture changed
- README or docs when behavior changed

Record enough recovery detail for the next Codex session:

- current or just-finished task id
- changed files or areas
- last verification commands and results
- local service URLs and ephemeral PIDs, if any
- next concrete acceptance target

Final response should include:

- What changed.
- Verification run.
- Any services left running.
- The next recommended task.

## Standard Continue Prompt

Use this prompt to resume long-running work:

```text
继续执行 .harness/RUNBOOK.md。先执行 Decomposition Gate，必要时把当前进行中或下一个 P0/P1 任务拆成更小任务；然后完成一个具体任务切片。完成后更新 STATE、BACKLOG、DECISIONS，并运行 dev_check。
```
