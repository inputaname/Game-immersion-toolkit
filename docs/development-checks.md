# Faster development checks

Use `npm run check:changed` for working changes. For a branch, fetch the actual
PR target and add `-- --base <target-remote>/<target-branch>`. A fork targeting
this upstream repository normally uses `upstream/main`; `origin/main` is correct
only when origin is the actual PR target. The report records the resolved base
SHA. An invalid or unavailable base fails without valid branch evidence.
See the [verification rules](ai-development-workflow.md#verification-and-evidence)
for task scope, evidence and handoff requirements.

The [rework roadmap](rework-roadmap.md) assigns independent workstreams and
[R25](rework-roadmap.md#r25--reduce-test-cost-and-keep-necessary-coverage) reviews
test necessity and cost. The [architecture study](rework-architecture.md) explains
the boundaries, and the [screenshot regression plan](screenshot-regression-plan.md)
defines planned image/package tests. The selector, doctor, evidence records and
preview lifecycle described below are implemented. The roadmap's screenshot
replay/controller work, test pruning and supported-platform CI migration remain
planned; these documents do not implement those changes.

All engineering prose is in English, regardless of the language used to request
a change. Preserve intended multilingual product text and test input.

## Current check selection

Documentation changes check generated guides, links and publication safety.
Python, desktop and mobile changes select their relevant checks; desktop and
mobile changes also run `npm run lint`. Lint rules with pre-existing violations
are warnings until those are cleaned up, and `vendor/` is linted in its shared
source repository. Unknown inputs
and dependencies use the comprehensive gate; mixed desktop/mobile edits run unit
tests once. Changes to the selector, evidence runner, shared test server, Python
resolver or CI gate select the full suite. Mobile companion and offline update
harness changes also select the offline update/restart scenario. Stage new
documentation before checking links so `git ls-files` includes it. Do not run
Python, OCR or full browser suites for documentation alone.

`npm run check:full` runs the comprehensive local gate when needed. Release tags
run full checks and packaging on GitHub-hosted Windows. Atomic release pushes
delegate comprehensive main-branch checks to the tag for the same commit while
retaining documentation/publication checks. Normal branch pushes do not duplicate
PR checks. Manual **Checks and release** runs exercise the comprehensive gate
and validate the extracted candidate on a branch without publishing. Pages
retains browser smoke tests, macOS/WebKit transport verification and publication
validation; the release gate owns the full browser matrix.

Release checks build the frontend once, then use that build in separate desktop,
setup, capture, offline-storage and OCR jobs. Every required group must pass before
packaging. A failed group can be rerun without repeating successful groups. Reuse
unchanged browser builds only when source fingerprints and output hashes match.
Checks record elapsed time under ignored `output/checks/`; a cache hit is not a
clean-build timing promise.

For a Windows offline failure, run **Online companion** manually with
`check: offline` on the relevant branch. It exercises cache activation, offline
reloads and updates without unrelated matrices. Firefox owns a fresh profile and tests
reopening after a browser restart. Browser caches follow the pinned Playwright
version. Log the failing operation before browser cleanup can obscure it.

Frame-source changes select native-frame and receiver/OCR/reader scenarios, plus
applicable pairing/recovery checks. `scripts/mobile-vdo-source-e2e.mjs` uses
synthetic cross-origin viewers; `scripts/mobile-source-e2e.mjs` runs real OCR and
catalog matching. Live-device probes are private and opt-in. See the
[source decision](mobile-vdo-decision.md) and
[physical protocol](mobile-capture-verification.md).

The source scenario probes MP4/WebM support separately. Only the known
Windows/WebKit runtime with both codecs explicitly unsupported may leave that
video-adapter subcase unverified; unexpected failures/timeouts still fail. Native
PNG, English/Chinese OCR, slow results, explicit Stop and recovery remain testable.
The screenshot plan does not need video decoding to test those image paths.

## Prepare the development environment

Run `npm run dev:doctor` (or supply the same `-- --base ...` / `-- --full`
scope) first. It checks only prerequisites for that scope: supported Node/npm
lock metadata, Python 3.12 and pinned distributions when needed, browser binaries
and generated assets. It never installs packages, downloads models, imports
native OCR, starts the app, or accesses game/account data. Exit 0 means required
prerequisites were observed, 2 means prerequisites are unavailable, and 1 means
invalid configuration. A passing doctor is not a passing test run.

Use Node 24, `npm ci`, and `npm run dev:prepare` to prepare JavaScript and
generated mobile assets. Install Playwright engines explicitly with
`npx playwright install chromium firefox webkit` when browser checks are needed.
For backend work create a project `.venv` using Python 3.12 and install the
locked requirements into it. Some packages and acceptance checks need Windows.
Development runners choose `PYTHON`, then this project's `.venv`, then PATH
(`python` on Windows, `python3` elsewhere). An incomplete project venv is an
error; a running companion's installed environment is never used as a fallback.
The production updater keeps its independent environment validation.
The doctor also checks prerequisites for selector tests and the actual Chromium
headless-shell executable used by default launches, rather than accepting only
the regular Chromium executable.

`npm run test:infra` runs dependency-light regression tests for selection,
evidence, environment detection, CI aggregation and preview isolation. It does
not replace selected application tests.

## Evidence and CI acceptance

Each executed check creates `output/checks/runs/<id>.json` before starting and
sets `output/checks/latest.json` to a pointer to that run. Progress and final
results update only the run file atomically, so an older run finishing cannot
overwrite the newer pointer. Records contain source HEAD,
resolved base, a hash of index metadata, raw tracked entries and nonignored
untracked content, command statuses and elapsed times. Source changes during
execution invalidate the run.
An interrupted run left `running` is unfinished, not a pass. A failed aggregate
`npm run check` does not claim its inner scripts passed.
Git `assume-unchanged` or `skip-worktree` flags can hide modified source files.
Such a checkout cannot produce valid evidence: checks stop without clearing
those flags. Inspect the flagged files or use a complete clean checkout before
retrying. Applied Git source transforms (`filter`, `ident` or
`working-tree-encoding`) also make source evidence unavailable:
checks stop without executing filters or changing attributes/configuration.
This conservatively includes explicitly disabled transform attributes, because
Git reports them like a literal `unset` value (which can name a filter driver).
Inspect the effective attributes, including local overrides, or use a checkout
without source transform attributes. Ordinary CRLF checkouts remain supported; changes to raw bytes during a run invalidate its
evidence. The doctor reports the same source limitations.

Commands are recorded as passed, failed, not-run, delegated or unavailable.
Split browser jobs and the source-audit job supply separate evidence; delegation
alone proves no test passed. Windows-only checks remain unavailable locally on
other hosts. Exit 1 means command failure and exit 2 means invalid source/base
evidence. Delegation and unavailable native checks retain exit 0 for orchestration
but leave the report incomplete. Read the report status as well as the exit code.
JSON records omit command output, absolute interpreter paths, file contents
and environment values. Only these allowlisted metadata files are uploaded;
ignored raw logs, screenshots and fixtures are not automatically safe to publish.

PR publication audit checks submitted HEAD, while application/browser jobs check
GitHub's exact event merge SHA and verify both event parents. The stable
`required-checks` context fails on failed, cancelled, missing or invalid jobs.
The browser matrix may be skipped only for validated selective scope, whose
selected browser scenarios run inline. Maintainers must select `required-checks`
in branch rules and require an up-to-date base. Parent verification alone proves
only the event snapshot. Manual dispatch evidence does not replace this PR gate.
The final gate report preserves the verified tested, workflow, head and base
commits alongside the selected jobs' results, and rechecks the checkout before
writing the aggregate outcome.

## Preview isolation and cleanup

The desktop, setup, language/account and React-state preview harnesses use
OS-assigned ports retained by their own Wrangler listeners, unique temporary
registry/persistence directories and per-run `output/e2e/` artifacts. Cleanup
targets only owned processes. Offline update tests keep one origin through
update and browser restart, then remove their owned profile.
SIGINT/SIGTERM await both owned browser and preview-server cleanup, including a
browser whose launch is still pending. The shared preview launcher disables
Playwright's competing signal exits so they cannot interrupt server cleanup.
If a Windows parent has already exited, its remaining descendants cannot be
safely identified: cleanup fails explicitly and retains the temporary runtime. Forced OS termination cannot run cleanup.

## Supported targets and proposed CI changes

Windows is the supported desktop target. Relevant macOS/WebKit checks provide
mobile-browser evidence; physical iOS and native Windows checks remain distinct.
**Do not add Linux product/browser verification.** Linux working incidentally
does not make it a supported platform or justify extra test jobs.

The Online companion workflow currently includes Ubuntu browser checks, and
earlier evidence includes Linux codec tests. R25 must
remove or relocate those test jobs to Windows and, where needed, macOS/WebKit,
preserving useful browser/codec coverage. This documentation does not claim that
migration has happened. Linux runners used solely for static publishing are
infrastructure, not Linux compatibility tests; do not remove publication machinery
just because its runner is Linux.

## Planned test review and pruning

R25 remains planned. Review existing tests, including the thousand-plus Python
cases, by the distinct failure they catch, current supported behavior and
measured runtime. Record a
small keep/consolidate/remove mapping for each reviewed area. Remove redundant,
obsolete and implementation-mirroring tests; identify equivalent retained coverage
or why the behavior is retired. There is no target test count.

Protect useful regressions and account/data/locale isolation, voice identity,
migration, cancellation, lifecycle and publication behavior. Never remove a
failing test, add a skip or relax a threshold to hide an unresolved defect.
Removing genuine duplication is planned maintenance, not a blanket prohibition
on deleting tests.

New tests must name the failure and explain why existing cheaper coverage is
insufficient. Test pure logic at unit/contract level, with a few real OCR/package
cases for integration. Avoid tests that restate implementation details or inspect
file layout instead of behavior. Simple reversible copy/style changes need no
new tests. Review expensive browser cases before adding overlapping coverage.

Build once, reuse fixture/model setup and deduplicate selected scenarios. Measure
before/after wall-clock time in `output/checks/` and set a realistic budget before
expanding a costly job. Run affected cases on PRs and a bounded supplemental sample
on manual/candidate runs. Repeat passed broad suites only for relevant changes,
failures or unresolved concerns. Full packaging remains a candidate/release gate.

## Planned screenshot and language regressions

The corpus inventory, manifest-driven screenshot/sequence runner and mobile
controller extraction in R01, R07a/R07b, R11 and R13c remain planned. Existing
image/OCR and package checks do not complete this broader acceptance contract.

Use fixed screenshots for game-specific presentation gaps, plus a few supported
language combinations through actual-format mobile packages. Do not prioritize
ZZZ or multiply every game by every language, browser and resolution. Inventory
all active games, then choose cases for distinct untested behavior or reported
defects. Keep known regressions fixed and record any rotating supplemental sample.

Use the built mobile artifact, normal ZIP import and production OCR/controller/
matching path. Independently annotated expected/forbidden identities prevent an
empty or wrong-locale result from passing. A single screenshot tests visible text;
ordered screenshot sequences and controlled observations cover timing and stale
work. Label injected OCR separately from real image OCR. Live YouTube playback
is not a required input source.

Public Actions jobs use authored screenshots, small synthetic catalogs and owned
audio. Real screenshots/packages stay private by default; optional trusted hosted
processing must satisfy the screenshot plan's access and output restrictions.
Never publish the supplied real package or private media through caches, traces,
failure artifacts or Pages. A synthetic pass cannot replace a missing real-input
result. Report exact commit/artifact/corpus/package/model versions and selected
game/presentation/language cases, elapsed time and pass/fail/not-run/unavailable.

R07a characterizes current production; R13c extracts the mobile controller; R07b
reuses it for screenshot replay. Keep extraction and behavior fixes independently
reviewable. Check affected consumers on the integrated commit. M2 is the combined
user flow; M3 is candidate/device evidence. A completed independent improvement
can ship through the normal authorized process without waiting for every stream.

## Generated guides and OCR model metadata

Update `public/mobile-capture/games-data.json`, then run `npm run docs:generate`
when changing capabilities. All four README and language-matrix versions are
generated together; `npm run docs:check` detects drift.
Keep storefront availability separate from actual reader and package support.
Existing localized product guides are intentionally multilingual; the English-only
rule concerns engineering prose, not removal of product localization.

`npm run ocr:manifest` is an explicit maintainer operation that verifies pinned
model downloads and records sizes/SHA-256. Normal builds do not fetch optional
language models; users download only chosen packs. Regression fixtures must select
their required verified models explicitly instead of downloading every language.
