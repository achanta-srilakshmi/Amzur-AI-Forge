"""Test script to debug NL-to-SQL agent creation."""
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.utilities import SQLDatabase
from app.ai.llm import llm
from app.ai.chains.nl_to_sql_chain import _build_sync_db_url

print("Creating SQLDatabase...")
sql_database = SQLDatabase.from_uri(
    _build_sync_db_url(),
    include_tables=['users', 'threads', 'messages'],
)
print("✓ Database created successfully")
print(f"  Tables: {sql_database.get_usable_table_names()}")

print("\nCreating SQL agent with unbound LLM...")
try:
    sql_agent = create_sql_agent(
        llm=llm,
        db=sql_database,
        agent_type='zero-shot-react-description',
        verbose=True,
        return_intermediate_steps=True,
    )
    print("✓ Agent created successfully!")
    print(f"  Agent type: {type(sql_agent)}")
    
    print("\nTesting agent invocation...")
    result = sql_agent.invoke(
        {"input": "How many users are there?"},
        config={"metadata": {"user_email": "test@amzur.com"}},
    )
    print("✓ Agent invocation successful!")
    print(f"  Output: {result['output']}")
    if result.get('intermediate_steps'):
        print(f"  Generated SQL: {result['intermediate_steps']}")
except Exception as e:
    import traceback
    print(f"✗ ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()


