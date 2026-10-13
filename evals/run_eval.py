import os
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Any

# Add project root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.analyzer import HTMLParserService, DeterministicTechnicalAnalyzer

# Verified inventory of all 13 distinct check IDs emitted across the 10 rule categories in app/core/analyzer.py
VERIFIED_RULE_REGISTRY: List[str] = [
    "CHECK-TITLE-01",      # Check 1: Missing Title
    "CHECK-TITLE-02",      # Check 1: Sub-optimal Title Length (<30 or >60)
    "CHECK-META-01",       # Check 2: Missing Meta Description
    "CHECK-META-02",       # Check 2: Sub-optimal Meta Description Length (<120 or >160)
    "CHECK-H1-01",         # Check 3: Missing H1 Heading
    "CHECK-H1-02",         # Check 3: Multiple H1 Headings Detected
    "CHECK-ALT-01",        # Check 4: Images Missing Alt Text
    "CHECK-CANONICAL-01",  # Check 5: Missing Canonical Link
    "CHECK-ROBOTS-01",     # Check 6: Robots Meta with 'noindex'
    "CHECK-SCHEMA-01",     # Check 7: Missing Schema.org JSON-LD Structured Data
    "CHECK-SCHEMA-02",     # Check 8: Lacks High-Value AEO Schema Types
    "CHECK-THIN-CONTENT",  # Check 9: Thin Content (<300 words)
    "CHECK-HEADING-H2",    # Check 10: Missing H2 Section Headings
]


