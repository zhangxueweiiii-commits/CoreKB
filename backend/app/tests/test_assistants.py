import json
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.api.routes.assistants import assistant_chat, presets
from app.api.routes.evaluation import latest_assistant_evaluation, list_evaluation_runs, update_evaluation_run_metadata
from app.models.document import Document, DocumentStatus
from app.models.evaluation_run import EvaluationRun, EvaluationType
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.schemas.evaluation import (
    AssistantEvaluationMetrics,
    AssistantEvaluationResponse,
    EvaluationRunMetadataUpdateRequest,
)
from app.schemas.evaluation import AssistantEvaluationCaseResult, EvalCase
from app.schemas.assistant import AssistantChatRequest, AssistantChatResponse
from app.schemas.chat import Citation
from app.services.assistant_failure_analyzer import analyze_failed_case, classify_failure_reason
from app.services.assistant_preset_service import get_assistant_preset, list_assistant_presets
from app.services.assistant_quality_thresholds import evaluate_quality_gate
from app.services.assistant_service import AssistantService
from app.services.evaluation_service import EvaluationService
from app.services.evaluation_run_metadata_service import (
    format_evaluation_run_display,
    get_evaluation_mode_summary,
)


def make_user(db, username: str, role: UserRole = UserRole.editor) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User, name: str = "kb") -> KnowledgeBase:
    kb = KnowledgeBase(name=name, owner_id=owner.id, visibility="private")
    db.add(kb)
    db.flush()
    db.add(
        KBPermission(
            knowledge_base_id=kb.id,
            user_id=owner.id,
            role=KBPermissionRole.owner,
            created_by=owner.id,
        )
    )
    db.commit()
    db.refresh(kb)
    return kb


def test_list_assistant_presets_returns_four_types() -> None:
    items = list_assistant_presets()

    assert {item.assistant_type.value for item in items} == {"maintenance", "quality", "sop", "material"}


def test_assistant_preset_default_categories() -> None:
    assert get_assistant_preset("maintenance").default_metadata_filter == {"category": "maintenance"}
    assert get_assistant_preset("quality").default_metadata_filter == {"category": "quality"}
    assert get_assistant_preset("sop").default_metadata_filter == {"category": "sop"}
    assert get_assistant_preset("material").default_metadata_filter == {"category": "material"}


def test_assistant_preset_default_rerank_top_n() -> None:
    assert get_assistant_preset("maintenance").default_rerank_top_n == 20
    assert get_assistant_preset("quality").default_rerank_top_n == 15
    assert get_assistant_preset("sop").default_rerank_top_n == 15
    assert get_assistant_preset("material").default_rerank_top_n == 20


def make_failed_case_result(**overrides) -> AssistantEvaluationCaseResult:
    data = {
        "id": "case_001",
        "assistant_type": "maintenance",
        "category": "maintenance",
        "query": "A200 E12",
        "passed": False,
        "citation_present": True,
        "keyword_match_rate": 1.0,
        "metadata_match_rate": 1.0,
        "hit_at_1": False,
        "hit_at_3": False,
        "hit_at_5": False,
        "expected_document": "A200维修手册",
        "actual_top_documents": ["B300维修手册.txt"],
        "expected_metadata": {"equipment_model": "A200"},
        "used_metadata_filter": {"equipment_model": "A200"},
    }
    data.update(overrides)
    return AssistantEvaluationCaseResult(**data)


def test_assistant_failure_analyzer_detects_wrong_document_retrieved() -> None:
    case = EvalCase(
        id="case_001",
        category="maintenance",
        query="A200 E12",
        expected_document="A200维修手册",
        should_have_answer=True,
    )
    result = make_failed_case_result(actual_top_documents=["B300维修手册.txt"])

    analysis = analyze_failed_case(case, result)

    assert analysis["failure_reason"] == "wrong_document_retrieved"
    assert analysis["suggested_fix_type"] == "rerank"


