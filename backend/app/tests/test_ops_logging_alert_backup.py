import json
import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.routes.alerts import ignore_alert, resolve_alert
from app.api.routes.backups import list_backups, verify_backup
from app.core.logging import JsonLogFormatter
from app.main import app
from app.models.alert_event import AlertEvent, AlertEventStatus
from app.models.backup_job import BackupJob, BackupJobStatus, BackupJobType
from app.models.document import Document, DocumentStatus
from app.models.index_job import IndexJobStatus
from app.models.knowledge_base import KBPermission, KBPermissionRole, KnowledgeBase
from app.models.user import User, UserRole
from app.services.alert_service import AlertService
from app.services.backup_service import BackupService
from app.services.index_job_service import IndexJobService
from app.tasks.document_tasks import process_reindex_job


def make_user(db, username: str, role: UserRole = UserRole.viewer) -> User:
    user = User(username=username, password_hash="x", role=role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_kb(db, owner: User) -> KnowledgeBase:
    kb = KnowledgeBase(name=f"kb-{uuid.uuid4().hex[:6]}", owner_id=owner.id, visibility="private")
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


def make_document(db, kb: KnowledgeBase, path: Path) -> Document:
    document = Document(
        knowledge_base_id=kb.id,
        filename=path.name,
        file_path=str(path),
        file_type="txt",
        file_size=path.stat().st_size,
        status=DocumentStatus.uploaded,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def test_json_logging_redacts_secrets() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="corekb.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="login failed password=secret api_key=sk-test",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["module"] == "corekb.test"
    assert "secret" not in payload["message"]
    assert "sk-test" not in payload["message"]
    assert "[redacted]" in payload["message"]


def test_failed_index_job_triggers_alert(db_session, tmp_path, monkeypatch) -> None:
    owner = make_user(db_session, "owner", UserRole.editor)
    kb = make_kb(db_session, owner)
    path = tmp_path / "doc.txt"
    path.write_text("hello", encoding="utf-8")
    document = make_document(db_session, kb, path)
    job = IndexJobService(db_session).create_kb_reindex_job(kb.id, [document], owner, True)
    alerts = []

    class FailingIngestion:
        async def process(self, db, document):
            document.status = DocumentStatus.failed
            document.error_message = "embedding failed"
            db.commit()
            return document

    class FakeAlertService:
        def __init__(self, *args, **kwargs):
            return None

        def index_job_failed(self, job_id, message):
            alerts.append(("index_job_failed", job_id, message))

        def failed_job_threshold_exceeded(self, count):
            alerts.append(("threshold", count))

    monkeypatch.setattr("app.tasks.document_tasks.SessionLocal", lambda: db_session)
    monkeypatch.setattr("app.tasks.document_tasks.DocumentIngestionService", FailingIngestion)
    monkeypatch.setattr("app.tasks.document_tasks.AlertService", FakeAlertService)
    monkeypatch.setattr("app.tasks.document_tasks.get_settings", lambda: SimpleNamespace(alert_failed_job_threshold=99))

    process_reindex_job(str(job.id))
    job = db_session.get(type(job), job.id)

    assert job.status == IndexJobStatus.failed
    assert alerts[0][0] == "index_job_failed"


def test_alert_service_persists_alert_event(db_session) -> None:
    service = AlertService(db_session)
    service.settings = SimpleNamespace(alert_enabled=False, alert_webhook_url=None)

    event = service.send(
        alert_type="backup_failed",
        severity="critical",
        title="Backup failed",
        message="pg_dump failed",
        resource_type="backup_job",
        resource_id="backup-1",
        metadata={"job_type": "all"},
    )

    stored = db_session.get(AlertEvent, event.id)
    assert stored is not None
    assert stored.alert_type == "backup_failed"
    assert stored.status == AlertEventStatus.open
    assert stored.webhook_sent is False
    assert stored.meta["job_type"] == "all"


def test_alert_webhook_failure_does_not_interrupt(db_session, monkeypatch) -> None:
    service = AlertService(db_session)
    service.settings = SimpleNamespace(alert_enabled=True, alert_webhook_url="http://alerts.invalid/webhook")

    def fail_post(*args, **kwargs):
        raise RuntimeError("webhook down")

    monkeypatch.setattr("app.services.alert_service.httpx.post", fail_post)

    event = service.send(alert_type="health_unavailable", severity="critical", message="redis down")

    assert event.webhook_sent is False
    assert "webhook down" in event.webhook_error


def test_admin_can_resolve_alert(db_session) -> None:
    admin = make_user(db_session, "admin", UserRole.admin)
    event = AlertService(db_session).send(alert_type="backup_failed", severity="critical", message="failed")

    resolved = resolve_alert(event.id, admin, db_session)

    assert resolved.status == AlertEventStatus.resolved
    assert resolved.resolved_at is not None


def test_admin_can_ignore_alert(db_session) -> None:
    admin = make_user(db_session, "admin", UserRole.admin)
    event = AlertService(db_session).send(alert_type="health_unavailable", severity="critical", message="redis down")

    ignored = ignore_alert(event.id, admin, db_session)

    assert ignored.status == AlertEventStatus.ignored
    assert ignored.resolved_at is not None


def test_non_admin_cannot_resolve_or_ignore_alerts(db_session) -> None:
    viewer = make_user(db_session, "viewer", UserRole.viewer)
    AlertService(db_session).send(alert_type="backup_failed", severity="critical", message="failed")

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: viewer
    try:
        client = TestClient(app)
        alert_id = str(uuid.uuid4())
        resolve_response = client.patch(f"/api/alerts/{alert_id}/resolve")
        ignore_response = client.patch(f"/api/alerts/{alert_id}/ignore")
    finally:
        app.dependency_overrides.clear()

    assert resolve_response.status_code == 403
    assert ignore_response.status_code == 403


def test_backup_all_success_creates_backup_job(db_session, tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "backup.tgz"
    artifact.write_bytes(b"backup-data")
    monkeypatch.setattr(BackupService, "_execute", lambda self, job_type, job_id: artifact)
    monkeypatch.setattr(BackupService, "cleanup_retention", lambda self: None)

    job = BackupService(db_session).run(BackupJobType.all)

    assert job.status == BackupJobStatus.completed
    assert job.file_size == len(b"backup-data")
    assert job.checksum == BackupService.compute_checksum(artifact)


def test_backup_failed_records_failed_and_alerts(db_session, monkeypatch) -> None:
    alerts = []

    class FakeAlertService:
        def backup_failed(self, backup_id, message):
            alerts.append((backup_id, message))

    def fail_execute(self, job_type, job_id):
        raise RuntimeError("pg_dump failed")

    monkeypatch.setattr(BackupService, "_execute", fail_execute)
    monkeypatch.setattr("app.services.backup_service.AlertService", FakeAlertService)

    job = BackupService(db_session).run(BackupJobType.all)

    assert job.status == BackupJobStatus.failed
    assert "pg_dump failed" in job.error_message
    assert alerts and alerts[0][0] == job.id


def test_verify_backup_checksum_true(db_session, tmp_path) -> None:
    artifact = tmp_path / "backup.tgz"
    artifact.write_bytes(b"ok")
    job = BackupJob(
        job_type=BackupJobType.uploads,
        status=BackupJobStatus.completed,
        backup_path=str(artifact),
        file_size=2,
        checksum=BackupService.compute_checksum(artifact),
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    result = verify_backup(job.id, make_user(db_session, "admin", UserRole.admin), db_session)

    assert result.verified is True


def test_verify_backup_checksum_false(db_session, tmp_path) -> None:
    artifact = tmp_path / "backup.tgz"
    artifact.write_bytes(b"ok")
    job = BackupJob(
        job_type=BackupJobType.uploads,
        status=BackupJobStatus.completed,
        backup_path=str(artifact),
        file_size=2,
        checksum="0" * 64,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    result = verify_backup(job.id, make_user(db_session, "admin", UserRole.admin), db_session)

    assert result.verified is False
    assert result.actual_checksum != result.expected_checksum


def test_dr_restore_check_missing_file_returns_non_zero() -> None:
    shell = shutil.which("sh") or shutil.which("bash")
    if shell is None:
        pytest.skip("POSIX shell is not available")
    if "system32" in shell.lower() and shell.lower().endswith("bash.exe"):
        pytest.skip("WSL bash placeholder is not usable for shell script tests")
    script = Path(__file__).resolve().parents[3] / "scripts" / "dr_restore_check.sh"

    result = subprocess.run(
        [shell, str(script), "missing-backup-file.tgz"],
        cwd=script.parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert result.returncode != 0
    assert "Backup file not found" in result.stdout


def test_non_admin_cannot_access_backups_endpoint(db_session) -> None:
    viewer = make_user(db_session, "viewer", UserRole.viewer)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: viewer
    try:
        response = TestClient(app).get("/api/backups")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
