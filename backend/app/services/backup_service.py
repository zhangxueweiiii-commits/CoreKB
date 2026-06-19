import hashlib
import json
import logging
import shutil
import subprocess
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.tracing import start_span
from app.models.backup_job import BackupJob, BackupJobStatus, BackupJobType
from app.services.alert_service import AlertService


logger = logging.getLogger("corekb.backup")


class BackupService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def run(self, job_type: BackupJobType) -> BackupJob:
        now = datetime.now(timezone.utc)
        job = BackupJob(job_type=job_type, status=BackupJobStatus.running, started_at=now)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        try:
            with start_span("backup.job", job_type=job_type.value, backup_job_id=job.id):
                target = self._execute(job_type, job.id.hex)
            job.backup_path = str(target)
            job.file_size = target.stat().st_size
            job.checksum = self.compute_checksum(target)
            job.status = BackupJobStatus.completed
            job.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(job)
            self.cleanup_retention()
            logger.info("Backup completed", extra={"resource_id": job.id})
            return job
        except Exception as exc:
            self.db.rollback()
            job = self.db.get(BackupJob, job.id)
            job.status = BackupJobStatus.failed
            job.error_message = str(exc)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            AlertService().backup_failed(job.id, str(exc))
            logger.exception("Backup failed", extra={"resource_id": job.id, "error": str(exc)})
            return job

    def verify(self, job: BackupJob) -> tuple[bool, str | None]:
        if not job.backup_path or not job.checksum:
            return False, None
        path = Path(job.backup_path)
        if not path.exists():
            return False, None
        actual = self.compute_checksum(path)
        return actual == job.checksum, actual

    def latest(self) -> BackupJob | None:
        return self.db.scalar(select(BackupJob).order_by(BackupJob.created_at.desc()))

    def latest_failed(self) -> BackupJob | None:
        return self.db.scalar(
            select(BackupJob)
            .where(BackupJob.status == BackupJobStatus.failed)
            .order_by(BackupJob.created_at.desc())
        )

    def cleanup_retention(self) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.backup_retention_days)
        for path in self.settings.backup_dir.glob("*"):
            try:
                if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
            except Exception as exc:
                logger.warning("Backup retention cleanup failed", extra={"path": str(path), "error": str(exc)})

    @staticmethod
    def compute_checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _execute(self, job_type: BackupJobType, job_id: str) -> Path:
        base_dir = self.settings.backup_dir / f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{job_id}"
        base_dir.mkdir(parents=True, exist_ok=True)
        if job_type == BackupJobType.postgres:
            return self._backup_postgres(base_dir)
        if job_type == BackupJobType.qdrant:
            return self._backup_qdrant(base_dir)
        if job_type == BackupJobType.uploads:
            return self._backup_uploads(base_dir)
        return self._backup_all(base_dir)

    def _backup_postgres(self, base_dir: Path) -> Path:
        target = base_dir / "postgres.dump"
        database_url = self.settings.database_url.replace("postgresql+psycopg://", "postgresql://")
        command = ["pg_dump", "--format=custom", "--file", str(target), database_url]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=3600)
        return target

    def _backup_uploads(self, base_dir: Path) -> Path:
        target = base_dir / "uploads.tgz"
        with tarfile.open(target, "w:gz") as archive:
            if self.settings.upload_dir.exists():
                archive.add(self.settings.upload_dir, arcname="uploads")
        return target

    def _backup_qdrant(self, base_dir: Path) -> Path:
        target = base_dir / "qdrant.tgz"
        with tarfile.open(target, "w:gz") as archive:
            if self.settings.qdrant_storage_dir and self.settings.qdrant_storage_dir.exists():
                archive.add(self.settings.qdrant_storage_dir, arcname="qdrant_storage")
            else:
                manifest = base_dir / "qdrant_manifest.json"
                manifest.write_text(
                    json.dumps(
                        {
                            "qdrant_url": self.settings.qdrant_url,
                            "note": "No QDRANT_STORAGE_DIR configured; use Qdrant snapshots or volume backup in production.",
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                archive.add(manifest, arcname="qdrant_manifest.json")
        return target

    def _backup_all(self, base_dir: Path) -> Path:
        safe_config = base_dir / "config"
        safe_config.mkdir(exist_ok=True)
        env_example = Path("/app/.env.example")
        local_env_example = Path(".env.example")
        if env_example.exists():
            shutil.copy2(env_example, safe_config / ".env.example")
        elif local_env_example.exists():
            shutil.copy2(local_env_example, safe_config / ".env.example")

        artifacts: list[Path] = []
        artifacts.append(self._backup_uploads(base_dir))
        artifacts.append(self._backup_qdrant(base_dir))
        try:
            artifacts.append(self._backup_postgres(base_dir))
        except Exception as exc:
            (base_dir / "postgres_backup_error.txt").write_text(str(exc), encoding="utf-8")
            raise

        target = base_dir.with_suffix(".tgz")
        with tarfile.open(target, "w:gz") as archive:
            archive.add(base_dir, arcname=base_dir.name)
        shutil.rmtree(base_dir)
        return target
