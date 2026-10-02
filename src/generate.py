"""Deterministic generators for public-pattern and synthetic evolution cases."""
from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any


def load_public_fixtures(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _public_model(fixture: dict[str, Any], guard_state: str = "F") -> dict[str, Any]:
    raw: dict[str, str] = {}
    origins: dict[str, str] = {}
    normalizer: dict[str, list[str]] = {}
    required_atoms: list[str] = []
    forbidden_atoms: list[str] = []
    origin = f"{fixture['source_path']}:{fixture['annotated_lines']}"
    for item in fixture["required"]:
        raw[item["raw"]] = "T"
        origins[item["raw"]] = origin
        normalizer[item["canonical"]] = [item["raw"]]
        required_atoms.append(item["canonical"])
    for item in fixture["forbidden"]:
        raw[item["raw"]] = guard_state
        origins[item["raw"]] = "authored finite repair point"
        normalizer[item["canonical"]] = [item["raw"]]
        forbidden_atoms.append(item["canonical"])
    raw["irrelevant_metadata"] = "F"
    origins["irrelevant_metadata"] = "synthetic unrelated edit"
    return {
        "name": fixture["id"],
        "targets": [
            {
                "anchor": fixture["anchor"],
                "raw": raw,
                "origins": origins,
            }
        ],
        "normalizer": normalizer,
        "rules": [
            {
                "id": f"rule-{fixture['category']}",
                "family": fixture["category"],
                "requires": required_atoms,
                "forbids": forbidden_atoms,
            }
        ],
    }


def make_public_evolutions(fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for fixture in fixtures:
        family = fixture["category"]
        anchor = fixture["anchor"]

        old = _public_model(fixture, guard_state="F")
        new = copy.deepcopy(old)
        target = new["targets"][0]
        target["raw"]["irrelevant_metadata"] = "T"
        cases.append(
            {
                "id": f"{fixture['id']}-preserved",
                "fixture": fixture["id"],
                "kind": "public-pattern-informed authored evolution",
                "mutation": "unrelated observation added",
                "family": family,
                "anchor": anchor,
                "old": old,
                "new": new,
            }
        )

        old = _public_model(fixture, guard_state="F")
        new = copy.deepcopy(old)
        guard_raw = fixture["forbidden"][0]["raw"]
        new["targets"][0]["raw"][guard_raw] = "T"
        new["targets"][0]["origins"][guard_raw] = "authored finite guard insertion"
        cases.append(
            {
                "id": f"{fixture['id']}-invalidated",
                "fixture": fixture["id"],
                "kind": "public-pattern-informed authored evolution",
                "mutation": "guard inserted",
                "family": family,
                "anchor": anchor,
                "old": old,
                "new": new,
            }
        )

        old = _public_model(fixture, guard_state="T")
        new = copy.deepcopy(old)
        for guard in fixture["forbidden"]:
            guard_raw = guard["raw"]
            new["targets"][0]["raw"][guard_raw] = "F"
            new["targets"][0]["origins"][guard_raw] = "authored finite guard removal"
        cases.append(
            {
                "id": f"{fixture['id']}-newly-justified",
                "fixture": fixture["id"],
                "kind": "public-pattern-informed authored evolution",
                "mutation": "guard removed",
                "family": family,
                "anchor": anchor,
                "old": old,
                "new": new,
            }
        )

        old = _public_model(fixture, guard_state="F")
        new = copy.deepcopy(old)
        missing = fixture["required"][0]["canonical"]
        del new["normalizer"][missing]
        cases.append(
            {
                "id": f"{fixture['id']}-unresolved",
                "fixture": fixture["id"],
                "kind": "public-pattern-informed authored evolution",
                "mutation": "required normalization entry removed",
                "family": family,
                "anchor": anchor,
                "old": old,
                "new": new,
            }
        )
    return cases


def make_random_case(
    rng: random.Random,
    case_id: str,
    target_count: int,
    family_count: int,
    rule_count: int,
    change_count: int,
) -> dict[str, Any]:
    canonical_count = max(8, min(32, family_count * 3))
    raw_count = canonical_count + 4
    canonical = [f"c{index:02d}" for index in range(canonical_count)]
    raw_names = [f"x{index:02d}" for index in range(raw_count)]
    normalizer = {name: [raw_names[index]] for index, name in enumerate(canonical)}
    rules = []
    for index in range(rule_count):
        family = f"f{index % family_count:02d}"
        first = canonical[(index * 3) % canonical_count]
        second = canonical[(index * 3 + 1) % canonical_count]
        guard = canonical[(index * 5 + 2) % canonical_count]
        requires = [first] if index % 3 else [first, second]
        rules.append(
            {
                "id": f"r{index:03d}",
                "family": family,
                "requires": requires,
                "forbids": [guard],
            }
        )
    targets = []
    choices = ["T", "F", "F", "F", "U"]
    for target_index in range(target_count):
        observations = {name: rng.choice(choices) for name in raw_names}
        origins = {name: f"synthetic:{target_index}:{name}" for name in raw_names}
        targets.append(
            {
                "anchor": f"t{target_index:04d}",
                "raw": observations,
                "origins": origins,
            }
        )
    old = {
        "name": f"{case_id}-old",
        "targets": targets,
        "normalizer": normalizer,
        "rules": rules,
    }
    new = copy.deepcopy(old)
    new["name"] = f"{case_id}-new"

    used_program: set[tuple[int, int]] = set()
    used_normalizer: set[int] = set()
    used_rules: set[int] = set()
    for index in range(change_count):
        mode = index % 4
        if mode in (0, 1):
            while True:
                target_index = rng.randrange(target_count)
                raw_index = rng.randrange(raw_count)
                if (target_index, raw_index) not in used_program:
                    used_program.add((target_index, raw_index))
                    break
            target = new["targets"][target_index]
            raw_name = raw_names[raw_index]
            old_state = target["raw"][raw_name]
            target["raw"][raw_name] = {"T": "F", "F": "T", "U": "T"}[old_state]
            target["origins"][raw_name] = f"synthetic-change:{index}"
        elif mode == 2:
            while True:
                canonical_index = rng.randrange(canonical_count)
                if canonical_index not in used_normalizer:
                    used_normalizer.add(canonical_index)
                    break
            name = canonical[canonical_index]
            alias = raw_names[(canonical_index + 1 + index) % raw_count]
            new["normalizer"][name] = [alias]
        else:
            while True:
                rule_index = rng.randrange(rule_count)
                if rule_index not in used_rules:
                    used_rules.add(rule_index)
                    break
            rule = new["rules"][rule_index]
            replacement = canonical[(rule_index + index + 7) % canonical_count]
            rule["requires"] = [replacement]
    return {
        "id": case_id,
        "kind": "deterministic generated evolution",
        "family_count": family_count,
        "target_count": target_count,
        "rule_count": rule_count,
        "change_count": change_count,
        "old": old,
        "new": new,
    }
