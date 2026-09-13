from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query

from vocab_bot.webapi.deps import ApiError, CurrentUser, ReviewServiceDep
from vocab_bot.webapi.schemas import GradeRequest, GradeResponse, QueueCard, QueueResponse

router = APIRouter()


@router.get("/reviews/queue", response_model=QueueResponse)
async def get_queue(
    user: CurrentUser,
    review_service: ReviewServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    first: Annotated[int | None, Query(ge=1)] = None,
) -> QueueResponse:
    due = await review_service.list_due_cards_for_user(user_id=user.telegram_id, limit=limit, first_card_id=first)
    total_due = await review_service.count_due_for_user(user_id=user.telegram_id)
    return QueueResponse(cards=[QueueCard.from_due(item) for item in due], total_due=total_due)


@router.post("/reviews/{card_id}/grade", response_model=GradeResponse)
async def grade_card(
    card_id: Annotated[int, Path(ge=1)],
    body: GradeRequest,
    user: CurrentUser,
    review_service: ReviewServiceDep,
) -> GradeResponse:
    result = await review_service.apply_grade(card_id=card_id, user_id=user.telegram_id, quality=body.quality)
    if result is None:
        raise ApiError(404, "card_not_found", "card not found")
    return GradeResponse.from_result(card_id, result)
