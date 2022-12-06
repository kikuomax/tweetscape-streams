# -*- coding: utf-8 -*-

"""Defines the common exceptions.
"""

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
