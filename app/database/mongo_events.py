from __future__ import annotations
from typing import List, Mapping, Any
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.database.event_repo import SubmissionEventRepo
from app.schemas.review import DeliveredSubmission


class MongoSubmissionDeliveredRepository(SubmissionEventRepo):
    """
    Gestisce la persistenza dei messaggi di submission consegnate.
    Collection: 'submission-consegnate'
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.col = db["submission-consegnate"]

    async def ensure_indexes(self):
        """
        Indici:
        - Unicità per (assignmentId, studentId): una sola consegna "corrente" per studente/compito.
        - Indici di supporto su submissionId e timestamp utili per query/ordinamenti.
        """
        await self.col.create_index(
            [("assignmentId", 1), ("studentId", 1)],
            name="uniq_assignment_student",
            unique=True,
        )
        await self.col.create_index([("submissionId", 1)])
        await self.col.create_index("deliveredAt")

    async def save_message(self, payload: Mapping[str, Any]) -> bool:
        """
        Salva/aggiorna un messaggio di consegna.

        Regole:
        - Identità documento: (assignmentId, studentId).
        - Se non esiste ancora: inserisce.
        - Se esiste: aggiorna submissionId e gli altri campi del payload.
        - Nessun campo extra oltre al payload; aggiunge solo 'receivedAt'.

        Ritorna:
        - True  -> è stato creato un nuovo documento
        - False -> documento esistente aggiornato
        """
        now = datetime.now(timezone.utc).isoformat()

        assignment_id = payload.get("assignmentId")
        student_id = payload.get("studentId")

        if not assignment_id or not student_id:
            raise ValueError("assignmentId e studentId sono obbligatori")

        # Campi aggiornabili: tutto il payload + 'receivedAt'
        update_doc = {
            **payload,
            "receivedAt": now,
        }

        try:
            res = await self.col.update_one(
                filter={"assignmentId": assignment_id, "studentId": student_id},
                update={"$set": update_doc},
                upsert=True,
            )
            # Se ha inserito un nuovo documento, upserted_id è valorizzato
            return res.upserted_id is not None

        except DuplicateKeyError:
            # In rari casi di race condition con stessa coppia (assignmentId, studentId)
            # riprova come semplice update.
            await self.col.update_one(
                {"assignmentId": assignment_id, "studentId": student_id},
                {"$set": update_doc},
                upsert=False,
            )
            return False

    async def list_delivered_by_assignment(self, assignment_id: str) -> List[DeliveredSubmission]:
        """
        Ritorna la lista di consegne (submissionId, studentId) per l'assignment.
        """
        cursor = self.col.find(
            {"assignmentId": assignment_id},
            {"_id": 0, "submissionId": 1, "studentId": 1, "assignmentId": 1},
        )
        out: List[dict] = []
        async for doc in cursor:
            if all(k in doc for k in ("submissionId", "studentId")):
                out.append(DeliveredSubmission(**doc))
        return out
