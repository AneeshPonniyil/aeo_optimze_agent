import os
import json
import sys
from pathlib import Path

# Add project root directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.analyzer import HTMLParserService, DeterministicTechnicalAnalyzer


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

    print("=" * 80)
    print("ZENVORA AI WEBSITE & AEO AUDIT COPILOT - EVALUATION HARNESS")
    print("=" * 80)

    for item in dataset:
        case_id = item["id"]
        name = item["name"]
        fixture_file = item["fixture"]
        target_url = item["target_url"]
        expected_checks = set(item["expected_findings"])

        fixture_path = fixtures_dir / fixture_file
        if not fixture_path.exists():
            print(f"[-] Fixture file missing: {fixture_path}")
            continue

        with open(fixture_path, "r", encoding="utf-8") as html_f:
            html_content = html_f.read()

        # Parse HTML & Run Deterministic Analyzer
        parsed_page = HTMLParserService.parse_html(
            target_url=target_url,
            status_code=200,
            html_text=html_content,
            headers={"content-type": "text/html"},
            fetch_time=0.1
        )
        summary = DeterministicTechnicalAnalyzer.analyze(parsed_page)
        detected_checks = set(finding.check_id for finding in summary.findings)

        tp = len(expected_checks.intersection(detected_checks))
        fp = len(detected_checks - expected_checks)
        fn = len(expected_checks - detected_checks)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0

        print(f"\n[+] Test Case: {case_id} - {name}")
        print(f"    Expected Findings ({len(expected_checks)}): {list(expected_checks)}")
        print(f"    Detected Findings ({len(detected_checks)}): {list(detected_checks)}")
        print(f"    Precision: {precision:.2f} | Recall: {recall:.2f} | Score: {summary.score}/100")

    # Overall Summary
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    f1_score = 2 * (overall_precision * overall_recall) / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0.0

    print("\n" + "=" * 80)
    print("OVERALL BENCHMARK EVALUATION METRICS")
    print("=" * 80)
    print(f"True Positives (TP) : {total_tp}")
    print(f"False Positives (FP): {total_fp}")
    print(f"False Negatives (FN): {total_fn}")
    print(f"PRECISION           : {overall_precision * 100:.2f}%")
    print(f"RECALL              : {overall_recall * 100:.2f}%")
    print(f"F1 SCORE            : {f1_score * 100:.2f}%")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark_evaluation()
