from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Optional, Sequence

# Se vuoi tipizzare lo stato:
# from schemas.review import ReviewStatus  # Literal["pending", "complete"]

class ReviewRepo(ABC):
    """
    Interfaccia astratta per la persistenza del dominio 'review'.

    NOTE:
    - Gli ID applicativi sono stringhe (UUID):
        * processId per i processi di review
        * reviewId  per le singole review
    - Le implementazioni NON devono esporre/affidarsi a _id di Mongo.
    - I metodi che ritornano liste/dizionari lasciano al service la
      conversione verso modelli Pydantic (es. Review, ReviewProcess).
    """

    # --------- Review tasks (studenti)
    @abstractmethod
    async def bulk_create_reviews(self, docs: Iterable[dict]) -> Sequence[str]:
        """
        Crea in bulk N review collegate a un processo.
        Ogni doc deve includere:
            - assignmentId: str
            - reviewerId: str
            - submissionId: str
            - createdAt: datetime (UTC)
            - stato: "pending"
            - valutazione: list[{"criterio": str, "punteggio": int}]
            - processId: str (UUID del processo)
        L'implementazione deve generare internamente `reviewId` (UUID) per ciascun doc.
        Ritorna: lista dei reviewId creati.
        """
        raise NotImplementedError

    @abstractmethod
    async def for_student(self, student_id: str, stato: Optional[str] = None) -> Sequence[dict]:
        """
        Elenca le review assegnate a uno studente, opzionalmente filtrate per stato.
        `stato` accetta "pending" | "complete" (o None per tutte).
        Ritorna una lista di dict che includono sempre `reviewId`.
        """
        raise NotImplementedError

    @abstractmethod
    async def by_id_for_student(self, review_id: str, student_id: str) -> Optional[dict]:
        """
        Recupera una singola review per `reviewId` verificando l'appartenenza
        allo `student_id`. Se non trovata o non appartenente, ritorna None.
        """
        raise NotImplementedError

    @abstractmethod
    async def update_scores(self, review_id: str, valutazione: Sequence[dict]) -> bool:
        """
        Aggiorna i punteggi (lista di {criterio, punteggio}) per una review
        e imposta lo stato a 'complete'. Ritorna True se l'update ha toccato 1 doc.
        """
        raise NotImplementedError

    @abstractmethod
    async def by_assignment_for_teacher(self, assignment_id: str) -> Sequence[dict]:
        """
        Elenca tutte le review relative a un assignment (vista docente).
        Ritorna una lista di dict che includono sempre `reviewId`.
        """
        raise NotImplementedError

