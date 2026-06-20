import uuid

import pytest
from fastapi import HTTPException

from app.api.deps import require_admin
from app.api.routes.evaluation import (
    batch_update_failure_triage_notes,
    get_evaluation_case_result,
    list_failure_triage_notes,
    upsert_failure_triage_note,
)
from app.models.evaluation_run import EvaluationCaseResult, EvaluationRun, EvaluationType
from app.models.evaluation_triage_note import EvaluationFailureTriageNote
from app.models.user import User, UserRole
from app.schemas.evaluation import EvaluationFailureTriageBatchUpdateRequest, EvaluationFailureTriageNotePayload


def make_user(db, username: str, role: UserRole = UserRole.admin) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_case_result(db, user: User, case_id: str = "case_triage") -> tuple[EvaluationRun, EvaluationCaseResult]:
    run = EvaluationRun(
        eval_type=EvaluationType.assistant,
        total_cases=1,
        metrics={},
        failed_cases=[],
        created_by=user.id,
    )
    db.add(run)
    db.flush()
    case_result = EvaluationCaseResult(
        evaluation_run_id=run.id,
        case_id=case_id,
        assistant_type="maintenance",
        query="A200 E12",
        expected_document="A200 manual",
        expected_keywords=["E12"],
        expected_metadata={"equipment_model": "A200"},
        should_have_answer=True,
        passed=False,
        failure_reason="metadata_mismatch",
        suggested_fix_type="document_metadata",
        used_metadata_filter={},
        use_rerank=True,
        rerank_applied=True,
        answer_excerpt="answer",
        citations=[],
        retrieved_results=[],
    )
    db.add(case_result)
    db.flush()
    run.failed_cases = [
        {
            "id": case_id,
            "assistant_type": "maintenance",
            "failure_reason": "metadata_mismatch",
            "suggested_fix_type": "document_metadata",
            "case_result_id": str(case_result.id),
        }
    ]
    db.commit()
    db.refresh(run)
    db.refresh(case_result)
    return run, case_result


def note_payload(**overrides) -> EvaluationFailureTriageNotePayload:
    data = {
        "triage_status": "reviewing",
        "note": "Check whether document metadata contains equipment_model=A200.",
    }
    data.update(overrides)
    return EvaluationFailureTriageNotePayload(**data)


def test_admin_can_create_failure_triage_note(db_session) -> None:
    admin = make_user(db_session, "triage-admin")
    _, case_result = make_case_result(db_session, admin)

    note = upsert_failure_triage_note(case_result.id, note_payload(), admin, db_session)

    assert note.evaluation_case_result_id == case_result.id
    assert note.triage_status.value == "reviewing"
    assert note.note == "Check whether document metadata contains equipment_model=A200."
    assert note.created_by == admin.id
    assert note.updated_by == admin.id


def test_upsert_failure_triage_note_updates_existing_row(db_session) -> None:
    admin = make_user(db_session, "triage-update-admin")
    _, case_result = make_case_result(db_session, admin)

    first = upsert_failure_triage_note(case_result.id, note_payload(), admin, db_session)
    second = upsert_failure_triage_note(
        case_result.id,
        note_payload(triage_status="resolved", note="Resolved by metadata dictionary update."),
        admin,
        db_session,
    )

    rows = db_session.query(EvaluationFailureTriageNote).filter_by(evaluation_case_result_id=case_result.id).all()
    assert len(rows) == 1
    assert second.id == first.id
    assert second.triage_status.value == "resolved"
    assert second.note == "Resolved by metadata dictionary update."


def test_list_failure_triage_notes_filters_by_run_and_status(db_session) -> None:
    admin = make_user(db_session, "triage-list-admin")
    run, case_result = make_case_result(db_session, admin, "case_reviewing")
    _, case_result_2 = make_case_result(db_session, admin, "case_ignored")
    upsert_failure_triage_note(case_result.id, note_payload(triage_status="reviewing"), admin, db_session)
    upsert_failure_triage_note(case_result_2.id, note_payload(triage_status="ignored"), admin, db_session)

    by_run = list_failure_triage_notes(evaluation_run_id=run.id, _=admin, db=db_session)
    by_status = list_failure_triage_notes(triage_status="ignored", _=admin, db=db_session)

    assert len(by_run) == 1
    assert by_run[0]["case_id"] == "case_reviewing"
    assert len(by_status) == 1
    assert by_status[0]["case_id"] == "case_ignored"


def test_failure_triage_note_invalid_status_returns_bad_request(db_session) -> None:
    admin = make_user(db_session, "triage-invalid-admin")
    _, case_result = make_case_result(db_session, admin)

    with pytest.raises(HTTPException) as exc:
        upsert_failure_triage_note(
            case_result.id,
            note_payload(triage_status="not_a_status"),
            admin,
            db_session,
        )

    assert exc.value.status_code == 400


