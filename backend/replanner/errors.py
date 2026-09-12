"""Public, sanitized errors raised by the Backend B boundary."""


class ReplannerError(RuntimeError):
    """Base class for recoverable replanner failures."""


class PlanningProviderError(ReplannerError):
    """The configured planning provider did not return a usable response."""


class PlanningOutputError(ReplannerError):
    """The provider returned malformed or refused structured output."""


class PlanValidationError(ReplannerError):
    """A structured candidate violates deterministic trip constraints."""
