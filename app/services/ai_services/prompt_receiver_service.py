"""Prompt receiver: persist raw prompts; optional SVG interpretation stub.

``user_prompt``
    Inserts a ``PromptReceiver`` row from ``PromptReceiverBase``—useful for
    logging or non–drawing-stage AI experiments.

``interpret_svg_prompt``
    **Incomplete / not wired:** intended to call an LLM with an element catalog
    and parse JSON. Currently references undefined ``element_catalog`` and
    should not be called from production code until finished.
"""

from __future__ import annotations

import json
import os
import re

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_models.prompt_receiver import PromptReceiver
from app.schemas.ai_schemas.prompt_receiver_schema import PromptReceiverBase

api_key = os.getenv("OPENAI_API_KEY")


# =============================================================================
# 1. Prompt persistence
# =============================================================================


async def user_prompt(db: AsyncSession, data: PromptReceiverBase):
    """Create and return a ``PromptReceiver`` record (simple DB insert)."""
    prompt_data = data.model_dump()
    new_prompt = PromptReceiver(**prompt_data)
    db.add(new_prompt)
    await db.commit()
    await db.refresh(new_prompt)
    return new_prompt


# =============================================================================
# 2. Experimental / WIP (LangChain SVG stub — not production-ready)
# =============================================================================


async def interpret_svg_prompt(prompt: str):
    """[WIP] Intended to produce SVG-oriented JSON from a user string.

    ``element_catalog`` is a stub until you inject real template definitions.
    """
    element_catalog = "(define element_catalog before using this in production)"

    template = PromptTemplate.from_template(
        """
    You are an SVG generator AI.

    Use the available SVG element templates provided below to construct
    a meaningful composition based on the user's prompt.

                                            """
    )

    final_prompt = template.format(
        user_prompt=prompt,
        element_catalog=element_catalog,
    )

    llm = ChatOpenAI(
        temperature=0.3,
        model="gpt-4o",
        api_key=api_key,
    )

    response = llm.invoke(final_prompt)
    raw = response.content.strip()

    clean_json = re.sub(r"^```(?:json)?\s*|```$", "", raw, flags=re.IGNORECASE | re.MULTILINE)

    try:
        result = json.loads(clean_json)
    except Exception as e:
        print("JSON parse error", e)
        result = []

    return result
