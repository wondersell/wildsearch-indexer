class DumpStateError(Exception):
    """Raised when dump has wrong state for action"""
    pass


class DumpStateTooEarlyError(DumpStateError):
    """Raised when dump has wrong state for action (too early to be processed)"""
    pass


class DumpStateTooLateError(DumpStateError):
    """Raised when dump has wrong state for action (too late to be processed)"""
    pass


class DumpCorruptedError(DumpStateError):
    """Raised when dump is imported incoreclty, i.e. there is more versions than items"""
    pass