def test_assistant_failure_analyzer_detects_metadata_mismatch() -> None:
    case = EvalCase(
        id="case_001",
        category="maintenance",
        query="A200 E12",
        expected_document="A200维修手册",
        expected_metadata={"equipment_model": "A200"},
        should_have_answer=True,
    )
    result = make_failed_case_result(
        actual_top_documents=["A200维修手册.txt"],
        metadata_match_rate=0.0,
        used_metadata_filter={"equipment_model": "B300"},
    )

    assert classify_failure_reason(case, result) == "metadata_mismatch"


def test_assistant_failure_analyzer_detects_no_citation() -> None:
    case = EvalCase(id="case_001", category="maintenance", query="A200 E12", should_have_answer=True)
    result = make_failed_case_result(citation_present=False, actual_top_documents=[])

    assert classify_failure_reason(case, result) == "no_citation"


def test_assistant_failure_analyzer_detects_answered_should_no_answer() -> None:
    case = EvalCase(id="case_001", category="maintenance", query="unknown", should_have_answer=False)
    result = make_failed_case_result(no_answer_correct=False)

    assert classify_failure_reason(case, result) == "answered_should_no_answer"


def test_assistant_quality_thresholds_pass_and_fail() -> None:
    passing = AssistantEvaluationMetrics(
        assistant_type="maintenance",
        total_cases=2,
        hit_at_1=0.9,
        hit_at_3=0.9,
        mrr=0.8,
        keyword_match_rate=1.0,
        metadata_match_rate=1.0,
        no_answer_accuracy=0.9,
        citation_rate=1.0,
    )
    failing = passing.model_copy(update={"mrr": 0.5})

    assert evaluate_quality_gate("maintenance", passing)["quality_gate_passed"] is True
    failed_gate = evaluate_quality_gate("maintenance", failing)
    assert failed_gate["quality_gate_passed"] is False
    assert failed_gate["failed_thresholds"][0]["metric"] == "mrr"


@pytest.mark.asyncio
async def test_assistant_chat_merges_preset_metadata_filter(db_session) -> None:
    user = make_user(db_session, "owner")
    make_kb(db_session, user)
    seen = {}

    class FakeChatService:
        async def answer(self, **kwargs):
            seen.update(kwargs)
            return "answer", [{"filename": "A200维修手册.txt", "chunk_id": str(uuid.uuid4()), "quote": "E12"}], type("ConversationStub", (), {"id": uuid.uuid4()})(), {"category": "maintenance", "equipment_model": "A200"}, True, None

    service = AssistantService(chat_service=FakeChatService())
    response = await service.chat(
        db_session,
        user,
        "maintenance",
        AssistantChatRequest(query="A200 报 E12"),
    )

    assert seen["base_metadata_filter"] == {"category": "maintenance"}
    assert seen["auto_metadata_filter"] is True
    assert response.used_metadata_filter["category"] == "maintenance"
    assert response.citations


@pytest.mark.asyncio
async def test_user_explicit_metadata_filter_overrides_auto_extract(db_session) -> None:
    user = make_user(db_session, "owner-explicit")
    make_kb(db_session, user)
    seen = {}

    class FakeChatService:
        async def answer(self, **kwargs):
            seen.update(kwargs)
            return "answer", [], type("ConversationStub", (), {"id": uuid.uuid4()})(), {"category": "maintenance", "equipment_model": "B300"}, False, None

    service = AssistantService(chat_service=FakeChatService())
    await service.chat(
        db_session,
        user,
        "maintenance",
        AssistantChatRequest(query="A200 报 E12", metadata_filter={"equipment_model": "B300"}),
    )

    assert seen["metadata_filter"] == {"equipment_model": "B300"}


