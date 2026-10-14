"""Independent replay checker for finite finding-drift certificates.

This file intentionally imports no producer code.  It repeats the small frozen
semantics in a differently structured implementation and validates producer
claims from serialized inputs alone.
"""
from __future__ import annotations

import copy
import itertools
from typing import Any, Callable, Iterable

_ALLOWED = {"T", "F", "U"}


def _identifier(value: Any) -> bool:
    """Check the independently implemented serialized-identifier grammar."""
    if not isinstance(value, str) or not value or "|" in value:
        return False
    return all(ord(character) >= 32 and ord(character) != 127 for character in value)


def _target_table(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["anchor"]: entry for entry in model["targets"]}


def _rule_table(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["id"]: entry for entry in model["rules"]}


def _check_input(model: dict[str, Any]) -> bool:
    try:
        if not isinstance(model, dict):
            return False
        if set(("targets", "normalizer", "rules")) - set(model):
            return False
        if not isinstance(model["targets"], list):
            return False
        if not isinstance(model["normalizer"], dict):
            return False
        if not isinstance(model["rules"], list):
            return False
        if any(not isinstance(entry, dict) for entry in model["targets"]):
            return False
        anchors = [entry["anchor"] for entry in model["targets"]]
        if (
            len(anchors) != len(set(anchors))
            or any(not _identifier(value) for value in anchors)
        ):
            return False
        if any(not isinstance(entry, dict) for entry in model["rules"]):
            return False
        identifiers = [entry["id"] for entry in model["rules"]]
        if (
            len(identifiers) != len(set(identifiers))
            or any(not _identifier(value) for value in identifiers)
        ):
            return False
        for target in model["targets"]:
            raw = target.get("raw", {})
            origins = target.get("origins", {})
            if not isinstance(raw, dict) or not isinstance(origins, dict):
                return False
            if any(
                not _identifier(name) or value not in _ALLOWED
                for name, value in raw.items()
            ):
                return False
            if any(
                not _identifier(name)
                or not isinstance(origin, str)
                for name, origin in origins.items()
            ):
                return False
        for canonical, aliases in model["normalizer"].items():
            if not _identifier(canonical):
                return False
            if (
                not isinstance(aliases, list)
                or not aliases
                or any(not _identifier(alias) for alias in aliases)
                or len(aliases) != len(set(aliases))
            ):
                return False
        for rule in model["rules"]:
            if not _identifier(rule.get("family")):
                return False
            for field in ("requires", "forbids"):
                values = rule.get(field, [])
                if (
                    not isinstance(values, list)
                    or any(not _identifier(value) for value in values)
                    or len(values) != len(set(values))
                ):
                    return False
    except (KeyError, TypeError):
        return False
    return True


def _candidate_member(
    before: dict[str, Any], after: dict[str, Any], family: str, anchor: str
) -> bool:
    families = {entry["family"] for entry in before["rules"]}
    families.update(entry["family"] for entry in after["rules"])
    anchors = {entry["anchor"] for entry in before["targets"]}
    anchors.update(entry["anchor"] for entry in after["targets"])
    return family in families and anchor in anchors


def _literal(model: dict[str, Any], target: dict[str, Any], name: str) -> dict[str, Any]:
    aliases = model["normalizer"].get(name)
    if aliases is None:
        return {
            "canonical": name,
            "value": "U",
            "reason": "missing_normalizer",
            "aliases": [],
            "observations": [],
        }
    observations = []
    for alias in aliases:
        observations.append(
            {
                "alias": alias,
                "value": target.get("raw", {}).get(alias, "F"),
                "origin": target.get("origins", {}).get(alias, "closed_world"),
            }
        )
    values = {entry["value"] for entry in observations}
    if "T" in values:
        value, reason = "T", "true_alias"
    elif "U" in values:
        value, reason = "U", "unknown_alias"
    else:
        value, reason = "F", "all_aliases_false"
    return {
        "canonical": name,
        "value": value,
        "reason": reason,
        "aliases": list(aliases),
        "observations": observations,
    }


