# Structural support for framed complete-keyed evidence

## 1. Fixed comparison frame

Fix an old state `o`, a new state `n`, and one observation. A comparison frame
`F` is chosen from that endpoint pair and observation before any change subset is
selected. It fixes:

1. a finite coordinate set partitioned into strata
   `K = K_0 disjoint-union ... disjoint-union K_h`;
2. stable coordinate identities and canonical orders;
3. a projected value `z_F(k)` for every admitted state `z` and coordinate `k`;
4. an ordinary distinguished absence value `bottom`; and
5. one canonical evidence decoder shared by every endpoint hybrid.

The last condition permits a sparse byte representation without making omission
ambiguous. A serialized keyed map may omit `(k,bottom)` only when `F` fixes the
possible keys and the decoder therefore restores every omitted key as `bottom`.
The comparison is pair-relative: changing the endpoint frame while searching
subsets would define a different predicate.

Evidence is defined first as a decoded stratified record. At stratum `i`, the
visible set `R_i` is a deterministic function only of decoded records at lower
strata. The record contains every `(key,value)` pair for `R_i` in canonical order.
False, unknown, absence, stable identity, origin, and semantically ordered
sequences are ordinary recorded values. No unrecorded coordinate may choose a
later visible set.

The concrete serialization `E_F(z)` must be an injective canonical encoding of
all stratum records. Deterministic annotations such as a derived value, reason,
or decisive entry may be included when they are functions of the decoded
records. Such annotations do not add independent state coordinates and may not
control visibility unless their inputs have already appeared in the decoded
prefix. Serialization order need not be stratum order, provided the decoder
recovers the same conceptual record uniquely.

The final decoded read closure is

`R_F(z) = union_i R_i(z)`.

## 2. Observably separable block delta

Let the changed projected coordinates be

`C_F = { k in K : o_F(k) != n_F(k) }`.

A canonical endpoint delta `D` is *observably separable* for this frame when each
atom `d` has a possibly empty footprint `B_F(d) subseteq C_F` satisfying:

1. the footprints are pairwise disjoint;
2. their union is exactly `C_F`; and
3. for every subset `S subseteq D` and coordinate `k`,

   `patch(o,S)_F(k) = n_F(k)` if the unique atom whose footprint contains `k`
   belongs to `S`, and equals `o_F(k)` otherwise.

Thus one atom may own several changed coordinates. A whole-target addition is a
block write, not one coordinate atom. Atoms with empty candidate-relative
footprints are also allowed: they may change excluded metadata or another
observation while leaving this projected state unchanged. The patch law rules
out a selected atom changing a coordinate outside its declared footprint.

For the fixed frame, define

`Q(S) := [ E_F(patch(o,S)) = E_F(n) ]`.

Define the structural support by atom ownership:

`W_F = { d in D : B_F(d) intersects R_F(n) }`.

This is not simply a set of coordinates. It is the set of endpoint atoms owning
at least one changed coordinate read by the final decoded traversal.

## 3. Prefix synchronization

Write `R_<=i(n) = union_{j=0}^i R_j(n)`. If `S` contains every atom whose
footprint intersects `R_<=i(n)`, then the hybrid and final decoded records agree
through stratum `i`; consequently they select the same visible set at stratum
`i+1`, when it exists.

The empty prefixes agree, so both traversals expose the same stratum-zero key set.
Every changed coordinate in that final set belongs to a selected footprint and
therefore has its new value by the patch law; every unchanged coordinate already
agrees at the endpoints. Suppose the decoded records agree through stratum
`i-1`. They choose the same stratum-`i` keys. Every changed coordinate in that
final set again belongs to a selected footprint, so the records and deterministic
annotations agree. Induction and canonical encoding give equal serialized
prefixes.

## 4. Necessity

If `Q(S)` holds, then `W_F subseteq S`.

Take `d in W_F` and choose a coordinate `k` in
`B_F(d) intersect R_F(n)`, recorded at stratum `i`. Exact serialized equality and
injective decoding imply equal lower records, so both traversals expose `k` at
stratum `i`. If `d` is omitted, the patch law leaves `k` at `o_F(k)`, which differs
from `n_F(k)` because footprints contain only changed coordinates. Disjoint
footprints prevent another atom from supplying the new value. The decoded
stratum record, and hence its injective encoding, would differ. Therefore `d`
must be selected.

