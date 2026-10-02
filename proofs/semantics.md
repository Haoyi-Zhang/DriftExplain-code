# Finite semantics, impact, and source boundary

## Determinacy

Normalizer lookup is absent (U), contains a true alias (T), contains no true but
some unknown alias (U), or contains only false aliases (F). A rule is false if
any requirement is false or any prohibition true; otherwise it is unknown if
some literal is unknown, and true otherwise. Family disjunction selects true
before unknown before false. An absent target or empty family is false, with
different absence reasons. Ordered evidence makes decisive entries deterministic.
The relational class gives uncertainty precedence and partitions the remaining
four Boolean endpoint pairs into preserved, newly justified, invalidated and
absent. This is total only on the stated well-formed input language.

## Impact and incremental equivalence

A target atom marks every family at its anchor. A rule atom marks its old and
new families at every union anchor. A normalizer atom marks every family whose
old or new rules mention that canonical name. A program atom marks its anchor
and every family that mentions a canonical name whose old or new alias entry
contains that raw name. Intersect their union with the pair's candidate space.

Outside this set, target presence agrees, every family rule is unchanged, every
referenced mapping agrees, and every observed raw value-origin pair agrees.
Hence endpoint evidence and values agree. This compares old and new reads; it
does not require independence of arbitrary intermediate edit sequences.
For valid old and new endpoint versions, recompute affected candidates under
the new model and reuse the rest from a correct old cache covering their union
candidate space. Case analysis then gives exact equality with full new
analysis. Both incremental entry points validate both endpoints before they
construct the candidate space, including when a caller supplies the old cache.
Cache key validation then checks coverage but not correctness of cached values.
Untrusted cached values are outside this incremental theorem's precondition.

The impact set is conservative, not minimum. For example, an origin-only change
or a metadata-only rule edit can trigger a value recomputation. Both old and new
dependencies are needed to avoid losing newly added or removed reads. Exact
new-evidence support and conservative endpoint impact are different relations.

## Source-only indistinguishability

Keep target observations fixed with an old true rule. One new model leaves its
rules and mappings unchanged; another removes a required mapping, with no
independent refutation. The old/new raw inputs seen by a source-only observer
are identical, while the correct classes are preserved and unresolved. Such an
observer cannot classify all pairs. This result says nothing about an analyzer
that actually receives the catalogue and normalization inputs.

## Conditional scenario-property bridge

Let admitted source/configuration endpoints be `P_o,P_n`, and let deterministic,
fail-closed extraction `X` produce finite keyed endpoints `o=X(P_o)` and
`n=X(P_n)`. Checked correspondence must fix one comparison frame and a canonical
atom set shared by source/configuration and finite levels. For a source-side
hybrid operator `patch_P` over that atom set, the required commuting condition is,
for every subset `S`,

`X(patch_P(P_o,S))_F = patch(o,S)_F`.

The source-relative observation must also factor through extraction:

`O_F(P) = E_F(X(P))`.

If the induced finite delta is observably separable, these equations make every
source-relative subset predicate pointwise equal to the finite predicate. The
principal-filter theorem therefore transfers. The replay-query lower bound
transfers only if the lifted checker is still denied the frame and footprints
and can access this predicate solely through binary membership queries.

This conditional proposition maps a scenario-property interface to a checkable
finite evolution question. It does not prove that GPTScan, LogicScan, or any
Solidity frontend meets the premises. There is no concrete source semantics,
control-flow extraction, path feasibility, source-to-fact soundness, source-side
hybrid relation, or checked identity migration in this artifact. Nine fact
abstractions do not discharge these premises or constitute 120 source-contract
cases.