@pytest.mark.asyncio
async def test_assistant_chat_route_calls_existing_chat_service(db_session, monkeypatch) -> None:
    user = make_user(db_session, "route-owner")
    make_kb(db_session, user)
    called = {"value": False}

    class FakeAssistantService:
        async def chat(self, db, user, assistant_type, payload):
            called["value"] = True
            return AssistantChatResponse(
                assistant_type=assistant_type,
                answer="answer",
                citations=[Citation(filename="guide.txt", chunk_id=uuid.uuid4(), quote="quote")],
                used_metadata_filter={"category": "maintenance"},
                use_rerank=True,
                rerank_applied=True,
                sources=[Citation(filename="guide.txt", chunk_id=uuid.uuid4(), quote="quote")],
                no_answer_detected=False,
                conversation_id=uuid.uuid4(),
            )

    monkeypatch.setattr("app.api.routes.assistants.AssistantService", lambda: FakeAssistantService())

    response = await assistant_chat("maintenance", AssistantChatRequest(query="hello"), user, db_session)

    assert called["value"] is True
    assert response.citations


@pytest.mark.asyncio
async def test_invalid_assistant_type_returns_404(db_session) -> None:
    user = make_user(db_session, "invalid-owner")
    make_kb(db_session, user)

    with pytest.raises(HTTPException) as exc:
        await AssistantService().chat(db_session, user, "unknown", AssistantChatRequest(query="hello"))

    assert exc.value.status_code == 404


def test_presets_route_returns_four_for_logged_in_user() -> None:
    assert len(presets(User(username="u", password_hash="x", role=UserRole.viewer))) == 4


@pytest.mark.asyncio
async def test_assistant_evaluation_runs_by_assistant_type_and_citation_rate(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "eval-admin", UserRole.admin)
    kb = make_kb(db_session, admin, "CoreKB Evaluation KB")
    db_session.add(
        Document(
            knowledge_base_id=kb.id,
            filename="maintenance_A200.txt",
            file_path=str(tmp_path / "maintenance_A200.txt"),
            file_type="txt",
            file_size=1,
            status=DocumentStatus.indexed,
            meta={"document_title": "A200维修手册"},
        )
    )
    db_session.commit()
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "maintenance_001",
                    "category": "maintenance",
                    "assistant_type": "maintenance",
                    "query": "A200 报 E12",
                    "expected_document": "A200维修手册",
                    "expected_keywords": ["E12"],
                    "expected_metadata": {"equipment_model": "A200"},
                    "should_have_answer": True,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class FakeAssistantService:
        async def chat(self, db, user, assistant_type, payload):
            citation = Citation(filename="A200维修手册.txt", chunk_id=uuid.uuid4(), quote="E12 检查接线")
            return AssistantChatResponse(
                assistant_type=assistant_type,
                answer="检查接线",
                citations=[citation],
                sources=[citation],
                used_metadata_filter={"equipment_model": "A200"},
                use_rerank=True,
                rerank_applied=True,
                no_answer_detected=False,
                conversation_id=uuid.uuid4(),
            )

    result = await EvaluationService(assistant_service=FakeAssistantService()).run_assistant_eval(
        db_session,
        admin,
        cases_path,
    )

    assert result.total_cases == 1
    assert result.metrics_by_assistant["maintenance"].citation_rate == 1.0
    assert result.metrics_by_assistant["maintenance"].hit_at_1 == 1.0
    assert result.per_assistant_metrics["maintenance"].citation_rate == 1.0
    assert result.overall_metrics.citation_rate == 1.0
    assert result.quality_gate_passed is True
    assert result.per_assistant_metrics["maintenance"].quality_gate_passed is True
    assert result.change_type == "unknown"
    assert result.config_snapshot["use_metadata_filter"] is True
    assert result.config_snapshot["use_rerank"] is True


