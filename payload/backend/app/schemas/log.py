from pydantic import BaseModel


class LogItem(BaseModel):
    id: int
    time: str
    ts: float
    level: str
    source: str
    message: str
    traceback: str = ""


class LogListOut(BaseModel):
    items: list[LogItem] = []
    total: int = 0
