RESOURCE_LOOKUP_HINT = 'Search with search_type="resource" and use the result\'s id or context_url.'


class LacunaMCPError(RuntimeError):
    """Raised for user-facing MCP errors from Lacuna API access."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
