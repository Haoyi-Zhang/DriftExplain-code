"""Portable finite regression; invoke explicitly as documented in README.

The reference scans raw records and enumerates literal subsets. It uses neither
the producer's support selector nor the checker's delta, patch, or evidence code.
"""
import copy
import itertools
import unittest
from unittest import mock

import checker
import producer
from support_study import base, directed_pairs


def cases():
    result = list(directed_pairs())
    for number in range(12):
        left, right = base(), base()
        if number == 0:
            pass
        elif number == 1:
            right["targets"][0]["raw"]["unused"] = "T"
        elif number == 2:
            del right["targets"][0]["raw"]["x"]
            del right["targets"][0]["origins"]["x"]
        elif number == 3:
            del left["targets"][0]["raw"]["x"]
            del right["targets"][0]["raw"]["x"]
            right["targets"][0]["origins"]["x"] = "explicit:false"
        elif number == 4:
            right["rules"][0]["requires"] = ["u", "p"]
            right["normalizer"]["p"] = ["z", "x"]
        elif number == 5:
            left["rules"][0]["requires"] = ["u", "p"]
            right["rules"][0]["requires"] = ["p", "u"]
        elif number == 6:
            right["rules"][0]["note"] = {"inert": ["metadata"]}
        elif number == 7:
            right["rules"] = right["rules"][1:]
        elif number == 8:
            right["targets"].append({"anchor": "unused", "raw": {"x": "T"}})
        elif number == 9:
            right["normalizer"]["p"] = ["y"]
            right["targets"][0]["origins"]["y"] = "new:y"
        elif number == 10:
            right["rules"][0]["family"] = "g"
            right["rules"].append({"id": "new", "family": "f", "forbids": ["u"]})
        else:
            right["targets"] = []
            right["rules"] = []
        result.extend([(f"variant-{number:02}-forward", left, right, "f", "a"),
                       (f"variant-{number:02}-reverse", right, left, "f", "a")])
    return result


def scan_evidence(version, family, anchor):
    target = next((t for t in version["targets"] if t["anchor"] == anchor), None)
    header = {"family": family, "anchor": anchor}
    if target is None:
        return dict(header, value="F", reason="target_absent", rules=[])
    rules = sorted([r for r in version["rules"] if r["family"] == family],
                   key=lambda r: r["id"])
    if not rules:
        return dict(header, value="F", reason="family_absent", rules=[])

    def literal(name):
        aliases = version["normalizer"].get(name)
        if aliases is None:
            return {"canonical": name, "value": "U", "reason": "missing_normalizer",
                    "aliases": [], "observations": []}
        observations = [{"alias": raw,
                         "value": target.get("raw", {}).get(raw, "F"),
                         "origin": target.get("origins", {}).get(raw, "closed_world")}
                        for raw in aliases]
        values = [o["value"] for o in observations]
        value = max(values, key={"F": 0, "U": 1, "T": 2}.__getitem__)
        reason = {"F": "all_aliases_false", "U": "unknown_alias", "T": "true_alias"}[value]
        return {"canonical": name, "value": value, "reason": reason,
                "aliases": list(aliases), "observations": observations}

    evidence = []
    for rule in rules:
        required = [literal(n) for n in rule.get("requires", [])]
        forbidden = [literal(n) for n in rule.get("forbids", [])]
        failures = [e for e in required if e["value"] == "F"]
        violations = [e for e in forbidden if e["value"] == "T"]
        unknowns = [e for e in required + forbidden if e["value"] == "U"]
        if failures:
            value, reason, decisive = "F", "required_false", failures[0]
        elif violations:
            value, reason, decisive = "F", "forbidden_true", violations[0]
        elif unknowns:
            value, reason, decisive = "U", "unknown_literal", unknowns[0]
        else:
            value, reason, decisive = "T", "all_literals_satisfied", None
        evidence.append({"rule": rule["id"], "family": family, "value": value,
                         "reason": reason, "decisive": decisive,
                         "required": required, "forbidden": forbidden})
    value = max([e["value"] for e in evidence], key={"F": 0, "U": 1, "T": 2}.__getitem__)
    reason = {"F": "all_rules_refuted", "U": "unresolved_rule", "T": "supporting_rule"}[value]
    return dict(header, value=value, reason=reason, rules=evidence)


