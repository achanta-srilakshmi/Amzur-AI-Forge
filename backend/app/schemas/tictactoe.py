"""Schemas for Tic Tac Toe move API."""

from pydantic import BaseModel, Field


class TicTacToeHistoryItem(BaseModel):
    player: str = Field(..., min_length=1, max_length=1, description="X or O")
    cell: int = Field(..., ge=1, le=9)
    message: str = Field(default="", description="Optional move message")


class TicTacToeMoveRequest(BaseModel):
    board: list[str] = Field(..., min_length=9, max_length=9)
    history: list[TicTacToeHistoryItem] = Field(default_factory=list)
    user_move: int = Field(..., ge=1, le=9)


class TicTacToeMoveResponse(BaseModel):
    board: list[str] = Field(..., min_length=9, max_length=9)
    ai_cell: int | None = Field(default=None, ge=1, le=9)
    ai_message: str
    winner: str | None
    history: list[TicTacToeHistoryItem]
