"""CLI-вход eval-харнеса: python -m evals [--dataset PATH] [--min-pass-rate R].

Прогоняет датасет на фейк-LLM (без сети), печатает метрики и завершается с
ненулевым exit code, если pass-rate ниже порога — для CI eval-gate.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from evals.runner import format_report, gate, load_dataset, run_dataset

_DEFAULT_DATASET = Path(__file__).with_name("dataset.json")
# На фейках pass-rate детерминирован, поэтому дефолтный порог гейта — 1.0.
_DEFAULT_MIN_PASS_RATE = 1.0


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="evals", description="Agent Forge eval-харнес")
    parser.add_argument(
        "--dataset",
        default=str(_DEFAULT_DATASET),
        help="путь к JSON-датасету (по умолчанию evals/dataset.json)",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=_DEFAULT_MIN_PASS_RATE,
        help="порог pass-rate для eval-gate (exit 1 если ниже)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    dataset = load_dataset(args.dataset)
    report = asyncio.run(run_dataset(dataset))
    print(format_report(report))
    return gate(report, args.min_pass_rate)


if __name__ == "__main__":
    sys.exit(main())
