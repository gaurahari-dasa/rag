from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import uuid
import tempfile
import os
import anthropic
import whisper
from app import get_schema, run_query, resolve_connection

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_whisper_model = whisper.load_model("base")
client = anthropic.Anthropic()

_schemas: Dict[str, str] = {}                    # connection_name -> schema DDL
_sessions: Dict[str, tuple[str, list]] = {}      # session_id -> (conn_name, history)


def _get_schema(conn_name: str, db_url: str) -> str:
    if conn_name not in _schemas:
        _schemas[conn_name] = get_schema(db_url)
    return _schemas[conn_name]


class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    connection: Optional[str] = None    # named connection from connections.yml


class AskResponse(BaseModel):
    answer: str
    sql: str
    rows: List[Dict[str, Any]]
    session_id: str
    connection: str


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    try:
        conn_name, db_url = resolve_connection(req.connection)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    session_id = req.session_id or str(uuid.uuid4())
    session_conn_name, history = _sessions.get(session_id, (conn_name, []))

    # Lock a session to its first connection so cross-DB mixing is caught early.
    if session_conn_name != conn_name:
        raise HTTPException(
            status_code=400,
            detail="Session was started with a different connection."
        )

    schema = _get_schema(conn_name, db_url)

    sql_response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": (
                    "You are a MySQL expert. Given a database schema and a question, "
                    "return ONLY a valid SQL query — no explanation, no markdown fences.\n\n"
                    f"Schema:\n{schema}"
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": req.question}],
    )
    sql = sql_response.content[0].text.strip()

    try:
        rows = run_query(sql, db_url)
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

    _sessions[session_id] = (conn_name, messages + [{"role": "assistant", "content": answer}])

    return AskResponse(answer=answer, sql=sql, rows=rows, session_id=session_id, connection=conn_name)


@app.delete("/session/{session_id}")
def clear_session(session_id: str) -> Dict[str, str]:
    _sessions.pop(session_id, None)
    return {"cleared": session_id}


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    suffix = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    try:
        result = _whisper_model.transcribe(tmp_path)
    finally:
        os.unlink(tmp_path)
    return {"text": result["text"].strip()}
