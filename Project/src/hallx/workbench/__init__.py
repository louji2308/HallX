"""Fixture-backed, loopback-only reviewer workbench shell (P5 batch 1)."""

from hallx.workbench.app import PageResponse, WorkbenchApp, serve
from hallx.workbench.state import (
    FIXTURE_BADGE,
    FIXTURE_BANNER,
    OFFSET_WARNING,
    UNSUPPORTED_MAP_LABEL,
    WorkbenchState,
    build_fixture_state,
)

__all__ = [
    "FIXTURE_BADGE",
    "FIXTURE_BANNER",
    "OFFSET_WARNING",
    "UNSUPPORTED_MAP_LABEL",
    "PageResponse",
    "WorkbenchApp",
    "WorkbenchState",
    "build_fixture_state",
    "serve",
]
