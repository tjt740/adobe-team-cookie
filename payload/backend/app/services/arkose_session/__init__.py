"""Same-session Arkose for invited-account completion.

gt2 is harvested in a real page (Playwright, not Cloak pool). Images are
classified with YesCaptcha FunCaptchaClassification. Answers go back to
the same /fc/ca/ session. FunCaptchaTask widget tokens are not used.
"""

from app.services.arkose_session.classify import ClassifyError, UnknownQuestion
from app.services.arkose_session.harvest import HarvestError, HarvestSeed, NavigationFailed
from app.services.arkose_session.solver import (
    SessionResult,
    SessionSolveError,
    is_navigation_failed,
    is_unknown_question,
    not_retryable,
    solve_session,
)

__all__ = [
    "ClassifyError",
    "HarvestError",
    "HarvestSeed",
    "NavigationFailed",
    "SessionResult",
    "SessionSolveError",
    "UnknownQuestion",
    "is_navigation_failed",
    "is_unknown_question",
    "not_retryable",
    "solve_session",
]
