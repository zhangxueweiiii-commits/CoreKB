from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


DEFAULT_API_BASE_URL = "http://localhost:8000"


@dataclass(frozen=True)
class HarnessConfig:
    api_base_url: str
    token: str
    mode: str = "single"
    use_metadata_filter: bool = False
    use_rerank: bool = False
    rerank_top_n: int | None = None
    timeout_seconds: float = 60.0
    confirm_persist: bool = False


Transport = Callable[[str, str, dict[str, Any], float], dict[str, Any]]


class HarnessError(RuntimeError):
    pass


def normalize_api_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized:
        raise HarnessError("API base URL is required")
    return normalized


def build_endpoint(api_base_url: str, mode: str) -> str:
    base = normalize_api_base_url(api_base_url)
    if mode == "single":
        return f"{base}/api/evaluation/retrieval/run"
    if mode == "compare":
        return f"{base}/api/evaluation/retrieval/compare"
    raise HarnessError("mode must be 'single' or 'compare'")


def build_payload(use_metadata_filter: bool, use_rerank: bool, rerank_top_n: int | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "use_metadata_filter": use_metadata_filter,
        "use_rerank": use_rerank,
    }
    if rerank_top_n is not None:
        payload["rerank_top_n"] = rerank_top_n
    return payload


def require_persistence_confirmation(confirm_persist: bool) -> None:
    if not confirm_persist:
        raise HarnessError(
            "Refusing to run real retrieval evaluation without --confirm-persist. "
            "The existing API creates evaluation run records."
        )


def redact_secret(value: str | None) -> str | None:
    if not value:
        return value
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def post_json(url: str, token: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        try:
            error_json: Any = json.loads(error_body) if error_body else {}
        except json.JSONDecodeError:
            error_json = {"message": error_body}
        raise HarnessError(f"CoreKB API returned HTTP {exc.code}: {error_json}") from exc
    except urllib.error.URLError as exc:
        raise HarnessError(f"Could not connect to CoreKB API: {exc.reason}") from exc


def summarize_response(response: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode == "single":
        return {
            "run_id": response.get("run_id"),
            "total_cases": response.get("total_cases"),
            "hit_at_1": response.get("hit_at_1"),
            "hit_at_3": response.get("hit_at_3"),
            "hit_at_5": response.get("hit_at_5"),
            "mrr": response.get("mrr"),
            "keyword_match_rate": response.get("keyword_match_rate"),
            "metadata_match_rate": response.get("metadata_match_rate"),
            "no_answer_accuracy": response.get("no_answer_accuracy"),
            "failed_case_count": len(response.get("failed_cases") or []),
        }

    summaries: dict[str, Any] = {}
    for key in ("baseline", "metadata_filter", "metadata_filter_rerank"):
        item = response.get(key) or {}
        summaries[key] = {
            "run_id": item.get("run_id"),
            "total_cases": item.get("total_cases"),
            "hit_at_1": item.get("hit_at_1"),
            "hit_at_3": item.get("hit_at_3"),
            "mrr": item.get("mrr"),
            "failed_case_count": len(item.get("failed_cases") or []),
        }
    return {"runs": summaries, "delta": response.get("delta") or {}}


def run_real_retrieval_evaluation(config: HarnessConfig, transport: Transport = post_json) -> dict[str, Any]:
    require_persistence_confirmation(config.confirm_persist)
    if not config.token:
        raise HarnessError("Admin bearer token is required via --token or COREKB_ADMIN_TOKEN")

    endpoint = build_endpoint(config.api_base_url, config.mode)
    payload = build_payload(config.use_metadata_filter, config.use_rerank, config.rerank_top_n)
    response = transport(endpoint, config.token, payload, config.timeout_seconds)
    return {
        "eval_type": "real_retrieval_api_harness",
        "mode": config.mode,
        "endpoint": endpoint,
        "request": {
            "use_metadata_filter": config.use_metadata_filter,
            "use_rerank": config.use_rerank,
            "rerank_top_n": config.rerank_top_n,
            "token": redact_secret(config.token),
        },
        "persistence_confirmed": config.confirm_persist,
        "persistence_behavior": "existing API creates evaluation run records",
        "summary": summarize_response(response, config.mode),
        "response": response,
        "runtime_dependencies": {
            "corekb_api": True,
            "database": "via_api",
            "qdrant": "via_api",
            "embedding": "via_api",
            "rerank_provider": "via_api_when_enabled",
            "llm": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run CoreKB real retrieval evaluation through the existing API")
    parser.add_argument("--api-base-url", default=os.getenv("COREKB_API_BASE_URL", DEFAULT_API_BASE_URL))
    parser.add_argument("--token", default=os.getenv("COREKB_ADMIN_TOKEN"), help="Admin bearer token; env: COREKB_ADMIN_TOKEN")
    parser.add_argument("--mode", choices=("single", "compare"), default="single")
    parser.add_argument("--use-metadata-filter", action="store_true")
    parser.add_argument("--use-rerank", action="store_true")
    parser.add_argument("--rerank-top-n", type=int)
    parser.add_argument("--timeout", type=float, default=float(os.getenv("COREKB_EVAL_TIMEOUT", "60")))
    parser.add_argument("--confirm-persist", action="store_true", help="Required: API creates evaluation run records")
    parser.add_argument("--output", help="Optional path for writing the JSON result")
    parser.add_argument("--compact", action="store_true", help="Print compact JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = HarnessConfig(
        api_base_url=args.api_base_url,
        token=args.token or "",
        mode=args.mode,
        use_metadata_filter=args.use_metadata_filter,
        use_rerank=args.use_rerank,
        rerank_top_n=args.rerank_top_n,
        timeout_seconds=args.timeout,
        confirm_persist=args.confirm_persist,
    )
    try:
        result = run_real_retrieval_evaluation(config)
    except HarnessError as exc:
        error = {
            "eval_type": "real_retrieval_api_harness",
            "ok": False,
            "error": str(exc).replace(config.token, redact_secret(config.token) or "") if config.token else str(exc),
            "token": redact_secret(config.token),
        }
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    indent = None if args.compact else 2
    output = json.dumps(result, ensure_ascii=False, indent=indent)
    if args.output:
        from pathlib import Path

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
