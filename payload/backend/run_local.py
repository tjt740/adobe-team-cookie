"""Serve the API and the prebuilt web UI together for local development."""

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from app.main import app


class FrontendFiles(StaticFiles):
    @staticmethod
    def index_file(scope):
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        return "index-okad.html" if headers.get("x-forwarded-prefix") == "/okad" else "index.html"

    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            # Vue routes use browser history; missing assets and API paths stay 404.
            if exc.status_code != 404 or path == "api" or path.startswith("api/") or Path(path).suffix:
                raise
            response = await super().get_response(self.index_file(scope), scope)
        response.headers["Cache-Control"] = "no-store"
        return response


app.mount(
    "/",
    FrontendFiles(directory=Path(__file__).resolve().parent.parent / "frontend-v2", html=True),
    name="local-frontend",
)