def _rule_result(
    model: dict[str, Any], target: dict[str, Any], rule: dict[str, Any]
) -> dict[str, Any]:
    positive = [_literal(model, target, name) for name in rule.get("requires", [])]
    negative = [_literal(model, target, name) for name in rule.get("forbids", [])]
    decisive = next((item for item in positive if item["value"] == "F"), None)
    reason = "required_false"
    if decisive is None:
        decisive = next((item for item in negative if item["value"] == "T"), None)
        reason = "forbidden_true"
    if decisive is not None:
        value = "F"
    else:
        decisive = next(
            (item for item in positive + negative if item["value"] == "U"), None
        )
        if decisive is None:
            value, reason = "T", "all_literals_satisfied"
        else:
            value, reason = "U", "unknown_literal"
    return {
        "rule": rule["id"],
        "family": rule["family"],
        "value": value,
        "reason": reason,
        "decisive": decisive,
        "required": positive,
        "forbidden": negative,
    }


def _family_result(model: dict[str, Any], family: str, anchor: str) -> dict[str, Any]:
    target = _target_table(model).get(anchor)
    if target is None:
        return {
            "family": family,
            "anchor": anchor,
            "value": "F",
            "reason": "target_absent",
            "rules": [],
        }
    rules = sorted(
        (entry for entry in model["rules"] if entry["family"] == family),
        key=lambda entry: entry["id"],
    )
    if not rules:
        return {
            "family": family,
            "anchor": anchor,
            "value": "F",
            "reason": "family_absent",
            "rules": [],
        }
    evidence = [_rule_result(model, target, rule) for rule in rules]
    states = {entry["value"] for entry in evidence}
    if "T" in states:
        value, reason = "T", "supporting_rule"
    elif "U" in states:
        value, reason = "U", "unresolved_rule"
    else:
        value, reason = "F", "all_rules_refuted"
    return {
        "family": family,
        "anchor": anchor,
        "value": value,
        "reason": reason,
        "rules": evidence,
    }


def _classify(left: str, right: str) -> str:
    if "U" in (left, right):
        return "unresolved"
    if (left, right) == ("T", "T"):
        return "preserved"
    if (left, right) == ("F", "T"):
        return "newly_justified"
    if (left, right) == ("T", "F"):
        return "invalidated"
    return "absent"


def _changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    left_targets = _target_table(before)
    right_targets = _target_table(after)
    for anchor in sorted(left_targets.keys() | right_targets.keys()):
        if anchor not in left_targets or anchor not in right_targets:
            changes.append(
                {
                    "id": f"target|{anchor}",
                    "kind": "target",
                    "anchor": anchor,
                    "old": copy.deepcopy(left_targets.get(anchor)),
                    "new": copy.deepcopy(right_targets.get(anchor)),
                }
            )
            continue
        left = left_targets[anchor]
        right = right_targets[anchor]
        raw_names = set(left.get("raw", {})) | set(right.get("raw", {}))
        raw_names |= set(left.get("origins", {})) | set(right.get("origins", {}))
        for raw_name in sorted(raw_names):
            left_obs = {
                "value": left.get("raw", {}).get(raw_name, "F"),
                "origin": left.get("origins", {}).get(raw_name, "closed_world"),
            }
            right_obs = {
                "value": right.get("raw", {}).get(raw_name, "F"),
                "origin": right.get("origins", {}).get(raw_name, "closed_world"),
            }
            if left_obs != right_obs:
                changes.append(
                    {
                        "id": f"program|{anchor}|{raw_name}",
                        "kind": "program",
                        "anchor": anchor,
                        "raw": raw_name,
                        "old": left_obs,
                        "new": right_obs,
                    }
                )
    for name in sorted(set(before["normalizer"]) | set(after["normalizer"])):
        if before["normalizer"].get(name) != after["normalizer"].get(name):
            changes.append(
                {
                    "id": f"normalizer|{name}",
                    "kind": "normalizer",
                    "canonical": name,
                    "old": copy.deepcopy(before["normalizer"].get(name)),
                    "new": copy.deepcopy(after["normalizer"].get(name)),
                }
            )
    left_rules = _rule_table(before)
    right_rules = _rule_table(after)
    for rid in sorted(left_rules.keys() | right_rules.keys()):
        if left_rules.get(rid) != right_rules.get(rid):
            changes.append(
                {
                    "id": f"rule|{rid}",
                    "kind": "rule",
                    "rule": rid,
                    "old": copy.deepcopy(left_rules.get(rid)),
                    "new": copy.deepcopy(right_rules.get(rid)),
                }
            )
    return sorted(changes, key=lambda item: item["id"])


