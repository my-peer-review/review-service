from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Mapping

from app.schemas.review import DeliveredSubmission

class SubmissionEventRepo(ABC):

    @abstractmethod
    async def save_message(self, payload: Mapping[str, Any]) -> bool:
        raise NotImplementedError
    
    @abstractmethod
    async def list_delivered_by_assignment(self, assignment_id: str) -> List[DeliveredSubmission]:
        """
        Ritorna la lista di {studentId, submissionId, assignmentId} per tutti
        gli studenti che hanno consegnato per l'assignment dato.
        """
        raise NotImplementedError