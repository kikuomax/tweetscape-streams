# -*- coding: utf-8 -*-

"""Indexes tweets from a given Twitter account.

To run this function on AWS Lambda, you have to specify the following
environment variable,
* ``EXTERNAL_CREDENTIALS_ARN``: ARN of the AWS SecretsManager secret containing
  credentials for external services.

You can specify the following optional environment variable,
* ``TIMELINE_PAGE_SIZE``: number of tweets in a timeline page; i.e., tweets
  requested in a single query. 100 by default.
"""

import functools
import logging
import os
from typing import Tuple
from libindexer import (
    AccountTwarc2,
    ExternalCredentialError,
    ExternalCredentials,
    SeedAccount,
    connect_neo4j_and_postgres,
    flatten_tweet_properties,
    flatten_twitter_account_properties,
    flatten_twitter_media_properties,
    get_latest_tweets_from,
    get_seed_account_node,
    get_twitter_access_token,
    reset_indexed_tweet_ids,
    save_twitter_access_token,
    update_latest_indexed_tweet_id,
    upsert_tweet_nodes,
    upsert_twitter_account_nodes,
    upsert_twitter_media_nodes,
)
import neo4j # type: ignore
from twarc import Twarc2 # type: ignore


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

TIMELINE_PAGE_SIZE = int(os.environ.get('TIMELINE_PAGE_SIZE', 100))


if __name__ != '__main__':
    import boto3
    aws_secrets = boto3.client('secretsmanager')
    EXTERNAL_CREDENTIALS_ARN = os.environ['EXTERNAL_CREDENTIALS_ARN']
    EXTERNAL_CREDENTIALS = ExternalCredentials(
        aws_secrets,
        EXTERNAL_CREDENTIALS_ARN,
    )


def index_latest_tweets_from(
    twitter: Twarc2,
    neo4j_driver: neo4j.Driver,
    account: SeedAccount,
):
    """Indexes latest tweets from a given seed Twitter account.
    """
    tweets_range = get_latest_tweets_from(
        twitter,
        account,
        page_size=TIMELINE_PAGE_SIZE,
    )
    # processes tweets and included objects
    # TODO: make them async
    updated = False
    for page_num, tweets_page in enumerate(tweets_range):
        # upserts included users
        LOGGER.debug('upserting included users: page=%d', page_num)
        account_nodes = upsert_twitter_account_nodes(
            neo4j_driver,
            [flatten_twitter_account_properties(a)
                for a in tweets_page.included_users],
        )
        for account_node in account_nodes:
            LOGGER.debug('upserted Twitter account: %s', account_node)
        # upserts included media
        LOGGER.debug('upserting include media: page=%d', page_num)
        media_nodes = upsert_twitter_media_nodes(
            neo4j_driver,
            [flatten_twitter_media_properties(m)
                for m in tweets_page.included_media]
        )
        for media_node in media_nodes:
            LOGGER.debug(
                'upserted Twitter media: key=%s, type=%s',
                media_node['media_key'],
                media_node['type'],
            )
        # upserts included tweets
        LOGGER.debug('upserting included tweets: page=%d', page_num)
        included_tweet_nodes = upsert_tweet_nodes(
            neo4j_driver,
            [flatten_tweet_properties(t) for t in tweets_page.included_tweets],
        )
        for tweet_node in included_tweet_nodes:
            LOGGER.debug(
                'upserted included tweet: id=%s, text=%s',
                tweet_node['id'],
                tweet_node.get('text', ''),
            )
        # upserts account's tweets
        LOGGER.debug('upserting tweets: page=%d', page_num)
        tweet_nodes = upsert_tweet_nodes(
            neo4j_driver,
            [flatten_tweet_properties(t) for t in tweets_page.tweets],
        )
        for tweet_node in tweet_nodes:
            LOGGER.debug(
                'upserted tweet: id=%s, text=%s',
                tweet_node['id'],
                tweet_node.get('text', ''),
            )
        updated = True
    # updates the indexed tweet range of the seed account
    if updated:
        LOGGER.debug('updating indexed tweet range')
        if account.earliest_tweet_id is None:
            # resets the full range
            LOGGER.debug('resetting indexed tweet range')
            updated_account = reset_indexed_tweet_ids(
                neo4j_driver,
                account=account,
                latest_tweet_id=tweets_range.latest_tweet_id,
                earliest_tweet_id=tweets_range.earliest_tweet_id,
            )
        else:
            # updates only the latest
            updated_account = update_latest_indexed_tweet_id(
                neo4j_driver,
                account,
                tweets_range.latest_tweet_id,
            )
        LOGGER.debug('updated indexed tweet range: %s', updated_account)
    else:
        LOGGER.debug('no newer tweets from %s', account.username)


def index_tweets_from_account(
    neo4j_driver: neo4j.Driver,
    postgres,
    twitter_client_cred: Tuple[str, str],
    requester_id: str,
    seed_account_id: str,
):
    """Indexes tweets from a given Twitter account.
    """
    LOGGER.debug('obtaining seed account: %s', seed_account_id)
    seed_account = get_seed_account_node(neo4j_driver, seed_account_id)
    LOGGER.debug('obtained seed account: %s', seed_account)
    LOGGER.debug('obtaining Twitter access token: %s', requester_id)
    access_token = get_twitter_access_token(postgres, requester_id)
    LOGGER.debug('using Twitter access token: %s', access_token)
    twitter = AccountTwarc2(
        twitter_client_cred,
        access_token,
        functools.partial(save_twitter_access_token, postgres),
    )
    LOGGER.debug('processing latest tweets from %s', seed_account.username)
    twitter.execute_with_retry_if_unauthorized(
        functools.partial(
            index_latest_tweets_from,
            neo4j_driver=neo4j_driver,
            account=seed_account,
        ),
    )


# TODO: add an option to index older tweets
def lambda_handler(event, _context):
    """Runs on AWS Lambda.

    ``event`` must be a ``dict`` similar to the following,

    .. code-block:: python

        {
            'requesterId': '<requester-id>',
            'seedAccountId': '<twitter-account-id>'
        }
    """
    requester_id = event['requesterId']
    seed_account_id = event['seedAccountId']
    LOGGER.debug('indexing tweets from an account: %s', seed_account_id)
    # retries the following internal function if there is an credential error
    def run():
        with connect_neo4j_and_postgres(EXTERNAL_CREDENTIALS) as (
            neo4j_driver,
            postgres,
        ):
            index_tweets_from_account(
                neo4j_driver,
                postgres,
                EXTERNAL_CREDENTIALS.twitter_client_cred,
                requester_id,
                seed_account_id,
            )
    try:
        run()
    except ExternalCredentialError:
        LOGGER.debug('refreshing cached credentials')
        EXTERNAL_CREDENTIALS.refresh()
        run()
