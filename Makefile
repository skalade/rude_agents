AGENT ?= claude
TRIALS ?= 1
REASONING_EFFORT ?= high
BENCH ?= skillsbench
BENCHFLOW_VERSION ?= 0.6.5
EXP = python3 experiment.py --bench $(BENCH)

setup:  ## install uv + the benchflow CLI (provides `bench`)
	command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
	uv tool install 'benchflow==$(BENCHFLOW_VERSION)'

list:  ## show all tasks, * marks the subset in tasks.txt (BENCH=tb2: tasks_tb2.txt)
	$(EXP) list

build:  ## materialize build/<condition>/ with phrases injected
	$(EXP) build

run:  ## print bench commands; EXECUTE=1 to actually run (make run AGENT=codex TRIALS=3)
	$(EXP) run --agent $(AGENT) --trials $(TRIALS) --reasoning-effort $(REASONING_EFFORT) $(if $(EXECUTE),--execute)

report:  ## aggregate jobs/ into results.csv + summary table
	$(EXP) report

clean:
	rm -rf build build_tb2 results.csv results_tb2.csv reproduced

.PHONY: setup list build run report clean