This argument also covers an atom whose footprint spans several strata: choose
any final-visible changed coordinate in the footprint. It covers sparse deletion
only because the fixed frame decodes the omitted key as an ordinary `bottom`
coordinate.

## 5. Sufficiency and exterior irrelevance

If `W_F subseteq S`, then `Q(S)` holds.

Induct over strata. Equal lower prefixes choose the same visible set. For every
coordinate visible in the final traversal:

- if its endpoint values differ, it belongs to exactly one footprint, that atom
  belongs to `W_F`, and the hybrid therefore has the new value;
- if its endpoint values agree, the patch law leaves the common value unchanged.

So the decoded stratum maps and deterministic annotations agree. An atom outside
`W_F` has a footprint disjoint from the final read closure. Since an unrecorded
coordinate cannot choose later visibility, selecting such an atom cannot disturb
the synchronized traversal. The induction reaches the complete evidence record.

## 6. Principal-filter theorem

For every `S subseteq D`,

`E_F(patch(o,S)) = E_F(n)` if and only if `W_F subseteq S`.

Therefore the sufficient subsets are exactly

`{ S subseteq D : W_F subseteq S }`.

They form the principal filter generated by `W_F`. The generator is the unique
least sufficient subset under inclusion and the unique cardinality-minimum
sufficient subset. A producer does not search subsets: it computes the final
decoded read closure, maps each changed read to its unique owning atom, and
returns the resulting atom set.

## 7. Batch support and refinement

For a finite canonically ordered observation set `X`, each observation may use a
different fixed frame over the same endpoint delta. Batch equality is componentwise,
so its support is

`W_X = union_{x in X} W_x`.

A shared atom is serialized once, but a hitting set is not sufficient: each
component requires every atom in its own support.

Suppose contracts `E_1` and `E_2` over the same delta both satisfy the
principal-filter theorem, and `E_2 = pi(E_1)` for a deterministic projection
`pi`. Equality under `E_1` implies equality under `E_2`, so the sufficient-set
family for contract 1 is contained in that for contract 2. Principal-filter
inclusion reverses generator inclusion, giving `W_2 subseteq W_1`. A refinement
can only retain or enlarge support while both contracts stay inside the theorem.
A coarsening may instead introduce incomparable minima.

## 8. Representation invariance

Let `f` be a bijection on coordinates and `g` a bijection on delta atoms. Suppose
they preserve strata, values, absence, canonical decoding, and visibility, and
for every atom `d`,

`f(B_F(d)) = B_F'(g(d))`.

The renamed final traversal reads exactly `f(R_F(n))`. A footprint intersects the
original closure exactly when its image intersects the renamed closure. Hence

`W_F' = g(W_F)`.

This permits checked namespacing and dictionary compression. A many-to-one map is
not covered: merging identities can overlap footprints or create alternatives.

## 9. Optimal replay-query identification

Assume a checker cannot inspect the frame or footprints and may only query the
binary predicate `Q(S)`. Let `d = |D|`. Every subset of `D` is realizable as a
support within the theorem's class: for a chosen `W subseteq D`, use one stratum,
one changed coordinate `k_d` per atom, singleton footprint `{k_d}`, old value
zero, new value one, and visible set `{k_d : d in W}`. The resulting predicate is
exactly

`Q_W(S) = [ W subseteq S ]`.

There are therefore `2^d` possible predicates. A deterministic binary decision
tree identifying one of them needs depth at least `log2(2^d) = d` in the worst
case.

The lower bound is attained inside the principal-filter class by the `d` queries
`D minus {d}`. Such a query is false exactly when `d` belongs to `W_F`.

The same answers have a useful characterization for any finite upward-closed
predicate `Q` with `Q(D)=true`. Define the deletion core

`C_Q = { d in D : not Q(D minus {d}) }`.

Every sufficient set contains `C_Q`: if a sufficient `S` omitted some
`d in C_Q`, then `S subseteq D minus {d}` and upward closure would make
`Q(D minus {d})` true. Conversely, if `d` is not in `C_Q`, then
`D minus {d}` is itself a sufficient set that omits `d`. Hence

`C_Q = intersection { S subseteq D : Q(S) }`.

The following are equivalent:

1. `Q(C_Q)`;
2. `C_Q` is the unique least sufficient set; and
3. the sufficient sets are exactly the supersets of `C_Q`.

