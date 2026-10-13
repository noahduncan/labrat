class LabratWarning(UserWarning):
    """Warning for labrat-client"""


class LabratError(Exception):
    """General error for labrat-client"""


class LabratConnectionError(LabratError):
    """Connection error when communicating with server"""


class LabratConfigError(LabratError):
    """An error parsing configuration data from server"""
