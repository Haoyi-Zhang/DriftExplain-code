# Same complete inputs, different information-access paths

`report.json` contains the actual owned old/new records, complete certificates,
literal sufficient subsets and 218 supplied candidate outcomes for all 48
existing forward/reverse pairs. All three receiver paths agree on every decision.
Twelve large pairs retain d=16/32/64 and k=0/1/d/2/d, with instrumented calls.
At d=64,k=1:

| Path | Delta reconstructions | Hybrid replays | Evidence evaluations |
|---|---:|---:|---:|
| Identifier plus core replay | 1 | 65 | 67 |
| Candidate replay verifier | 1 | 2 | 4 |
| Structure-visible verifier | 1 | 0 | 2 |

Every path receives the same two endpoints and complete certificate and
reconstructs evidence and delta independently of the producer. Structure access
is denied by the binary-oracle theorems: zero hybrids do not improve those bounds
or mean zero work. Validation, endpoint evaluation, delta reconstruction and
final-record/atom scanning remain. No timing, native/source contract, external
target or security effectiveness is measured.

From the artifact root, use a directory that does not exist:

```bash
python -B information_paths_check.py --output ../information-paths-new
```

The report retains actual Python/platform/timestamps and source bindings.
`verify_artifact.py` runs the unit and regression groups and this comparison in an
isolated copy. Query-execution regressions run with and without Python optimization.
Complete scientific records must match; run environment is excluded from
deterministic equality and actual source bindings are checked against that copy.
Historical receipts, query counts, negative controls and the terminated timing
campaign are unchanged. These tests do not provide native/frontend validation.