For the converse, any least sufficient set equals the intersection of all
sufficient sets, which is `C_Q`. If `Q(C_Q)` fails, no least sufficient set
exists. Because the sufficient family is finite, nonempty, and upward closed,
it nevertheless has inclusion-minimal members. If there were only one such
member, it would be contained in every sufficient set and would therefore be a
least member. Thus core-replay failure entails at least two incomparable
inclusion-minimal sufficient sets.

The delivered checker therefore uses the `d` co-singleton replays to construct
`C_Q` and replays `C_Q` once. Under the principal-filter theorem,
`C_Q=W_F` and that replay succeeds. More generally, under an independently
established upward-closure premise, failure of the core replay proves that no
least sufficient set exists. The replay does not itself test upward closure,
frame completeness, stable correspondence, disjoint footprints, or any other
representation premise; success cannot certify them.

This yields a three-layer interpretation. Co-singleton answers recover only the
unavoidable intersection `C_Q`. Core sufficiency establishes leastness only
after upward closure has been justified. The framed block-footprint theorem is
the stronger representation argument that derives the principal-filter
predicate used by the checker.

## 10. Finite rule-analyzer instantiation

For candidate `(family,anchor)`, the comparison frame is reconstructed from both
finite endpoints.

1. The fixed coordinate universe contains target presence; every rule identity
   in the endpoint union; every canonical name occurring in either endpoint
   projection of those rules for the candidate family; and every alias occurring
   in either endpoint normalizer value for those names. This endpoint-union
   closure contains every coordinate that any hybrid can expose.
2. At an absent candidate target, every framed raw coordinate has value
   `bottom`; at a present target it is the effective `(value,origin)` pair using
   `F` and `closed_world` defaults. Decoded target presence decides whether the
   rule-map stratum is traversed. A rule coordinate has canonical value `(id,family,ordered requires,ordered
   forbids)` when the current rule belongs to the candidate family and `bottom`
   otherwise. The JSON list sparsely emits only non-bottom projections in
   identifier order; the fixed union frame restores omitted entries. With
   `enc_F` as this encoder and `dec_F` filling every omitted framed identity with
   `bottom`, unique validated identities and canonical order give
   `dec_F(enc_F(m)) = m` for every admitted total framed rule map `m`. Hence the
   sparse encoder is injective relative to the fixed frame. A deletion or move
   out of the family is therefore a changed final coordinate even if the final
   list is empty.
3. Every canonical literal in a current non-bottom rule projection exposes its
   complete ordered normalizer coordinate, including explicit missing mapping.
4. Every alias in a current non-bottom mapping exposes the effective raw value and
   origin pair at the candidate target.
5. Rule, literal, family, reason, decisive, and class fields are deterministic
   annotations of those decoded records.

The concrete delta has whole-target add/delete atoms, common-target raw
value-origin atoms, whole normalizer-entry atoms, and whole identified-rule
atoms. Their candidate-relative footprints are:

- a one-sided target atom owns target presence and all changed framed raw
  coordinates at that anchor;
- a program atom owns one effective raw value-origin coordinate;
- a normalizer atom owns one ordered mapping coordinate;
- a rule atom owns one candidate-family projection coordinate when that
  projection changes, and has an empty footprint when it does not; and
- atoms outside the candidate view have empty footprints.

Target and program atoms cannot coexist at the same anchor. The remaining atom
kinds have disjoint stable keys. Ignored metadata is outside the projected state;
a metadata-only rule atom can consequently have an empty footprint. Full-delta
replay is observational rather than necessarily identical to the input JSON after
default normalization.

The producer's direct selector is precisely the set of atoms whose footprints
intersect the final decoded read closure. The checker reconstructs the same
finite predicate with separate code and deletion replay.

## 11. Boundaries and falsifiers

### Value-only observation

Let one required canonical fact have aliases `u,v`, both changing from false to
true. Either singleton endpoint atom makes the final truth value true, so there
are two incomparable minimum value supports. Complete evidence records both
alias/value-origin pairs and therefore requires both.

For the value-only predicate, the deletion core is empty because deleting either
atom from the full delta leaves a sufficient singleton, but the empty set is not
sufficient. This is exactly the `Q(C_Q)=false` branch of the deletion-core
characterization: an upward-closed predicate has no least sufficient set.

