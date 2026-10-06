# Reproducing the finite artifact

## Requirements

A standard Python 3.10 or newer installation is sufficient. The acceptance surface uses
only the Python standard library.  No network, package installation, external
solver, compiler, blockchain service, or model is required.

## Complete verification

Run from the artifact root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python verify_artifact.py
```

Expected final status: `PASS`. The verifier uses an isolated copy, so it does
not import modules from or write caches into the supplied tree. Each step has
a 120-second timeout. The copy, raw output and generated JSON are retained;
the report records their location. Choose an external new directory with
`--work-dir` and an external report with `--output` when preserving attempts
outside the artifact. Deterministic JSON has fixed LF newlines on both Windows
and Unix; semantic and exact-byte comparisons remain required.

## Individual commands

```bash
OUT="$(mktemp -d)"
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python run_tests.py
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python abstract_model_check.py --output "$OUT/abstract_model_check.json"
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python monotone_core_check.py --max-atoms 4 --output "$OUT/monotone_core_check.json"
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python generated_differential_check.py --output "$OUT/generated_differential_check.json"
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 python audit_static.py --root . --output "$OUT/static_consistency.json"
```

Expected invariants:

- 46 unit/regression tests pass, including the three verifier-chain mutations;
- `abstract_model_check.json` reports selector domains of sizes two and three,
  6,536 ordered non-identical endpoint pairs, 37,048 atom partitions, 192,176
  subset replays, zero counterexamples, and four executed failure witnesses whose
  restored-premise positive controls pass;
- `monotone_core_check.json` reports 65,814 predicates, 194 upward/full-set
  predicates, 970 theorem checks, and zero counterexamples;
- `generated_differential_check.json` reports 60 generated endpoint pairs, 240
  candidates, 240 accepted certificates, 1,176 exhaustive subset replays, 480
  representation-metamorphism checks, and zero disagreements; and
- the structural audit reports `PASS`.

The preserved tiny-domain counts are not target-presence or alias-order sweeps.
Target `site` is fixed present; `x`, `y`, and `z` range independently over three
values; canonical names are `a`, `b`, and `guard`; ordinary aliases are
singletons; and the 8,748 comparisons are `27 x 27 x 3 x 2 x 2`.  A
class-stratified sample of 301 tiny cases and all 64 directed cases receives
complete subset enumeration, yielding 365 minimum comparisons.  Their subset
replay totals are 2,302 and 1,753, respectively.

## Determinism and interpretation

The generated check uses five fixed seeds recorded in its JSON output.  The two
bounded enumerators traverse finite spaces in canonical order.  The one-command
verifier never trusts the frozen files copied into its temporary artifact: it
passes explicit fresh output paths, checks that those paths were created,
parses the newly written JSON, rejects forbidden `schema_version` metadata, and
then requires semantic and byte-for-byte equality with the frozen files.  The
unit suite mutates this chain so that a missing new file, a changed frozen field,
or a generated/frozen format conflict is observed as `FAIL`. It also exercises
timeout handling with a mocked owned generator and requires partial diagnostics
and exit status 124 to be retained. Reusing an existing fresh-result path is
rejected rather than deleting or trusting the old output.

These checks validate implementation correspondence on bounded finite spaces.
They do not mechanize the proof, authenticate upstream source observations, or
estimate real-world detector accuracy.  There is no fitted model and no train/
test split.  The checks address specification and fixture bias through exhaustive
small domains, generated cases, representation metamorphisms, and failure
controls.

## Preserved but non-reproducible campaign surface

The historical timing/scaling campaign is intentionally not a positive
reproduction target: retained accounting already exceeds the declared campaign
cap.  Its raw files remain available for audit, but no speedup or resource-
closure conclusion is drawn from them.  The nine public-pattern contexts are
also not a source corpus; the consumed artifact inputs are the authored finite
records in `data/public_fixtures.json`.
