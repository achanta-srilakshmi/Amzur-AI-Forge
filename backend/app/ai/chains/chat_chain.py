"""
LCEL chat chain — prompt | llm | str_parser.
Prompt template is read from /ai/prompts/chat_system.txt.
"""
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.ai.llm import llm

_SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "chat_system.txt"
_system_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", _system_prompt),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{human_input}"),
    ]
)

chat_chain = prompt | llm | StrOutputParser()
