# -*- coding: utf-8 -*-

"""Defines the common exceptions.
"""

import json
from typing import Any, Dict


class LibIndexerException(Exception):
    """Base class of all the exceptions raised by this library.
    """
    message: str

    def __init__(self, message: str):
        """Initializes with a given message.
        """
        self.message = message

    def __str__(self):
        typename = type(self).__name__
        return f'{typename}("{self.message}")'

    def __repr__(self):
        typename = type(self).__name__
        return f'{typename}({repr(self.message)})'


class WorkflowException(Exception):
    """Base class of exceptions related to workflows.

    The string representation of this class is a JSON-formatted string so that
    AWS Step Functions (Amazon States Language) can parse it.
    """
    payload: Dict[str, Any]

    def __init__(self, payload: Dict[str, Any]):
        """Initializes with a given payload.

        The string representation of the new instance is a JSON representation
        of ``payload``.
        """
        self.payload = payload

    def __str__(self):
        return json.dumps(self.payload)

    def __repr__(self):
        return str(self)
