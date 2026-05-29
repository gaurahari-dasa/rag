from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import uuid
import anthropic
from app import get_schema, run_query

app = FastAPI()
client = anthropic.Anthropic()

_schema: Optional[str] = None
_sessions: Dict[str, list] = {}  # session_id -> conversation history


@app.on_event("startup")
def startup() -> None:
    global _schema
    _schema = get_schema()


class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    sql: str
    rows: List[Dict[str, Any]]
    session_id: str


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    session_id = req.session_id or str(uuid.uuid4())
    history = _sessions.get(session_id, [])

    sql_response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": (
                    "You are a MySQL expert. Given a database schema and a question, "
                    "return ONLY a valid SQL query — no explanation, no markdown fences.\n\n"
                    f"Schema:\n{_schema}"
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": req.question}],
    )
    sql = sql_response.content[0].text.strip()

    try:
        rows = run_query(sql)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"SQL execution failed: {exc}")

    messages = history + [
        {"role": "user", "content": f"Question: {req.question}\nSQL result: {rows}"}
    ]
    answer_response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=512,
        system=(
            "You are a data analyst. Given a user question and its SQL query result, "
            "answer clearly and concisely in plain English. Do not include SQL in your response."
        ),
        messages=messages,
    )
    answer = answer_response.content[0].text

    _sessions[session_id] = messages + [{"role": "assistant", "content": answer}]

    return AskResponse(answer=answer, sql=sql, rows=rows, session_id=session_id)


@app.delete("/session/{session_id}")
def clear_session(session_id: str) -> Dict[str, str]:
    _sessions.pop(session_id, None)
    return {"cleared": session_id}