For a set-cover instance with universe `U` and sets `B_j` whose union is `U` (the problem remains NP-hard under this restriction), create one changed
alias per set and one required canonical fact per element. Map the fact for `e`
to exactly the aliases whose sets contain `e`. Selecting aliases makes every
required fact true exactly when the selected sets cover `U`, preserving
cardinality. Minimum value support is therefore at least as hard as set cover.
This is a proof construction, not an executed solver claim.

### Overlapping footprints or repeated writers

Let one recorded bit start at zero. Atom `a` writes one and a later atom `b`
writes zero. The full patch has final evidence zero. The empty subset is
sufficient; its superset `{a}` is not; `{a,b}` is sufficient. Upward closure
fails. Its deletion core is `{b}` and that core replays successfully even though
the empty set is least. Thus a successful core replay cannot substitute for the
upward-closure premise. The same concern arises if two nominal endpoint atoms can
both alter one framed coordinate. The separability premise excludes these cases.

### Ambiguous sparse absence

If two different key frames can decode the same sparse bytes, deleting an
old-only key may or may not be visible depending on hidden decoder state. Evidence
equality is then not one fixed predicate. The theorem requires one endpoint-bound
frame or an explicit total representation.

### Hidden controls and short-circuit traces

If an unrecorded value selects a later branch, an atom outside the reported read
set can change evidence. If evidence records only one successful or decisive
branch, dominated alternatives can disappear and incomparable minima can arise.
The theorem supplies no result for either interface.

### Unstable identity

A rename, split, or merge can admit several plausible old/new coordinate
correspondences. Each correspondence induces a different frame, delta, and
possibly support. Stable identity or an independently checked correspondence
certificate is therefore an admission premise.

## 12. Certificate acceptance

For valid finite endpoints, the checker first admits the certificate's schema
and candidate in the union family-anchor space, nonboolean integer bounds
`0 <= |D| <= b <= M`, and sorted, duplicate-free in-delta witness shape, under
the nonnegative integer checker cap `M`. It independently reconstructs old/new
evidence, classification, candidate frame, canonical complete delta, and deletion
core. Conditional on that admission and the structural theorem premises,
acceptance is equivalent to exact required serialized fields, a witness equal
to the core, and core replay reproducing final evidence. The core then equals
the unique least support. Semantic equality alone does not admit a certificate
whose declared bound exceeds the configured checker cap.

A bound failure is distinct from a failed core-sufficiency replay. Under the
theorem premises, the latter is an implementation inconsistency. Outside those
premises, it may instead expose an upward-closed predicate with no least
sufficient set; a successful replay still does not prove upward closure or the
frame/footprint premises. The acceptance statement also assumes that the Python
functions implement the written finite semantics. It is not a mechanized proof,
source-observation authentication, cache-authenticity guarantee, or hostile-input
resource supervisor.

## 13. Conditional source and layered lifting

Let admitted source/configuration endpoints be `P_o,P_n`. A deterministic,
fail-closed extractor `X` yields finite keyed endpoints `o=X(P_o)` and
`n=X(P_n)`. Checked correspondence must fix one frame `F` and one canonical atom
set `D` for both levels. Let `patch_P(P_o,S)` be an admitted source/configuration
hybrid for each `S subseteq D`. The source lift requires two pointwise equations:

`X(patch_P(P_o,S))_F = patch(o,S)_F` for every `S subseteq D`, and

`O_F(P) = E_F(X(P))` for every admitted endpoint or hybrid `P`.

The first is a commuting condition for extraction and subset patching on all
framed coordinates; it packages syntax coverage, stable identity, complete
source/configuration delta coverage, and the absence-decoding frame. The second
states exactly which source-relative observation the finite evidence represents.
If the induced finite delta is observably separable, then for every `S`,

`O_F(patch_P(P_o,S)) = O_F(P_n)` iff `W_F subseteq S`.

This follows because the source-relative predicate is pointwise identical to the
finite predicate. The query lower bound and matching deletion upper bound carry
over only when the post-extraction checker remains denied the frame and
footprints and may access the predicate solely through binary membership
queries. A checker given structural access can identify support without those
queries.

The artifact supplies no source parser, Solidity-like semantics, source-side
hybrid relation, identity certificate, extraction proof, or 120-contract corpus.
The lifting statement is conditional and identifies the missing bridge; it does
not discharge it.
