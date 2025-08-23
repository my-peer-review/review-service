from __future__ import annotations
from typing import Iterable, List, Optional, Sequence
from datetime import datetime, timezone
import random

from motor.motor_asyncio import AsyncIOMotorDatabase
from app.database.review_repo import ReviewRepo

def create_review_id() -> str:
    return f"rv-{random.randint(0, 99999):05d}"

class MongoReviewRepository(ReviewRepo):

    def __init__(self, db: AsyncIOMotorDatabase):
        self.rev  = db["reviews"]

    async def ensure_indexes(self):
        # Reviews
        await self.rev.create_index("reviewId", unique=True)
        await self.rev.create_index([("reviewerId", 1), ("stato", 1)])
        await self.rev.create_index("assignmentId")
        await self.rev.create_index("processId")  # riferimento al processId applicativo

    # ---------- Reviews (studenti)
    async def bulk_create_reviews(self, docs: Iterable[dict]) -> List[str]:
        """
        Per ogni review genera un reviewId (UUID).
        Ritorna la lista dei reviewId generati.
        """
        prepared = []
        out_ids: List[str] = []
        now = datetime.now(timezone.utc)
        for d in docs:
            rid = create_review_id()
            out_ids.append(rid)
            prepared.append({
                "reviewId": rid,
                "createdAt": d.get("createdAt", now),
                **d,
            })
        if prepared:
            print(f"Preparing {len(prepared)} reviews for bulk insert")
            print(prepared)
            await self.rev.insert_many(prepared)
        return out_ids

    async def for_student(self, student_id: str, stato: Optional[str] = None) -> List[dict]:
        q = {"reviewerId": str(student_id)}
        if stato:
            q["stato"] = stato
        cursor = self.rev.find(q)
        return [d async for d in cursor]

    async def by_id_for_student(self, review_id: str, student_id: str) -> Optional[dict]:
        return await self.rev.find_one({"reviewId": str(review_id), "reviewerId": str(student_id)})

    async def update_scores(self, review_id: str, valutazione: Sequence[dict]) -> bool:
        res = await self.rev.update_one(
            {"reviewId": str(review_id)},
            {"$set": {
                "valutazione": list(valutazione),
                "stato": "complete",
                "updatedAt": datetime.now(timezone.utc),
            }},
        )
        return res.matched_count == 1

    async def by_assignment_for_teacher(self, assignment_id: str) -> List[dict]:
        cursor = self.rev.find({"assignmentId": str(assignment_id)})
        return [d async for d in cursor]
