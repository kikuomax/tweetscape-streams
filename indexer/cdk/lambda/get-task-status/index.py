# -*- coding: utf-8 -*-

"""Obtains the status of a given task.
"""

import logging
import boto3


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

stepfunctions = boto3.client('stepfunctions')


def lambda_handler(event, _context):
    """Obtains the status of a given task.

    ``event`` must be a ``dict`` similar to the following,

    .. code-block:: python

        {
            'executionArn': '<execution-arn>'
        }
    """
    LOGGER.debug('obtaining task status: %s', event)
    execution_arn = event['executionArn']
    res = stepfunctions.describe_execution(
        executionArn=execution_arn,
    )
    # TODO: handle errors
    LOGGER.debug('obtained task status: %s', res)
    return {
        'status': res['status'],
        'error': res.get('error', ''),
        'cause': res.get('cause', ''),
    }
