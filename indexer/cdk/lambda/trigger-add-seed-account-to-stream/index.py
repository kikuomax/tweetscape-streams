# -*- coding: utf-8 -*-

"""Triggers a workflow to add a seed account to a stream.

You have to specify the following environment variable,
* ``WORKFLOW_ARN``: ARN of the workflow (state machine) to add a seed account to
  a stream.
"""

import json
import logging
import os
import boto3


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

WORKFLOW_ARN = os.environ['WORKFLOW_ARN']

stepfunctions = boto3.client('stepfunctions')


def lambda_handler(event, _context):
    """Triggers a workflow to add a seed account to a stream.

    ``event`` must be a ``dict`` similar to the following,

    .. code-block:: python

        {
            'requesterId': '<requester-id>',
            'streamName': '<stream-name>',
            'twitterUsername': '<twitter-username>'
        }
    """
    LOGGER.debug(
        'triggering a workflow to add a seed account to a stream: %s',
        event,
    )
    requester_id = event['requesterId']
    stream_name = event['streamName']
    twitter_username = event['twitterUsername']
    res = stepfunctions.start_execution(
        stateMachineArn=WORKFLOW_ARN,
        input=json.dumps({
            'requesterId': requester_id,
            'streamName': stream_name,
            'twitterUsername': twitter_username,
        }),
    )
    # TODO: handle errors
    LOGGER.debug('triggered workflow: %s', res)
    # TODO: return a task ID instead of an execution ARN
    return {
        'executionArn': res['executionArn'],
        'startDate': res['startDate'].strftime('%Y-%m-%dT%H:%M:%S%z'),
    }
