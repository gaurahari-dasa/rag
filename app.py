import anthropic
from sqlalchemy import create_engine, text

engine = create_engine("mysql+pymysql://root@localhost/local_krishna_life")
client = anthropic.Anthropic()


def get_schema():
    with engine.connect() as conn:
        tables = conn.execute(text("SHOW TABLES")).fetchall()
        parts = []
        for (table,) in tables:
            ddl = conn.execute(text(f"SHOW CREATE TABLE `{table}`")).fetchone()[1]
            parts.append(ddl)
        return "\n\n".join(parts)


def run_query(sql):
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        return [dict(zip(columns, row)) for row in result.fetchall()]


def ask(question, schema, history):
    # Step 1: generate SQL — schema is cached after the first call
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

    # Step 2: execute the SQL
    rows = run_query(sql)

    # Step 3: answer using conversation history for follow-up context
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
    schema = get_schema()
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

        answer, rows = ask(question, schema, history)
        print(f"\nAssistant: {answer}\n")

        # Keep history so follow-up questions have context
        history.append({
            "role": "user",
            "content": f"Question: {question}\nSQL result: {rows}",
        })
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
