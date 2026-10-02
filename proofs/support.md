# Exact framed evidence support in the finite rule analyzer

The model-independent theorem, replay-query lower bound, representation results,
and falsifiers are stated in `stratified_support.md`. This document gives the
concrete comparison frame, observable atom footprints, and implementation
correspondence for the delivered finite analyzer.

## Statement and scope

The model contains finite targets, an ordered alias normalizer, and identified
rules grouped by family. The result concerns this admitted JSON projection, not
Solidity source extraction. The mathematical argument is written by hand; the
Python implementation is not mechanically verified.

Fix valid old and new inputs `o,n` and candidate `x=(f,a)` in the cross product of
their union family and anchor sets. Let `D` be the complete ordered endpoint delta.
The candidate frame `F_x(o,n)` is reconstructed once from both endpoints and is
held fixed for every subset. A subset `S` is sufficient when

`E_Fx(patch(o,S),x) = E_Fx(n,x)`.

The relational class is a deterministic field of endpoint evidence, so exact
final-evidence equality also reproduces the final class. It is not a second
optimization predicate.

The theorem instantiated here states that one set `W_x` satisfies, for every
`S subseteq D`,

`S is sufficient` if and only if `W_x subseteq S`.

Thus `W_x` is the unique inclusion-least and cardinality-minimum exact-evidence
support.

## Admitted observations

At a present target, a missing raw value is effective `F` and a missing origin is
`closed_world`. A missing normalizer entry is explicit unknown, with a
`missing_normalizer` reason. A present mapping contains a nonempty ordered,
duplicate-free alias list. Every alias contributes its name, effective value, and
effective origin; evidence construction does not stop after a true alias.

A rule records its stable identifier, family, ordered required and forbidden
canonical occurrences, every resulting literal record, derived value and reason,
and a deterministic decisive entry. A family records every member rule rather
than stopping after one true rule. Target absence and present-target family
absence both have value `F` but distinct reasons. Omitted required/forbidden
fields mean explicit empty sequences. Extension metadata is outside this
projection and cannot be allowed to control evaluation without a schema change.

## Fixed candidate frame and sparse rule decoding

The conceptual evidence is a decoded stratified record even though the JSON is a
compact serialization.

1. The frame always contains target presence for anchor `a`.
2. Its fixed universe also contains every endpoint-union rule identity, every
   canonical name occurring in either endpoint projection of those rules for
   `f`, and every alias occurring in either endpoint normalizer value for those
   names. This endpoint-union closure is sufficient for every hybrid because each
   atom selects an old or new endpoint block rather than inventing a third block.
3. Decoded target presence controls visibility of the rule-map stratum. For each
   framed identity `i`, define the current family projection

   `phi_f(r) = (id,family,requires,forbids)` when `r` exists and belongs to `f`,
   and `bottom` otherwise.

   Missing literal sequences decode as empty sequences; metadata is excluded.
   The concrete `rules` array emits only non-bottom projections in identifier
   order. Given the fixed union identity frame, omission uniquely decodes to
   `bottom`. Write `enc_F` for this sparse encoder and `dec_F` for the decoder
   that fills every omitted framed identity with `bottom`. Validation makes
   identities unique and ordering canonical, so for every admitted total framed
   rule map `m`, `dec_F(enc_F(m)) = m`. Thus `enc_F` is injective relative to the
   fixed frame, and equality of sparse identity/projection skeletons is exactly
   total rule-map equality. Nested literal and observation records belong to later
   strata and are compared separately. A
   deletion or move out of `f` is therefore visible even when the current array
   is empty. This claim is pair-relative: changing the frame changes the decoded
   map and hence the evidence predicate.
4. Current non-bottom rule projections expose each canonical literal occurrence
   and its complete normalizer coordinate: an ordered alias sequence or `bottom`.
5. At an absent target, every framed raw coordinate is `bottom`. At a present
   target, current non-bottom alias sequences expose effective `(value,origin)`
   coordinates at `a`, using `F` and `closed_world` defaults.
6. Literal, rule, family, reason, decisive, and classification fields are
   deterministic annotations of these decoded coordinates.

The frame is pair-relative and is not chosen by a proposed witness. The checker
has both versions and candidate, so it can reconstruct the same frame instead of
trusting a producer-supplied list of visible identities.

## Delta blocks and patch conformance

The global endpoint delta has four kinds of atoms.

- At an anchor present on just one side, a target atom adds or deletes the whole
  target. No program atom occurs at that anchor.
- At a common anchor, a program atom changes one effective `(value,origin)` pair
  by raw name.
- A normalizer atom adds, deletes, or replaces one complete ordered alias entry.
- A rule atom adds, deletes, or replaces one complete identified rule record,
  including a family move.

For candidate `x`, these atoms induce candidate-relative observable footprints.
A target atom at `a` owns target presence and every changed framed raw coordinate
at that anchor. A target atom elsewhere has an empty footprint. A program atom at
`a` owns its one raw pair; a program atom elsewhere is exterior. A normalizer atom
owns its mapping coordinate. A rule atom owns its `phi_f` coordinate exactly when
the old and new projections differ; metadata-only edits and moves between two
other families have empty footprints for `x`.

The footprints are pairwise disjoint. Target/program overlap is excluded by delta
construction. Program coordinates are keyed by anchor and raw name; mappings by
canonical name; rules by stable rule identity. Applying a subset changes a framed
coordinate to its new value exactly when its owning atom is selected. Every other
framed coordinate remains old. Applying all atoms consequently reproduces all
final observed fields, although it need not reproduce literally identical input
JSON: defaults can become explicit and excluded metadata can remain old.

## Structural support construction

