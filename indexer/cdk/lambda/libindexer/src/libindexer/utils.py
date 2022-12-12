# -*- coding: utf-8 -*-

"""Defines utility functions.
"""

import datetime
import itertools
from typing import Iterable, List, TypeVar, Union
import pytz


T = TypeVar('T')

def chunk(sequence: Iterable[T], size: int) -> Iterable[List[T]]:
    """Splits a given sequence into chunks of a specified size.
    """
    return iter(lambda: list(itertools.islice(sequence, size)), [])


UNIX_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=pytz.utc)

def unix_epoch_to_datetime(timestamp: Union[int, float]) -> datetime.datetime:
    """Converts a given UNIX epoch timestamp into an equivalent ``datetime`` in
    UTC.

    :param Union[int, float] timestamp: UNIX epoch timestamp to be converted
    into an equivalent ``datetime`` in UTC. It is the number of seconds elapsed
    since 00:00:00 on January 1, 1970 in UTC.
    """
    return UNIX_EPOCH + datetime.timedelta(seconds=timestamp)


def current_time_string() -> str:
    """Returns a string representing the current time in UTC.

    You will get a string similar to "2022-12-11T05:49:23.123456Z".
    """
    now = datetime.datetime.now(tz=pytz.utc)
    return now.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
