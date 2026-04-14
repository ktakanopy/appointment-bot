from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from app.domain.models import RememberedIdentity, RememberedIdentityStatus


class SQLiteRememberedIdentityRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._ensure_schema()

    def get_by_id(self, remembered_identity_id: str) -> RememberedIdentity | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select
                    remembered_identity_id,
                    patient_id,
                    display_name,
                    verification_fingerprint,
                    issued_at,
                    expires_at,
                    revoked_at,
                    status
                from remembered_identity
                where remembered_identity_id = ?
                """,
                (remembered_identity_id,),
            ).fetchone()
        return self._row_to_identity(row)

    def get_active_by_patient_id(self, patient_id: str) -> RememberedIdentity | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                select
                    remembered_identity_id,
                    patient_id,
                    display_name,
                    verification_fingerprint,
                    issued_at,
                    expires_at,
                    revoked_at,
                    status
                from remembered_identity
                where patient_id = ? and status = ? and revoked_at is null
                order by issued_at desc
                limit 1
                """,
                (patient_id, RememberedIdentityStatus.ACTIVE.value),
            ).fetchone()
        return self._row_to_identity(row)

    def save(self, identity: RememberedIdentity) -> RememberedIdentity:
        with self._connect() as connection:
            connection.execute(
                """
                insert into remembered_identity (
                    remembered_identity_id,
                    patient_id,
                    display_name,
                    verification_fingerprint,
                    issued_at,
                    expires_at,
                    revoked_at,
                    status
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(remembered_identity_id) do update set
                    patient_id = excluded.patient_id,
                    display_name = excluded.display_name,
                    verification_fingerprint = excluded.verification_fingerprint,
                    issued_at = excluded.issued_at,
                    expires_at = excluded.expires_at,
                    revoked_at = excluded.revoked_at,
                    status = excluded.status
                """,
                (
                    identity.remembered_identity_id,
                    identity.patient_id,
                    identity.display_name,
                    identity.verification_fingerprint,
                    identity.issued_at.isoformat(),
                    identity.expires_at.isoformat(),
                    identity.revoked_at.isoformat() if identity.revoked_at else None,
                    identity.status.value,
                ),
            )
        return identity

    def revoke(self, remembered_identity_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                """
                update remembered_identity
                set revoked_at = ?, status = ?
                where remembered_identity_id = ? and revoked_at is null
                """,
                (datetime.now().astimezone().isoformat(), RememberedIdentityStatus.REVOKED.value, remembered_identity_id),
            )
        return result.rowcount > 0

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                create table if not exists remembered_identity (
                    remembered_identity_id text primary key,
                    patient_id text not null,
                    display_name text,
                    verification_fingerprint text not null,
                    issued_at text not null,
                    expires_at text not null,
                    revoked_at text,
                    status text not null
                )
                """
            )
            connection.execute(
                """
                create index if not exists idx_remembered_identity_patient_id
                on remembered_identity(patient_id)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_identity(self, row: sqlite3.Row | None) -> RememberedIdentity | None:
        if row is None:
            return None
        revoked_at = datetime.fromisoformat(row["revoked_at"]) if row["revoked_at"] else None
        return RememberedIdentity(
            remembered_identity_id=row["remembered_identity_id"],
            patient_id=row["patient_id"],
            display_name=row["display_name"],
            verification_fingerprint=row["verification_fingerprint"],
            issued_at=datetime.fromisoformat(row["issued_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            revoked_at=revoked_at,
            status=RememberedIdentityStatus(row["status"]),
        )