def _patch(base: dict[str, Any], selected: Iterable[dict[str, Any]]) -> dict[str, Any]:
    model = copy.deepcopy(base)
    for change in sorted(selected, key=lambda item: item["id"]):
        kind = change["kind"]
        if kind == "target":
            model["targets"] = [
                item for item in model["targets"] if item["anchor"] != change["anchor"]
            ]
            if change["new"] is not None:
                model["targets"].append(copy.deepcopy(change["new"]))
                model["targets"].sort(key=lambda item: item["anchor"])
        elif kind == "program":
            target = _target_table(model).get(change["anchor"])
            if target is None:
                raise ValueError("orphan program change")
            target.setdefault("raw", {})[change["raw"]] = change["new"]["value"]
            target.setdefault("origins", {})[change["raw"]] = change["new"]["origin"]
        elif kind == "normalizer":
            name = change["canonical"]
            if change["new"] is None:
                model["normalizer"].pop(name, None)
            else:
                model["normalizer"][name] = copy.deepcopy(change["new"])
        elif kind == "rule":
            model["rules"] = [item for item in model["rules"] if item["id"] != change["rule"]]
            if change["new"] is not None:
                model["rules"].append(copy.deepcopy(change["new"]))
                model["rules"].sort(key=lambda item: item["id"])
        else:
            raise ValueError("unknown change kind")
    if not _check_input(model):
        raise ValueError("patched model is malformed")
    return model


def _least_witness(
    before: dict[str, Any],
    after: dict[str, Any],
    family: str,
    anchor: str,
    maximum_changes: int,
    *,
    changes: list[dict[str, Any]] | None = None,
    final_result: dict[str, Any] | None = None,
) -> list[str]:
    """Recover and replay the deletion core with independent semantics.

    This checker deliberately does not reproduce the producer's structural
    selector. The d co-singleton replays recover the atoms whose deletion from
    the full delta changes evidence. For an upward-closed sufficiency predicate,
    this deletion core is contained in every sufficient set and is least exactly
    when its own replay succeeds. The full-evidence principal-filter theorem
    supplies that premise and identifies the core with structural support.

    Replaying the core does not independently validate upward closure, framing,
    correspondence, or footprint disjointness. A failure is rejected, never
    repaired by trusting the supplied witness. This algorithm uses d+1 hybrid
    replays.
    """
    # Invocation-local admitted data; never producer/certificate-supplied bodies.
    changes = _changes(before, after) if changes is None else changes
    if len(changes) > maximum_changes:
        raise ValueError("change bound exceeded")
    final_result = (_family_result(after, family, anchor)
                    if final_result is None else final_result)
    mandatory = []
    for index, change in enumerate(changes):
        try:
            without = _patch(before, changes[:index] + changes[index + 1:])
        except ValueError as error:
            raise AssertionError("canonical deletion patch failed") from error
        if _family_result(without, family, anchor) != final_result:
            mandatory.append(change)
    try:
        joint = _patch(before, mandatory)
    except ValueError as error:
        raise AssertionError("deletion core patch failed") from error
    if _family_result(joint, family, anchor) != final_result:
        raise AssertionError("deletion core did not replay final evidence")
    return [change["id"] for change in mandatory]


def enumerated_witness(
    before: dict[str, Any],
    after: dict[str, Any],
    family: str,
    anchor: str,
    maximum_changes: int,
) -> list[str]:
    changes = _changes(before, after)
    if len(changes) > maximum_changes:
        raise ValueError("change bound exceeded")
    old_result = _family_result(before, family, anchor)
    full_result = _family_result(after, family, anchor)
    desired = _classify(old_result["value"], full_result["value"])
    for size in range(len(changes) + 1):
        for positions in itertools.combinations(range(len(changes)), size):
            subset = [changes[position] for position in positions]
            candidate = _patch(before, subset)
            candidate_result = _family_result(candidate, family, anchor)
            if (
                _classify(old_result["value"], candidate_result["value"]) == desired
                and candidate_result == full_result
            ):
                return [entry["id"] for entry in subset]
    raise AssertionError("no witness for full change set")