def test_failure_triage_note_missing_case_result_returns_not_found(db_session) -> None:
    admin = make_user(db_session, "triage-missing-admin")

    with pytest.raises(HTTPException) as exc:
        upsert_failure_triage_note(uuid.uuid4(), note_payload(), admin, db_session)

    assert exc.value.status_code == 404


def test_non_admin_cannot_access_failure_triage_notes() -> None:
    viewer = User(id=uuid.uuid4(), username="triage-viewer", password_hash="x", role=UserRole.viewer)

    with pytest.raises(HTTPException) as exc:
        require_admin(viewer)

    assert exc.value.status_code == 403


def test_drilldown_includes_failure_triage_note(db_session) -> None:
    admin = make_user(db_session, "triage-drill-admin")
    _, case_result = make_case_result(db_session, admin)
    note = upsert_failure_triage_note(case_result.id, note_payload(), admin, db_session)

    detail = get_evaluation_case_result(case_result.id, admin, db_session)

    assert detail["triage_note"]["id"] == note.id
    assert detail["triage_note"]["triage_status"] == "reviewing"
    assert detail["triage_note"]["note"] == note.note


def batch_payload(case_result_ids: list[uuid.UUID], **overrides) -> EvaluationFailureTriageBatchUpdateRequest:
    data = {
        "evaluation_case_result_ids": case_result_ids,
        "triage_status": "reviewing",
        "note": "Batch triage note.",
        "note_mode": "replace",
    }
    data.update(overrides)
    return EvaluationFailureTriageBatchUpdateRequest(**data)


def test_admin_can_batch_update_failure_triage_notes(db_session) -> None:
    admin = make_user(db_session, "triage-batch-admin")
    _, first = make_case_result(db_session, admin, "case_batch_one")
    _, second = make_case_result(db_session, admin, "case_batch_two")

    notes = batch_update_failure_triage_notes(
        batch_payload([first.id, second.id], triage_status="reviewing", note="Investigate together."),
        admin,
        db_session,
    )

    assert len(notes) == 2
    assert {note.evaluation_case_result_id for note in notes} == {first.id, second.id}
    assert all(note.triage_status.value == "reviewing" for note in notes)
    assert all(note.note == "Investigate together." for note in notes)


def test_batch_update_deduplicates_case_result_ids(db_session) -> None:
    admin = make_user(db_session, "triage-batch-dedupe-admin")
    _, case_result = make_case_result(db_session, admin, "case_batch_dedupe")

    notes = batch_update_failure_triage_notes(
        batch_payload([case_result.id, case_result.id], triage_status="resolved", note="One update."),
        admin,
        db_session,
    )

    rows = db_session.query(EvaluationFailureTriageNote).filter_by(evaluation_case_result_id=case_result.id).all()
    assert len(notes) == 1
    assert len(rows) == 1
    assert rows[0].triage_status.value == "resolved"


def test_batch_update_append_mode_preserves_existing_note(db_session) -> None:
    admin = make_user(db_session, "triage-batch-append-admin")
    _, case_result = make_case_result(db_session, admin, "case_batch_append")
    upsert_failure_triage_note(case_result.id, note_payload(note="Initial note."), admin, db_session)

    notes = batch_update_failure_triage_notes(
        batch_payload([case_result.id], triage_status="reviewing", note="Follow-up note.", note_mode="append"),
        admin,
        db_session,
    )

    assert notes[0].note == "Initial note.\nFollow-up note."


def test_batch_update_keep_mode_changes_status_without_changing_note(db_session) -> None:
    admin = make_user(db_session, "triage-batch-keep-admin")
    _, case_result = make_case_result(db_session, admin, "case_batch_keep")
    upsert_failure_triage_note(case_result.id, note_payload(note="Keep this note."), admin, db_session)

    notes = batch_update_failure_triage_notes(
        batch_payload([case_result.id], triage_status="ignored", note="Do not use this note.", note_mode="keep"),
        admin,
        db_session,
    )

    assert notes[0].triage_status.value == "ignored"
    assert notes[0].note == "Keep this note."


def test_batch_update_invalid_note_mode_returns_bad_request(db_session) -> None:
    admin = make_user(db_session, "triage-batch-invalid-mode-admin")
    _, case_result = make_case_result(db_session, admin, "case_batch_invalid_mode")

    with pytest.raises(HTTPException) as exc:
        batch_update_failure_triage_notes(
            batch_payload([case_result.id], note_mode="merge"),
            admin,
            db_session,
        )

    assert exc.value.status_code == 400


def test_batch_update_missing_case_result_returns_not_found(db_session) -> None:
    admin = make_user(db_session, "triage-batch-missing-admin")

    with pytest.raises(HTTPException) as exc:
        batch_update_failure_triage_notes(batch_payload([uuid.uuid4()]), admin, db_session)

    assert exc.value.status_code == 404
