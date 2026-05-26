import re
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.models.user import User

GITHUB_PR_URL_PATTERN = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)/?$")


def _build_n8n_webhook_candidates(url: str) -> list[str]:
    """Generate likely n8n webhook URL variants for common copy/paste mistakes."""
    parts = urlsplit(url)
    base_path = parts.path.rstrip("/")
    candidates: list[str] = []

    def add_candidate(path: str) -> None:
        candidate = urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
        if candidate not in candidates:
            candidates.append(candidate)

    add_candidate(base_path)

    if base_path.endswith("/webhook"):
        add_candidate(base_path[:-len("/webhook")])

    if "/webhook-test/" in base_path:
        add_candidate(base_path.replace("/webhook-test/", "/webhook/", 1))
        if base_path.endswith("/webhook"):
            stripped = base_path[:-len("/webhook")]
            add_candidate(stripped)
            add_candidate(stripped.replace("/webhook-test/", "/webhook/", 1))
    elif "/webhook/" in base_path:
        add_candidate(base_path.replace("/webhook/", "/webhook-test/", 1))

    return candidates


async def trigger_pr_review(github_pr_url: str, current_user: User) -> dict[str, str]:
    """Trigger the n8n smart PR review workflow for a GitHub pull request URL."""
    match = GITHUB_PR_URL_PATTERN.match(github_pr_url.strip())
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid GitHub PR URL in the format https://github.com/{owner}/{repo}/pull/{number}",
        )

    if not settings.N8N_WEBHOOK_URL:
        raise HTTPException(status_code=503, detail="n8n webhook not configured")

    owner, repo, pull_number = match.groups()
    payload = {
        "pr_url": github_pr_url,
        "owner": owner,
        "repo": repo,
        "pull_number": int(pull_number),
        "triggered_by": current_user.email,
    }

    headers = {"Content-Type": "application/json"}

    webhook_url = settings.N8N_WEBHOOK_URL
    webhook_candidates = _build_n8n_webhook_candidates(webhook_url)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response: httpx.Response | None = None
            attempts: list[tuple[str, int]] = []
            for candidate_url in webhook_candidates:
                response = await client.post(
                    candidate_url,
                    json=payload,
                    headers=headers,
                )
                attempts.append((candidate_url, response.status_code))

                # Keep probing variants only when the endpoint is not found.
                if response.status_code != 404:
                    break

            if response is None:
                raise HTTPException(status_code=502, detail="Failed to trigger n8n workflow: no webhook URL candidates")

            if response.status_code == 404:
                attempts_text = ", ".join(f"{url} ({status})" for url, status in attempts)
                raise HTTPException(
                    status_code=502,
                    detail=(
                        "Failed to trigger n8n workflow: webhook endpoint not found (404). "
                        "This is typically an n8n workflow/webhook configuration issue (wrong URL, wrong webhook type, "
                        "or workflow not active). Tried: "
                        f"{attempts_text}"
                    ),
                )

            if response.status_code == 401:
                raise HTTPException(
                    status_code=502,
                    detail="Failed to trigger n8n workflow: webhook returned 401 Unauthorized. Verify webhook authentication settings in n8n.",
                )

            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to trigger n8n workflow: {exc}") from exc

    return {
        "status": "triggered",
        "pr_url": github_pr_url,
        "message": "PR review started",
    }