If `a` is absent from the final input, the final traversal records only the
absent-target branch. Candidate membership implies that `a` existed before, so
`W_x` is exactly its target-deletion atom. Rule, mapping, and program atoms are
below the absent branch and are exterior even if their endpoint fields changed.

If `a` is present in the final input, let `C` contain every canonical literal in
final rules belonging to `f`, and let `A` contain every alias in final mappings
for names in `C`. Then `W_x` is the union of:

1. the target-addition atom for `a`, when `a` was absent before;
2. every rule atom whose old and new `phi_f` projections differ, including a rule
   deleted from or moved out of `f`;
3. every changed normalizer atom whose canonical key is in `C`; and
4. every changed program atom at `a` whose raw key is in `A`.

This is the producer's direct selector. It computes the complete delta and final
rule/mapping/alias vocabulary and selects the owning atoms. It does not enumerate
subsets. The retained increasing-cardinality implementation is a small-domain
comparison oracle only.

## Necessity

Assume a subset reproduces final evidence.

For a final-absent target, the distinct target-absence reason forces the unique
deletion atom. For a final-present target that was absent before, the presence
branch forces the unique target-addition block.

Now consider the total framed rule map. If a rule projection changed, omitting its
atom leaves the old `phi_f` value. This differs whether the final value is a tuple
or `bottom`. The latter is the important sparse case: deleting a rule or moving
it out of the family produces no final list member, but the fixed identity frame
decodes that omission as `bottom`; an unselected atom would leave the old tuple
and therefore a different sparse encoding. Another rule cannot compensate
because identities are framed separately. Metadata-only changes whose projections
agree are not forced.

The forced rule map fixes the final canonical occurrences. Every such occurrence
records either a complete alias sequence or explicit missing mapping, so a changed
mapping reaches the final record only through its normalizer atom. Once final
aliases are fixed, each effective value-origin pair reaches its final value only
through its common-target program atom, or through the already forced whole-target
addition. Hence every atom listed in `W_x` is necessary.

This proof depends on complete all-branch evidence. A refuted rule still records
its observations, a true family alternative does not erase other rules, and
origin or declared sequence-order changes remain observable.

## Sufficiency and supersets

At a final-absent target, the selected deletion establishes the complete absence
branch. At a final-present target, a selected addition, if needed, establishes
presence and owns all changed raw coordinates at that one-sided anchor. Selected
rule atoms give exactly the final total framed family projection, including
`bottom` for old-only or moved rules. Selected referenced normalizer atoms give
the final alias sequences or missing entries. Selected referenced program atoms
give final raw value-origin pairs. All other visible coordinates already agree.
Deterministic bottom-up evaluation therefore reconstructs every final evidence
field.

An additional atom has a footprint disjoint from the final read closure. It cannot
overwrite a forced coordinate because footprints are disjoint, and it cannot
change later visibility because all visibility controls are decoded from the
already synchronized prefix. Every superset of `W_x` remains sufficient. Together
with necessity, this proves the principal-filter property and unique minimum.

## Independent deletion checker

For each atom `d` in the full delta, the checker applies `D minus {d}` to the old
input and compares framed final evidence. These `|D|` answers construct the
deletion core

`C_Q = { d in D : Q(D minus {d}) is false }`.

For any finite upward-closed replay predicate with `Q(D)=true`, every sufficient
set contains `C_Q`; indeed `C_Q` is their intersection. It is a least sufficient
set exactly when replaying `C_Q` succeeds. If that replay fails, the finite
upward-closed family has at least two incomparable inclusion-minimal sufficient
sets. Under the framed block-footprint theorem, `C_Q=W_x`; thus the `|D|` queries
attain the black-box identification lower bound and the extra replay checks core
sufficiency.

The core replay is fail-closed relative to the admitted theorem contract. A bound
or malformed-input failure is an admission error; failure of the reconstructed
core to reproduce final evidence is a distinct consistency error. This replay
does not independently establish upward closure, frame completeness, stable
identity, or disjoint footprints. If upward closure and full-delta sufficiency
are established independently, failure proves that no least sufficient set
exists. Without monotonicity, neither failure nor success has that
order-theoretic interpretation.
The checker also reconstructs endpoint evidence, classification, complete sorted
delta, candidate membership, and sorted, duplicate-free in-delta witness
membership. It imports no producer module.

The default admission cap is 12 atoms. A caller can explicitly choose a larger
cap. This is an input bound, not an exponential-search requirement. If `P` bounds
one hybrid patch and `E_x` one candidate evaluation, replay work is
`O((d+1)(P+E_x))`, plus endpoint and delta construction. The replay count is not a
constant-memory or linear-wall-time claim.

## Value-only negative control

One rule requires canonical `p`, mapped to aliases `u,v`. Both raw values start
false and end true. Either singleton program atom reproduces the final truth value,
while their intersection does not. Complete framed evidence records both pairs and
requires both. The retained negative-control JSON records these sufficient sets.
For the value-only predicate, both co-singleton deletions succeed, so the deletion
core is empty; replaying it fails. This is the upward-closed no-least branch of
the deletion-core characterization.

More generally, take a finite set-cover instance whose sets cover the universe. Create one raw alias per set and
one required canonical fact per universe element. Map each canonical fact to the
aliases corresponding to sets that contain that element. Selecting program atoms
makes every required fact true exactly when the selected sets cover the universe,
with the same cardinality. This is a proof construction, not an executed
hard-instance claim.

## Boundaries

The proof does not transfer unchanged to an endpoint-dependent frame that varies
by subset, ambiguous sparse absence, short-circuit evidence, overlapping
footprints, repeated edit-log writes, unordered-but-un-normalized aliases,
identity migration, value-only comparison, or a whole-target replacement mixed
with program atoms at the same anchor. The selector is an exact framed
read-footprint projection for this interface, not a general causal explanation or
a proof of business-logic safety.
