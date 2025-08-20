import pytest
from datetime import date, datetime, timezone
from uuid import uuid4, UUID

# Adatta questi import al tuo layout:
from app.services.review_service import ReviewService
from app.schemas.context import UserContext
from app.schemas.review import (
    ReviewProcessCreate, ReviewUpdate,
    RubricItem, AssignmentPair, ValutazioneItem, Review
)

# ------------------------- Fake repository (minimale) -------------------------
class FakeReviewRepo:
    """
    In-memory repo che emula i metodi usati da ReviewService.
    bulk_create_reviews genera automaticamente reviewId (UUID).
    """
    def __init__(self):
        self.reviews: list[dict] = []

    async def bulk_create_reviews(self, docs):
        ids = []
        for d in docs:
            rid = str(uuid4())
            self.reviews.append({**d, "reviewId": rid})
            ids.append(rid)
        return ids

    async def for_student(self, student_id: str, stato: str | None = None):
        out = [r for r in self.reviews if r["reviewerId"] == student_id]
        if stato is not None:
            out = [r for r in out if r["stato"] == stato]
        return out

    async def by_id_for_student(self, review_id: str, student_id: str):
        for r in self.reviews:
            if r["reviewId"] == review_id and r["reviewerId"] == student_id:
                return r
        return None

    async def update_scores(self, review_id: str, valutazione):
        for r in self.reviews:
            if r["reviewId"] == review_id:
                r["valutazione"] = list(valutazione)
                r["stato"] = "complete"
                r["updatedAt"] = datetime.now(timezone.utc)
                return True
        return False

    async def by_assignment_for_teacher(self, assignment_id: str):
        return [r for r in self.reviews if r["assignmentId"] == assignment_id]


# ------------------------------- Fixtures -------------------------------------
@pytest.fixture
def repo():
    return FakeReviewRepo()

@pytest.fixture
def teacher():
    return UserContext(user_id="t-1", role="teacher")

@pytest.fixture
def student1():
    return UserContext(user_id="s-1", role="student")

@pytest.fixture
def student2():
    return UserContext(user_id="s-2", role="student")

def _make_process_payload(**overrides) -> ReviewProcessCreate:
    base = dict(
        assignmentId="ASSIGN-001",
        deadline=date(2025, 10, 15),
        lista_assegnazioni=[
            AssignmentPair(reviewer="s-1", submissionId="SUB-100"),
            AssignmentPair(reviewer="s-2", submissionId="SUB-200"),
        ],
        rubrica=[
            RubricItem(criterio="Chiarezza"),
            RubricItem(criterio="Correttezza"),
            RubricItem(criterio="Completezza"),
        ],
    )
    base.update(overrides)
    return ReviewProcessCreate(**base)

def _make_review_update() -> ReviewUpdate:
    return ReviewUpdate(
        valutazione=[
            ValutazioneItem(criterio="Chiarezza", punteggio=8),
            ValutazioneItem(criterio="Correttezza", punteggio=9),
            ValutazioneItem(criterio="Completezza", punteggio=7),
        ]
    )


# --------------------------------- Tests --------------------------------------
@pytest.mark.asyncio
async def test_start_process_requires_teacher(repo, student1):
    with pytest.raises(PermissionError):
        await ReviewService.start_process(_make_process_payload(), student1, repo)

@pytest.mark.asyncio
async def test_start_process_creates_reviews_and_returns_process_id(repo, teacher):
    payload = _make_process_payload()
    process_id = await ReviewService.start_process(payload, teacher, repo)

    # process_id è un UUID valido
    UUID(process_id)

    # sono state create N review (una per coppia)
    assert len(repo.reviews) == len(payload.lista_assegnazioni)

    # campi attesi su ogni review
    for r in repo.reviews:
        assert r["assignmentId"] == payload.assignmentId
        assert r["submissionId"] in {"SUB-100", "SUB-200"}
        assert r["reviewerId"] in {"s-1", "s-2"}
        assert r["stato"] == "pending"
        assert r["processId"] == process_id
        assert r["deadline"] == payload.deadline  # presente nell'impl corrente
        assert isinstance(r["createdAt"], datetime) and r["createdAt"].tzinfo == timezone.utc
        # valutazione iniziale coerente con rubrica
        assert len(r["valutazione"]) == len(payload.rubrica)
        assert all(v["punteggio"] == -1 for v in r["valutazione"])
        assert {v["criterio"] for v in r["valutazione"]} == {i.criterio for i in payload.rubrica}
        assert "reviewId" in r  # generato dal repo fake

