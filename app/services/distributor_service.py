
from __future__ import annotations

from typing import List, Dict, Sequence, Set
import random

from app.schemas.review import AssignmentPair, ReviewProcessCreate
from app.database.event_repo import SubmissionEventRepo

# === Exceptions ===
class DistributionError(ValueError):
    """Raised when the provided manual assignment list is inconsistent."""

class DistributorService:
    """
    Produces a verified list of (reviewer -> submission) assignments:
    - If automatic_mode=True: generates a random derangement so nobody reviews their own submission.
    - If automatic_mode=False: validates the provided lista_assegnazioni against the set of students who submitted.
    """

    @staticmethod
    async def build_verified_assignments(
        payload: ReviewProcessCreate,
        event_reader: SubmissionEventRepo
    ) -> List[AssignmentPair]:
        
        rng = random.Random()
        submissions = await event_reader.list_delivered_by_assignment(payload.assignmentId)
        if not submissions:
            raise DistributionError("Nessuna submission trovata per questo assignment.")

        # Build maps/sets
        student_to_submission: Dict[str, str] = {s.studentId: s.submissionId for s in submissions}
        submission_ids: Set[str] = {s.submissionId for s in submissions}
        students: Set[str] = set(student_to_submission.keys())

        if payload.automatic_mode:
            return DistributorService._auto_distribute(students, student_to_submission, rng)
        else:
            if not payload.lista_assegnazioni:
                raise DistributionError("Modalità manuale: 'lista_assegnazioni' è obbligatoria.")
            return DistributorService._validate_manual(payload.lista_assegnazioni, students, student_to_submission, submission_ids)

    # ----- helpers -----

    @staticmethod
    def _validate_manual(
        manual_list: Sequence[AssignmentPair],
        students: Set[str],
        student_to_submission: Dict[str, str],
        submission_ids: Set[str],
    ) -> List[AssignmentPair]:
        reviewers = [a.reviewer for a in manual_list]
        # 1) Tutti gli studenti che hanno consegnato DEVONO essere presenti come reviewer
        diff_missing = students.difference(reviewers)
        if diff_missing:
            raise DistributionError(f"Mancano assegnazioni per i seguenti studenti: {sorted(diff_missing)}")

        # 2) Nessuno può recensire la propria submission
        errors = []
        for a in manual_list:
            own_sub = student_to_submission.get(a.reviewer)
            if own_sub and a.submissionId == own_sub:
                errors.append(f"{a.reviewer} è assegnato alla propria submission {a.submissionId}")
            # 3) La submission assegnata deve esistere tra quelle consegnate
            if a.submissionId not in submission_ids:
                errors.append(f"Submission {a.submissionId} non trovata tra le consegne")

        if errors:
            raise DistributionError("; ".join(errors))

        # 4) (opzionale) Garanzia che ogni reviewer appaia una sola volta
        if len(set(reviewers)) != len(reviewers):
            raise DistributionError("Un reviewer appare più volte nella lista manuale.")

        return list(manual_list)

    @staticmethod
    def _auto_distribute(
        students: Set[str],
        student_to_submission: Dict[str, str],
        rng: random.Random,
    ) -> List[AssignmentPair]:
        """
        Crea una permutazione senza punti fissi (derangement) delle submission,
        quindi abbina ogni reviewer alla submission di un altro.
        Usa l'algoritmo di Sattolo per ottenere un'unica ciclo (nessun fisso).
        """
        reviewers = sorted(students)  # ordinamento stabile per determinismo se rng seeded
        # lista di submission nello stesso ordine dei reviewers
        subs = [student_to_submission[r] for r in reviewers]

        # produce una permutazione ciclica su 'subs'
        # tale che per ogni i, subs_perm[i] != subs[i]
        subs_perm = subs[:]  # copy
        n = len(subs_perm)
        if n == 1:
            raise DistributionError("Impossibile generare una distribuzione automatica con un solo studente.")
        for i in range(n - 1, 0, -1):
            j = rng.randrange(0, i)  # 0 <= j < i
            subs_perm[i], subs_perm[j] = subs_perm[j], subs_perm[i]

        # Se dovesse capitare un fisso (estremamente raro con Sattolo custom),
        # facciamo un fallback semplice: ruota di 1 posizione
        if any(subs_perm[i] == subs[i] for i in range(n)):
            subs_perm = subs_perm[1:] + subs_perm[:1]

        result = [AssignmentPair(reviewer=r, submissionId=s) for r, s in zip(reviewers, subs_perm)]
        # Safety net finale
        for ap in result:
            assert student_to_submission[ap.reviewer] != ap.submissionId, "Derangement fallito"
        return result
