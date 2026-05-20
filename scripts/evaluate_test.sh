#!/bin/bash
# Evaluate the held-out test slice from pre-generated method result artifacts.
#
# Usage: ./scripts/evaluate_test.sh [results_path] [--method-name NAME[,NAME...]] [--output FILE]

set -euo pipefail

cd /home/user

RESULTS_PATH=""
METHOD_NAMES=""
OUTPUT_FILE="/home/user/scoring/scores_test.json"
TRAIN_SCORES="${TRAIN_SCORES:-/home/user/scoring/scores_train.json}"

if [ $# -gt 0 ] && [[ "$1" != -* ]]; then
    RESULTS_PATH="$1"
    shift
fi

while [ $# -gt 0 ]; do
    case "$1" in
        --method-name|-m)
            METHOD_NAMES="${2:-}"
            shift 2
            ;;
        --output|-o)
            OUTPUT_FILE="${2:-}"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

RESULTS_PATH="${RESULTS_PATH:-/home/user/experiment_results}"

if [ ! -e "$RESULTS_PATH" ]; then
    echo "Error: results path not found: $RESULTS_PATH" >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"

python3 - "$RESULTS_PATH" "$OUTPUT_FILE" "$METHOD_NAMES" "$TRAIN_SCORES" "/home/user/eval/test/evaluate.py" "/home/user/scoring/scores.json" <<'PYEOF'
import json
import subprocess
import sys
import tempfile
from pathlib import Path

results_path = Path(sys.argv[1])
output_file = Path(sys.argv[2])
method_names_arg = sys.argv[3]
train_scores_path = Path(sys.argv[4])
eval_script = Path(sys.argv[5])
seed_scores_path = Path(sys.argv[6])


def split_method_names(raw: str) -> list[str]:
    return [part for part in raw.replace(",", " ").split() if part]


def has_result_json(path: Path) -> bool:
    if path.is_file():
        return path.suffix == ".json"
    return any(child.suffix == ".json" for child in path.iterdir() if child.is_file())


def train_score_methods(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r") as handle:
        payload = json.load(handle)
    names: list[str] = []
    seen: set[str] = set()
    for experiment_payload in payload.values():
        for method_name in experiment_payload.get("results", {}):
            if method_name not in seen:
                seen.add(method_name)
                names.append(method_name)
    return names


def seed_score_methods(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r") as handle:
        payload = json.load(handle)
    names: list[str] = []
    seen: set[str] = set()
    for experiment_payload in payload.values():
        for method_name in experiment_payload.get("results", {}):
            if method_name not in seen:
                seen.add(method_name)
                names.append(method_name)
    return names


def resolve_named_inputs(path: Path, method_names: list[str]) -> list[tuple[str, Path]]:
    discovered: list[tuple[str, Path]] = []
    for method_name in method_names:
        method_dir = path / method_name if path.is_dir() else path
        if method_dir.exists() and has_result_json(method_dir):
            method_path = method_dir
        elif has_result_json(path):
            method_path = path
        else:
            raise SystemExit(f"No JSON result artifacts found for method {method_name}")
        discovered.append((method_name, method_path))
    return discovered


def discover_method_inputs(path: Path, requested: list[str]) -> list[tuple[str, Path]]:
    train_methods = train_score_methods(train_scores_path)
    seeded_methods = seed_score_methods(seed_scores_path)
    if (
        train_methods
        and seeded_methods
        and has_result_json(path)
        and not requested
        and set(train_methods) != set(seeded_methods)
    ):
        print(
            "Ignoring stale train-score method set because top-level artifacts "
            "match scoring/scores.json methods.",
            file=sys.stderr,
        )
        train_methods = []
    target_methods = train_methods or requested or seeded_methods
    if target_methods:
        # The held-out pass must mirror the train score method set when it exists.
        # An explicit --method-name only narrows discovery before train scores exist.
        if requested and train_methods:
            missing = [name for name in train_methods if name not in requested]
            if missing:
                print(
                    "Ignoring --method-name narrowing because train scores also contain: "
                    + ", ".join(missing),
                    file=sys.stderr,
                )
        return resolve_named_inputs(path, target_methods)

    if path.is_file():
        return [(path.stem, path)]

    method_dirs = {
        child.name: child for child in sorted(path.iterdir())
        if child.is_dir() and has_result_json(child)
    }

    if method_dirs:
        return list(method_dirs.items())

    if has_result_json(path):
        return [(path.name, path)]

    raise SystemExit(f"No JSON result artifacts found under {path}")


def merge_scores(dst: dict, src: dict) -> None:
    for experiment_name, experiment_payload in src.items():
        dst.setdefault(experiment_name, {"results": {}})
        dst[experiment_name]["results"].update(experiment_payload.get("results", {}))


discovered = discover_method_inputs(results_path, split_method_names(method_names_arg))
print("Found methods:", " ".join(name for name, _ in discovered))

merged_scores: dict = {}
with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir_path = Path(tmpdir)
    for method_name, method_path in discovered:
        tmp_output = tmpdir_path / f"{method_name}.json"
        subprocess.run(
            [
                "python3",
                str(eval_script),
                str(method_path),
                "--method-name",
                method_name,
                "--output",
                str(tmp_output),
            ],
            check=True,
        )
        with tmp_output.open("r") as handle:
            merge_scores(merged_scores, json.load(handle))

output_file.parent.mkdir(parents=True, exist_ok=True)
with output_file.open("w") as handle:
    json.dump(merged_scores, handle, indent=2)
    handle.write("\n")

print(f"Test-slice evaluation complete. Scores written to {output_file}")
PYEOF