def write_assistant_eval_cases(path: Path, expected_document: str = "MaintenanceGuide") -> Path:
    cases_path = path / "assistant_cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "maintenance_001",
                    "category": "maintenance",
                    "assistant_type": "maintenance",
                    "query": "A200 reports E12",
                    "expected_document": expected_document,
                    "expected_keywords": ["E12"],
                    "expected_metadata": {"equipment_model": "A200"},
                    "should_have_answer": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    return cases_path


def make_indexed_eval_document(db, kb: KnowledgeBase, tmp_path: Path, filename: str = "MaintenanceGuide.txt") -> Document:
    document = Document(
        knowledge_base_id=kb.id,
        filename=filename,
        file_path=str(tmp_path / filename),
        file_type="txt",
        file_size=1,
        status=DocumentStatus.indexed,
        meta={"document_title": "MaintenanceGuide"},
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@pytest.mark.asyncio
async def test_assistant_evaluation_persists_flags_and_latest_api(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "eval-latest-admin", UserRole.admin)
    kb = make_kb(db_session, admin, "CoreKB Evaluation KB")
    make_indexed_eval_document(db_session, kb, tmp_path)
    cases_path = write_assistant_eval_cases(tmp_path)
    seen_payloads = []

    class FakeAssistantService:
        async def chat(self, db, user, assistant_type, payload):
            seen_payloads.append(payload)
            citation = Citation(filename="MaintenanceGuide.txt", chunk_id=uuid.uuid4(), quote="E12 wiring")
            return AssistantChatResponse(
                assistant_type=assistant_type,
                answer="Check wiring",
                citations=[citation],
                sources=[citation],
                used_metadata_filter=payload.metadata_filter or {},
                use_rerank=payload.use_rerank,
                rerank_applied=payload.use_rerank,
                no_answer_detected=False,
                conversation_id=uuid.uuid4(),
            )

    result = await EvaluationService(assistant_service=FakeAssistantService()).run_assistant_eval(
        db_session,
        admin,
        cases_path,
        use_metadata_filter=False,
        use_rerank=False,
        rerank_top_n=7,
        run_label="maintenance_prompt_v2",
        change_type="prompt",
        change_summary="tighten no-answer",
        operator_notes="watch citation",
    )

    assert result.run_id is not None
    assert result.created_at is not None
    assert result.use_metadata_filter is False
    assert result.use_rerank is False
    assert result.rerank_top_n == 7
    assert result.run_label == "maintenance_prompt_v2"
    assert result.change_type == "prompt"
    assert result.change_summary == "tighten no-answer"
    assert result.operator_notes == "watch citation"
    assert result.config_snapshot["use_rerank"] is False
    assert result.config_snapshot["assistant_types"] == ["maintenance"]
    assert result.config_snapshot["eval_type"] == "assistant"
    assert result.config_snapshot["evaluation_case_set_signature"]
    assert result.config_snapshot["evaluation_case_ids"] == ["maintenance_001"]
    assert result.per_assistant_metrics["maintenance"].total_cases == 1
    assert seen_payloads[0].disable_preset_metadata_filter is True

    stored = db_session.get(EvaluationRun, result.run_id)
    assert stored is not None
    assert stored.eval_type == EvaluationType.assistant
    assert stored.metrics["use_metadata_filter"] is False
    assert stored.metrics["use_rerank"] is False
    assert stored.metrics["rerank_top_n"] == 7
    assert "per_assistant_metrics" in stored.metrics
    assert stored.run_label == "maintenance_prompt_v2"
    assert stored.change_type == "prompt"
    assert stored.config_snapshot["rerank_top_n"] == 7

    latest = latest_assistant_evaluation(admin, db_session)
    assert latest is not None
    assert latest.run_id == result.run_id
    assert latest.use_metadata_filter is False
    assert latest.run_label == "maintenance_prompt_v2"
    assert latest.per_assistant_metrics["maintenance"].citation_rate == 1.0
    assert latest.quality_gate_passed is True


def test_update_evaluation_run_metadata_route(db_session) -> None:
    admin = make_user(db_session, "metadata-route-admin", UserRole.admin)
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=0,
        metrics={},
        failed_cases=[],
        created_by=admin.id,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    updated = update_evaluation_run_metadata(
        run.id,
        EvaluationRunMetadataUpdateRequest(
            run_label="baseline_v1",
            change_type="baseline",
            change_summary="initial baseline",
            operator_notes="before prompt changes",
        ),
        admin,
        db_session,
    )

    assert updated.run_label == "baseline_v1"
    assert updated.change_type == "baseline"
    assert updated.change_summary == "initial baseline"
    assert updated.operator_notes == "before prompt changes"


def test_invalid_change_type_rejected(db_session) -> None:
    admin = make_user(db_session, "invalid-change-admin", UserRole.admin)
    run = EvaluationRun(eval_type=EvaluationType.assistant, total_cases=0, metrics={}, failed_cases=[])
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    with pytest.raises(HTTPException) as exc:
        update_evaluation_run_metadata(
            run.id,
            EvaluationRunMetadataUpdateRequest(change_type="git_magic"),
            admin,
            db_session,
        )

    assert exc.value.status_code == 400


def test_non_admin_cannot_update_evaluation_run_metadata() -> None:
    viewer = User(username="viewer", password_hash="x", role=UserRole.viewer)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403


def test_format_evaluation_run_display_uses_run_label(db_session) -> None:
    admin = make_user(db_session, "display-admin", UserRole.admin)
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=1,
        metrics={"overall_metrics": {"hit_at_1": 0.8, "hit_at_3": 0.9, "mrr": 0.85}},
        failed_cases=[],
        run_label="maintenance_prompt_v2",
        change_type="prompt",
        created_by=admin.id,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    display = format_evaluation_run_display(run)

    assert display["display_label"] == f"maintenance_prompt_v2 · Run #{run.id}"
    assert display["metrics_summary"]["hit_at_1"] == 0.8


def test_format_evaluation_run_display_fallbacks(db_session) -> None:
    change_type_run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=0,
        metrics={},
        failed_cases=[],
        change_type="metadata",
    )
    plain_run = EvaluationRun(eval_type=EvaluationType.assistant, total_cases=0, metrics={}, failed_cases=[])
    db_session.add_all([change_type_run, plain_run])
    db_session.commit()
    db_session.refresh(change_type_run)
    db_session.refresh(plain_run)

    assert format_evaluation_run_display(change_type_run)["display_label"] == f"metadata · Run #{change_type_run.id}"
    assert format_evaluation_run_display(plain_run)["display_label"] == f"Run #{plain_run.id}"


