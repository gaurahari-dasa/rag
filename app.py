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


def ask(question):
    schema = get_schema()

    # Step 1: generate SQL from the question
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
    print(f"Generated SQL: {sql}\n")

    # Step 2: execute the SQL
    rows = run_query(sql)

    # Step 3: turn the raw result into a natural language answer
    answer_response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": f"Question: {question}\nSQL result: {rows}\nAnswer concisely:",
            }
        ],
    )
    return answer_response.content[0].text


print(ask("How many contacts are there?"))
