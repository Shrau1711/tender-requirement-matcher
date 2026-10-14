from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.routes import known_run
from app.db.reviews import Decision, Review

router = APIRouter()


class Decisions(BaseModel):
    items: list[Decision] = Field(max_length=2000)


@router.get("/runs/{run_id}/reviews")
def list_reviews(request: Request, run_id: str) -> list[Review]:
    """What people decided about this run's rows."""
    known_run(request, run_id)
    return request.app.state.reviews.all(run_id)


@router.put("/runs/{run_id}/reviews")
def save_reviews(request: Request, run_id: str, body: Decisions) -> list[Review]:
    """Record decisions (confirm a row, or say what its status should be). A decision of null clears it. Scores are not changed."""
    known_run(request, run_id)
    request.app.state.reviews.save(run_id, body.items)
    return request.app.state.reviews.all(run_id)
