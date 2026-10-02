# Artifact evaluation guide

## Claims that can be checked directly

1. **Finite semantics and certificates.** Run `python run_tests.py` and inspect
   `src/producer.py`, `src/checker.py`, and `schema.md`.
2. **Principal-filter correspondence on bounded abstract frames.** Run
   `python abstract_model_check.py`; inspect the executed hidden-selector, unstable-identity, value-only, and overlapping-write witnesses and their restored-premise positive controls.
3. **Deletion-core order theory on all small predicates.** Run
   `python monotone_core_check.py`; inspect the executed sequential-write counterexample and restored monotone predicate.
4. **Cross-implementation and representation robustness.** Run
   `python generated_differential_check.py`.
5. **Cross-surface consistency and package hygiene.** Run
   `python audit_static.py --root .`.
6. **All checks in an isolated copy.** Run `python verify_artifact.py`; confirm that each fresh-output comparison is `PASS` and that the verifier mutation tests pass only because their deliberately corrupted cases are rejected.

The complete sequence requires no external dependency and normally finishes in
seconds on an ordinary CPU.

## Evidence interpretation

Passing checks support only the finite observation contract and implementation
surfaces described in the paper.  The theorem is justified by the paper and
`proofs/`, not by finite enumeration.  Zero disagreement is not a probability,
accuracy, scalability, or deployment result.

The following are explicit non-claims: Solidity/source parsing, source-to-fact
soundness, historical evolution, a 120-contract corpus, production security
coverage, prevalence of the failure modes, and performance superiority.  The
historical timing files are retained as negative protocol evidence because the
campaign exceeded its declared cap.

## Useful inspection order

1. `schema.md`
2. `proofs/stratified_support.md`
3. `src/producer.py` and `src/checker.py`
4. `theorem_assumption_matrix.csv`
5. the three current finite-check JSON files under `results/`
6. `claim_evidence_ledger.csv`
7. `reference_verification.csv` and `citation_claim_map.csv`
