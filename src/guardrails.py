"""Input guardrails for BRD generation system."""

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class GuardrailViolation:
    """Represents a guardrail violation."""

    rule_name: str
    violation_type: str
    message: str
    severity: str  # "error", "warning", "info"


class InputGuardrail:
    """Validates user input and queries against defined guardrails."""

    def __init__(self):
        """Initialize guardrails with default rules."""
        # Default banned words/patterns (user can customize)
        self.banned_patterns: List[Tuple[str, str]] = [
            (r"(?i)drop\s+table", "SQL injection attempt"),
            (r"(?i)delete\s+from", "SQL injection attempt"),
            (r"(?i)<script", "XSS attempt"),
            (r"(?i)javascript:", "XSS attempt"),
        ]

        # Required fields
        self.required_fields = ["user_query"]

        # Min/max lengths
        self.min_query_length = 3
        self.max_query_length = 5000

    def add_banned_pattern(
        self, pattern: str, description: str
    ) -> None:
        """Add a banned pattern to check."""
        self.banned_patterns.append((pattern, description))

    def validate_input(
        self,
        user_query: str,
        golden_brd_content: str = "",
        **kwargs,
    ) -> Tuple[bool, List[GuardrailViolation]]:
        """
        Validate user input against guardrails.

        Args:
            user_query: User's input query
            golden_brd_content: Reference BRD content
            **kwargs: Additional fields to validate

        Returns:
            Tuple of (is_valid, list of violations)
        """
        violations: List[GuardrailViolation] = []

        # Check required fields
        if not user_query or not user_query.strip():
            violations.append(
                GuardrailViolation(
                    rule_name="required_field",
                    violation_type="error",
                    message="user_query is required and cannot be empty",
                    severity="error",
                )
            )

        # Check query length
        if len(user_query) < self.min_query_length:
            violations.append(
                GuardrailViolation(
                    rule_name="min_length",
                    violation_type="error",
                    message=f"user_query must be at least {self.min_query_length} characters",
                    severity="error",
                )
            )

        if len(user_query) > self.max_query_length:
            violations.append(
                GuardrailViolation(
                    rule_name="max_length",
                    violation_type="error",
                    message=f"user_query must not exceed {self.max_query_length} characters",
                    severity="error",
                )
            )

        # Check for banned patterns
        for pattern, description in self.banned_patterns:
            try:
                if re.search(pattern, user_query, re.IGNORECASE):
                    violations.append(
                        GuardrailViolation(
                            rule_name="banned_pattern",
                            violation_type="error",
                            message=f"Query contains banned pattern: {description}",
                            severity="error",
                        )
                    )
            except re.error:
                # Invalid regex pattern
                pass

        # Check for special characters (optional validation)
        if not self._has_valid_characters(user_query):
            violations.append(
                GuardrailViolation(
                    rule_name="invalid_characters",
                    violation_type="warning",
                    message="Query contains unusual special characters",
                    severity="warning",
                )
            )

        is_valid = all(v.severity != "error" for v in violations)
        return is_valid, violations

    def _has_valid_characters(self, text: str) -> bool:
        """Check if text contains mostly valid characters."""
        # Allow alphanumeric, spaces, common punctuation
        valid_pattern = r"^[a-zA-Z0-9\s\.\,\-\_\(\)\[\]\{\}:;!?'\"/@#$%&*+\n\r]+$"
        return bool(re.match(valid_pattern, text))

    def get_violation_summary(
        self, violations: List[GuardrailViolation]
    ) -> str:
        """Create a summary message from violations."""
        if not violations:
            return "All guardrails passed."

        error_count = sum(1 for v in violations if v.severity == "error")
        warning_count = sum(1 for v in violations if v.severity == "warning")

        summary = f"Validation failed: {error_count} errors, {warning_count} warnings\n"
        for v in violations:
            summary += f"  [{v.severity.upper()}] {v.message}\n"

        return summary


# Global guardrail instance
_guardrail_instance: InputGuardrail | None = None


def get_input_guardrail() -> InputGuardrail:
    """Get or create the global input guardrail instance."""
    global _guardrail_instance
    if _guardrail_instance is None:
        _guardrail_instance = InputGuardrail()
    return _guardrail_instance


def reset_input_guardrail() -> None:
    """Reset guardrail instance (useful for testing)."""
    global _guardrail_instance
    _guardrail_instance = None