@pytest.mark.asyncio
async def test_list_my_reviews_requires_student(repo, teacher):
    with pytest.raises(PermissionError):
        await ReviewService.list_my_reviews(teacher, repo, stato=None)

@pytest.mark.asyncio
async def test_list_my_reviews_returns_models_and_filters(repo, teacher, student1, student2):
    # seed: crea processo per s-1 e s-2
    await ReviewService.start_process(_make_process_payload(), teacher, repo)

    # aggiungi una review "complete" per s-1
    rid = next(r["reviewId"] for r in repo.reviews if r["reviewerId"] == "s-1")
    await repo.update_scores(rid, [{"criterio":"Chiarezza","punteggio":10}])

    # senza filtro: 1 complete + 0/1 pending (dipende da s-1)
    all_s1 = await ReviewService.list_my_reviews(student1, repo, stato=None)
    assert all(isinstance(x, Review) for x in all_s1)
    assert {x.stato for x in all_s1} == {"complete"} or {x.stato for x in all_s1} == {"complete", "pending"}

    # filtro pending
    pend_s2 = await ReviewService.list_my_reviews(student2, repo, stato="pending")
    assert all(r.stato == "pending" for r in pend_s2)

@pytest.mark.asyncio
async def test_get_my_review_access(repo, teacher, student1, student2):
    await ReviewService.start_process(_make_process_payload(), teacher, repo)
    # prendi una review di s-1
    rid = next(r["reviewId"] for r in repo.reviews if r["reviewerId"] == "s-1")

    # chi non è student -> 403 (PermissionError)
    with pytest.raises(PermissionError):
        await ReviewService.get_my_review(user=teacher, repo=repo, review_id=rid)

    # owner ottiene Review
    mine = await ReviewService.get_my_review(user=student1, repo=repo, review_id=rid)
    assert isinstance(mine, Review)
    assert mine.reviewerId == "s-1"

    # altro studente -> None (non accessibile)
    other = await ReviewService.get_my_review(user=student2, repo=repo, review_id=rid)
    assert other is None

@pytest.mark.asyncio
async def test_submit_review_requires_student(repo, teacher):
    await ReviewService.start_process(_make_process_payload(), teacher, repo)
    rid = next(r["reviewId"] for r in repo.reviews if r["reviewerId"] == "s-1")
    with pytest.raises(PermissionError):
        await ReviewService.submit_review(teacher, repo, rid, _make_review_update())

@pytest.mark.asyncio
async def test_submit_review_wrong_owner_returns_false(repo, teacher, student2):
    await ReviewService.start_process(_make_process_payload(), teacher, repo)
    # rid appartiene a s-1
    rid = next(r["reviewId"] for r in repo.reviews if r["reviewerId"] == "s-1")
    ok = await ReviewService.submit_review(student2, repo, rid, _make_review_update())
    assert ok is False

@pytest.mark.asyncio
async def test_submit_review_ok_updates_scores_and_state(repo, teacher, student1):
    await ReviewService.start_process(_make_process_payload(), teacher, repo)
    rid = next(r["reviewId"] for r in repo.reviews if r["reviewerId"] == "s-1")

    payload = _make_review_update()
    ok = await ReviewService.submit_review(student1, repo, rid, payload)
    assert ok is True

    # verifica update sul repo
    saved = await repo.by_id_for_student(rid, "s-1")
    assert saved["stato"] == "complete"
    assert [v for v in saved["valutazione"]] == [v.__dict__ for v in payload.valutazione]

@pytest.mark.asyncio
async def test_list_by_assignment_for_teacher(repo, teacher, student1):
    await ReviewService.start_process(_make_process_payload(), teacher, repo)
    items = await ReviewService.list_by_assignment_for_teacher(teacher, repo, "ASSIGN-001")
    assert all(isinstance(x, Review) for x in items)
    # ruolo non docente -> PermissionError
    with pytest.raises(PermissionError):
        await ReviewService.list_by_assignment_for_teacher(student1, repo, "ASSIGN-001")
