import anthropic
import yaml
from pathlib import Path
from typing import Dict
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

client = anthropic.Anthropic()

_engines: Dict[str, Engine] = {}
_config: dict = {}


def _load_config() -> dict:
    global _config
    if not _config:
        config_path = Path(__file__).parent / "connections.yml"
        with open(config_path) as f:
            _config = yaml.safe_load(f)
    return _config


def resolve_connection(name: str | None = None) -> tuple[str, str]:
    """Return (connection_name, db_url) for the given name, or the default."""
    cfg = _load_config()
    name = name or cfg["default"]
    connections = cfg.get("connections", {})
    if name not in connections:
        raise KeyError(f"Unknown connection: '{name}'. Known: {list(connections)}")
    return name, connections[name]["url"]


def get_engine(db_url: str) -> Engine:
    if db_url not in _engines:
        _engines[db_url] = create_engine(db_url)
    return _engines[db_url]


def get_schema(db_url: str) -> str:
    engine = get_engine(db_url)
    with engine.connect() as conn:
        tables = conn.execute(text("SHOW TABLES")).fetchall()
        parts = []
        for (table,) in tables:
            ddl = conn.execute(text(f"SHOW CREATE TABLE `{table}`")).fetchone()[1]
            parts.append(ddl)
        return "\n\n".join(parts)


def run_query(sql: str, db_url: str) -> list[dict]:
    engine = get_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]


def ask(question, schema, history, db_url):
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
        messages=[{"role": "user", "content": question}],
    )
    sql = sql_response.content[0].text.strip()
    print(f"\n  SQL: {sql}")

    rows = run_query(sql, db_url)

    messages = history + [
        {
            "role": "user",
            "content": f"Question: {question}\nSQL result: {rows}",
        }
    ]
    answer_response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=512,
        system="You are a data analyst. Given a user question and its SQL query result, answer clearly and concisely in plain English. Do not include SQL in your response.",
        messages=messages,
    )
    return answer_response.content[0].text, rows


def main():
    print("Connecting to database...")
    _, db_url = resolve_connection()
    schema = get_schema(db_url)
    print("Ready. Ask anything about your database, or type 'exit' to quit.\n")

    history = []

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question or question.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        answer, rows = ask(question, schema, history, db_url)
        print(f"\nAssistant: {answer}\n")

        history.append({
            "role": "user",
            "content": f"Question: {question}\nSQL result: {rows}",
        })
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
