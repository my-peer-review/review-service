from fastapi import Request
from app.database.review_repo import ReviewRepo
from app.database.event_repo import SubmissionEventRepo
from app.services.publisher_service import ReviewPublisher

def get_repository(request: Request) -> ReviewRepo:
    repo = getattr(request.app.state, "review_repo", None)
    if repo is None:
        raise RuntimeError("Repository Review non inizializzato")
    return repo

def get_event_repository(request: Request) -> SubmissionEventRepo:
    repo = getattr(request.app.state, "event_repo", None)
    if repo is None:
        raise RuntimeError("Repository Events non inizializzato")
    return repo

def get_publisher(request: Request) -> ReviewPublisher:
    publisher = getattr(request.app.state, "review_publisher", None)
    if publisher is None:
        raise RuntimeError("Publiscer non inizializzato")
    return publisher