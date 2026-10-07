# Finite evidence support for evolving rule analyzers

This artifact accompanies **When Complete Evidence Makes Minimum Drift
Explanations Structural**.  It implements the finite three-valued rule model,
a certificate producer, an independently implemented replay checker, bounded
model checks, generated differential checks, and the evidence needed to audit
the paper's finite claims.

## Scientific scope

The positive result is deliberately narrow.  For one fixed comparison frame,
complete key-addressed evidence, and an endpoint delta whose observable atom
footprints are disjoint and complete, the sufficient change subsets are exactly
the supersets of the atoms read by the final evidence traversal.  The producer
computes that structural projection.  The checker is denied the projection and
recovers the deletion core by replay.

The artifact does **not** provide a Solidity parser, a source-to-fact soundness
argument, a 120-contract corpus, historical source/rule evolution, production
accuracy, or a performance advantage.  The nine records in
`data/public_fixtures.json` are authored finite abstractions informed by public
pattern examples; `external_inputs/selection.csv` records their context and
explicitly denies source-level validation.

No statistical model is trained.  Predictive overfitting is therefore not an
applicable interpretation.  The corresponding risk is specification and fixture
bias, addressed only within a finite scope by complete small enumeration,
generated endpoint pairs, two representation metamorphisms, and explicit
negative controls.

The regression suite additionally fixes boundary behavior that is easy to
misread: explicit origins on closed-world-false names remain observable; a
canonical literal may appear once in both rule polarities under the declared
three-valued equations; old-only framed rules remain observable when a newly
present target has no final family rule; and cache-key validation does not
authenticate cached values.

## One-command verification

