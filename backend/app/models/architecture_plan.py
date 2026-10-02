"""ArchitecturePlan: the deterministic result of architecture inference.

This is the contract between the InferenceEngine and the Scaffolder. It is data,
not prose: the scaffolder consumes it to choose an archetype / CLI template and
a module layout, so the LLM never decides structure.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ArchitecturePlan(BaseModel):
    profile: str = Field(..., description="layered | hexagonal | hexagonal-ddd")
    buildTool: str = Field(..., description="maven | gradle")
    databaseType: str = Field(..., description="postgresql | mysql | h2")
    modules: List[str] = Field(..., description="Module/layer list in dependency order")
    libraries: List[str] = Field(default_factory=list, description="Inferred libraries")
    reasons: List[str] = Field(default_factory=list, description="Human-readable justifications")
