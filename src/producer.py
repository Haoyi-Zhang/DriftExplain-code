"""Producer for finite finding-drift certificates.

The producer analyzes a deliberately bounded, three-valued rule language.  It
emits certificates that are consumed by ``checker.py``.  The checker does not
import this module and reimplements normalization, rule evaluation, change
application, classification, and witness minimality.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable

TRI = {"T", "F", "U"}
CLASSIFICATIONS = {
    ("T", "T"): "preserved",
    ("F", "T"): "newly_justified",
    ("T", "F"): "invalidated",
}


def _valid_identifier(value: Any) -> bool:
    """Return whether a value is safe in the frozen serialized ID grammar.

    Atomic-change and candidate identifiers use ``|`` as a separator.  The
    model therefore reserves that character and ASCII control characters;
    integrations can encode richer source names before constructing a model.
    """
    return (
        isinstance(value, str)
        and bool(value)
        and "|" not in value
        and all(ord(character) >= 32 and ord(character) != 127 for character in value)
    )


@dataclass
class Counts:
    canonical_evaluations: int = 0
    rule_evaluations: int = 0
    family_evaluations: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "canonical_evaluations": self.canonical_evaluations,
            "rule_evaluations": self.rule_evaluations,
            "family_evaluations": self.family_evaluations,
        }


def validate_version(version: dict[str, Any]) -> None:
    """Reject malformed analyzer inputs before scientific use."""
    if not isinstance(version, dict):
        raise TypeError("version must be a mapping")
    for field in ("targets", "normalizer", "rules"):
        if field not in version:
            raise ValueError(f"missing field: {field}")
    if not isinstance(version["targets"], list):
        raise ValueError("targets must be a list")
    if not isinstance(version["rules"], list):
        raise ValueError("rules must be a list")
    anchors: set[str] = set()
    for target in version["targets"]:
        if not isinstance(target, dict):
            raise ValueError("every target must be a mapping")
        anchor = target.get("anchor")
        if not _valid_identifier(anchor):
            raise ValueError("every target needs a nonempty anchor")
        if anchor in anchors:
            raise ValueError(f"duplicate anchor: {anchor}")
        anchors.add(anchor)
        raw = target.get("raw", {})
        if not isinstance(raw, dict):
            raise ValueError("target raw observations must be a mapping")
        for raw_name, state in raw.items():
            if not _valid_identifier(raw_name):
                raise ValueError("raw observation names must be nonempty strings")
            if state not in TRI:
                raise ValueError(f"invalid abstract state: {state}")
        origins = target.get("origins", {})
        if not isinstance(origins, dict):
            raise ValueError("target origins must be a mapping")
        for raw_name, origin in origins.items():
            if not _valid_identifier(raw_name):
                raise ValueError("origin names must be nonempty strings")
            if not isinstance(origin, str):
                raise ValueError("origin values must be strings")
    if not isinstance(version["normalizer"], dict):
        raise ValueError("normalizer must be a mapping")
    for canonical, aliases in version["normalizer"].items():
        if not _valid_identifier(canonical):
            raise ValueError("canonical names must be nonempty strings")
        if not isinstance(aliases, list) or not aliases:
            raise ValueError(f"normalizer entry {canonical} needs aliases")
        if any(not _valid_identifier(alias) for alias in aliases):
            raise ValueError(f"invalid alias in {canonical}")
        if len(aliases) != len(set(aliases)):
            raise ValueError(f"duplicate alias in {canonical}")
    rule_ids: set[str] = set()
    for rule in version["rules"]:
        if not isinstance(rule, dict):
            raise ValueError("every rule must be a mapping")
        rid = rule.get("id")
        family = rule.get("family")
        if not _valid_identifier(rid):
            raise ValueError("every rule needs a nonempty id")
        if rid in rule_ids:
            raise ValueError(f"duplicate rule id: {rid}")
        rule_ids.add(rid)
        if not _valid_identifier(family):
            raise ValueError("every rule needs a nonempty family")
        for field in ("requires", "forbids"):
            values = rule.get(field, [])
            if not isinstance(values, list) or any(
                not _valid_identifier(value) for value in values
            ):
                raise ValueError(f"invalid {field} in rule {rid}")
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {field} literal in rule {rid}")


def _targets(version: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {target["anchor"]: target for target in version["targets"]}


def _rules(version: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rule["id"]: rule for rule in version["rules"]}


def families(version: dict[str, Any]) -> set[str]:
    return {rule["family"] for rule in version["rules"]}


def anchors(version: dict[str, Any]) -> set[str]:
    return {target["anchor"] for target in version["targets"]}


def candidate_space(old: dict[str, Any], new: dict[str, Any]) -> list[tuple[str, str]]:
    return sorted(
        (family, anchor)
        for family in families(old) | families(new)
        for anchor in anchors(old) | anchors(new)
    )


def is_candidate(
    old: dict[str, Any], new: dict[str, Any], family: str, anchor: str
) -> bool:
    """Return whether a family--anchor pair belongs to the declared universe."""
    return family in (families(old) | families(new)) and anchor in (
        anchors(old) | anchors(new)
    )


def canonical_value(
    version: dict[str, Any],
    target: dict[str, Any],
    canonical: str,
    counts: Counts | None = None,
) -> dict[str, Any]:
    """Normalize raw observations with a finite disjunction.

    A missing normalizer entry is unknown.  An absent raw observation is false
    under the frozen closed-world input contract.  A true alias dominates; an
    unknown alias dominates only when no alias is true.
    """
    if counts is not None:
        counts.canonical_evaluations += 1
    aliases = version["normalizer"].get(canonical)
    if aliases is None:
        return {
            "canonical": canonical,
            "value": "U",
            "reason": "missing_normalizer",
            "aliases": [],
            "observations": [],
        }
    raw = target.get("raw", {})
    origins = target.get("origins", {})
    observations = [
        {
            "alias": alias,
            "value": raw.get(alias, "F"),
            "origin": origins.get(alias, "closed_world"),
        }
        for alias in aliases
    ]
    values = [entry["value"] for entry in observations]
    if "T" in values:
        value = "T"
        reason = "true_alias"
    elif "U" in values:
        value = "U"
        reason = "unknown_alias"
    else:
        value = "F"
        reason = "all_aliases_false"
    return {
        "canonical": canonical,
        "value": value,
        "reason": reason,
        "aliases": list(aliases),
        "observations": observations,
    }


def evaluate_rule(
    version: dict[str, Any],
    target: dict[str, Any],
    rule: dict[str, Any],
    counts: Counts | None = None,
) -> dict[str, Any]:
    if counts is not None:
        counts.rule_evaluations += 1
    required = [
        canonical_value(version, target, atom, counts) for atom in rule.get("requires", [])
    ]
    forbidden = [
        canonical_value(version, target, atom, counts) for atom in rule.get("forbids", [])
    ]
    false_required = next((entry for entry in required if entry["value"] == "F"), None)
    true_forbidden = next((entry for entry in forbidden if entry["value"] == "T"), None)
    if false_required is not None or true_forbidden is not None:
        value = "F"
        decisive = false_required or true_forbidden
        reason = "required_false" if false_required is not None else "forbidden_true"
    else:
        unknown = next(
            (entry for entry in required + forbidden if entry["value"] == "U"), None
        )
        if unknown is not None:
            value = "U"
            decisive = unknown
            reason = "unknown_literal"
        else:
            value = "T"
            decisive = None
            reason = "all_literals_satisfied"
    return {
        "rule": rule["id"],
        "family": rule["family"],
        "value": value,
        "reason": reason,
        "decisive": decisive,
        "required": required,
        "forbidden": forbidden,
    }


def evaluate_family(
    version: dict[str, Any],
    family: str,
    anchor: str,
    counts: Counts | None = None,
) -> dict[str, Any]:
    if counts is not None:
        counts.family_evaluations += 1
    target = _targets(version).get(anchor)
    if target is None:
        return {
            "family": family,
            "anchor": anchor,
            "value": "F",
            "reason": "target_absent",
            "rules": [],
        }
    family_rules = sorted(
        (rule for rule in version["rules"] if rule["family"] == family),
        key=lambda rule: rule["id"],
    )
    if not family_rules:
        return {
            "family": family,
            "anchor": anchor,
            "value": "F",
            "reason": "family_absent",
            "rules": [],
        }
    rule_evidence = [evaluate_rule(version, target, rule, counts) for rule in family_rules]
    if any(evidence["value"] == "T" for evidence in rule_evidence):
        value = "T"
        reason = "supporting_rule"
    elif any(evidence["value"] == "U" for evidence in rule_evidence):
        value = "U"
        reason = "unresolved_rule"
    else:
        value = "F"
        reason = "all_rules_refuted"
    return {
        "family": family,
        "anchor": anchor,
        "value": value,
        "reason": reason,
        "rules": rule_evidence,
    }


def analyze(
    version: dict[str, Any],
    spaces: Iterable[tuple[str, str]],
    counts: Counts | None = None,
) -> dict[str, dict[str, Any]]:
    validate_version(version)
    return {
        key(family, anchor): evaluate_family(version, family, anchor, counts)
        for family, anchor in spaces
    }


def key(family: str, anchor: str) -> str:
    return f"{family}|{anchor}"


def classify_values(old_value: str, new_value: str) -> str:
    if old_value == "U" or new_value == "U":
        return "unresolved"
    return CLASSIFICATIONS.get((old_value, new_value), "absent")


def classify_candidate(
    old: dict[str, Any], new: dict[str, Any], family: str, anchor: str
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    old_evidence = evaluate_family(old, family, anchor)
    new_evidence = evaluate_family(new, family, anchor)
    return (
        classify_values(old_evidence["value"], new_evidence["value"]),
        old_evidence,
        new_evidence,
    )


def classify_all(
    old: dict[str, Any], new: dict[str, Any], counts: Counts | None = None
) -> dict[str, dict[str, Any]]:
    spaces = candidate_space(old, new)
    old_results = analyze(old, spaces, counts)
    new_results = analyze(new, spaces, counts)
    return {
        item: {
            "classification": classify_values(old_results[item]["value"], new_results[item]["value"]),
            "old": old_results[item],
            "new": new_results[item],
        }
        for item in old_results
    }




def _compact_index(version: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Build the reusable indexes used by the value-only update path."""
    target_index = _targets(version)
    rules_by_family: dict[str, list[dict[str, Any]]] = {}
    for rule in version["rules"]:
        rules_by_family.setdefault(rule["family"], []).append(rule)
    for family in rules_by_family:
        rules_by_family[family].sort(key=lambda rule: rule["id"])
    return target_index, rules_by_family


