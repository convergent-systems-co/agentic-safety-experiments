from __future__ import annotations

import re
import shlex


DEFAULT_SOURCES = {
    "shell": True,
    "git": True,
    "observer_interaction": True,
    "keylogging": False,
    "screenshots": False,
    "screen_recording": False,
    "clipboard": False,
    "microphone": False,
    "camera": False,
    "broad_file_content": False,
    "browser_history": False,
}

_SECRET_PATTERNS = (
    re.compile(
        r"(?i)(--(?:password|passwd|token|api[-_]?key|secret)(?:=|\s+))([^\s]+)"
    ),
    re.compile(
        r"(?i)\b([A-Z][A-Z0-9_]*(?:TOKEN|PASSWORD|SECRET|API_KEY)=)([^\s]+)"
    ),
    re.compile(r"(?i)\b(authorization:\s*(?:bearer|basic)\s+)([^\s]+)"),
)

_SENSITIVE_FACT_TERMS = {
    "password",
    "secret",
    "token",
    "api key",
    "medical",
    "diagnosis",
    "religion",
    "ethnicity",
    "sexual orientation",
    "political affiliation",
    "bank account",
    "credit card",
    "social security",
    "hiv",
    "aids",
    "pregnant",
    "pregnancy",
    "jewish",
    "christian",
    "muslim",
    "disabled",
    "disability",
    "therapy",
    "medication",
    "citizenship",
    "immigration",
    "home address",
    "phone number",
    "passphrase",
    "ssn",
    "social security number",
    "race",
    "racial",
    "gender identity",
    "genetic",
    "biometric",
}

_SAFE_PREFERENCE_VOCABULARY = {
    "a",
    "an",
    "and",
    "answer",
    "answers",
    "brief",
    "response",
    "responses",
    "concise",
    "detailed",
    "technical",
    "explanation",
    "explanations",
    "example",
    "examples",
    "bullet",
    "bullets",
    "point",
    "points",
    "code",
    "python",
    "go",
    "rust",
    "typescript",
    "javascript",
    "format",
    "formatting",
    "style",
    "workflow",
    "workflows",
    "tool",
    "tools",
    "editor",
    "test",
    "tests",
    "documentation",
    "direct",
    "short",
    "long",
    "plain",
    "text",
    "markdown",
    "table",
    "tables",
    "list",
    "lists",
    "step",
    "steps",
    "with",
    "without",
    "in",
    "as",
    "for",
    "to",
    "the",
    "use",
    "using",
    "include",
    "avoid",
    "prefer",
}

_CREDENTIAL_OPTION = re.compile(
    r"(?i)^--?[a-z0-9_-]*(?:password|passwd|secret|token|api[-_]?key|"
    r"credential|authorization|auth)[a-z0-9_-]*"
)

_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
)

_PROFANITY = re.compile(
    r"\b(?:fuck(?:ing|ed)?|shit|damn|bitch|asshole)\b", re.IGNORECASE
)


def redact_command(command: str) -> str:
    redacted = re.sub(
        r"(?i)([a-z][a-z0-9+.-]*://[^/\s:@]+:)([^@/\s]+)(@)",
        r"\1[REDACTED]\3",
        command,
    )
    redacted = re.sub(
        r"(?i)(\s(?:-u|--user|--proxy-user)\s+)"
        r"(?:\"[^\"]*\"|'[^']*'|\S+)",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)((?:authorization|proxy-authorization|x-api-key|"
        r"x-auth-token|cookie|set-cookie)\s*:\s*)([^'\"]+)",
        r"\1[REDACTED]",
        redacted,
    )
    for pattern in _SENSITIVE_VALUE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    try:
        tokens = shlex.split(redacted)
    except ValueError:
        return "[REDACTED: unparseable command]"
    safe: list[str] = []
    redact_next = False
    for token in tokens:
        if redact_next:
            safe.append("[REDACTED]")
            redact_next = False
            continue
        if _CREDENTIAL_OPTION.match(token):
            if "=" in token:
                option, _ = token.split("=", 1)
                safe.append(f"{option}=[REDACTED]")
            elif len(token) > 2 and token.startswith("-p") and not token.startswith("--"):
                safe.append("-p[REDACTED]")
            else:
                safe.append(token)
                redact_next = True
            continue
        if re.match(
            r"(?i)^[A-Z][A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY)=",
            token,
        ):
            key, _ = token.split("=", 1)
            safe.append(f"{key}=[REDACTED]")
            continue
        safe.append(token)
    return shlex.join(safe)


def is_sensitive_user_fact(fact: str) -> bool:
    normalized = fact.casefold()
    return any(term in normalized for term in _SENSITIVE_FACT_TERMS)


def is_allowed_preference(fact: str) -> bool:
    if is_sensitive_user_fact(fact):
        return False
    if not fact.isascii() or not re.fullmatch(r"[A-Za-z0-9_+\- ]+", fact):
        return False
    if len(fact) > 120 or any(character in fact for character in ";\n\r"):
        return False
    if any(pattern.search(fact) for pattern in _SENSITIVE_VALUE_PATTERNS):
        return False
    words = set(re.findall(r"[a-z0-9_+-]+", fact.casefold()))
    return bool(words) and words <= _SAFE_PREFERENCE_VOCABULARY


def sanitize_interaction_text(text: str) -> str:
    if is_sensitive_user_fact(text):
        return "[SENSITIVE CONTENT REDACTED]"
    redacted = re.sub(
        r"(?i)([a-z][a-z0-9+.-]*://[^/\s:@]+:)([^@/\s]+)(@)",
        r"\1[REDACTED]\3",
        text,
    )
    redacted = re.sub(
        r"(?i)(\s(?:-u|--user|--proxy-user)\s+)"
        r"(?:\"[^\"]*\"|'[^']*'|\S+)",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)((?:authorization|proxy-authorization|x-api-key|"
        r"x-auth-token|cookie|set-cookie)\s*:\s*)([^'\"]+)",
        r"\1[REDACTED]",
        redacted,
    )
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    for pattern in _SENSITIVE_VALUE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    redacted = _PROFANITY.sub("[EXPLETIVE]", redacted)
    return redacted


def sanitize_metadata_text(text: str) -> str:
    if not isinstance(text, str):
        raise ValueError("metadata value must be a string")
    if len(text) > 4096:
        raise ValueError("metadata value exceeds 4096 characters")
    redacted = re.sub(
        r"(?i)([a-z][a-z0-9+.-]*://[^/\s:@]+:)([^@/\s]+)(@)",
        r"\1[REDACTED]\3",
        text,
    )
    for pattern in _SECRET_PATTERNS + _SENSITIVE_VALUE_PATTERNS:
        redacted = pattern.sub(
            r"\1[REDACTED]" if pattern in _SECRET_PATTERNS else "[REDACTED]",
            redacted,
        )
    return redacted


def interaction_tone(text: str) -> str:
    normalized = text.casefold()
    if _PROFANITY.search(normalized):
        return "frustrated"
    return "neutral"