def literal_changes(left, right):
    """Changed endpoint slots, built independently by scanning raw records."""
    rows = []
    anchors = {t["anchor"] for v in (left, right) for t in v["targets"]}
    for anchor in sorted(anchors):
        a, b = [next((t for t in v["targets"] if t["anchor"] == anchor), None)
                for v in (left, right)]
        if a is None or b is None:
            rows.append({"id": f"target|{anchor}", "kind": "target", "anchor": anchor,
                         "old": copy.deepcopy(a), "new": copy.deepcopy(b)})
        else:
            names = {n for t in (a, b) for field in ("raw", "origins")
                     for n in t.get(field, {})}
            for name in sorted(names):
                old, new = [{"value": t.get("raw", {}).get(name, "F"),
                             "origin": t.get("origins", {}).get(name, "closed_world")}
                            for t in (a, b)]
                if old != new:
                    rows.append({"id": f"program|{anchor}|{name}", "kind": "program",
                                 "anchor": anchor, "raw": name, "old": old, "new": new})
    for name in sorted(set(left["normalizer"]) | set(right["normalizer"])):
        a, b = [v["normalizer"].get(name) for v in (left, right)]
        if a != b:
            rows.append({"id": f"normalizer|{name}", "kind": "normalizer",
                         "canonical": name, "old": copy.deepcopy(a), "new": copy.deepcopy(b)})
    ids = {r["id"] for v in (left, right) for r in v["rules"]}
    for rid in sorted(ids):
        a, b = [next((r for r in v["rules"] if r["id"] == rid), None)
                for v in (left, right)]
        if a != b:
            rows.append({"id": f"rule|{rid}", "kind": "rule", "rule": rid,
                         "old": copy.deepcopy(a), "new": copy.deepcopy(b)})
    return sorted(rows, key=lambda row: row["id"])


def literal_patch(left, rows):
    version = copy.deepcopy(left)
    for row in rows:
        if row["kind"] in ("target", "rule"):
            field, identity = ("targets", "anchor") if row["kind"] == "target" else ("rules", "id")
            wanted = row["anchor"] if field == "targets" else row["rule"]
            version[field] = [x for x in version[field] if x[identity] != wanted]
            if row["new"] is not None:
                version[field].append(copy.deepcopy(row["new"]))
            version[field].sort(key=lambda x: x[identity])
        elif row["kind"] == "normalizer":
            version["normalizer"].pop(row["canonical"], None)
            if row["new"] is not None:
                version["normalizer"][row["canonical"]] = copy.deepcopy(row["new"])
        else:
            target = next(t for t in version["targets"] if t["anchor"] == row["anchor"])
            target.setdefault("raw", {})[row["raw"]] = row["new"]["value"]
            target.setdefault("origins", {})[row["raw"]] = row["new"]["origin"]
    return version


def oracle(left, right, family, anchor, bound=12):
    rows = literal_changes(left, right)
    if len(rows) > 6:
        raise AssertionError("finite oracle fixture exceeds six atoms")
    old, new = [scan_evidence(v, family, anchor) for v in (left, right)]
    classification = ("unresolved" if "U" in (old["value"], new["value"]) else
                      {("T", "T"): "preserved", ("F", "T"): "newly_justified",
                       ("T", "F"): "invalidated"}.get((old["value"], new["value"]), "absent"))
    sufficient = []
    for bits in itertools.product((False, True), repeat=len(rows)):
        selected = [r for r, bit in zip(rows, bits) if bit]
        if scan_evidence(literal_patch(left, selected), family, anchor) == new:
            sufficient.append([r["id"] for r in selected])
    witness = min(sufficient, key=lambda ids: (len(ids), ids))
    cert = {"schema": "finite-finding-drift-certificate",
            "candidate": {"family": family, "anchor": anchor}, "change_bound": bound,
            "classification": classification, "old": old, "new": new,
            "delta": [r["id"] for r in rows], "witness": witness}
    return cert, sufficient


def outcome(call):
    try:
        return ("returned", call())
    except (ValueError, TypeError) as error:
        return (type(error).__name__, str(error))


