import pytest
from dataclasses import dataclass
from typing import List

# SUT
from app.services.distributor_service import DistributorService, DistributionError

# --------------------------- Fakes & helpers ---------------------------

@dataclass
class Submission:
    studentId: str
    submissionId: str

class FakeEventRepo:
    def __init__(self, submissions: list[Submission]):
        self._subs = submissions

    async def list_delivered_by_assignment(self, assignment_id: str):
        # L'impl reale filtra per assignment; qui basta restituire la lista
        return list(self._subs)

@dataclass
class Pair:
    reviewer: str
    submissionId: str

@dataclass
class Payload:
    assignmentId: str
    automatic_mode: bool
    lista_assegnazioni: List[Pair] | None = None


# ------------------------------- Tests ---------------------------------

@pytest.mark.asyncio
async def test_manual_ok_all_students_present_and_no_self_review():
    subs = [Submission("s-1", "SUB-1"), Submission("s-2", "SUB-2")]
    repo = FakeEventRepo(subs)
    payload = Payload(
        assignmentId="A1",
        automatic_mode=False,
        lista_assegnazioni=[
            Pair("s-1", "SUB-2"),
            Pair("s-2", "SUB-1"),
        ],
    )

    result = await DistributorService.build_verified_assignments(payload, repo)
    assert sorted((p.reviewer, p.submissionId) for p in result) == \
           sorted((p.reviewer, p.submissionId) for p in payload.lista_assegnazioni)


@pytest.mark.asyncio
async def test_manual_raises_if_missing_student():
    subs = [Submission("s-1", "SUB-1"), Submission("s-2", "SUB-2"), Submission("s-3", "SUB-3")]
    repo = FakeEventRepo(subs)
    payload = Payload(
        assignmentId="A1",
        automatic_mode=False,
        lista_assegnazioni=[
            Pair("s-1", "SUB-2"),
            Pair("s-2", "SUB-1"),
            # s-3 manca
        ],
    )
    with pytest.raises(DistributionError) as ei:
        await DistributorService.build_verified_assignments(payload, repo)
    assert "Mancano assegnazioni" in str(ei.value)


@pytest.mark.asyncio
async def test_manual_raises_if_self_review_present():
    subs = [Submission("s-1", "SUB-1"), Submission("s-2", "SUB-2")]
    repo = FakeEventRepo(subs)
    payload = Payload(
        assignmentId="A1",
        automatic_mode=False,
        lista_assegnazioni=[
            Pair("s-1", "SUB-1"),  # self-review vietata
            Pair("s-2", "SUB-1"),
        ],
    )
    with pytest.raises(DistributionError) as ei:
        await DistributorService.build_verified_assignments(payload, repo)
    assert "assegnato alla propria submission" in str(ei.value)


@pytest.mark.asyncio
async def test_manual_raises_if_submission_not_found():
    subs = [Submission("s-1", "SUB-1")]
    repo = FakeEventRepo(subs)
    payload = Payload(
        assignmentId="A1",
        automatic_mode=False,
        lista_assegnazioni=[
            Pair("s-1", "SUB-XXX"),  # non esiste
        ],
    )
    with pytest.raises(DistributionError) as ei:
        await DistributorService.build_verified_assignments(payload, repo)
    assert "non trovata" in str(ei.value)


@pytest.mark.asyncio
async def test_automatic_generates_derangement_all_students_included():
    subs = [Submission("s-1", "SUB-1"), Submission("s-2", "SUB-2"), Submission("s-3", "SUB-3")]
    repo = FakeEventRepo(subs)
    payload = Payload(assignmentId="A1", automatic_mode=True)

    result = await DistributorService.build_verified_assignments(payload, repo)
    # Tutti e soli i reviewer che hanno consegnato
    assert sorted(p.reviewer for p in result) == sorted(s.studentId for s in subs)
    # Nessun self-review
    student_to_sub = {s.studentId: s.submissionId for s in subs}
    for p in result:
        assert p.submissionId != student_to_sub[p.reviewer]


@pytest.mark.asyncio
async def test_automatic_with_single_student_raises():
    subs = [Submission("s-1", "SUB-1")]
    repo = FakeEventRepo(subs)
    payload = Payload(assignmentId="A1", automatic_mode=True)
    with pytest.raises(DistributionError):
        await DistributorService.build_verified_assignments(payload, repo)


@pytest.mark.asyncio
async def test_no_submissions_raises():
    repo = FakeEventRepo([])
    payload = Payload(assignmentId="A1", automatic_mode=True)
    with pytest.raises(DistributionError) as ei:
        await DistributorService.build_verified_assignments(payload, repo)
    assert "Nessuna submission" in str(ei.value)


# ------------------- Regression: mode switch is correct ------------------
@pytest.mark.asyncio
async def test_regression_manual_vs_automatic_branching():
    subs = [Submission("s-1", "SUB-1"), Submission("s-2", "SUB-2")]
    repo = FakeEventRepo(subs)

    # automatico -> ignora lista e genera derangement
    auto_payload = Payload(
        assignmentId="A1",
        automatic_mode=True,
        lista_assegnazioni=[Pair("s-1", "SUB-1"), Pair("s-2", "SUB-2")]  # deve essere ignorata
    )
    auto_res = await DistributorService.build_verified_assignments(auto_payload, repo)
    student_to_sub = {s.studentId: s.submissionId for s in subs}
    assert all(p.submissionId != student_to_sub[p.reviewer] for p in auto_res)

    # manuale -> usa e valida la lista
    man_payload = Payload(
        assignmentId="A1",
        automatic_mode=False,
        lista_assegnazioni=[Pair("s-1", "SUB-2"), Pair("s-2", "SUB-1")]
    )
    man_res = await DistributorService.build_verified_assignments(man_payload, repo)
    assert sorted((p.reviewer, p.submissionId) for p in man_res) == \
           sorted((p.reviewer, p.submissionId) for p in man_payload.lista_assegnazioni)
