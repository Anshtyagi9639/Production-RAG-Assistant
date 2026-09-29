from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum


class WorkspaceRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class AgentRunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def string_enum(enum_class: type[StrEnum]) -> Enum:
    """VARCHAR column mapped to a Python enum; the allowed values are enforced by `in_check`."""
    return Enum(
        enum_class,
        native_enum=False,
        create_constraint=False,
        length=20,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


def in_check(column: str, enum_class: type[StrEnum]) -> CheckConstraint:
    """CHECK constraint named by the metadata convention: ck_<table>_<column>."""
    values = ", ".join(f"'{member.value}'" for member in enum_class)
    return CheckConstraint(f"{column} IN ({values})", name=column)