def _canonical_state(
    version: dict[str, Any],
    target: dict[str, Any],
    canonical: str,
    counts: Counts | None = None,
) -> str:
    if counts is not None:
        counts.canonical_evaluations += 1
    aliases = version["normalizer"].get(canonical)
    if aliases is None:
        return "U"
    raw = target.get("raw", {})
    values = [raw.get(alias, "F") for alias in aliases]
    if "T" in values:
        return "T"
    if "U" in values:
        return "U"
    return "F"


def _rule_state(
    version: dict[str, Any],
    target: dict[str, Any],
    rule: dict[str, Any],
    counts: Counts | None = None,
) -> str:
    if counts is not None:
        counts.rule_evaluations += 1
    required = [
        _canonical_state(version, target, atom, counts)
        for atom in rule.get("requires", [])
    ]
    forbidden = [
        _canonical_state(version, target, atom, counts)
        for atom in rule.get("forbids", [])
    ]
    if "F" in required or "T" in forbidden:
        return "F"
    if "U" in required or "U" in forbidden:
        return "U"
    return "T"


def _family_state_indexed(
    version: dict[str, Any],
    target_index: dict[str, dict[str, Any]],
    rules_by_family: dict[str, list[dict[str, Any]]],
    family: str,
    anchor: str,
    counts: Counts | None = None,
) -> str:
    if counts is not None:
        counts.family_evaluations += 1
    target = target_index.get(anchor)
    if target is None:
        return "F"
    family_rules = rules_by_family.get(family, [])
    if not family_rules:
        return "F"
    states = [_rule_state(version, target, rule, counts) for rule in family_rules]
    if "T" in states:
        return "T"
    if "U" in states:
        return "U"
    return "F"


