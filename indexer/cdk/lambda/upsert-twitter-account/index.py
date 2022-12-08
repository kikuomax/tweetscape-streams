# -*- coding: utf-8 -*-

"""Upserts a Twitter account to the graph database.

To run this function on AWS Lambda, you have to specify the following
environment variables,
* ``EXTERNAL_CREDENTIALS_ARN``: ARN of the SecretsManager Secret that contains
  credentials for external services: neo4j, PostgreSQL, and Twitter.
"""

import functools
import logging
import os
from typing import Any, Dict, Tuple
from libindexer import (
    AccountTwarc2,
    ExternalCredentialError,
    ExternalCredentials,
    connect_neo4j_and_postgres,
    flatten_twitter_account_properties,
    get_twitter_access_token,
    save_twitter_access_token,
    upsert_twitter_account_node,
)
import boto3
import neo4j # type: ignore
from twarc import Twarc2 # type: ignore


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


# loads credentials for external services
if __name__ != '__main__':
    aws_secrets = boto3.client('secretsmanager')
    EXTERNAL_CREDENTIALS_ARN = os.environ['EXTERNAL_CREDENTIALS_ARN']
    EXTERNAL_CREDENTIALS = ExternalCredentials(
        aws_secrets,
        EXTERNAL_CREDENTIALS_ARN,
    )


TWITTER_USER_LOOKUP_PARAMETERS = {
    'tweet_fields': ','.join([
        'attachments',
        'author_id',
        'context_annotations',
        'conversation_id',
        'created_at',
        'entities',
        'geo',
        'id',
        'in_reply_to_user_id',
        'lang',
        'public_metrics',
        'text',
        'possibly_sensitive',
        'referenced_tweets',
        'reply_settings',
        'source',
        'withheld',
    ]),
    'user_fields': ','.join([
        'created_at',
        'description',
        'entities',
        'id',
        'location',
        'name',
        'pinned_tweet_id',
        'profile_image_url',
        'protected',
        'public_metrics',
        'url',
        'username',
        'verified',
    ]),
}


def get_twitter_account_by_username(
    api: Twarc2,
    username: str,
) -> Dict[str, Any]:
    """Obtains the account information of a given Twitter user.
    """
    LOGGER.debug('looking up Twitter account: %s', username)
    res = api.user_lookup(
        users=[username],
        usernames=True,
        **TWITTER_USER_LOOKUP_PARAMETERS,
    )
    # TODO: handle errors
    accounts = next(res)
    account = accounts['data'][0]
    return flatten_twitter_account_properties(account)


def upsert_twitter_account(
    neo4j_driver: neo4j.Driver,
    postgres: Any,
    twitter_client_cred: Tuple[str, str],
    requester_id: str,
    account_username: str,
):
    """Upserts a Twitter account to the graph database.

    :param Tuple[str, str] twitter_client_cred: tuple of Twitter the client ID
    and secret.

    :param str requester_id: Twitter account ID of the requester who offers the
    rate limit.

    :param str account_username: username of the Twitter account to be upserted.
    """
    # obtains the access token of the requester
    LOGGER.debug('obtaining Twitter access token for %s', requester_id)
    token = get_twitter_access_token(postgres, requester_id)
    LOGGER.debug('using token: %s', token)
    # prepares Twitter API
    twitter = AccountTwarc2(
        twitter_client_cred,
        token,
        functools.partial(save_twitter_access_token, postgres),
    )
    # obtains the Twitter account information
    account_info = twitter.execute_with_retry_if_unauthorized(
        functools.partial(
            get_twitter_account_by_username,
            username=account_username,
        )
    )
    LOGGER.debug('upserting account node: %s', account_info)
    # upserts the Account node
    with neo4j_driver.session() as session:
        account_node = session.execute_write(
            functools.partial(
                upsert_twitter_account_node,
                account=account_info,
            ),
        )
        return account_node


def lambda_handler(event, _context):
    """Runs on AWS Lambda.

    ``event`` must be a ``dict`` similar to the following,

    .. code-block:: python

        {
            'requesterId': '<requester-id>',
            'twitterUsername': '<twitter-username>'
        }

    Returns a ``dict`` similar to the following,

    .. code-block:: python

        {
            'accountId': '<twitter-account-id>'
        }
    """
    requester_id = event['requesterId']
    twitter_username = event['twitterUsername']
    LOGGER.debug('upserting a Twitter account: %s', twitter_username)
    # uses an internal function to simplify retry
    def run():
        with connect_neo4j_and_postgres(EXTERNAL_CREDENTIALS) as (
            neo4j_driver,
            postgres,
        ):
            return upsert_twitter_account(
                neo4j_driver,
                postgres,
                EXTERNAL_CREDENTIALS.twitter_client_cred,
                requester_id,
                twitter_username,
            )
    try:
        account_node = run()
    except ExternalCredentialError:
        # refreshes the cached credentials and retries
        LOGGER.debug('refreshing external credentials')
        EXTERNAL_CREDENTIALS.refresh()
        account_node = run()
    else:
        LOGGER.debug('upserted account node: %s', account_node)
        return {
            'accountId': account_node.account_id,
        }
