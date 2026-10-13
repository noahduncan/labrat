class LabratWarning(UserWarning):
    """Warning for labrat-assignment"""


class LabratError(Exception):
    """General error for labrat-assignment"""


class LabratConnectionError(LabratError):
    """Connection error when communicating with server"""


class LabratConfigError(LabratError):
    """An error parsing configuration data from server"""
