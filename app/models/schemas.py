"""Validated contracts for model responses."""
from pydantic import BaseModel, Field


class GroundedAnswer(BaseModel):
    answer: str = Field(min_length=1, description="Jawaban dari konteks, tanpa ID sitasi inline.")
    citations: list[str] = Field(description="ID chunk pendukung, hanya dari konteks.")
