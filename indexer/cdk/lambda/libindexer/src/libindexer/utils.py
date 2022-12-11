# -*- coding: utf-8 -*-

"""Defines utility functions.
"""

import datetime
import itertools
import pytz
from typing import Iterable, List, TypeVar


T = TypeVar('T')

def chunk(sequence: Iterable[T], size: int) -> Iterable[List[T]]:
    """Splits a given sequence into chunks of a specified size.
    """
    return iter(lambda: list(itertools.islice(sequence, size)), [])


def current_time_string() -> str:
    """Returns a string representing the current time in UTC.

    You will get a string similar to "2022-12-11T05:49:23.123456Z".
    """
    now = datetime.datetime.now(tz=pytz.utc)
    return now.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