From this directory:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python verify_artifact.py
```

The command copies the artifact to an isolated directory and runs the base
finite gates:

1. all 46 unit/regression tests;
2. the independent stratified-frame enumerator;
3. the independent monotone-predicate enumerator;
4. the seeded differential and metamorphic checker; and
5. the deterministic structural audit.

For each deterministic finite checker, the verifier supplies an explicit
`--output` path in a fresh sibling directory, requires the new file to exist,
parses the new file, rejects forbidden result metadata, and then compares both
its JSON value and exact bytes with the shipped frozen result. The static audit
also writes to a fresh path and must pass; it is not byte-compared with the
shipped project-mode audit because the one-command verifier audits the standalone
artifact mode. Unit tests include three verifier mutations:
a missing fresh output, a changed frozen field, and a format conflict must all
produce `FAIL`.  No copied frozen JSON is accepted as evidence of regeneration.
The original artifact directory is not modified except for the final verification
report.

Every verification step has a 120-second timeout. The isolated copy, fresh
results, and raw output are retained on success or failure; the report gives
their location. Use `--work-dir /path/to/new-directory` outside the artifact and
`--output /path/to/report.json` to choose where evidence is retained. Strict
result comparison uses a fixed LF encoding on Windows and Unix alike.

The hidden-selector control computes an empty support from its actual final
leaf read set while a selector edit changes the keyed leaf evidence. Recording
the selector restores support `{0}` and the principal-filter correspondence.
The interacting-delta regression distinguishes replacing a true alias with an
unknown alias from appending the unknown alias: a retained true alias dominates.

`.github/workflows/scientific-checks.yml` runs these finite gates from the flat
artifact repository root on Ubuntu 24.04. Its whole run is limited to 300 seconds,
with CPU, address-space and output-file bounds; raw output and fresh results are
uploaded even when a gate fails. This workflow is separate from source-syntax
integrity checks and does not run the terminated historical campaign.

## Acceptance path and retained harnesses

Certificate generation reuses its own admitted endpoints and complete delta
for structural support selection. Public `minimum_witness` still validates
its inputs and admission bound; the independent checker still reconstructs
its deletion core and replays it without importing producer support code.

An additional portable six-method regression scans complete evidence and
enumerates literal subsets on 48 owned forward/reverse endpoint pairs, each
with at most six changes. Run it separately from the 46-method base suite:

```bash
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python -B -m unittest discover -s tests -p check_prepared_support.py -v
```

The scientific workflow runs this explicit step and retains its output. Its
name intentionally keeps it separate from `run_tests.py` discovery and the
archived 46-method unit, resource, and one-command receipts. Those receipts
are not evidence that this additional regression ran. Complete certificates,
ordered delta/support, admission errors, input immutability, independent
checker rejection, and semantic counters are checked; no runtime gain is
measured or claimed.

The current acceptance path is `run_tests.py`, the three bounded finite checks,
`audit_static.py`, and `verify_artifact.py`.  `src/evaluate.py` and the campaign
entry points in `src/support_study.py` are retained only to interpret predecessor
CSV/JSON evidence and are not a current performance or source-evaluation target.
The regression suite imports only the directed finite cases and negative control
from the latter.  A passing current verification therefore does not certify every
historical campaign branch or reopen its terminated resource budget.

## Main components

- `src/producer.py` — finite semantics, canonical endpoint delta, structural
  support, certificates, and conservative incremental reuse.
- `src/checker.py` — separately implemented admission, finite semantics, delta,
  deletion-core reconstruction, and certificate acceptance.  It imports no
  producer or shared analysis module.
- `abstract_model_check.py` — standard-library-only enumeration of bounded
  stratified frames, endpoint pairs, atom partitions, all change subsets, and
  four executed premise-breaking controls and their restored-premise
  positive controls.
- `monotone_core_check.py` — standard-library-only enumeration of every Boolean
  predicate on zero through four atoms.
- `generated_differential_check.py` — deterministic generated endpoint pairs,
  producer/checker/exhaustive agreement, certificate checks, and container-order
  and bijective-renaming metamorphisms.
- `tests/` — 46 current tests for finite semantics, support, certificates,
  incrementality, admission, independent checks, and generated cases.
- `proofs/` — the abstract theorem, concrete instantiation, incremental theorem,
  checker relation, counterexamples, and conditional source-lifting statement.
- `theorem_assumption_matrix.csv` — each theorem premise, where it is used, and
  a failure construction or enforcement surface.
- `claim_evidence_ledger.csv` — paper claims mapped to proof, code, tests, raw
  evidence, maturity, and current recheck status.
- `citation_claim_map.csv`, `reference_verification.csv`, and
  `literature_calibration.csv` — citation use, bibliographic identity, and
  closest-work distinctions for all 67 cited publications.

## Current finite results

- Unit/regression suite: **46/46 passed**.
- Stratified-frame enumeration: **two selector domains**, **6,536 ordered
  non-identical endpoint pairs**, **37,048 atom partitions**, and **192,176
  subset replays**, with no theorem counterexample; all four executed negative
  controls expose the expected failure and their positive controls restore the
  premise.
- Monotone-predicate enumeration: **65,814 predicates**, including **194**
  upward-closed predicates accepting the full set and **970** checked theorem
  instances, with no counterexample.
- Generated differential surface: **60 endpoint pairs**, **240 candidates**,
  **240 certificate checks**, **1,176 exhaustive subset replays**, **240
  container-order checks**, and **240 bijective-renaming checks**, with no
  disagreement.

These are finite defect-detection results, not a proof, an accuracy estimate, a
source-level evaluation, or a statistical generalization claim.  The proofs are
the basis of the theorem statements.

The retained tiny comparison count has a fixed interpretation: target `site`
is present; `x`, `y`, and `z` are three three-valued observations; the canonical
names are `a`, `b`, and `guard`; ordinary aliases are singleton lists; and the
product is `27 x 27 x 3 x 2 x 2 = 8,748`.  Target addition/deletion and alias
reordering occur in directed/unit cases.  Full subset enumeration covers 301
tiny samples and all 64 directed cases, for 365 exact-small minimum comparisons;
the corresponding subset replays split as 2,302 tiny plus 1,753 directed.

## Retained predecessor evidence and resource boundary

The archive retains earlier finite comparison, certificate-corruption, timing,
and scaling records because they affect interpretation.  A reconstructable
lower bound for the historical timing activity is 902,768 family-anchor
evaluations, exceeding the frozen 800,000-obligation cap.  The campaign remains
`EMPIRICAL_CAMPAIGN_TERMINATED_OVER_CAP`; timing and scaling files are not used
for a positive performance claim.  Current unit and finite-check runs are
post-disposition artifact verification and do not reset that accounting.
