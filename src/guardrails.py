"""Input guardrails for BRD generation system.

MVP content moderation: violence, sexual abuse, hate speech, self-harm.
Length validation. Extensible for Bedrock guardrails later.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class GuardrailViolation:
  """A guardrail violation."""

  rule_name: str
  message: str
  severity: str  # "error" or "warning"


class InputGuardrail:
  """Validates user input against content moderation rules."""

  def __init__(self):
    self.min_query_length = 3
    self.max_query_length = 5000

    # Content moderation patterns (MVP -- will be replaced with Bedrock guardrails)
    self.banned_patterns: List[Tuple[str, str]] = [
      (r"(?i)\b(kill|murder|assassinat|massacre|slaughter)\b.*\b(people|person|human|child)", "Violence"),
      (r"(?i)\b(sexual\s+abuse|rape|molestation|child\s+porn)", "Sexual abuse"),
      (r"(?i)\b(hate\s+speech|racial\s+slur|white\s+supremac|ethnic\s+cleansing)", "Hate speech"),
      (r"(?i)\b(suicide\s+method|how\s+to\s+harm|self[\-\s]harm\s+instruction)", "Self-harm"),
      (r"(?i)\b(bomb\s+making|weapon\s+instruction|explosive\s+recipe)", "Dangerous content"),
    ]

  def validate_input(
    self,
    user_query: str,
    **kwargs,
  ) -> Tuple[bool, List[GuardrailViolation]]:
    """Validate user input.

    Returns:
        Tuple of (is_valid, violations).
    """
    violations: List[GuardrailViolation] = []

    # Empty check
    if not user_query or not user_query.strip():
      violations.append(GuardrailViolation(
        rule_name="required",
        message="Query cannot be empty",
        severity="error",
      ))
      return False, violations

    # Length checks
    if len(user_query) < self.min_query_length:
      violations.append(GuardrailViolation(
        rule_name="min_length",
        message=f"Query must be at least {self.min_query_length} characters",
        severity="error",
      ))

    if len(user_query) > self.max_query_length:
      violations.append(GuardrailViolation(
        rule_name="max_length",
        message=f"Query must not exceed {self.max_query_length} characters",
        severity="error",
      ))

    # Content moderation
    for pattern, category in self.banned_patterns:
      try:
        if re.search(pattern, user_query):
          violations.append(GuardrailViolation(
            rule_name="content_moderation",
            message=f"Content flagged: {category}",
            severity="error",
          ))
      except re.error:
        pass

    is_valid = all(v.severity != "error" for v in violations)
    return is_valid, violations

  def get_violation_summary(self, violations: List[GuardrailViolation]) -> str:
    """Create summary from violations."""
    if not violations:
      return "All guardrails passed."

    errors = sum(1 for v in violations if v.severity == "error")
    warnings = sum(1 for v in violations if v.severity == "warning")
    summary = f"Validation failed: {errors} error(s), {warnings} warning(s)\n"
    for v in violations:
      summary += f"  [{v.severity.upper()}] {v.message}\n"
    return summary


# Singleton
_guardrail_instance: InputGuardrail | None = None


def get_input_guardrail() -> InputGuardrail:
  global _guardrail_instance
  if _guardrail_instance is None:
    _guardrail_instance = InputGuardrail()
  return _guardrail_instance


def reset_input_guardrail() -> None:
  global _guardrail_instance
  _guardrail_instance = None
