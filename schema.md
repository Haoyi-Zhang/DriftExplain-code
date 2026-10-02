# Model, frame, delta, and certificate schema

## Admitted finite model

A model is a JSON object with mandatory `targets`, `normalizer`, and `rules`
fields. Targets have unique anchors, finite raw maps into `T/F/U`, and optional
origin strings. An origin may deliberately describe a closed-world-false raw name
that is absent from the raw map; that pair is still observable evidence.
Normalizer entries are nonempty, duplicate-free, ordered alias lists. Identified
rules belong to families and have optional duplicate-free, ordered `requires` and
`forbids` lists; omission means an empty list. A canonical literal may occur once
in each list: under the declared three-valued equations, the resulting
require-and-forbid conjunction is false for `T` or `F` and unknown for `U`. Semantic
names are nonempty strings excluding `|` and ASCII control/delete characters.
Map/container order is canonicalized; alias and literal order is evidence.

At a present target, a missing raw observation has value `F` and a missing origin
is `closed_world`. A missing canonical normalizer entry is unknown. A present
entry takes three-valued disjunction of its aliases, with true dominating unknown
and unknown dominating false. A rule is false if a requirement is false or a
prohibition true; otherwise it is unknown when any literal is unknown and true
otherwise. A family is the corresponding disjunction over all its rules. Missing
target and present target with no family rules both have value `F`, with distinct
reasons; target absence is checked first.

The old/new candidate space is the cross product of all family names and all
anchors present on either side. Classes are preserved (`T/T`), newly justified
(`F/T`), invalidated (`T/F`), unresolved (either side `U`), and absent (`F/F`).
Malformed admitted fields are rejected rather than interpreted as uncertainty.
Extension metadata is outside the semantics unless the schema is explicitly
extended; it must not influence evidence or visibility silently.

## Endpoint-derived comparison frame

For each endpoint pair and candidate `(family,anchor)`, the checker reconstructs
one frame before any subset replay. It remains fixed for all hybrids.

- The fixed coordinate universe contains candidate target presence, every rule
  identity in the endpoint union, every canonical name occurring in either
  endpoint candidate-family rule projection, and every alias occurring in either
  endpoint normalizer value for those canonical names. Because hybrids select
  endpoint blocks, this union closure contains every coordinate a hybrid can
  expose.
- Decoded target presence controls visibility of the complete rule-map stratum.
  Each rule coordinate has the current canonical candidate-family projection
  `(id,family,requires,forbids)` or explicit absence.
- Current nonabsent rule projections expose their canonical literal and
  normalizer coordinates.
- At an absent candidate target, every framed raw coordinate is explicit absence.
  At a present target, current nonabsent normalizer sequences expose effective
  alias value-origin coordinates using `F` and `closed_world` defaults.

The JSON `rules` array is a sparse encoding of the total framed rule map: only
nonabsent projections are emitted in identifier order. The decoder fills every
omitted identity in the fixed endpoint-union frame with explicit absence. Unique
validated identities and canonical order give a round-trip from every admitted
total framed map through sparse encoding and back, so equality of the sparse identity/projection skeleton is exactly total
framed-map equality relative to that frame. Nested literal and observation
records are later evidence strata. A rule deletion or move
out of the candidate family is a changed decoded coordinate even when the final
array is empty. Missing normalizer entries are represented explicitly in literal
evidence. Derived literal/rule/family values, reasons, decisive entries, and class
are deterministic annotations of the decoded coordinates.

## Atomic endpoint delta and observable footprints

The global endpoint delta has four atom kinds.

1. A target atom adds or removes an anchor present on just one side and carries
   the whole target record. No program atom occurs at that anchor.
2. At a common anchor, a program atom changes one effective value-origin pair.
3. A normalizer atom changes one complete ordered alias entry, including absence.
4. A rule atom changes one complete identified rule record, including addition,
   deletion, or family movement.

For one candidate, each atom has a possibly empty observable footprint. A
one-sided target atom at the candidate anchor owns target presence and every
changed framed raw coordinate at that anchor. A common-target program atom owns
one value-origin coordinate. A normalizer atom owns one mapping coordinate. A
rule atom owns its candidate-family projection coordinate when that projection
changes. Atoms outside the candidate view and metadata-only atoms have empty
footprints.

The footprints partition all changed observable coordinates and are pairwise
disjoint. Applying a subset changes a framed coordinate to its new value exactly
when its unique owning atom is selected. This is the concrete separability premise
used by the structural theorem. Complete-delta replay reproduces final evidence,
not necessarily byte-identical input JSON: defaults can become explicit and
excluded metadata can remain old.

## Certificate fields

A certificate uses schema `finite-finding-drift-certificate` and contains:

- a candidate object with `family` and `anchor`;
- a nonnegative integer `change_bound`;
- the endpoint-derived classification;
- complete old and new serialized evidence;
- the complete sorted list of canonical delta identifiers; and
- a sorted, duplicate-free list of witness identifiers referencing that delta.

Boolean values are not integer bounds. The declared bound and actual delta length
must be no greater than the independently configured checker cap. The default cap
is 12; an explicitly larger checker-side cap preserves the same semantics.

The versions themselves remain checker inputs. They are needed to reconstruct the
candidate frame, atom bodies, endpoint evidence, and complete delta; otherwise a
producer could fabricate mutually consistent certificate fields.

## Acceptance relation and diagnostics

The checker independently reconstructs endpoint evidence, class, the endpoint
information that fixes the conceptual frame, the delta, and the deletion core. It
imports no producer module. For each atom it replays the complete delta without
that atom; the atoms whose deletions fail form the core. For any upward-closed
sufficiency predicate whose full delta is sufficient, the core is the
intersection of all sufficient sets and is the least sufficient set exactly when
replaying the core succeeds. If replay fails, no least set exists and at least
two incomparable inclusion-minimal sufficient sets remain. Under the proved
principal-filter premise, this core is exact structural support.

Acceptance requires all supplied required fields to equal the independent
reconstructions, the witness to equal the recovered deletion core, and the core
replay to succeed. Representative stable diagnostics include:

- `malformed_input`, `candidate`, or `candidate_space` for admission failures;
- `old_evidence`, `new_evidence`, or `classification` for endpoint mismatch;
- `delta` for incomplete or noncanonical endpoint delta;
- `checker_bound` or `witness_bound` for configured/admitted bounds;
- `witness_shape`, `witness_order`, or `witness_member` for malformed references;
- `witness_minimality` when the supplied set differs from the deletion core; and
- `witness_consistency` when the reconstructed core itself fails replay.

The final code distinguishes the last condition from an input-bound failure. A
failed core replay is an implementation inconsistency under the structural
premises. If upward closure and full-delta sufficiency are established
independently, it instead proves that no least sufficient set exists. Without
monotonicity, neither replay outcome establishes leastness. Success also does not
verify the fixed frame, stable correspondence, or disjoint footprints. The
mathematical guarantee assumes
that the finite specification and Python implementations correspond. It is not a
machine-checked proof, source-extraction argument, cache-authenticity guarantee,
or hostile-input resource supervisor.

The incremental entry points validate both endpoint versions before candidate-
space construction even when an old cache is supplied. They verify cache-key
coverage separately; cached-value correctness remains a theorem precondition.

See `proofs/stratified_support.md` for the abstract theorem and lower bound,
`proofs/support.md` for the concrete frame/footprint correspondence, and
`proofs/semantics.md` for finite incrementality and the conditional source bridge.
