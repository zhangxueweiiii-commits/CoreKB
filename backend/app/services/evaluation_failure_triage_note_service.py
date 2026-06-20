from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.evaluation_run import EvaluationCaseResult, EvaluationRun
from app.models.evaluation_triage_note import EvaluationFailureTriageNote, FailureTriageStatus
from app.models.user import User
from app.services.evaluation_run_metadata_service import format_evaluation_run_display


class EvaluationFailureTriageNoteService:
    NOTE_MODES = {"replace", "append", "keep"}

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_note(self, case_result_id: UUID) -> EvaluationFailureTriageNote | None:
        self._require_case_result(case_result_id)
        return self._note_for_case(case_result_id)

    def upsert_note(
        self,
        case_result_id: UUID,
        user: User,
        triage_status: str = FailureTriageStatus.open.value,
        note: str | None = None,
    ) -> EvaluationFailureTriageNote:
        self._require_case_result(case_result_id)
        record = self._note_for_case(case_result_id)
        if record is None:
            record = EvaluationFailureTriageNote(
                evaluation_case_result_id=case_result_id,
                created_by=user.id,
            )
            self.db.add(record)
        record.triage_status = FailureTriageStatus(triage_status)
        record.note = note
        record.updated_by = user.id
        self.db.commit()
        self.db.refresh(record)
        return record

    def batch_upsert_notes(
        self,
        case_result_ids: list[UUID],
        user: User,
        triage_status: str,
        note: str | None = None,
        note_mode: str = "replace",
    ) -> list[EvaluationFailureTriageNote]:
        if note_mode not in self.NOTE_MODES:
            raise ValueError("Invalid note_mode")
        status = FailureTriageStatus(triage_status)
        unique_case_result_ids = list(dict.fromkeys(case_result_ids))
        if not unique_case_result_ids:
            raise ValueError("At least one evaluation case result id is required")

        case_results = self.db.scalars(
            select(EvaluationCaseResult).where(EvaluationCaseResult.id.in_(unique_case_result_ids))
        ).all()
        found_ids = {case_result.id for case_result in case_results}
        missing_ids = [case_result_id for case_result_id in unique_case_result_ids if case_result_id not in found_ids]
        if missing_ids:
            raise KeyError(f"Evaluation case result not found: {missing_ids[0]}")

        existing_notes = {
            record.evaluation_case_result_id: record
            for record in self.db.scalars(
                select(EvaluationFailureTriageNote).where(
                    EvaluationFailureTriageNote.evaluation_case_result_id.in_(unique_case_result_ids)
                )
            ).all()
        }

        records: list[EvaluationFailureTriageNote] = []
        for case_result_id in unique_case_result_ids:
            record = existing_notes.get(case_result_id)
            if record is None:
                record = EvaluationFailureTriageNote(
                    evaluation_case_result_id=case_result_id,
                    created_by=user.id,
                )
                self.db.add(record)
            record.triage_status = status
            record.note = self._merge_note(record.note, note, note_mode)
            record.updated_by = user.id
            records.append(record)

        self.db.commit()
        for record in records:
            self.db.refresh(record)
        return records

    def list_notes(
        self,
        evaluation_run_id: UUID | None = None,
        case_result_ids: list[UUID] | None = None,
        triage_status: str | None = None,
    ) -> list[dict]:
        stmt = (
            select(EvaluationFailureTriageNote, EvaluationCaseResult, EvaluationRun)
            .join(EvaluationCaseResult, EvaluationCaseResult.id == EvaluationFailureTriageNote.evaluation_case_result_id)
            .join(EvaluationRun, EvaluationRun.id == EvaluationCaseResult.evaluation_run_id)
            .order_by(EvaluationFailureTriageNote.updated_at.desc(), EvaluationFailureTriageNote.created_at.desc())
        )
        if evaluation_run_id:
            stmt = stmt.where(EvaluationCaseResult.evaluation_run_id == evaluation_run_id)
        if case_result_ids:
            stmt = stmt.where(EvaluationFailureTriageNote.evaluation_case_result_id.in_(case_result_ids))
        if triage_status:
            stmt = stmt.where(EvaluationFailureTriageNote.triage_status == FailureTriageStatus(triage_status))
        rows = self.db.execute(stmt).all()
        return [self._list_item(note, case_result, run) for note, case_result, run in rows]

    def _require_case_result(self, case_result_id: UUID) -> EvaluationCaseResult:
        record = self.db.get(EvaluationCaseResult, case_result_id)
        if record is None:
            raise KeyError("Evaluation case result not found")
        return record

    def _note_for_case(self, case_result_id: UUID) -> EvaluationFailureTriageNote | None:
        return self.db.scalar(
            select(EvaluationFailureTriageNote).where(
                EvaluationFailureTriageNote.evaluation_case_result_id == case_result_id
            )
        )

    @staticmethod
    def _merge_note(existing_note: str | None, incoming_note: str | None, note_mode: str) -> str | None:
        if note_mode == "keep":
            return existing_note
        if note_mode == "append":
            incoming = (incoming_note or "").strip()
            if not incoming:
                return existing_note
            existing = (existing_note or "").strip()
            return f"{existing}\n{incoming}" if existing else incoming
        return incoming_note

    @staticmethod
    def _note_payload(note: EvaluationFailureTriageNote) -> dict:
        return {
            "id": note.id,
            "evaluation_case_result_id": note.evaluation_case_result_id,
            "triage_status": note.triage_status.value,
            "note": note.note,
            "created_by": note.created_by,
            "updated_by": note.updated_by,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }

    def _list_item(
        self,
        note: EvaluationFailureTriageNote,
        case_result: EvaluationCaseResult,
        run: EvaluationRun,
    ) -> dict:
        payload = self._note_payload(note)
        payload.update(
            {
                "evaluation_run_id": case_result.evaluation_run_id,
                "case_id": case_result.case_id,
                "assistant_type": case_result.assistant_type,
                "query": case_result.query,
                "failure_reason": case_result.failure_reason,
                "suggested_fix_type": case_result.suggested_fix_type,
                "evaluation_run_display_label": format_evaluation_run_display(run)["display_label"],
            }
        )
        return payload