def test_mode_summary_four_combinations() -> None:
    def make_run(use_metadata_filter: bool, use_rerank: bool) -> EvaluationRun:
        return EvaluationRun(
            eval_type=EvaluationType.assistant,
            total_cases=0,
            metrics={"use_metadata_filter": use_metadata_filter, "use_rerank": use_rerank},
            failed_cases=[],
        )

    assert get_evaluation_mode_summary(make_run(False, False)) == "Baseline"
    assert get_evaluation_mode_summary(make_run(True, False)) == "Metadata filter"
    assert get_evaluation_mode_summary(make_run(True, True)) == "Metadata filter + Rerank"
    assert get_evaluation_mode_summary(make_run(False, True)) == "Rerank only"


def test_evaluation_runs_api_returns_display_fields(db_session) -> None:
    admin = make_user(db_session, "runs-api-admin", UserRole.admin)
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=1,
        metrics={
            "use_metadata_filter": True,
            "use_rerank": True,
            "overall_metrics": {"hit_at_1": 0.5, "hit_at_3": 1.0, "mrr": 0.75, "citation_rate": 1.0},
        },
        failed_cases=[],
        run_label="baseline_v1",
        change_type="baseline",
        created_by=admin.id,
    )
    db_session.add(run)
    db_session.commit()

    result = list_evaluation_runs("assistant", None, None, 20, "created_at", admin, db_session)

    assert result[0]["display_label"] == f"baseline_v1 · Run #{run.id}"
    assert result[0]["mode_summary"] == "Metadata filter + Rerank"
    assert result[0]["metrics_summary"]["mrr"] == 0.75


