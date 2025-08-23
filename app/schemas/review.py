from __future__ import annotations
from typing import List, Literal
from datetime import datetime
from pydantic import BaseModel, Field

ReviewStatus = Literal["pending", "complete"]
ProcessStatus = Literal["in_corso", "completata"]

class DeliveredSubmission(BaseModel):
    assignmentId: str
    submissionId: str
    studentId: str

class RubricItem(BaseModel):
    criterio: str = Field(..., description="Nome del criterio di valutazione")

class ValutazioneItem(BaseModel):
    criterio: str
    punteggio: int = Field(..., ge=-1, le=10)  # -1 = non valutato

class AssignmentPair(BaseModel):
    reviewer: str
    submissionId: str

class ReviewProcessCreate(BaseModel):
    assignmentId: str
    automatic_mode: bool
    deadline: datetime
    lista_assegnazioni: List[AssignmentPair] = Field(..., min_length=1)
    rubrica: List[RubricItem] = Field(..., min_length=1)

class Review(BaseModel):
    reviewId: str
    assignmentId: str
    submissionId: str
    reviewerId: str
    createdAt: datetime
    deadline: datetime
    stato: ReviewStatus
    valutazione: List[ValutazioneItem]

class ReviewUpdate(BaseModel):
    valutazione: List[ValutazioneItem]