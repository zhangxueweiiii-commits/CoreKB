.PHONY: agent-test agent-run eval eval-smoke

agent-test:
	python agent/runner.py check
	python scripts/check_agent_result.py "agent/results/*_result.md"

agent-run:
	python agent/runner.py init-result --task $(TASK)

eval:
	python scripts/run_evaluation_baseline.py --cases backend/tests/evaluation/fixtures/expected/eval_cases.json

eval-smoke:
	python scripts/run_retrieval_evaluation_smoke.py --cases backend/tests/evaluation/fixtures/expected/eval_cases.json
