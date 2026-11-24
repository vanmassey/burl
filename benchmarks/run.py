"""The Burl benchmark suite runner.

The programs in this directory define the workload the ROADMAP v0.5 gate
measures ("the VM is >=10x the tree-walker on the benchmark suite"). Each one
prints deterministic output, so any engine can be diffed against any other.

Usage:
  python benchmarks/run.py                    # time each program (best of N)
  python benchmarks/run.py --repeat 5         # more repeats, best-of is reported
  python benchmarks/run.py --check            # no timing: outputs must match expected/
  python benchmarks/run.py --save baseline.json
  python benchmarks/run.py --baseline baseline.json [--threshold 10]

No dependencies beyond Python 3.8+. Timing is wall-clock around one process,
so run on a quiet machine: this suite compares engines, never checkins.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
REPO_DIR = BENCH_DIR.parent
EXPECTED_DIR = BENCH_DIR / "expected"

VERSION = "0.1"


def run_once(path):
    """Run one program with the current default engine. Returns (seconds, stdout, stderr, code)."""
    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "burl", str(path)],
        capture_output=True, text=True, cwd=str(REPO_DIR),
    )
    return time.perf_counter() - start, proc.stdout, proc.stderr, proc.returncode


def programs():
    return sorted(p for p in BENCH_DIR.glob("*.burl"))


def check():
    """Verify every program runs and reproduces its recorded expected/ output."""
    failures = 0
    for path in programs():
        expected_file = EXPECTED_DIR / (path.stem + ".out")
        if not expected_file.exists():
            print(f"{path.name}: FAIL (no expected/{path.stem}.out)")
            failures += 1
            continue
        _, stdout, stderr, code = run_once(path)
        expected = expected_file.read_text(encoding="utf-8")
        if code != 0:
            print(f"{path.name}: FAIL (exit {code})\n{stderr}")
            failures += 1
        elif stdout != expected:
            print(f"{path.name}: FAIL (output differs)\n--- expected ---\n{expected}--- actual ---\n{stdout}")
            failures += 1
        else:
            print(f"{path.name}: ok")
    if failures:
        print(f"\n{failures} benchmark(s) failed")
        return 1
    print(f"\nall {len(programs())} benchmark(s) reproduce their expected output")
    return 0


def measure(repeat):
    """Time every program, best of `repeat`. Returns {name: best_seconds}."""
    results = {}
    for path in programs():
        best = None
        for _ in range(repeat):
            elapsed, stdout, stderr, code = run_once(path)
            if code != 0:
                sys.stderr.write(f"{path.name} failed (exit {code}):\n{stderr}")
                sys.exit(1)
            if best is None or elapsed < best:
                best = elapsed
        results[path.name] = best
    return results


def report(results, repeat):
    print(f"burl benchmark suite, best of {repeat} run(s), lower is better:")
    for name, seconds in results.items():
        print(f"  {name:<16} {seconds:8.3f} s")
    print("(programs are timed per-process; see benchmarks/README.md for the rules)")


def save(results, repeat, path):
    payload = {
        "tool": "burl-benchmark",
        "version": VERSION,
        "repeat": repeat,
        "results": results,
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"baseline written to {path}")


def compare(results, baseline_path, threshold):
    with open(baseline_path, encoding="utf-8") as handle:
        baseline = json.load(handle)
    ratios = []
    for name, base_seconds in baseline["results"].items():
        if name not in results:
            sys.exit(f"benchmark '{name}' is in the baseline but no longer exists")
        ratio = base_seconds / results[name]
        ratios.append(ratio)
        print(f"  {name:<16} {ratio:6.2f}x  ({baseline['repeat']}-run base {base_seconds:.3f} s vs {results[name]:.3f} s)")
    geomean = 1.0
    for ratio in ratios:
        geomean *= ratio
    geomean **= 1.0 / len(ratios)
    print(f"geometric mean: {geomean:.2f}x")
    if threshold is not None and geomean < threshold:
        print(f"below threshold {threshold}x")
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run the Burl benchmark suite.")
    parser.add_argument("--repeat", type=int, default=3, help="runs per program, best-of reported (default 3)")
    parser.add_argument("--check", action="store_true", help="verify outputs against expected/; no timing")
    parser.add_argument("--save", metavar="PATH", help="write results as a baseline json")
    parser.add_argument("--baseline", metavar="PATH", help="compare against a baseline json (e.g. two engines)")
    parser.add_argument("--threshold", type=float, default=None,
                        help="with --baseline: exit 1 unless the geometric mean speedup >= threshold")
    args = parser.parse_args()

    if args.check:
        return check()
    results = measure(args.repeat)
    report(results, args.repeat)
    if args.save:
        save(results, args.repeat, args.save)
    if args.baseline:
        return compare(results, args.baseline, args.threshold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
