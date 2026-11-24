# The benchmark suite

The programs in this directory define the workload the ROADMAP v0.5 gate
measures ("the VM is >=10x the tree-walker on the benchmark suite"). The
roadmap names the gate, but the *suite* — not a vibe about speed — decides
it. Hence this directory.

## The programs

| Program | What it loads |
|---|---|
| `fibrec.burl` | Deep recursion and call overhead |
| `primes.burl` | Arithmetic, conditionals, nested loops |
| `sort.burl` | List operations, comparisons, heavier recursion |
| `strings.burl` | Interpolation, string tools, maps, closures |

Every program prints deterministic output (no `random`, no `clock` in the
output, no `input`), recorded in `expected/<name>.out`. Any engine that can
run Burl must reproduce those bytes — that is what `--check` verifies, and
output-diffing is how CI tells engines apart (ROADMAP v0.5).

## How to use the runner

```
python benchmarks/run.py --check            # outputs only; safe for CI
python benchmarks/run.py --repeat 5         # time it (best of 5 per program)
python benchmarks/run.py --save wt.json     # tree-walker numbers become a baseline
# later, with a bytecode VM behind the same CLI:
python benchmarks/run.py --baseline wt.json --threshold 10
```

`--baseline` compares two measurement runs of the *same suite* and prints a
ratio per program plus the geometric mean.

## The rules

1. **Timing is wall-clock around one process** (`python -m burl
   program.burl`), so startup is included. Eval ever more cleverly and the
   suite still counts your startup; that is honest and it is fine.
2. **Best of N repeats**, reported with N. Never quote a single run.
3. **A benchmark earns its place by covering an engine path, not by hardness.**
   Half a second of runtime is plenty; the suite must stay runnable in CI
   and on laptops.
4. **Expected output changes only with the language**, never with an engine.
   If a benchmark must change, rename it and re-record — the ledger
   (`LEDGER.md`) gets an entry for the old one.
