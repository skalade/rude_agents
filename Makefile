AGENT ?= claude-code
TRIALS ?= 1

setup:  ## install uv + the benchflow CLI (provides `bench`)
	command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
	uv tool install benchflow

list:  ## show all tasks, * marks the subset in tasks.txt
	python3 experiment.py list

build:  ## materialize build/<condition>/ with phrases injected
	python3 experiment.py build

run:  ## print bench commands; EXECUTE=1 to actually run (make run AGENT=codex TRIALS=3)
	python3 experiment.py run --agent $(AGENT) --trials $(TRIALS) $(if $(EXECUTE),--execute)

report:  ## aggregate jobs/ into results.csv + summary table
	python3 experiment.py report

clean:
	rm -rf build jobs results.csv

.PHONY: setup list build run report clean
