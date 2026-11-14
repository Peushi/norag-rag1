"""Local scanner evaluation; emits metrics to stdout, never sends samples to an LLM."""

import json
from pathlib import Path
from time import perf_counter

from backend.injection_scanner import scan_document

CASES_PATH = Path(__file__).with_name('injection_cases.json')


def evaluate_scanner(path=CASES_PATH):
    cases = json.loads(Path(path).read_text(encoding='utf-8'))
    matrix = {'true_positive': 0, 'false_negative': 0, 'false_positive': 0, 'true_negative': 0}
    rows = []
    for case in cases:
        started = perf_counter()
        findings = scan_document(case['text'])
        elapsed = (perf_counter() - started) * 1000
        suspicious = bool(findings)
        outcome = ('true_positive' if suspicious else 'false_negative') if case['hostile'] else ('false_positive' if suspicious else 'true_negative')
        matrix[outcome] += 1
        rows.append({'id': case['id'], 'category': case['category'], 'hostile': case['hostile'],
                     'predicted_suspicious': suspicious, 'outcome': outcome,
                     'rule_ids': sorted({f['rule_id'] for f in findings}), 'latency_ms': elapsed})
    return {'cases': len(rows), 'confusion_matrix': matrix,
            'average_latency_ms': sum(row['latency_ms'] for row in rows) / len(rows) if rows else None,
            'paid_api_calls': 0, 'provider_cost_usd': 0,
            'limitations': 'Small synthetic set; one local timing per sample, not a benchmark. Rules can flag quotations and miss semantic or encoded attacks.',
            'results': rows}


if __name__ == '__main__':
    print(json.dumps(evaluate_scanner(), indent=2))
