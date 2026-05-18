"""Service layer for natural language to SQL queries."""

from fastapi import HTTPException, status
from openai import OpenAIError

from app.ai.chains.nl_to_sql_chain import run_nl_to_sql_agent
from app.models.user import User


async def run_nl_query(question: str, current_user: User) -> dict[str, str]:
    try:
        return run_nl_to_sql_agent(question, current_user.email)
    except HTTPException:
        raise
    except OpenAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "llm_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "unexpected", "message": str(exc)},
        ) from exc