def verify_candidate_witness(
    delta_ids: list[str],
    witness: list[str],
    query: Callable[[frozenset[str]], bool],
) -> bool:
    """Verify a supplied least support, without identifying an unknown support.

    Contract: delta_ids and witness are sorted duplicate-free string lists,
    witness is a subset of delta_ids, and query is a deterministic Boolean
    oracle promised to satisfy Q(S) iff H <= S for some unknown H <= D.
    The result is True iff witness == H. The promise is not tested here.

    For k=|witness|<d=|D|, query witness and then its k single deletions;
    for witness==D, Q(D) is promised true and only the d deletions are needed.
    Successful verification uses k+1 or d queries respectively; rejection
    can stop early. With only upward closure, this tests inclusion-minimality,
    not leastness or minimum cardinality. Inputs are not modified.
    """
    for values in (delta_ids, witness):
        if (not isinstance(values, list)
                or any(not isinstance(item, str) for item in values)
                or len(values) != len(set(values)) or values != sorted(values)):
            raise ValueError("noncanonical witness or delta")
    universe, proposed = frozenset(delta_ids), frozenset(witness)
    if not proposed <= universe:
        raise ValueError("witness outside delta")
    if proposed != universe and not query(proposed):
        return False
    for atom in witness:
        if query(proposed - {atom}):
            return False
    return True


def check_certificate(
    before: dict[str, Any],
    after: dict[str, Any],
    certificate: dict[str, Any],
    maximum_changes: int = 12,
) -> tuple[bool, str]:
    """Check via full-support identification and core replay (d+1 hybrids)."""
    return _check_certificate(before, after, certificate, maximum_changes, "identify")


def check_candidate_certificate(
    before: dict[str, Any],
    after: dict[str, Any],
    certificate: dict[str, Any],
    maximum_changes: int = 12,
) -> tuple[bool, str]:
    """Check the supplied witness under the same finite structural contract.

    All admission, endpoint, classification, and complete-delta checks are
    identical to check_certificate. Only the support algorithm differs: use
    verify_candidate_witness against independently reconstructed exact evidence.
    No producer selector, frame-footprint projection, or support discovery is
    called. Under the finite principal-filter theorem this accepts exactly the
    same certificates as check_certificate. See proofs/candidate_verification.md.
    """
    return _check_certificate(before, after, certificate, maximum_changes, "candidate")


def _structural_witness(changes, final_result, family, anchor):
    """Read the independently reconstructed complete final record and delta.

    This path is structure-visible, not a structure-blind membership oracle.
    Sparse omitted rules still have their endpoint-union identities in changes.
    No producer selector, subset replay or support discovery is called.
    """
    if final_result["reason"] == "target_absent":
        return [change["id"] for change in changes
                if change["kind"] == "target" and change["anchor"] == anchor]
    literals = [literal for rule in final_result["rules"]
                for polarity in ("required", "forbidden") for literal in rule[polarity]]
    names = {literal["canonical"] for literal in literals}
    aliases = {observation["alias"] for literal in literals
               for observation in literal["observations"]}

    def projection(rule):
        if rule is None or rule["family"] != family: return None
        return (rule["id"], rule["family"], tuple(rule.get("requires", [])),
                tuple(rule.get("forbids", [])))

    selected = []
    for change in changes:
        kind = change["kind"]
        observed = (
            (kind == "target" and change["anchor"] == anchor)
            or (kind == "rule" and projection(change["old"]) != projection(change["new"]))
            or (kind == "normalizer" and change["canonical"] in names)
            or (kind == "program" and change["anchor"] == anchor and change["raw"] in aliases)
        )
        if observed: selected.append(change["id"])
    return selected


