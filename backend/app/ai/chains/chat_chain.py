"""
LCEL chat chain — prompt | llm | str_parser.
Prompt template is read from /ai/prompts/chat_system.txt.
"""
from datetime import date
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.ai.llm import llm

_SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "chat_system.txt"
_base_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
_system_prompt = (
    f"{_base_prompt}\n\n"
    f"Today's date is {date.today().strftime('%B %d, %Y')}. "
    "If a question involves recent events or information that may have changed after your training cutoff, "
    "clearly state that your knowledge has a cutoff date and the information may be outdated."
)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", _system_prompt),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{human_input}"),
    ]
)

chat_chain = prompt | llm | StrOutputParser()
