# -*- coding: utf-8 -*-

"""Indexeds Twitter accounts whom a specific account is following.

You have to specify the following environment variable to run this function on
AWS,
* ``EXTERNAL_CREDENTIALS_ARN``: ARN of the AWS SecretsManager secret containing
  credentials for external services.

You can specify the following optional environment variable,
* ``FOLLOWING_PAGE_SIZE``: maximum number of accounts included in a single page
  of a request for following accounts. 1000 by default.
* ``ACCOUNTS_BATCH_SIZE``: maximum number of accounts to be sent to the neo4j
  database at once. 100 by default.
"""

import functools
import logging
import os
from typing import Tuple
from libindexer import (
    AccountTwarc2,
    ExternalCredentialError,
    ExternalCredentials,
    connect_neo4j_and_postgres,
    delete_follows_relationships_from,
    get_twitter_access_token,
    get_twitter_accounts_followed_by,
    save_twitter_access_token,
    update_last_follows_index,
    upsert_twitter_account_nodes_followed_by,
)
from libindexer.utils import chunk
import neo4j # type: ignore
from twarc import Twarc2 # type: ignore


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

FOLLOWING_PAGE_SIZE = int(os.environ.get('FOLLOWING_PAGE_SIZE', 1000))
ACCOUNTS_BATCH_SIZE = int(os.environ.get('ACCOUNTS_BATCH_SIZE', 100))


# loads credentials for external services.
if __name__ != '__main__':
    import boto3
    aws_secrets = boto3.client('secretsmanager')
    EXTERNAL_CREDENTIALS_ARN = os.environ['EXTERNAL_CREDENTIALS_ARN']
    EXTERNAL_CREDENTIALS = ExternalCredentials(
        aws_secrets,
        EXTERNAL_CREDENTIALS_ARN,
    )


def process_twitter_accounts_followed_by(
    twitter: Twarc2,
    neo4j_driver: neo4j.Driver,
    account_id: str,
):
    """Processes Twitter accounts followed by a given account.

    :raises requests.exceptions.HTTPError: if there is an error with a call to
    the Twitter API.
    """
    # obtains accounts the account is following
    LOGGER.debug('obtaining Twitter accounts followed by %s', account_id)
    followed_accounts = get_twitter_accounts_followed_by(
        twitter,
        account_id,
        page_size=FOLLOWING_PAGE_SIZE,
    )
    # upserts accounts and updates FOLLOWS relationships
    # deletes all the FOLLOWS relationships from the account first
    LOGGER.debug('deleting old FOLLOWS relationships from %s', account_id)
    num_deleted = delete_follows_relationships_from(neo4j_driver, account_id)
    LOGGER.debug('deleted %d old FOLLOWS relationships', num_deleted)
    for accounts_batch in chunk(followed_accounts, ACCOUNTS_BATCH_SIZE):
        # please note the access token may expire in this loop
        LOGGER.debug('upserting %d followed accounts', len(accounts_batch))
        upsert_twitter_account_nodes_followed_by(
            neo4j_driver,
            account_id,
            accounts_batch,
        )


def index_following(
    neo4j_driver: neo4j.Driver,
    postgres,
    twitter_client_cred: Tuple[str, str],
    requester_id: str,
    account_id: str,
):
    """Indexes Twitter accounts whom a given account is following.
    """
    # prepares the Twitter API
    LOGGER.debug('obtaining access token for %s', requester_id)
    access_token = get_twitter_access_token(postgres, requester_id)
    LOGGER.debug('using access token: %s', access_token)
    twitter = AccountTwarc2(
        twitter_client_cred,
        access_token,
        on_token_refreshed=functools.partial(
            save_twitter_access_token,
            postgres,
        )
    )
    # processes Twitter accounts followed by the account
    twitter.execute_with_retry_if_unauthorized(
        functools.partial(
            process_twitter_accounts_followed_by,
            neo4j_driver=neo4j_driver,
            account_id=account_id,
        ),
    )
    # updates lastFollowsIndex
    LOGGER.debug('updating lastFollowsIndex')
    updated_account = update_last_follows_index(neo4j_driver, account_id)
    LOGGER.debug('updated lastFollowsIndex: %s', updated_account)


def lambda_handler(event, _context):
    """Runs on the AWS Lambda.

    ``event`` must be a ``dict`` similar to the following,

    .. code-block:: python

        {
            'requesterId': '<requester-id>',
            'accountId': '<twitter-account-id>'
        }
    """
    LOGGER.debug('indexing following: %s', event)
    requester_id = event['requesterId']
    account_id = event['accountId']
    # reruns the following internal function when a credential error occurs
    def run():
        with connect_neo4j_and_postgres(EXTERNAL_CREDENTIALS) as (
            neo4j_driver,
            postgres,
        ):
            index_following(
                neo4j_driver,
                postgres,
                EXTERNAL_CREDENTIALS.twitter_client_cred,
                requester_id,
                account_id,
            )
    try:
        run()
    except ExternalCredentialError:
        # refreshes the cached credentials and retries
        LOGGER.debug('refreshing cached credentials')
        EXTERNAL_CREDENTIALS.refresh()
        run()