@pytest.mark.asyncio
async def test_assistant_comparison_returns_three_groups_and_delta(db_session, tmp_path: Path) -> None:
    admin = make_user(db_session, "eval-compare-admin", UserRole.admin)
    kb = make_kb(db_session, admin, "CoreKB Evaluation KB")
    make_indexed_eval_document(db_session, kb, tmp_path)
    cases_path = write_assistant_eval_cases(tmp_path)

    class FakeAssistantService:
        async def chat(self, db, user, assistant_type, payload):
            if payload.disable_preset_metadata_filter:
                return AssistantChatResponse(
                    assistant_type=assistant_type,
                    answer="No citation",
                    citations=[],
                    sources=[],
                    used_metadata_filter={},
                    use_rerank=payload.use_rerank,
                    rerank_applied=False,
                    no_answer_detected=False,
                    conversation_id=uuid.uuid4(),
                )
            citation = Citation(filename="MaintenanceGuide.txt", chunk_id=uuid.uuid4(), quote="E12 wiring")
            return AssistantChatResponse(
                assistant_type=assistant_type,
                answer="Check wiring",
                citations=[citation],
                sources=[citation],
                used_metadata_filter=payload.metadata_filter or {"category": "maintenance"},
                use_rerank=payload.use_rerank,
                rerank_applied=payload.use_rerank,
                no_answer_detected=False,
                conversation_id=uuid.uuid4(),
            )

    result = await EvaluationService(assistant_service=FakeAssistantService()).compare_assistant_eval(
        db_session,
        admin,
        cases_path=cases_path,
        rerank_top_n=11,
    )

    assert result.baseline.mode == "baseline"
    assert result.metadata_filter.mode == "metadata_filter"
    assert result.metadata_filter_rerank.mode == "metadata_filter_rerank"
    assert result.baseline.overall_metrics.citation_rate == 0.0
    assert result.metadata_filter.overall_metrics.citation_rate == 1.0
    assert result.metadata_filter_rerank.use_rerank is True
    assert result.metadata_filter_rerank.rerank_top_n == 11
    assert result.delta["metadata_filter_vs_baseline"]["hit_at_1"] == 1.0
    assert result.delta["metadata_filter_vs_baseline"]["citation_rate"] == 1.0
    assert result.baseline.failed_cases[0].failure_reason == "no_citation"


def test_assistant_delta_calculation() -> None:
    previous = AssistantEvaluationResponse(
        total_cases=1,
        overall_metrics=AssistantEvaluationMetrics(
            total_cases=1,
            hit_at_1=0.2,
            hit_at_3=0.4,
            mrr=0.3,
            keyword_match_rate=0.0,
            metadata_match_rate=0.0,
            no_answer_accuracy=0.5,
            citation_rate=0.25,
        ),
        per_assistant_metrics={},
        failed_cases=[],
        case_results=[],
    )
    current = previous.model_copy(
        update={
            "overall_metrics": AssistantEvaluationMetrics(
                total_cases=1,
                hit_at_1=0.7,
                hit_at_3=0.8,
                mrr=0.6,
                keyword_match_rate=0.0,
                metadata_match_rate=0.0,
                no_answer_accuracy=0.75,
                citation_rate=1.0,
            )
        }
    )

    delta = EvaluationService._assistant_delta(current, previous)

    assert delta == {
        "hit_at_1": pytest.approx(0.5),
        "mrr": pytest.approx(0.3),
        "citation_rate": pytest.approx(0.75),
        "no_answer_accuracy": pytest.approx(0.25),
    }
