"""Error types shared by all commands."""


class ChreosError(Exception):
    """A user or validation error: reported to the user, exit code 1."""


class FormatError(ChreosError):
    """A file whose frontmatter can't be parsed."""