def check_structural_certificate(before, after, certificate, maximum_changes=12):
    """Same complete inputs/admission as both replay paths; zero hybrid calls.

    Correctness relies on complete framed evidence and separable endpoint atoms,
    not on the oracle query promise alone. This is a strong same-information
    baseline, not a new lower bound or claim of source/production validation.
    """
    return _check_certificate(before, after, certificate, maximum_changes, "structure")


def _check_certificate(
    before: dict[str, Any],
    after: dict[str, Any],
    certificate: dict[str, Any],
    maximum_changes: int,
    support_mode: str,
) -> tuple[bool, str]:
    """Shared admission and evidence checks; two distinct support obligations."""
    if not isinstance(certificate, dict):
        return False, "certificate_shape"
    if (
        not isinstance(maximum_changes, int)
        or isinstance(maximum_changes, bool)
        or maximum_changes < 0
    ):
        return False, "checker_bound"
    if not _check_input(before) or not _check_input(after):
        return False, "malformed_input"
    if certificate.get("schema") != "finite-finding-drift-certificate":
        return False, "schema"
    candidate = certificate.get("candidate")
    if not isinstance(candidate, dict):
        return False, "candidate"
    family = candidate.get("family")
    anchor = candidate.get("anchor")
    if (
        not isinstance(family, str)
        or not family
        or not isinstance(anchor, str)
        or not anchor
    ):
        return False, "candidate"
    if not _candidate_member(before, after, family, anchor):
        return False, "candidate_space"
    declared_bound = certificate.get("change_bound")
    if (
        not isinstance(declared_bound, int)
        or isinstance(declared_bound, bool)
        or declared_bound < 0
        or declared_bound > maximum_changes
    ):
        return False, "witness_bound"
    left = _family_result(before, family, anchor)
    right = _family_result(after, family, anchor)
    if certificate.get("old") != left:
        return False, "old_evidence"
    if certificate.get("new") != right:
        return False, "new_evidence"
    classification = _classify(left["value"], right["value"])
    if certificate.get("classification") != classification:
        return False, "classification"
    changes = _changes(before, after)
    change_ids = [entry["id"] for entry in changes]
    if len(changes) > declared_bound:
        return False, "witness_bound"
    if certificate.get("delta") != change_ids:
        return False, "delta"
    witness = certificate.get("witness")
    if not isinstance(witness, list) or any(not isinstance(item, str) for item in witness):
        return False, "witness_shape"
    if len(witness) != len(set(witness)) or witness != sorted(witness):
        return False, "witness_order"
    if any(item not in change_ids for item in witness):
        return False, "witness_member"
    if support_mode == "structure":
        expected = _structural_witness(changes, right, family, anchor)
        return (True, "accepted") if witness == expected else (False, "witness_minimality")
    if support_mode == "candidate":
        def query(selected: frozenset[str]) -> bool:
            operations = [entry for entry in changes if entry["id"] in selected]
            hybrid = _patch(before, operations)
            return _family_result(hybrid, family, anchor) == right

        try:
            verified = verify_candidate_witness(change_ids, witness, query)
        except (ValueError, AssertionError):
            return False, "witness_consistency"
        return (True, "accepted") if verified else (False, "witness_minimality")
    try:
        expected = _least_witness(before, after, family, anchor, declared_bound,
                                  changes=changes, final_result=right)
    except ValueError:
        return False, "witness_bound"
    except AssertionError:
        return False, "witness_consistency"
    if witness != expected:
        return False, "witness_minimality"
    return True, "accepted"


def replay_classification(
    before: dict[str, Any], after: dict[str, Any], family: str, anchor: str
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Recompute a classification without trusting producer evidence.

    This entry point is used for exhaustive tiny-model agreement; the stronger
    ``check_certificate`` entry point additionally rechecks exact evidence and
    witness minimality.
    """
    if not _check_input(before) or not _check_input(after):
        raise ValueError("malformed input")
    if not _candidate_member(before, after, family, anchor):
        raise ValueError("candidate outside declared family-anchor space")
    left = _family_result(before, family, anchor)
    right = _family_result(after, family, anchor)
    return _classify(left["value"], right["value"]), left, right
