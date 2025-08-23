from __future__ import annotations
from datetime import datetime, timezone
from typing import List
from uuid import uuid4

from app.schemas.context import UserContext
from app.schemas.review import ReviewProcessCreate, Review, ReviewUpdate
from app.database.review_repo import ReviewRepo

def _is_teacher(role):
    return role == "teacher" or (isinstance(role, (list, tuple, set)) and "teacher" in role)

def _is_student(role):
    return role == "student" or (isinstance(role, (list, tuple, set)) and "student" in role)

class ReviewService:
    @staticmethod
    async def start_process(data: ReviewProcessCreate, user: UserContext, repo: ReviewRepo) -> str:
        if not _is_teacher(user.role):
            raise PermissionError("Solo i docenti possono avviare le review")

        # Template punteggi iniziali (-1)
        valutazione_template = [{"criterio": r.criterio, "punteggio": -1} for r in data.rubrica]
        now = datetime.now(timezone.utc)
        review_docs = [{
            "assignmentId": data.assignmentId,
            "reviewerId": pair.reviewer,
            "submissionId": pair.submissionId,
            "createdAt": now,
            "deadline": data.deadline,
            "stato": "pending",
            "valutazione": list(valutazione_template),
        } for pair in data.lista_assegnazioni]

        await repo.bulk_create_reviews(review_docs)  # genera i reviewId
        return data.assignmentId

    @staticmethod
    async def list_my_reviews(user: UserContext, repo: ReviewRepo, stato: str | None) -> List[Review]:
        if not _is_student(user.role):
            raise PermissionError("Solo gli studenti possono consultare sue reviews")
        docs = await repo.for_student(user.user_id, stato)
        return [Review(**d) for d in docs]

    @staticmethod
    async def get_my_review(user: UserContext, repo: ReviewRepo, review_id: str) -> Review | None:
        if not _is_student(user.role):
            raise PermissionError("Accesso consentito solo agli studenti")
        d = await repo.by_id_for_student(review_id, user.user_id)
        return Review(**d) if d else None

    @staticmethod
    async def submit_review(user: UserContext, repo: ReviewRepo, review_id: str, payload: ReviewUpdate) -> bool:
        if not _is_student(user.role):
            raise PermissionError("Solo gli studenti possono inviare una review")
        if not await repo.by_id_for_student(review_id, user.user_id):
            return False
        return await repo.update_scores(review_id, [v.model_dump() for v in payload.valutazione])

    @staticmethod
    async def list_by_assignment_for_teacher(user: UserContext, repo: ReviewRepo, assignment_id: str) -> List[Review]:
        if not _is_teacher(user.role):
            raise PermissionError("Solo i docenti possono consultare le review di un assignment")
        docs = await repo.by_assignment_for_teacher(assignment_id)
        return [Review(**d) for d in docs]