def analyze_values(
    version: dict[str, Any],
    spaces: Iterable[tuple[str, str]],
    counts: Counts | None = None,
) -> dict[str, str]:
    """Evaluate only abstract outcomes, without retaining proof trees.

    This is the compact update path used by the scaling experiment.  The
    evidence-producing path above is retained for certificates.  Both share
    the same three-valued equations and are cross-checked in the test suite.
    """
    validate_version(version)
    target_index, rules_by_family = _compact_index(version)
    return {
        key(family, anchor): _family_state_indexed(
            version, target_index, rules_by_family, family, anchor, counts
        )
        for family, anchor in spaces
    }


def classify_all_values(old: dict[str, Any], new: dict[str, Any]) -> dict[str, str]:
    spaces = candidate_space(old, new)
    old_values = analyze_values(old, spaces)
    new_values = analyze_values(new, spaces)
    return {
        item: classify_values(old_values[item], new_values[item])
        for item in old_values
    }


def compute_delta(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    """Return atomic, stable, lexicographically ordered changes."""
    operations: list[dict[str, Any]] = []
    old_targets = _targets(old)
    new_targets = _targets(new)
    for anchor in sorted(old_targets.keys() | new_targets.keys()):
        if anchor not in old_targets or anchor not in new_targets:
            operations.append(
                {
                    "id": f"target|{anchor}",
                    "kind": "target",
                    "anchor": anchor,
                    "old": deepcopy(old_targets.get(anchor)),
                    "new": deepcopy(new_targets.get(anchor)),
                }
            )
            continue
        old_target = old_targets[anchor]
        new_target = new_targets[anchor]
        raw_names = set(old_target.get("raw", {})) | set(new_target.get("raw", {}))
        raw_names |= set(old_target.get("origins", {})) | set(new_target.get("origins", {}))
        for raw_name in sorted(raw_names):
            old_observation = {
                "value": old_target.get("raw", {}).get(raw_name, "F"),
                "origin": old_target.get("origins", {}).get(raw_name, "closed_world"),
            }
            new_observation = {
                "value": new_target.get("raw", {}).get(raw_name, "F"),
                "origin": new_target.get("origins", {}).get(raw_name, "closed_world"),
            }
            if old_observation != new_observation:
                operations.append(
                    {
                        "id": f"program|{anchor}|{raw_name}",
                        "kind": "program",
                        "anchor": anchor,
                        "raw": raw_name,
                        "old": old_observation,
                        "new": new_observation,
                    }
                )
    old_norm = old["normalizer"]
    new_norm = new["normalizer"]
    for canonical in sorted(old_norm.keys() | new_norm.keys()):
        if old_norm.get(canonical) != new_norm.get(canonical):
            operations.append(
                {
                    "id": f"normalizer|{canonical}",
                    "kind": "normalizer",
                    "canonical": canonical,
                    "old": deepcopy(old_norm.get(canonical)),
                    "new": deepcopy(new_norm.get(canonical)),
                }
            )
    old_rules = _rules(old)
    new_rules = _rules(new)
    for rid in sorted(old_rules.keys() | new_rules.keys()):
        if old_rules.get(rid) != new_rules.get(rid):
            operations.append(
                {
                    "id": f"rule|{rid}",
                    "kind": "rule",
                    "rule": rid,
                    "old": deepcopy(old_rules.get(rid)),
                    "new": deepcopy(new_rules.get(rid)),
                }
            )
    return sorted(operations, key=lambda operation: operation["id"])


def apply_operations(
    old: dict[str, Any], operations: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    hybrid = deepcopy(old)
    for operation in sorted(operations, key=lambda entry: entry["id"]):
        kind = operation["kind"]
        if kind == "target":
            hybrid["targets"] = [
                target for target in hybrid["targets"] if target["anchor"] != operation["anchor"]
            ]
            if operation["new"] is not None:
                hybrid["targets"].append(deepcopy(operation["new"]))
                hybrid["targets"].sort(key=lambda target: target["anchor"])
        elif kind == "program":
            target = _targets(hybrid).get(operation["anchor"])
            if target is None:
                raise ValueError("program operation refers to absent target")
            value = operation["new"]["value"]
            origin = operation["new"]["origin"]
            target.setdefault("raw", {})[operation["raw"]] = value
            target.setdefault("origins", {})[operation["raw"]] = origin
        elif kind == "normalizer":
            canonical = operation["canonical"]
            if operation["new"] is None:
                hybrid["normalizer"].pop(canonical, None)
            else:
                hybrid["normalizer"][canonical] = deepcopy(operation["new"])
        elif kind == "rule":
            hybrid["rules"] = [
                rule for rule in hybrid["rules"] if rule["id"] != operation["rule"]
            ]
            if operation["new"] is not None:
                hybrid["rules"].append(deepcopy(operation["new"]))
                hybrid["rules"].sort(key=lambda rule: rule["id"])
        else:
            raise ValueError(f"unsupported operation kind: {kind}")
    validate_version(hybrid)
    return hybrid


def _family_signature(rule: dict[str, Any] | None, family: str) -> Any:
    """Project a rule to the structural fields serialized in family evidence."""
    if rule is None or rule["family"] != family:
        return None
    return (rule["id"], rule["family"], tuple(rule.get("requires", [])),
            tuple(rule.get("forbids", [])))


def minimum_witness(
    old: dict[str, Any],
    new: dict[str, Any],
    family: str,
    anchor: str,
    maximum_changes: int = 12,
) -> list[str]:
    """Return the unique least exact-evidence change subset.

    The endpoints bind one fixed conceptual comparison frame; sparse omissions
    in that frame decode as explicit absence. Complete evidence serializes all
    family rules, literal sequences, aliases, and observations. Candidate-relative
    observable atom footprints are disjoint, so all sufficient subsets are
    precisely the supersets of the forced support.
    The bound remains an admission limit, not an exponential-search necessity.
    ``enumerated_witness`` is retained as a small-domain comparison algorithm.
    """
    validate_version(old)
    validate_version(new)
    if not isinstance(maximum_changes, int) or isinstance(maximum_changes, bool):
        raise TypeError("change bound must be an integer")
    if maximum_changes < 0:
        raise ValueError("change bound must be nonnegative")
    if not is_candidate(old, new, family, anchor):
        raise ValueError("candidate is outside the declared family-anchor space")
    changes = compute_delta(old, new)
    if len(changes) > maximum_changes:
        raise ValueError("change bound exceeded for exact witness admission")
    return _minimum_witness_prepared(new, family, anchor, changes)


def _minimum_witness_prepared(
    new: dict[str, Any],
    family: str,
    anchor: str,
    changes: list[dict[str, Any]],
) -> list[str]:
    """Select support from this call's admitted endpoint and complete delta."""
    after_targets = _targets(new)
    # Target absence is a distinct evidence reason, prior to rule lookup.
    if anchor not in after_targets:
        return [entry["id"] for entry in changes
                if entry["kind"] == "target" and entry["anchor"] == anchor]
    required: set[str] = set()
    canonical_names = _rule_atoms(new, {family})
    raw_names = {raw for name in canonical_names
                 for raw in new["normalizer"].get(name, [])}
    for entry in changes:
        kind = entry["kind"]
        if kind == "target":
            if entry["anchor"] == anchor:
                required.add(entry["id"])
        elif kind == "rule":
            if (_family_signature(entry["old"], family) !=
                    _family_signature(entry["new"], family)):
                required.add(entry["id"])
        elif kind == "normalizer":
            if entry["canonical"] in canonical_names:
                required.add(entry["id"])
        elif kind == "program":
            if entry["anchor"] == anchor and entry["raw"] in raw_names:
                required.add(entry["id"])
    return sorted(required)


def enumerated_witness(
    old: dict[str, Any],
    new: dict[str, Any],
    family: str,
    anchor: str,
    maximum_changes: int = 12,
) -> list[str]:
    """Find the cardinality-minimum delta subset, with lexical tie-breaking.

    The subset must reproduce both the full classification and the complete
    new-side evidence tree relative to the unchanged old input.  Enumeration
    is exact for the declared change bound.
    """
    validate_version(old)
    validate_version(new)
    if not isinstance(maximum_changes, int) or isinstance(maximum_changes, bool):
        raise TypeError("change bound must be an integer")
    if maximum_changes < 0:
        raise ValueError("change bound must be nonnegative")
    if not is_candidate(old, new, family, anchor):
        raise ValueError("candidate is outside the declared family-anchor space")
    desired_class, _, desired_new = classify_candidate(old, new, family, anchor)
    operations = compute_delta(old, new)
    if len(operations) > maximum_changes:
        raise ValueError("change bound exceeded for exact witness minimization")
    ordered = sorted(operations, key=lambda operation: operation["id"])
    for size in range(len(ordered) + 1):
        for indices in combinations(range(len(ordered)), size):
            selected = [ordered[index] for index in indices]
            hybrid = apply_operations(old, selected)
            trial_class, _, trial_new = classify_candidate(old, hybrid, family, anchor)
            if trial_class == desired_class and trial_new == desired_new:
                return [operation["id"] for operation in selected]
    raise AssertionError("full delta failed to reproduce its own classification")


def make_certificate(
    old: dict[str, Any],
    new: dict[str, Any],
    family: str,
    anchor: str,
    maximum_changes: int = 12,
) -> dict[str, Any]:
    validate_version(old)
    validate_version(new)
    if not isinstance(maximum_changes, int) or isinstance(maximum_changes, bool):
        raise TypeError("change bound must be an integer")
    if maximum_changes < 0:
        raise ValueError("change bound must be nonnegative")
    if not is_candidate(old, new, family, anchor):
        raise ValueError("candidate is outside the declared family-anchor space")
    classification, old_evidence, new_evidence = classify_candidate(old, new, family, anchor)
    delta = compute_delta(old, new)
    if len(delta) > maximum_changes:
        raise ValueError("change bound exceeded for exact witness admission")
    witness = _minimum_witness_prepared(new, family, anchor, delta)
    return {
        "schema": "finite-finding-drift-certificate",
        "candidate": {"family": family, "anchor": anchor},
        "change_bound": maximum_changes,
        "classification": classification,
        "old": old_evidence,
        "new": new_evidence,
        "delta": [operation["id"] for operation in delta],
        "witness": witness,
    }


def _rule_atoms(version: dict[str, Any], families_of_interest: set[str]) -> set[str]:
    atoms: set[str] = set()
    for rule in version["rules"]:
        if rule["family"] in families_of_interest:
            atoms.update(rule.get("requires", []))
            atoms.update(rule.get("forbids", []))
    return atoms


def affected_candidates(
    old: dict[str, Any], new: dict[str, Any]
) -> set[tuple[str, str]]:
    """Compute a dependency-complete impact set for the frozen language."""
    spaces = candidate_space(old, new)
    all_anchors = anchors(old) | anchors(new)
    operations = compute_delta(old, new)
    affected: set[tuple[str, str]] = set()
    old_rules = _rules(old)
    new_rules = _rules(new)
    all_families = families(old) | families(new)

    def mark_families(family_set: set[str], anchor_set: set[str]) -> None:
        for family in family_set:
            for anchor in anchor_set:
                affected.add((family, anchor))

    for operation in operations:
        if operation["kind"] == "target":
            mark_families(all_families, {operation["anchor"]})
        elif operation["kind"] == "rule":
            family_set = {
                rule["family"]
                for rule in (operation.get("old"), operation.get("new"))
                if rule is not None
            }
            mark_families(family_set, all_anchors)
        elif operation["kind"] == "normalizer":
            canonical = operation["canonical"]
            family_set = {
                rule["family"]
                for rule in list(old_rules.values()) + list(new_rules.values())
                if canonical in rule.get("requires", []) or canonical in rule.get("forbids", [])
            }
            mark_families(family_set, all_anchors)
        elif operation["kind"] == "program":
            raw_name = operation["raw"]
            canonical_set = {
                canonical
                for normalizer in (old["normalizer"], new["normalizer"])
                for canonical, aliases in normalizer.items()
                if raw_name in aliases
            }
            family_set = {
                rule["family"]
                for rule in list(old_rules.values()) + list(new_rules.values())
                if canonical_set
                & (set(rule.get("requires", [])) | set(rule.get("forbids", [])))
            }
            mark_families(family_set, {operation["anchor"]})
    return affected & set(spaces)


def incremental_new_analysis(
    old: dict[str, Any],
    new: dict[str, Any],
    counts: Counts | None = None,
    cached_old: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, dict[str, Any]], set[tuple[str, str]]]:
    """Reuse cached old results and recompute the impact set only.

    The cache is the normal state of an evolving analyzer.  When omitted, the
    function constructs it for convenience; performance experiments pass the
    already-materialized old analysis and time only the update path.
    """
    # A supplied cache establishes only an old analysis result; it is not a
    # substitute for validating either endpoint.  The incremental theorem is
    # stated only for admitted old and new versions, so both model boundaries
    # are checked before candidate-space construction or cache reuse.
    validate_version(old)
    validate_version(new)
    spaces = candidate_space(old, new)
    old_results = cached_old if cached_old is not None else analyze(old, spaces)
    if set(old_results) != {key(family, anchor) for family, anchor in spaces}:
        raise ValueError("cached old analysis does not cover the candidate space")
    affected = affected_candidates(old, new)
    results: dict[str, dict[str, Any]] = {}
    for family, anchor in spaces:
        item = key(family, anchor)
        if (family, anchor) in affected:
            results[item] = evaluate_family(new, family, anchor, counts)
        else:
            results[item] = old_results[item]
    return results, affected




def incremental_new_values(
    old: dict[str, Any],
    new: dict[str, Any],
    counts: Counts | None = None,
    cached_old: dict[str, str] | None = None,
) -> tuple[dict[str, str], set[tuple[str, str]]]:
    """Compact counterpart of :func:`incremental_new_analysis`."""
    validate_version(old)
    validate_version(new)
    spaces = candidate_space(old, new)
    expected = {key(family, anchor) for family, anchor in spaces}
    old_values = cached_old if cached_old is not None else analyze_values(old, spaces)
    if set(old_values) != expected:
        raise ValueError("cached old values do not cover the candidate space")
    affected = affected_candidates(old, new)
    target_index, rules_by_family = _compact_index(new)
    results = dict(old_values)
    for family, anchor in affected:
        results[key(family, anchor)] = _family_state_indexed(
            new, target_index, rules_by_family, family, anchor, counts
        )
    return results, affected

def textual_baseline(
    old: dict[str, Any],
    new: dict[str, Any],
    family: str,
    anchor: str,
    operations: list[dict[str, Any]] | None = None,
    old_value: str | None = None,
) -> str:
    """A source-only differencing baseline that ignores catalog/normalizer drift.

    Callers processing many candidates from one version pair may pass the
    already-computed atomic delta.  This changes only reuse, not the baseline
    decision rule.
    """
    changes = [
        operation
        for operation in (operations if operations is not None else compute_delta(old, new))
        if operation["kind"] in {"program", "target"}
        and operation.get("anchor") == anchor
    ]
    if not changes:
        prior = (
            old_value
            if old_value is not None
            else evaluate_family(old, family, anchor)["value"]
        )
        return "preserved" if prior == "T" else "absent"
    rising = False
    falling = False
    for operation in changes:
        if operation["kind"] == "target":
            rising |= operation["old"] is None and operation["new"] is not None
            falling |= operation["old"] is not None and operation["new"] is None
        else:
            old_value = operation["old"]["value"]
            new_value = operation["new"]["value"]
            rising |= old_value in {"F", "U"} and new_value == "T"
            falling |= old_value == "T" and new_value in {"F", "U"}
    if rising and not falling:
        return "newly_justified"
    if falling and not rising:
        return "invalidated"
    return "unresolved"
