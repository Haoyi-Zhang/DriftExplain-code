# Identification and verification under the same promise

Fix a finite atom universe D, d=|D|, and a deterministic Boolean replay oracle
Q. The promise in both tasks is identical: for some unknown H subseteq D,
Q(S) iff H subseteq S. The framed complete-keyed, separable-delta theorem
establishes this promise for the finite rule analyzer. Neither algorithm checks
the promise by querying Q. The oracle exposes only a Boolean answer; endpoint
construction, admission, and evaluation cost are not counted as oracle queries.

## Identification

There is no proposed answer. The algorithm must output H. All 2^d possible H
are realizable by the one-stratum construction in stratified_support.md.
A deterministic binary decision tree needs d queries in the worst case.
The d queries Q(D minus {a}) identify H exactly: a is in H iff the answer is
false. The delivered identification checker additionally replays this core,
using d+1 hybrid evaluations. That extra replay is a consistency check, not
part of the information-theoretic identification bound.

## Verification contract and algorithm

The input additionally supplies a candidate W subseteq D, k=|W|. Return true
exactly when W=H. Both lists must be sorted, duplicate-free strings; an invalid
shape or out-of-universe entry raises ValueError before any query. The callable
must implement the deterministic Boolean oracle with the stated promise.

1. If W differs from D, query Q(W); reject if false. If W=D, Q(W)=true
   follows from the promise and this query is omitted.
2. For every a in W in canonical order, query Q(W minus {a}); reject if true.
3. Accept if all these checks pass.

The empty universe needs zero queries. An empty candidate in a nonempty universe
needs one. An accepted proper candidate uses exactly k+1 queries; an accepted
full-universe candidate uses d. A rejected candidate can stop earlier.

## Soundness

Step 1 or the full-universe promise gives H subseteq W. Suppose acceptance held
with some a in W minus H. Then H subseteq W minus {a}, so its deletion query
would be true and step 2 would reject. Hence W subseteq H and W=H. This rules
out both missing essential atoms and sufficient strict supersets.

## Completeness

If W=H, Q(W) is true, and each deletion omits an element of H so is false.
The algorithm accepts, including H=empty and H=D.

## Matching verification bound

For a fixed supplied W, consider the accepting oracle H=W and a deterministic
verifier sound and complete for every principal filter on D. For each a in W,
the transcript must distinguish H=W from H=W minus {a}. A query S distinguishes
them only if it contains W minus {a} but omits a. One query cannot distinguish
two such deletion neighbors: it would have to contain and omit each of the two
atoms. At least k queries are therefore necessary on the accepting transcript.

If W is proper, choose b in D minus W. The transcript must also distinguish
H=W from H=W union {b}. This requires a query containing W and omitting b.
No deletion-neighbor query contains W, so at least one additional query is
necessary. Q(W) distinguishes every addition neighbor at once. The bounds k+1
for proper W and d for W=D are attained by the algorithm above. These are
verification bounds with W supplied, not the d-query identification bound.

## Finite certificate integration

check_candidate_certificate shares the original checker's admission sequence:
valid endpoints, schema, candidate membership, nonboolean integer caps,
reconstructed old/new evidence and class, complete sorted delta, and canonical
in-delta witness. It then uses verify_candidate_witness with Q(S) defined by
the independent checker's patch and exact final-evidence comparison. Thus under
the concrete structural theorem it accepts iff the required fields agree and
the supplied witness is the unique least support. The legacy check_certificate
retains identification plus core replay for comparison and its existing tests.
Both import no producer code and trust the same written finite semantics.

The candidate path performs two endpoint evaluations plus at most k+1 hybrid
evaluations (d when k=d); the already reconstructed new evidence is reused.
It still reconstructs the entire delta and validates the full inputs. If P is
hybrid patch/copy/validation cost and E is one candidate evaluation, its replay
work is O((k+1)(P+E)), besides admission and endpoint/delta construction. This
is a query bound, not a runtime, memory, extraction, or deployment guarantee.

## Structure-visible receiver correspondence

`check_structural_certificate` has the same endpoint, class, complete-delta,
bound and witness-shape admission as the two replay paths. It then scans the
independently reconstructed complete final evidence and the independently
reconstructed endpoint atom bodies. Unlike the binary-oracle task, it can read
the representation that determines visibility and coordinate ownership.

For a final absent target, the distinct absence branch forces exactly its target
deletion. For a present target, a one-sided target atom is forced by presence.
Every rule atom with a changed family projection is forced, including deleted
or moved-out rules whose identities remain in the endpoint-union frame. Final
literal records expose exactly their normalizer names; their complete
observations expose exactly the final alias value-origin coordinates. The scan
selects the changed mapping and program atoms at those coordinates. Metadata
outside the projection is not a read. These cases exhaust the four admitted
atom constructors, so the scan returns exactly the concrete `W_x` in support.md.
The principal-filter theorem therefore gives soundness and completeness of
comparing the supplied witness with this scan, conditional on the same finite
semantics and representation premises. This is implementation correspondence
with the existing projection theorem, not a new generic minimal-set theorem.

This path performs two endpoint evaluations and one complete delta construction,
and no hybrid evaluations. It still reads/validates the full inputs and scans
all atom bodies and final evidence. Its zero membership calls do not contradict
the d-query identification or candidate-relative verification bounds: those
bounds deny structure access. The identification implementation likewise reuses
its invocation-local admitted delta and final evidence, rather than rebuilding
them; it still performs d co-singleton hybrids plus one core replay. This reuse
changes neither the predicate nor its query count and is not a timing result.

## Boundary: monotonicity alone is insufficient for leastness

For D={x,y} and Q(S)=[x in S or y in S], W={x} passes the sufficiency and
single-deletion tests, although {y} is another inclusion-minimal sufficient set
and no least support exists. With upward closure alone, the algorithm checks
inclusion-minimality; the principal-filter promise is required to infer a unique
least set and minimum cardinality. Outside monotonicity even that inference
fails. Tests execute this harmless Boolean control. No source program, exploit,
or external analyzer is executed by the regression.
