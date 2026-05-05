from __future__ import annotations

import re
import unicodedata

from app.models.entities import Course

TRAILING_PARENTHETICAL_RE = re.compile(r"\s*\([^()]*\)\s*$")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
CLASS_SUFFIX_RE = re.compile(r"^[a-z]{1,3}\d+[a-z]?$")
SUFFIX_EQUIVALENT_NAME_KEYS = {"trabalho-de-conclusao-de-curso"}


def normalize_context_key(context_key: str | None) -> str | None:
    normalized = (context_key or "").strip().lower()
    return normalized or None


def canonical_context_key(context_key: str | None) -> str | None:
    normalized = normalize_context_key(context_key)
    if not normalized:
        return None
    parts = normalized.split(":")
    if len(parts) > 1 and CLASS_SUFFIX_RE.fullmatch(parts[-1]):
        return ":".join(parts[:-1])
    return normalized


def academic_context_key(course: Course) -> str | None:
    context_key = normalize_context_key(course.context_key)
    name_key = normalized_course_name_key(course.name)
    if name_key in SUFFIX_EQUIVALENT_NAME_KEYS:
        return canonical_context_key(context_key)
    return context_key


def course_base_name(name: str) -> str:
    base_name = name.strip()
    while True:
        next_name = TRAILING_PARENTHETICAL_RE.sub("", base_name).strip()
        if next_name == base_name:
            return base_name
        base_name = next_name


def normalized_course_name_key(name: str | None) -> str | None:
    if not name:
        return None
    without_suffix = course_base_name(name)
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", without_suffix)
        if not unicodedata.combining(char)
    )
    normalized = NON_ALNUM_RE.sub("-", without_accents.lower()).strip("-")
    return normalized or None


def academic_group_identity(course: Course, theoretical_hours: int | None = None) -> tuple[str, ...] | None:
    context_key = academic_context_key(course)
    name_key = normalized_course_name_key(course.name)
    identity_key = context_key or name_key
    if not course.shareable or not identity_key:
        return None
    return (
        "academic",
        identity_key,
        course.campus_id or "any-campus",
        str(course.workload_hours),
        str(theoretical_hours if theoretical_hours is not None else course.theoretical_hours or 0),
        str(course.practical_hours or 0),
        str(course.requires_lab),
        course.kind.value,
    )
