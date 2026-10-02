#!/usr/bin/env python3
"""Deterministic structural audit for the finite artifact.

The audit parses source and evidence files, checks cross-surface consistency, and
verifies packaging hygiene.  It deliberately does not import or execute the
producer, checker, experiment harnesses, model checkers, or unit tests.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="strict")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def bib_keys(text: str) -> list[str]:
    return re.findall(r"@\w+\s*\{\s*([^,\s]+)", text)


def cited_keys(text: str) -> list[str]:
    keys: list[str] = []
    for match in re.finditer(r"\\cite\w*\{([^}]*)\}", text):
        keys.extend(item.strip() for item in match.group(1).split(",") if item.strip())
    return keys


def bib_dois(text: str) -> dict[str, str]:
    """Extract DOI fields with a small balanced-entry scanner."""
    entries: dict[str, str] = {}
    start_re = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", re.I)
    pos = 0
    while True:
        match = start_re.search(text, pos)
        if not match:
            break
        depth = 1
        i = match.end()
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[match.end(): i - 1]
        doi_match = re.search(r"\bdoi\s*=\s*[\{\"]([^}\"]+)", body, re.I)
        entries[match.group(2)] = doi_match.group(1).strip().lower() if doi_match else ""
        pos = i
    return entries


def top_level_imports(path: Path) -> list[str]:
    tree = ast.parse(read_text(path), filename=str(path))
    imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split(".")[0])
    return sorted(set(imports))


def count_test_methods(pyfiles: Iterable[Path]) -> list[str]:
    methods: list[str] = []
    for path in pyfiles:
        tree = ast.parse(read_text(path), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                methods.append(f"{path.name}:{node.name}")
    return sorted(methods)


def main() -> int:
    args = parse_args()
    requested = args.root.resolve()
    if (requested / "artifact").is_dir():
        project = requested
        artifact = project / "artifact"
        paper = project / "paper"
        mode = "project"
    else:
        project = None
        artifact = requested
        paper = None
        mode = "artifact"

    checks: list[dict[str, Any]] = []

    def check(identifier: str, condition: bool, detail: Any) -> None:
        checks.append(
            {
                "id": identifier,
                "status": "PASS" if condition else "FAIL",
                "detail": detail,
            }
        )

    check("artifact_root_exists", artifact.is_dir(), "artifact" if mode == "project" else ".")

    # Project/package shape.
    if mode == "project":
        root_entries = sorted(path.name for path in project.iterdir())
        check(
            "project_root_entries",
            root_entries == ["README.md", "artifact", "paper"],
            root_entries,
        )
        check("paper_sources_present", (paper / "main.tex").is_file() and (paper / "main.pdf").is_file(), "main.tex and main.pdf")
    else:
        check("artifact_has_no_paper_tree", not (artifact / "paper").exists(), "standalone artifact root")

    # Hygiene: no caches, bytecode, nested archives, workflow/review/release residue, or private paths.
    all_paths = sorted(path for path in artifact.rglob("*") if path.is_file() or path.is_symlink())
    if project:
        all_paths += sorted(path for path in paper.rglob("*") if path.is_file() or path.is_symlink())
        all_paths += [project / "paper" / "provenance" / "CURRENT-STATE.md", project / "paper" / "provenance" / "research-plan.md"]
    symlinks = [str(path.relative_to(project or artifact)) for path in all_paths if path.is_symlink()]
    check("no_symlinks", not symlinks, symlinks)
    cache_residue = [
        str(path.relative_to(project or artifact))
        for path in all_paths
        if "__pycache__" in path.parts
        or path.suffix.lower() in {".pyc", ".pyo"}
        or path.name in {".coverage", ".DS_Store"}
    ]
    check("no_cache_or_bytecode", not cache_residue, cache_residue)
    nested_archives = [
        str(path.relative_to(project or artifact))
        for path in all_paths
        if path.suffix.lower() in {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z"}
    ]
    check("no_nested_archives", not nested_archives, nested_archives)
    forbidden_name_terms = (
        "release-notes",
        "release_manifest",
        "release_hygiene",
        "release_sanitization",
        "sha256",
        "checksum",
        "reviewer_concern",
        "venue_calibration",
        "submission-checklist",
        "source_context_ledger",
        "source_context_verification",
        "static_audit_reviewer",
        "unit_tests_reviewer",
        "unit_observation_reviewer",
        "post_disposition_intermediate",
        "post_disposition_failed",
    )
    forbidden_named = [
        str(path.relative_to(project or artifact))
        for path in all_paths
        if any(term in path.name.lower() for term in forbidden_name_terms)
    ]
    check("no_workflow_or_release_residue", not forbidden_named, forbidden_named)
    private_markers: list[str] = []
    for path in all_paths:
        if path.is_symlink() or path.name in {"audit_static.py", "static_consistency.json"} or path.suffix.lower() not in {".md", ".txt", ".csv", ".json", ".py", ".tex", ".bib", ".cff"}:
            continue
        try:
            text = read_text(path)
        except (UnicodeDecodeError, OSError):
            continue
        found = [marker for marker in ("sandbox:/", "/mnt/data/", "/opt/", "user-BTr7", "REPOSITORY_URL_PENDING") if marker in text]
        if found:
            private_markers.append(f"{path.relative_to(project or artifact)}: {found}")
    check("no_private_path_or_placeholder", not private_markers, private_markers)

    # Python syntax and test inventory.
    pyfiles = sorted(path for path in artifact.rglob("*.py") if "__pycache__" not in path.parts)
    syntax_errors: list[str] = []
    for path in pyfiles:
        try:
            ast.parse(read_text(path), filename=str(path))
        except Exception as exc:  # pragma: no cover - audit failure report
            syntax_errors.append(f"{path.relative_to(artifact)}: {exc}")
    check("python_ast", not syntax_errors, {"files": len(pyfiles), "errors": syntax_errors})
    test_files = sorted((artifact / "tests").glob("test_*.py"))
    try:
        test_methods = count_test_methods(test_files)
    except Exception as exc:  # pragma: no cover
        test_methods = []
        syntax_errors.append(str(exc))
    check("current_test_inventory", len(test_methods) >= 30, {"count": len(test_methods), "methods": test_methods})

    unit_log = artifact / "results" / "unit_tests.txt"
    unit_text = read_text(unit_log) if unit_log.exists() else ""
    ran_match = re.search(r"Ran\s+(\d+)\s+tests?", unit_text)
    ran_count = int(ran_match.group(1)) if ran_match else -1
    check(
        "current_unit_execution",
        unit_log.exists() and "OK" in unit_text and "FAILED" not in unit_text and ran_count == len(test_methods),
        {"logged": ran_count, "source_inventory": len(test_methods)},
    )

    # Trust boundaries and executable finite checks.
    checker_imports = top_level_imports(artifact / "src" / "checker.py")
    project_modules = {"producer", "evaluate", "generate", "support_study", "checker"}
    check("checker_import_boundary", not (set(checker_imports) & project_modules), checker_imports)
    for name in ("abstract_model_check", "monotone_core_check"):
        imports = top_level_imports(artifact / f"{name}.py")
        check(f"{name}_import_boundary", not (set(imports) & project_modules), imports)

    expected_result_files = {
        "abstract": artifact / "results" / "abstract_model_check.json",
        "monotone": artifact / "results" / "monotone_core_check.json",
        "generated": artifact / "results" / "generated_differential_check.json",
    }
    results: dict[str, dict[str, Any]] = {}
    for name, path in expected_result_files.items():
        try:
            data = read_json(path)
        except Exception as exc:  # pragma: no cover
            data = {"status": "UNREADABLE", "error": str(exc)}
        results[name] = data
        check(f"{name}_check_pass", data.get("status") == "PASS", data.get("status"))
        total = data.get("totals", {})
        check(f"{name}_check_no_disagreement", total.get("counterexamples", total.get("disagreements", 0)) == 0, total)
    abstract = results["abstract"].get("totals", {})
    monotone = results["monotone"].get("totals", {})
    generated = results["generated"].get("totals", {})
    check("abstract_check_scope", abstract.get("endpoint_pairs", 0) >= 6500 and abstract.get("subset_replays", 0) >= 190000, abstract)
    abstract_config = results["abstract"].get("configuration", {})
    check(
        "abstract_domain_accounting",
        abstract_config.get("selector_domain_sizes") == [2, 3]
        and abstract_config.get("endpoint_pair_scope") == "ordered non-identical endpoint pairs"
        and abstract.get("endpoint_pairs") == 6536
        and abstract.get("atom_partitions") == 37048,
        {"configuration": abstract_config, "totals": abstract},
    )
    abstract_controls = results["abstract"].get("negative_controls", {})
    hidden_control = abstract_controls.get("hidden_visibility_breaks_structural_identification", {})
    unstable_control = abstract_controls.get("unstable_identity_breaks_coordinate_correspondence", {})
    check(
        "abstract_negative_controls_executed",
        results["abstract"].get("negative_controls_passed") is True
        and hidden_control.get("empty_patch", {}).get("structural_equivalence_violated") is True
        and hidden_control.get("restored_complete_evidence", {}).get("all_subsets_agree") is True
        and unstable_control.get("unstable_positional_views", {}).get("failure_observed") is True
        and unstable_control.get("restored_stable_identity", {}).get("positive_control_passed") is True,
        abstract_controls,
    )
    check("monotone_check_scope", monotone.get("all_predicates_examined", 0) >= 65000 and monotone.get("theorem_checks", 0) >= 900, monotone)
    monotone_control = results["monotone"].get("negative_control", {})
    overwrite_control = monotone_control.get("executed_overwrite_state_machine", {})
    restored_monotone = monotone_control.get("restored_monotone_positive_control", {})
    check(
        "monotone_negative_control_executed",
        monotone_control.get("passed") is True
        and overwrite_control.get("upward_closed") is False
        and overwrite_control.get("sufficient_set_intersection") == "{}"
        and overwrite_control.get("deletion_core") == "{b}"
        and overwrite_control.get("theorem_failure_observed") is True
        and restored_monotone.get("upward_closed") is True
        and restored_monotone.get("principal_filter") is True
        and restored_monotone.get("positive_control_passed") is True,
        monotone_control,
    )
    check("generated_check_scope", generated.get("generated_endpoint_pairs", 0) >= 60 and generated.get("subset_replays", 0) >= 1000 and generated.get("certificate_checks", 0) >= 200, generated)
    check("generated_metamorphic_scope", generated.get("container_order_checks", 0) >= 200 and generated.get("bijective_renaming_checks", 0) >= 200, generated)

    # File-format integrity.
    json_errors: list[str] = []
    json_count = 0
    for path in sorted(artifact.rglob("*.json")):
        try:
            read_json(path)
            json_count += 1
        except Exception as exc:
            json_errors.append(f"{path.relative_to(artifact)}: {exc}")
    check("json_parse", not json_errors, {"parsed": json_count, "errors": json_errors})
    schema_metadata = []
    for path in sorted(artifact.rglob("*.json")):
        try:
            value = read_json(path)
        except Exception:
            continue
        if isinstance(value, dict) and "schema_version" in value:
            schema_metadata.append(str(path.relative_to(artifact)))
    check("no_project_schema_version_metadata", not schema_metadata, schema_metadata)
    csv_errors: list[str] = []
    csv_count = 0
    for path in sorted(artifact.rglob("*.csv")):
        try:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                rows = list(csv.reader(handle))
            widths = {len(row) for row in rows}
            if len(widths) > 1:
                raise ValueError(f"row widths {sorted(widths)}")
            csv_count += 1
        except Exception as exc:
            csv_errors.append(f"{path.relative_to(artifact)}: {exc}")
    check("csv_rectangular", not csv_errors, {"parsed": csv_count, "errors": csv_errors})

    # Authored finite inputs and retained result counts.
    fixtures = read_json(artifact / "data" / "public_fixtures.json")
    fixture_count = len(fixtures) if isinstance(fixtures, list) else len(fixtures.get("cases", []))
    selections = read_csv(artifact / "external_inputs" / "selection.csv")
    check("authored_fixture_count", fixture_count == 9, fixture_count)
    check("source_selection_count", len(selections) == 9, len(selections))
    check(
        "source_selection_boundary",
        all("no source frontend" in row.get("extraction_status", "").lower() for row in selections),
        "selection rows explicitly deny source-level validation",
    )
    certs = list((artifact / "results" / "certificates").glob("*.json"))
    check("certificate_count", len(certs) == 36, len(certs))
    public_rows = read_csv(artifact / "results" / "public_cases.csv")
    fault_rows = read_csv(artifact / "results" / "fault_injection.csv")
    exhaustive_rows = read_csv(artifact / "results" / "exhaustive_grid.csv")
    check("retained_public_interventions", len(public_rows) == 36, len(public_rows))
    check("retained_fault_injections", len(fault_rows) == 638, len(fault_rows))
    check("retained_exhaustive_grid", len(exhaustive_rows) >= 4000, len(exhaustive_rows))

    # Documentation and formal claim surfaces.
    for relative in (
        "README.md",
        "REPRODUCIBILITY.md",
        "ARTIFACT-EVALUATION.md",
        "CITATION.cff",
        "schema.md",
        "run_tests.py",
        "verify_artifact.py",
        "abstract_model_check.py",
        "monotone_core_check.py",
        "generated_differential_check.py",
    ):
        check(f"present_{re.sub(r'\W+', '_', relative).strip('_').lower()}", (artifact / relative).is_file(), relative)
    verifier_source = read_text(artifact / "verify_artifact.py")
    verifier_tests = read_text(artifact / "tests" / "test_verify_artifact.py") if (artifact / "tests" / "test_verify_artifact.py").is_file() else ""
    check(
        "fresh_output_verification_chain",
        all(
            token in verifier_source
            for token in (
                "regenerate_result",
                "--output",
                "generated_exists",
                "fresh_result_comparisons",
                "finite_check_totals_from_fresh_outputs",
            )
        ),
        "deterministic checkers must write and parse fresh isolated outputs",
    )
    required_mutation_tests = (
        "test_missing_fresh_output_is_fail",
        "test_changed_frozen_field_is_fail",
        "test_forbidden_format_conflict_is_fail",
    )
    check(
        "verification_chain_mutation_tests",
        all(name in verifier_tests for name in required_mutation_tests),
        list(required_mutation_tests),
    )
    one_command_path = artifact / "results" / "one_command_verification.json"
    try:
        one_command = read_json(one_command_path)
    except Exception as exc:  # pragma: no cover
        one_command = {"status": "UNREADABLE", "error": str(exc)}
    fresh_comparisons = one_command.get("fresh_result_comparisons", {})
    required_fresh_results = {
        "results/abstract_model_check.json",
        "results/monotone_core_check.json",
        "results/generated_differential_check.json",
    }
    check(
        "one_command_fresh_outputs_recorded",
        one_command.get("status") == "PASS"
        and one_command.get("current_unit_tests") == len(test_methods)
        and set(fresh_comparisons) == required_fresh_results
        and all(
            item.get("status") == "PASS"
            and item.get("generated_exists") is True
            and item.get("generated_parse_error") is None
            and item.get("semantic_equal") is True
            and item.get("byte_equal") is True
            and not item.get("forbidden_generated_fields")
            for item in fresh_comparisons.values()
        ),
        fresh_comparisons,
    )

    assumptions = read_csv(artifact / "theorem_assumption_matrix.csv")
    check("theorem_assumption_matrix", len(assumptions) >= 10 and all(row.get("failure_if_removed") for row in assumptions), len(assumptions))
    claims = read_csv(artifact / "claim_evidence_ledger.csv")
    claim_ids = [row.get("claim_id", "") for row in claims]
    check("claim_ledger_unique", len(claim_ids) >= 15 and len(claim_ids) == len(set(claim_ids)) and all(claim_ids), len(claim_ids))
    check("claim_ledger_linked", all(row.get("paper_surface") and row.get("maturity") for row in claims), "all claims have paper and maturity fields")

    # Resource-accounting boundary.
    accounting = read_json(artifact / "results" / "resource_accounting.json")
    lower = accounting.get("timing_candidate_evaluations_lower_bound", 0)
    cap = accounting.get("declared_campaign_obligation_cap", 0)
    check("resource_campaign_terminated", accounting.get("status") == "EMPIRICAL_CAMPAIGN_TERMINATED_OVER_CAP", accounting.get("status"))
    check("resource_cap_exceeded", isinstance(lower, int) and isinstance(cap, int) and lower > cap > 0, {"lower_bound": lower, "cap": cap})
    check("performance_claims_disabled", accounting.get("positive_performance_claims_allowed") is False, accounting.get("positive_performance_claims_allowed"))
    recorded_unit = accounting.get("current_post_disposition_verification", {}).get("unit_tests", {})
    check(
        "resource_unit_record_matches_current",
        recorded_unit.get("methods") == len(test_methods) and recorded_unit.get("status") == "PASS",
        {"recorded": recorded_unit.get("methods"), "current": len(test_methods), "status": recorded_unit.get("status")},
    )

    # Bibliography, citation-use, and manuscript consistency.
    if paper and (paper / "main.tex").exists():
        tex = read_text(paper / "main.tex")
        bib = read_text(paper / "references.bib")
        bibliography = bib_keys(bib)
        citations = cited_keys(tex)
        bib_set, citation_set = set(bibliography), set(citations)
        check("bibliography_minimum", len(bib_set) >= 55, len(bib_set))
        check("bibliography_unique", len(bibliography) == len(bib_set), len(bibliography))
        check("citations_resolve", not (citation_set - bib_set), sorted(citation_set - bib_set))
        check("all_bib_entries_cited", not (bib_set - citation_set), sorted(bib_set - citation_set))
        abstract_match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
        abstract_text = abstract_match.group(1) if abstract_match else ""
        abstract_plain = re.sub(r"\\[A-Za-z]+(?:\[[^]]*\])?", " ", abstract_text)
        abstract_plain = re.sub(r"[^A-Za-z0-9-]+", " ", abstract_plain)
        abstract_words = [word for word in abstract_plain.split() if word]
        check("abstract_word_count", 100 <= len(abstract_words) <= 200, len(abstract_words))
        check("abstract_has_no_citation", "\\cite" not in abstract_text, "citation-free")
        check(
            "abstract_has_no_math_expression",
            "$" not in abstract_text and "\\[" not in abstract_text and "\\begin{equation" not in abstract_text,
            "math-expression-free",
        )

        verification = read_csv(artifact / "reference_verification.csv")
        calibration = read_csv(artifact / "literature_calibration.csv")
        claim_map = read_csv(artifact / "citation_claim_map.csv")
        keysets = {
            "verification": {row.get("citation_key", "") for row in verification},
            "calibration": {row.get("citation_key", "") for row in calibration},
            "claim_map": {row.get("citation_key", "") for row in claim_map},
        }
        for name, keyset in keysets.items():
            check(f"reference_{name}_keyset", keyset == bib_set, {"missing": sorted(bib_set - keyset), "extra": sorted(keyset - bib_set)})
        check(
            "reference_verification_fields",
            all(
                row.get("title")
                and row.get("authors")
                and row.get("year")
                and row.get("venue_or_source")
                and row.get("stable_identifier")
                and row.get("authoritative_record_url")
                and row.get("evidence_basis")
                and row.get("scope_note")
                and (row.get("verification_status", "").startswith("verified_") or row.get("verification_status") == "corrected_and_verified")
                for row in verification
            ),
            len(verification),
        )
        check(
            "citation_claim_map_fields",
            all(row.get("section") and row.get("manuscript_claim") and row.get("support_role")
                and row.get("claim_audit") and row.get("audit_limit") for row in claim_map),
            len(claim_map),
        )
        current_citation_contexts: dict[str, set[tuple[str, str]]] = {}
        current_section = ""
        current_subsection = ""
        for manuscript_line in tex.splitlines():
            section_match = re.search(r"\\section\{([^}]*)\}", manuscript_line)
            if section_match:
                current_section = section_match.group(1)
                current_subsection = ""
            subsection_match = re.search(r"\\subsection\{([^}]*)\}", manuscript_line)
            if subsection_match:
                current_subsection = subsection_match.group(1)
            citation_matches = list(re.finditer(r"\\cite\{([^}]*)\}", manuscript_line))
            if not citation_matches:
                continue
            mapped_context = re.sub(r"\\cite\{[^}]*\}", "[citation]", manuscript_line).strip()
            mapped_context = re.sub(r"\s+", " ", mapped_context)
            mapped_section = current_section + (f" / {current_subsection}" if current_subsection else "")
            for citation_match in citation_matches:
                for citation_key in citation_match.group(1).split(","):
                    current_citation_contexts.setdefault(citation_key.strip(), set()).add((mapped_section, mapped_context))
        context_mismatches = []
        for row in claim_map:
            mapped = (row.get("section", ""), re.sub(r"\s+", " ", row.get("manuscript_claim", "").strip()))
            if mapped not in current_citation_contexts.get(row.get("citation_key", ""), set()):
                context_mismatches.append(row.get("citation_key", ""))
        check("citation_claim_map_current_context", not context_mismatches, context_mismatches)
        dois = bib_dois(bib)
        doi_mismatches: list[str] = []
        stable_values: list[str] = []
        for row in verification:
            stable = row.get("stable_identifier", "").strip().lower()
            if stable:
                stable_values.append(stable)
            if stable.startswith("10.") and dois.get(row["citation_key"], "") != stable:
                doi_mismatches.append(row["citation_key"])
        check("reference_doi_alignment", not doi_mismatches, doi_mismatches)
        doi_only = [item for item in stable_values if item.startswith("10.")]
        check("reference_identifier_uniqueness", len(doi_only) == len(set(doi_only)), len(doi_only))
        check("citation_claim_mapping_nonempty", all(row.get("manuscript_claim") and row.get("support_role") for row in claim_map), len(claim_map))

        scholarly_rows = [row for row in read_csv(artifact / "external_resources.csv") if row.get("resource_type") in {"scholarly publication", "scholarly preprint"}]
        check("scholarly_resource_count", len(scholarly_rows) == len(bib_set), len(scholarly_rows))
        def normalize_title(value: str) -> str:
            value = value.replace("\\ensuremath", "").replace("ensuremath", "").replace("\\lambda", "lambda")
            value = value.replace("{", "").replace("}", "")
            return re.sub(r"[^a-z0-9]+", "", value.lower())
        verification_titles = {normalize_title(row["title"]) for row in verification}
        resource_titles = {normalize_title(row["resource_name"]) for row in scholarly_rows}
        check("scholarly_resource_title_alignment", verification_titles == resource_titles, {"missing": sorted(verification_titles - resource_titles), "extra": sorted(resource_titles - verification_titles)})

        required_direct = {"MarquesSilva2013", "Janota2016", "MarquesSilva2017", "Ignatiev2019", "Darwiche2020"}
        check("closest_prior_art_present", required_direct <= bib_set and required_direct <= citation_set, sorted(required_direct))
        novelty_text = tex.lower()
        check(
            "generic_novelty_disclaimed",
            (
                ("claim none of that generic machinery as new" in novelty_text
                 or "do not claim those generic formulations" in novelty_text)
                and ("novelty is not deletion itself" in novelty_text
                     or "contribution is not this generic deletion fact" in novelty_text)
            ),
            "generic minimal-set and deletion machinery explicitly credited",
        )
        check(
            "overfitting_boundary",
            ("no statistical model is trained" in novelty_text or "no model is trained" in novelty_text)
            and ("specification or fixture bias" in novelty_text or "specification and fixture bias" in novelty_text),
            "non-ML overfitting analogue stated",
        )
        check("source_level_nonclaim", "no Solidity-like frontend" in tex or "no source parser" in tex, "source route excluded")
        test_source = "\n".join(read_text(path) for path in test_files)
        required_boundary_tests = (
            "test_closed_world_origin_without_explicit_raw_is_observed",
            "test_added_target_and_old_only_family_rule_are_both_observable",
            "test_contradictory_literal_has_declared_three_valued_semantics",
            "test_incorrect_cache_value_is_not_authenticated",
            "test_extended_malformed_forms_are_rejected_by_both_implementations",
        )
        check(
            "review_boundary_regressions_present",
            all(name in test_source for name in required_boundary_tests),
            list(required_boundary_tests),
        )

        check(
            "paper_tiny_domain_accounting",
            all(
                token in tex
                for token in (
                    r"fixes target \texttt{site} as present",
                    r"27\times27\times3\times2\times2=8{,}748",
                    "301 tiny",
                    "all 64 directed cases",
                    "$301+64=365$",
                    "$2{,}302+1{,}753=4{,}055$",
                )
            ),
            "tiny product and exact-small split stated explicitly",
        )
        check(
            "paper_abstract_enumerator_accounting",
            all(
                token in tex
                for token in (
                    "selector domains of sizes two and three separately",
                    "6,536 ordered non-identical endpoint pairs",
                    "37,048 changed-coordinate partitions",
                    "192,176 subset replays",
                )
            ),
            "domains, non-identical pairs, partitions, and replays separated",
        )

        # Recorded evidence is stated with current counts.
        required_counts = [
            len(test_methods),
            abstract.get("endpoint_pairs"),
            abstract.get("subset_replays"),
            monotone.get("all_predicates_examined"),
            monotone.get("theorem_checks"),
            generated.get("generated_endpoint_pairs"),
            generated.get("candidate_pairs"),
            generated.get("subset_replays"),
        ]
        count_strings = [f"{value:,}" for value in required_counts if isinstance(value, int)]
        check("paper_evidence_counts", all(value in tex for value in count_strings), count_strings)

        labels = re.findall(r"\\label\{([^}]+)\}", tex)
        refs = re.findall(r"\\(?:ref|eqref|autoref)\{([^}]+)\}", tex)
        check("latex_labels_unique", len(labels) == len(set(labels)), len(labels))
        check("latex_refs_resolve", not (set(refs) - set(labels)), sorted(set(refs) - set(labels)))
        sections = re.findall(r"\\section\{([^}]+)\}", tex)
        check("main_section_count", 7 <= len(sections) <= 9, sections)
        layout_hacks = [token for token in ("\\geometry", "\\fontsize", "\\linespread", "\\vspace{-", "\\hspace{-", "\\addtolength{\\text") if token in tex]
        check("no_layout_hacks", not layout_hacks, layout_hacks)
        check("publisher_files_present", (paper / "IEEEtran.cls").is_file() and (paper / "IEEEtranS.bst").is_file(), "IEEEtran assets")

    failed = [item for item in checks if item["status"] == "FAIL"]
    report = {
        "scope": "deterministic structural audit; no analyzer, checker, experiment, or test module is imported or executed",
        "mode": mode,
        "summary": {
            "status": "PASS" if not failed else "FAIL",
            "checks": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
        },
        "checks": checks,
    }
    output = args.output or (artifact / "results" / "static_consistency.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