def run_benchmark_evaluation():
    base_dir = Path(__file__).parent
    dataset_path = base_dir / "dataset.json"
    fixtures_dir = base_dir / "fixtures"

    if not dataset_path.exists():
        print(f"Error: Evaluation dataset file '{dataset_path}' not found.")
        sys.exit(1)

    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_tn = 0

    per_fixture_results = []
    clean_passes = []
    false_positive_cases = []

    # Rule-level tracking
    rule_stats: Dict[str, Dict[str, int]] = {
        rule: {"expected": 0, "detected": 0, "tp": 0, "fp": 0, "fn": 0}
        for rule in VERIFIED_RULE_REGISTRY
    }

    print("=" * 86)
    print("ZENVORA AI WEBSITE & AEO AUDIT COPILOT - EVALUATION HARNESS")
    print(f"Inventory of Applicable Rules: {len(VERIFIED_RULE_REGISTRY)} distinct check IDs verified in analyzer.py")
    print("=" * 86)

    for item in dataset:
        case_id = item["id"]
        name = item["name"]
        fixture_file = item["fixture"]
        target_url = item["target_url"]
        expected_checks: Set[str] = set(item["expected_findings"])

        fixture_path = fixtures_dir / fixture_file
        if not fixture_path.exists():
            print(f"[-] Fixture file missing: {fixture_path}")
            continue

        with open(fixture_path, "r", encoding="utf-8") as html_f:
            html_content = html_f.read()

        # Parse HTML & Run Deterministic Technical Analyzer
        parsed_page = HTMLParserService.parse_html(
            target_url=target_url,
            status_code=200,
            html_text=html_content,
            headers={"content-type": "text/html"},
            fetch_time=0.1
        )
        summary = DeterministicTechnicalAnalyzer.analyze(parsed_page)
        detected_checks: Set[str] = set(finding.check_id for finding in summary.findings)

        # Calculate Fixture Confusion Matrix
        tp = len(expected_checks.intersection(detected_checks))
        fp = len(detected_checks - expected_checks)
        fn = len(expected_checks - detected_checks)
        # TN = Verified rules that were correctly NOT triggered
        tn = len(set(VERIFIED_RULE_REGISTRY) - (expected_checks | detected_checks))

        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_tn += tn

        # Per-fixture precision & recall
        is_clean_negative = len(expected_checks) == 0

        if is_clean_negative:
            if fp == 0:
                clean_passes.append(case_id)
                fixture_precision = 1.0
                fixture_recall = 1.0
                fixture_f1 = 1.0
                case_status = "CLEAN PASS (0 expected, 0 triggered)"
            else:
                false_positive_cases.append(case_id)
                fixture_precision = 0.0
                fixture_recall = 1.0
                fixture_f1 = 0.0
                case_status = f"SPURIOUS TRIGGER ({fp} false positives on clean page)"
        else:
            fixture_precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            fixture_recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            fixture_f1 = (
                2 * (fixture_precision * fixture_recall) / (fixture_precision + fixture_recall)
                if (fixture_precision + fixture_recall) > 0
                else 0.0
            )
            case_status = "FINDINGS VERIFIED"

        per_fixture_results.append({
            "id": case_id,
            "name": name,
            "expected_count": len(expected_checks),
            "detected_count": len(detected_checks),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": fixture_precision,
            "recall": fixture_recall,
            "f1": fixture_f1,
            "score": summary.score,
            "is_clean_negative": is_clean_negative,
            "status": case_status,
        })

        # Update Rule-Level Statistics
        for rule in VERIFIED_RULE_REGISTRY:
            exp = rule in expected_checks
            det = rule in detected_checks
            if exp:
                rule_stats[rule]["expected"] += 1
            if det:
                rule_stats[rule]["detected"] += 1
            if exp and det:
                rule_stats[rule]["tp"] += 1
            elif det and not exp:
                rule_stats[rule]["fp"] += 1
            elif exp and not det:
                rule_stats[rule]["fn"] += 1

        print(f"\n[+] Fixture: {case_id} — {name}")
        print(f"    Status   : {case_status}")
        print(f"    Expected : {sorted(list(expected_checks))} ({len(expected_checks)})")
        print(f"    Detected : {sorted(list(detected_checks))} ({len(detected_checks)})")
        print(f"    Counts   : TP={tp}, FP={fp}, FN={fn}, TN={tn} (out of {len(VERIFIED_RULE_REGISTRY)} rules)")
        print(f"    Metrics  : Precision={fixture_precision * 100:.1f}% | Recall={fixture_recall * 100:.1f}% | F1={fixture_f1 * 100:.1f}% | Health Score={summary.score}/100")

    # Aggregate Micro Metrics (Strict pooled TP / FP / FN counts)
    micro_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (
        2 * (micro_prec * micro_rec) / (micro_prec + micro_rec)
        if (micro_prec + micro_rec) > 0
        else 0.0
    )

    # Macro Metrics across finding-bearing fixtures (non-clean negative)
    finding_fixtures = [r for r in per_fixture_results if not r["is_clean_negative"]]
    macro_prec_findings = (
        sum(r["precision"] for r in finding_fixtures) / len(finding_fixtures)
        if finding_fixtures
        else 0.0
    )
    macro_rec_findings = (
        sum(r["recall"] for r in finding_fixtures) / len(finding_fixtures)
        if finding_fixtures
        else 0.0
    )
    macro_f1_findings = (
        sum(r["f1"] for r in finding_fixtures) / len(finding_fixtures)
        if finding_fixtures
        else 0.0
    )

    # Macro Metrics across all fixtures (including clean passes defined as 1.0)
    all_macro_prec = sum(r["precision"] for r in per_fixture_results) / len(per_fixture_results)
    all_macro_rec = sum(r["recall"] for r in per_fixture_results) / len(per_fixture_results)
    all_macro_f1 = sum(r["f1"] for r in per_fixture_results) / len(per_fixture_results)

    # Print Clean-Negative Passes Report
    print("\n" + "=" * 86)
    print("CLEAN NEGATIVE PASSES & SPURIOUS TRIGGER VERIFICATION")
    print("=" * 86)
    print(f"Clean-Negative Reference Cases : {len(clean_passes)} ({clean_passes})")
    print(f"Spurious False Positive Cases : {len(false_positive_cases)} ({false_positive_cases})")

    # Print Rule-by-Rule Breakdown
    print("\n" + "=" * 86)
    print("PER-RULE DETECTION BREAKDOWN (Across 13 Verified Check IDs)")
    print("=" * 86)
    print(f"{'Check ID':<22} | {'Expected':<8} | {'Detected':<8} | {'TP':<4} | {'FP':<4} | {'FN':<4} | {'Precision':<10} | {'Recall':<8}")
    print("-" * 86)
    for rule, stats in rule_stats.items():
        r_tp = stats["tp"]
        r_fp = stats["fp"]
        r_fn = stats["fn"]
        r_p = r_tp / (r_tp + r_fp) if (r_tp + r_fp) > 0 else (1.0 if stats["expected"] == 0 else 0.0)
        r_r = r_tp / (r_tp + r_fn) if (r_tp + r_fn) > 0 else (1.0 if stats["expected"] == 0 else 0.0)
        p_str = f"{r_p * 100:.1f}%" if (r_tp + r_fp) > 0 else "N/A"
        r_str = f"{r_r * 100:.1f}%" if (r_tp + r_fn) > 0 else "N/A"
        print(f"{rule:<22} | {stats['expected']:<8} | {stats['detected']:<8} | {r_tp:<4} | {r_fp:<4} | {r_fn:<4} | {p_str:<10} | {r_str:<8}")

    # Summary Dashboard
    print("\n" + "=" * 86)
    print("OVERALL BENCHMARK EVALUATION METRICS")
    print("=" * 86)
    print(f"Total Fixtures Evaluated       : {len(per_fixture_results)}")
    print(f"Verified Applicable Check IDs  : {len(VERIFIED_RULE_REGISTRY)}")
    print(f"True Positives (TP)            : {total_tp} findings correctly triggered")
    print(f"False Positives (FP)           : {total_fp} spurious findings")
    print(f"False Negatives (FN)           : {total_fn} missed findings")
    print(f"True Negatives (TN)            : {total_tn} correctly untriggered check evaluations")
    print("-" * 86)
    print(f"MICRO PRECISION (Global Pooled): {micro_prec * 100:.2f}% ({total_tp}/{total_tp + total_fp})")
    print(f"MICRO RECALL    (Global Pooled): {micro_rec * 100:.2f}% ({total_tp}/{total_tp + total_fn})")
    print(f"MICRO F1 SCORE  (Global Pooled): {micro_f1 * 100:.2f}%")
    print("-" * 86)
    print(f"MACRO PRECISION (Finding Cases): {macro_prec_findings * 100:.2f}%")
    print(f"MACRO RECALL    (Finding Cases): {macro_rec_findings * 100:.2f}%")
    print(f"MACRO F1 SCORE  (Finding Cases): {macro_f1_findings * 100:.2f}%")
    print("-" * 86)
    print(f"MACRO F1 SCORE  (All Cases)    : {all_macro_f1 * 100:.2f}% (including clean negative passes)")
    print("=" * 86)

    return {
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "total_tn": total_tn,
        "micro_precision": micro_prec,
        "micro_recall": micro_rec,
        "micro_f1": micro_f1,
        "macro_f1_findings": macro_f1_findings,
    }


if __name__ == "__main__":
    run_benchmark_evaluation()
