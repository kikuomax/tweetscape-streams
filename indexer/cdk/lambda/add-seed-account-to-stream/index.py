# -*- coding: utf-8 -*-

"""Adds a seed Twitter account to a stream.

A seed Twitter account has to be added to the graph database prior to calling
this function.

To run this function on AWS Lambda, you have to specify the following
environment variable,
* ``EXTERNAL_CREDENTIALS_ARN``: ARN of the AWS SecretsManager secret containing
  credentials for external services.
"""

import functools
import logging
import os
from typing import Tuple
from libindexer import (
    AccountTwarc2,
    ExternalCredentialError,
    ExternalCredentials,
    add_seed_account_to_stream_node,
    connect_neo4j_and_postgres,
    get_stream_node_by_name,
    get_twitter_access_token,
    get_twitter_account_node,
    save_twitter_access_token,
)
import neo4j # type: ignore
from twarc import Twarc2 # type: ignore


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


# loads credentials for external services
if __name__ != '__main__':
    import boto3
    aws_secrets = boto3.client('secretsmanager')
    EXTERNAL_CREDENTIALS_ARN = os.environ['EXTERNAL_CREDENTIALS_ARN']
    EXTERNAL_CREDENTIALS = ExternalCredentials(
        aws_secrets,
        EXTERNAL_CREDENTIALS_ARN,
    )


def add_twitter_account_to_list(
    postgres,
    twitter_client_cred: Tuple[str, str],
    requester_id: str,
    twitter_list_id: str,
    twitter_account_id: str,
):
    """Adds an account to a Twitter list.
    """
    LOGGER.debug('obtaining Twitter access token: %s', requester_id)
    access_token = get_twitter_access_token(postgres, requester_id)
    LOGGER.debug('using access token: %s', access_token)
    twitter_api = AccountTwarc2(
        twitter_client_cred,
        access_token,
        functools.partial(save_twitter_access_token, postgres),
    )
    LOGGER.debug('adding an account to a Twitter list')
    twitter_api.execute_with_retry_if_unauthorized(
        functools.partial(
            add_twitter_list_member,
            list_id=twitter_list_id,
            new_member_id=twitter_account_id,
        ),
    )
    LOGGER.debug('added the account to the Twitter list')


def add_twitter_list_member(api: Twarc2, list_id: str, new_member_id: str):
    """Adds a given Twitter account to the member of a specified list.

    :raises requests.exceptions.HTTPError: if there is an error with the
    Twitter API call.
    """
    # TODO: validate list_id
    url = f'https://api.twitter.com/2/lists/{list_id}/members'
    res = api.post(url, {
        'user_id': new_member_id,
    })
    res.raise_for_status()
    res_json = res.json()
    LOGGER.debug('added a list member: %s', res_json)


def add_seed_account_to_stream(
    neo4j_driver: neo4j.Driver,
    postgres,
    twitter_client_cred,
    requester_id: str,
    stream_name: str,
    seed_account_id: str,
):
    """Adds a seed Twitter account to a stream.
    """
    # obtains the stream
    LOGGER.debug('obtaining stream node: %s', stream_name)
    stream_node = get_stream_node_by_name(neo4j_driver, stream_name)
    LOGGER.debug('obtained stream node: %s', stream_node)
    # makes sure that the seed account exists on the graph database
    # TODO: may we skip this to reduce the overhead?
    LOGGER.debug('obtaining seed account node: %s', seed_account_id)
    seed_account_node = get_twitter_account_node(neo4j_driver, seed_account_id)
    LOGGER.debug('obtained seed account node: %s', seed_account_node)
    # adds the seed account to the stream
    LOGGER.debug('adding seed account to stream node')
    seed_account_node = add_seed_account_to_stream_node(
        neo4j_driver,
        stream_name,
        seed_account_id,
    )
    LOGGER.debug('added seed account to stream node: %s', seed_account_node)
    # adds the seed account to the Twitter list
    add_twitter_account_to_list(
        postgres,
        twitter_client_cred,
        requester_id,
        stream_node.twitter_list_id,
        seed_account_id,
    )


def lambda_handler(event, _context):
    """Runs on AWS Lambda.

    ``event`` must be a ``dict`` similar to the following,

    .. code-block:: python

        {
            'requesterId': '<requester-id>',
            'streamName': '<stream-name>',
            'seedAccountId': '<twitter-account-id>'
        }
    """
    LOGGER.debug('adding a seed Twitter account: %s', event)
    requester_id = event['requesterId']
    stream_name = event['streamName']
    seed_account_id = event['seedAccountId']
    # uses an internal function to simplify retry
    def run():
        with connect_neo4j_and_postgres(EXTERNAL_CREDENTIALS) as (
            neo4j_driver,
            postgres,
        ):
            add_seed_account_to_stream(
                neo4j_driver,
                postgres,
                EXTERNAL_CREDENTIALS.twitter_client_cred,
                requester_id,
                stream_name,
                seed_account_id,
            )
    try:
        run()
    except ExternalCredentialError:
        # refreshes the cached credentials and retries
        LOGGER.debug('refreshing credentials')
        EXTERNAL_CREDENTIALS.refresh()
        run()
