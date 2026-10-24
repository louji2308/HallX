"""Frozen prompt payload models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PromptPayload(StrictModel):
    system_prompt: str
    user_prompt: str
    response_schema: dict
