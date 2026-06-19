.PHONY: agent-test agent-run eval

agent-test:
	python agent/runner.py check
	python scripts/check_agent_result.py "agent/results/*_result.md"

agent-run:
	python agent/runner.py init-result --task $(TASK)

eval:
	@echo "CoreKB evaluation placeholder. Future tasks should wire this to the retrieval and assistant evaluation workflow."
