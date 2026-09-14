"""Structured error types for Sentinel V1 evidence tool execution.

Contracts v1.2 S12 requires every tool call to fail with a structured error,
never a silent/bare exception -- these types are what the tool layer and the
Evidence Agent loop catch and branch on.
"""

from __future__ import annotations


class ToolError(Exception):
    """Base structured error raised by evidence tool execution."""

    def __init__(self, tool_name: str, message: str) -> None:
        """Initialize with the offending tool name and a human-readable reason.

        :param tool_name: Name of the tool that failed.
        :param message: Human-readable failure reason.
        """
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"[{tool_name}] {message}")


class UnknownToolError(ToolError):
    """Raised when a requested tool name is not in the explicit allow-list."""


class ToolValidationError(ToolError):
    """Raised when tool input arguments fail schema/reference validation."""


class ToolTimeoutError(ToolError):
    """Raised when a tool call exceeds its per-tool timeout budget."""


class ToolExecutionError(ToolError):
    """Raised when a tool call fails for a reason other than validation/timeout."""
