from fastapi import Request
from app.database.review_repo import ReviewRepo

def get_repository(request: Request) -> ReviewRepo:
    repo = getattr(request.app.state, "review_repo", None)
    if repo is None:
        raise RuntimeError("Repository non inizializzato")
    return repo