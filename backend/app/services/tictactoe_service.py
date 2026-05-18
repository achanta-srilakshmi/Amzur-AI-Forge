"""Tic Tac Toe game service powered by LiteLLM move selection."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from fastapi import HTTPException, status
from openai import OpenAIError

from app.ai.llm import openai_client
from app.core.config import settings
from app.models.user import User
from app.schemas.tictactoe import TicTacToeHistoryItem, TicTacToeMoveRequest, TicTacToeMoveResponse

_ALLOWED_MARKS = {"", "X", "O"}
_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)


def check_winner(board: list[str]) -> str | None:
    for a, b, c in _LINES:
        token = board[a]
        if token and token == board[b] == board[c]:
            return token

    if all(cell in {"X", "O"} for cell in board):
        return "draw"

    return None


def _validate_board(board: list[str]) -> list[str]:
    if len(board) != 9:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_board", "message": "board must contain exactly 9 cells"},
        )

    normalized: list[str] = []
    for cell in board:
        value = cell.strip().upper() if isinstance(cell, str) else ""
        if value not in _ALLOWED_MARKS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "invalid_board", "message": "board cells must be '', 'X', or 'O'"},
            )
        normalized.append(value)

    return normalized


def _normalize_history(history: list[TicTacToeHistoryItem]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in history:
        player = item.player.strip().upper()
        if player not in {"X", "O"}:
            continue
        normalized.append(
            {
                "player": player,
                "cell": int(item.cell),
                "message": str(item.message or "").strip(),
            }
        )
    return normalized


def _board_as_text(board: list[str]) -> str:
    def display(i: int) -> str:
        return board[i] if board[i] in {"X", "O"} else str(i + 1)

    rows = [
        f" {display(0)} | {display(1)} | {display(2)} ",
        f" {display(3)} | {display(4)} | {display(5)} ",
        f" {display(6)} | {display(7)} | {display(8)} ",
    ]
    return "\n-----------\n".join(rows)


def _extract_json(raw: str) -> dict[str, Any]:
    try:
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return {}

    try:
        loaded = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}

    return loaded if isinstance(loaded, dict) else {}


async def _call_move_llm(
    board: list[str],
    history: list[dict[str, Any]],
    current_user: User,
    retry_feedback: str | None = None,
) -> dict[str, Any]:
    available = [idx + 1 for idx, cell in enumerate(board) if cell == ""]
    winner_now = check_winner(board)

    history_text = "\n".join(
        f"- {entry['player']} played cell {entry['cell']}"
        + (f" | message: {entry['message']}" if entry.get("message") else "")
        for entry in history
    )
    if not history_text:
        history_text = "- No previous moves"

    system_prompt = (
        "You are O in a Tic Tac Toe game against a human user (X). "
        "You are competitive, playful, and witty. You taunt lightly but stay safe and non-abusive. "
        "Strategy order: 1) win immediately if possible, 2) if not possible block X immediate win, "
        "3) otherwise pick the strongest available tactical move. "
        "Never choose an occupied cell. "
        "Adapt your tone to the game phase: opening=cocky, blocking='Nice try...', "
        "about-to-win=excited/taunting, lost=gracious with revenge promise, draw=respectful. "
        "You must also evaluate game state (X/O/draw/none) from the board. "
        "Return JSON only."
    )

    user_prompt = (
        "Game state for your move.\n"
        f"Board grid:\n{_board_as_text(board)}\n\n"
        f"Raw board array: {json.dumps(board, ensure_ascii=True)}\n"
        f"Move history:\n{history_text}\n\n"
        f"Available cells: {available}\n"
        f"Current evaluated winner before your move: {winner_now}\n"
        "Respond with strict JSON object keys:\n"
        "- chosen_cell: integer 1-9\n"
        "- message: short natural playful comment\n"
        "- game_state: 'X' | 'O' | 'draw' | null\n"
        "No markdown, no code fences, no extra keys."
    )

    if retry_feedback:
        user_prompt += f"\n\nCorrection from last attempt: {retry_feedback}"

    def _run_completion() -> dict[str, Any]:
        completion = openai_client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
            user=current_user.email,
            extra_body={
                "metadata": {
                    "application": settings.APP_NAME,
                    "environment": settings.ENVIRONMENT,
                }
            },
        )

        content = ""
        if completion.choices and completion.choices[0].message.content:
            content = completion.choices[0].message.content

        return _extract_json(content)

    return await asyncio.to_thread(_run_completion)


async def get_llm_move(board: list[str], history: list[dict[str, Any]], current_user: User) -> dict[str, Any]:
    available = {idx + 1 for idx, cell in enumerate(board) if cell == ""}

    retry_feedback: str | None = None
    for _ in range(2):
        parsed = await _call_move_llm(board, history, current_user, retry_feedback=retry_feedback)

        chosen = parsed.get("chosen_cell")
        message = str(parsed.get("message") or "Your move was sharp. Let's see if you can handle this.").strip()

        try:
            cell = int(chosen)
        except (TypeError, ValueError):
            retry_feedback = "chosen_cell was not a valid integer 1-9. Return valid JSON only."
            continue

        if cell not in available:
            retry_feedback = (
                f"chosen_cell {cell} is invalid or occupied. "
                f"Only choose one of available cells: {sorted(available)}."
            )
            continue

        return {"cell": cell, "message": message}

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"error": "tictactoe_llm_invalid", "message": "LLM returned invalid move twice"},
    )


async def process_tictactoe_move(payload: TicTacToeMoveRequest, current_user: User) -> TicTacToeMoveResponse:
    try:
        board = _validate_board(payload.board)
        history = _normalize_history(payload.history)

        user_cell = int(payload.user_move)
        if board[user_cell - 1] not in {"", "X"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "invalid_user_move", "message": "user_move points to an occupied O cell"},
            )

        board[user_cell - 1] = "X"

        if not history or history[-1].get("player") != "X" or int(history[-1].get("cell", -1)) != user_cell:
            history.append({"player": "X", "cell": user_cell, "message": f"I played cell {user_cell}"})

        winner = check_winner(board)
        if winner is not None:
            end_message = (
                "You got this round. Respect. I'll be back stronger."
                if winner == "X"
                else "Solid deadlock. Respect for the draw."
            )
            return TicTacToeMoveResponse(
                board=board,
                ai_cell=None,
                ai_message=end_message,
                winner=winner,
                history=[TicTacToeHistoryItem(**entry) for entry in history],
            )

        llm_move = await get_llm_move(board, history, current_user)
        ai_cell = int(llm_move["cell"])
        ai_message = str(llm_move["message"]).strip() or "I made my move. Your turn."

        board[ai_cell - 1] = "O"
        history.append({"player": "O", "cell": ai_cell, "message": ai_message})

        winner = check_winner(board)

        return TicTacToeMoveResponse(
            board=board,
            ai_cell=ai_cell,
            ai_message=ai_message,
            winner=winner,
            history=[TicTacToeHistoryItem(**entry) for entry in history],
        )
    except OpenAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "llm_error", "message": str(exc)},
        ) from exc
