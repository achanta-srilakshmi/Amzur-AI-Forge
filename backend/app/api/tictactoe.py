"""Tic Tac Toe API routes."""

from fastapi import APIRouter, Depends

from app.models.user import User
from app.schemas.tictactoe import TicTacToeMoveRequest, TicTacToeMoveResponse
from app.services.auth_service import get_current_user
from app.services.tictactoe_service import process_tictactoe_move

router = APIRouter()


@router.post("/move", response_model=TicTacToeMoveResponse)
async def make_tictactoe_move(
    payload: TicTacToeMoveRequest,
    current_user: User = Depends(get_current_user),
) -> TicTacToeMoveResponse:
    return await process_tictactoe_move(payload, current_user)
