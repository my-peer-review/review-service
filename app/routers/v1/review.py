from __future__ import annotations
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.core.deps import get_repository, get_event_repository
from app.schemas.context import UserContext
from app.schemas.review import ReviewProcessCreate, Review, ReviewUpdate
from app.database.review_repo import ReviewRepo
from app.database.event_repo import SubmissionEventRepo
from app.services.auth_service import AuthService
from app.services.review_service import ReviewService
from app.services.distributor_service import DistributorService
from app.services.distributor_service import DistributionError

router = APIRouter()

RepoDep = Annotated[ReviewRepo, Depends(get_repository)]
EventRepository = Annotated[SubmissionEventRepo, Depends(get_event_repository)]
UserDep = Annotated[UserContext, Depends(AuthService.get_current_user)]

@router.post("/reviews/process", status_code=status.HTTP_201_CREATED)
async def start_review_process(payload: ReviewProcessCreate, user: UserDep, repo: RepoDep, event_repo: EventRepository):
    try:
        # 1) Costruisci la lista verificata (manuale/automatica)
        verified_list = await DistributorService.build_verified_assignments(payload, event_repo)

        # 2) Passa SOLO la lista validata al servizio di review
        process_id = await ReviewService.start_process(
            data=ReviewProcessCreate(
                assignmentId=payload.assignmentId,
                deadline=payload.deadline,
                automatic_mode=payload.automatic_mode,
                lista_assegnazioni=verified_list,
                rubrica=payload.rubrica,
            ),
            user=user,
            repo=repo,
        )
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"message": "Review process avviato per assignment", "id": process_id},
        )
    except DistributionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/reviews", response_model=list[Review])
async def list_my_reviews(
        user: UserDep, 
        repo: RepoDep, 
        stato: Literal["pending", "complete"] | None = Query(None)
    ):
        try:
            return await ReviewService.list_my_reviews(user, repo, stato)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))


@router.get("/reviews/{review_id}", response_model=Review | None)
async def get_my_review(review_id: str, user: UserDep, repo: RepoDep):
    try:
        res = await ReviewService.get_my_review(user, repo, review_id)
        print(f"Retrieved review: {res}")
        if not res:
            raise HTTPException(status_code=404, detail="Review non trovata")
        return res
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.patch("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def submit_review(review_id: str, payload: ReviewUpdate, user: UserDep, repo: RepoDep):
    try:
        ok = await ReviewService.submit_review(user, repo, review_id, payload)
        if not ok:
            raise HTTPException(status_code=404, detail="Review non trovata o non accessibile")
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/reviews/assignment/{assignment_id}/", response_model=list[Review])
async def list_reviews_for_assignment(
    assignment_id: str,
    user: UserContext = Depends(AuthService.get_current_user),
    repo: ReviewRepo = Depends(get_repository),
):
    try:
        res = await ReviewService.list_by_assignment_for_teacher(user, repo, assignment_id)
        if not res:  # <- True se [], alza 404
            raise HTTPException(status_code=404, detail="Nessuna review per questo assignment")
        return res
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