class PreparedSupportRegression(unittest.TestCase):
    def test_complete_certificates_and_literal_subset_oracle(self):
        self.assertEqual(len(cases()), 48)
        for name, left, right, family, anchor in cases():
            with self.subTest(name=name):
                snapshot = copy.deepcopy((left, right))
                expected, sufficient = oracle(left, right, family, anchor)
                actual = producer.make_certificate(left, right, family, anchor)
                self.assertEqual(actual, expected)
                self.assertEqual(producer.compute_delta(left, right), literal_changes(left, right))
                self.assertEqual(checker.check_certificate(left, right, actual), (True, "accepted"))
                self.assertEqual(producer.minimum_witness(left, right, family, anchor), actual["witness"])
                self.assertEqual(producer.enumerated_witness(left, right, family, anchor), actual["witness"])
                self.assertEqual(checker.enumerated_witness(left, right, family, anchor, 12), actual["witness"])
                for selected in sufficient:
                    self.assertTrue(set(actual["witness"]) <= set(selected))
                self.assertEqual((left, right), snapshot)

    def test_admission_and_bound_precedence(self):
        left, right = base(), base()
        right["targets"][0]["raw"]["x"] = "T"
        for api in (producer.make_certificate, producer.minimum_witness):
            for bound, expected in ((True, ("TypeError", "change bound must be an integer")),
                                    ("12", ("TypeError", "change bound must be an integer")),
                                    (-1, ("ValueError", "change bound must be nonnegative")),
                                    (0, ("ValueError", "change bound exceeded for exact witness admission"))):
                self.assertEqual(outcome(lambda: api(left, right, "f", "a", bound)), expected)
            self.assertEqual(outcome(lambda: api({}, right, "f", "a", True)),
                             ("ValueError", "missing field: targets"))
            self.assertEqual(outcome(lambda: api(left, right, "outside", "a", 0)),
                             ("ValueError", "candidate is outside the declared family-anchor space"))
        for name, left, right, family, anchor in cases():
            count = len(literal_changes(left, right))
            self.assertEqual(producer.make_certificate(left, right, family, anchor, count),
                             oracle(left, right, family, anchor, count)[0])
            if count:
                self.assertEqual(outcome(lambda: producer.make_certificate(
                    left, right, family, anchor, count - 1)),
                    ("ValueError", "change bound exceeded for exact witness admission"))

    def test_single_setup_and_public_api_validation(self):
        left, right = base(), base()
        right["targets"][0]["raw"]["x"] = "T"
        for api in (producer.make_certificate, producer.minimum_witness):
            with mock.patch.object(producer, "compute_delta", wraps=producer.compute_delta) as delta:
                with mock.patch.object(producer, "validate_version", wraps=producer.validate_version) as validate:
                    api(left, right, "f", "a")
                    self.assertEqual(delta.call_count, 1)
                    self.assertEqual(validate.call_count, 2)

    def test_no_cross_call_state_and_evidence_mutations(self):
        left, right = base(), base()
        first = producer.make_certificate(left, right, "f", "a")
        first_snapshot = copy.deepcopy(first)
        right["targets"][0]["origins"]["x"] = "changed"
        second = producer.make_certificate(left, right, "f", "a")
        self.assertEqual(first, first_snapshot)
        self.assertNotEqual(first, second)
        self.assertEqual(second, oracle(left, right, "f", "a")[0])
        for field, replacement, diagnostic in (
                ("old", {}, "old_evidence"), ("new", {}, "new_evidence"),
                ("classification", "bad", "classification"), ("delta", [], "delta"),
                ("witness", [], "witness_minimality"), ("change_bound", True, "witness_bound")):
            mutated = copy.deepcopy(second)
            mutated[field] = replacement
            self.assertEqual(checker.check_certificate(left, right, mutated), (False, diagnostic))

    def test_absence_metadata_and_value_only_boundary(self):
        named = {name: (left, right, family, anchor) for name, left, right, family, anchor in cases()}
        self.assertEqual(producer.make_certificate(*named["policy-07-forward"])["witness"], ["target|a"])
        self.assertEqual(producer.make_certificate(*named["variant-06-forward"])["witness"], [])
        left = {"targets": [{"anchor": "a", "raw": {"x": "F", "y": "F"}}],
                "normalizer": {"p": ["x", "y"]},
                "rules": [{"id": "r", "family": "f", "requires": ["p"]}]}
        right = copy.deepcopy(left)
        right["targets"][0]["raw"] = {"x": "T", "y": "T"}
        cert, sufficient = oracle(left, right, "f", "a")
        self.assertEqual(producer.make_certificate(left, right, "f", "a"), cert)
        self.assertEqual(sufficient, [["program|a|x", "program|a|y"]])
        rows = literal_changes(left, right)
        for row in rows:
            partial = scan_evidence(literal_patch(left, [row]), "f", "a")
            self.assertEqual(partial["value"], cert["new"]["value"])
            self.assertNotEqual(partial, cert["new"])

    def test_independent_checker_and_unchanged_semantic_counters(self):
        left, right = base(), base()
        right["targets"][0]["raw"]["x"] = "T"
        cert = producer.make_certificate(left, right, "f", "a")
        with mock.patch.object(producer, "_minimum_witness_prepared", side_effect=AssertionError("not a checker")):
            self.assertEqual(checker.check_certificate(left, right, cert), (True, "accepted"))
        for version in (left, right):
            counts = producer.Counts()
            self.assertEqual(producer.evaluate_family(version, "f", "a", counts),
                             scan_evidence(version, "f", "a"))
            self.assertEqual(counts.as_dict(), {"canonical_evaluations": 2,
                                             "rule_evaluations": 1, "family_evaluations": 1})


if __name__ == "__main__":
    unittest.main()

