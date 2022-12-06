# -*- coding: utf-8 -*-

"""Upserts a Twitter account to the graph database.

To run this function on AWS Lambda, you have to specify the following
environment variables,
* ``EXTERNAL_CREDENTIALS_ARN``: ARN of the SecretsManager Secret that contains
  credentials for external services: neo4j, PostgreSQL, and Twitter.
"""

import contextlib
import functools
import json
import logging
import os
from typing import Any, Dict, Generator, Tuple
from libindexer import (
    AccountTwarc2,
    flatten_twitter_account_properties,
    get_twitter_access_token,
    save_twitter_access_token,
    upsert_twitter_account_node,
)
import boto3
import neo4j # type: ignore
import psycopg2
from twarc import Twarc2 # type: ignore


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


class ExternalCredentials:
    """Caches credentials for external services.
    """
    secret_arn: str
    credentials: Dict[str, str]

    def __init__(self, s3_secrets, secret_arn: str):
        """Initializes with the ARN of a secret containing the credentials.

        Loads the credentials from the secret.

        :param boto3.SecretsManager.Client s3_secrets: client of AWS
        SecretsManager to access the secret credentials.

        :param str secret_arn: ARN of the secret that keeps credentials.
        """
        self.s3_secrets = s3_secrets
        self.secret_arn = secret_arn
        self.refresh()

    def refresh(self):
        """Refreshes (reloads) the credentials from the secret.
        """
        res = self.s3_secrets.get_secret_value(SecretId=self.secret_arn)
        # TODO: handle errors
        self.credentials = json.loads(res['SecretString'])

    @property
    def neo4j_uri(self) -> str:
        """URI of the neo4j database.
        """
        return self.credentials['neo4jUri']

    @property
    def neo4j_cred(self) -> Tuple[str, str]:
        """Credential to connect to the neo4j database.

        Tuple of the username and password.
        """
        return (
            self.credentials['neo4jUsername'],
            self.credentials['neo4jPassword'],
        )

    @property
    def postgres_uri(self) -> str:
        """URI of the PostgreSQL database.

        Contains the username and password.
        """
        return self.credentials['postgresUri']

    @property
    def twitter_client_cred(self) -> Tuple[str, str]:
        """Credential of the Twitter client app.

        Tuple of the client ID and secret.
        """
        return (
            self.credentials['clientId'],
            self.credentials['clientSecret'],
        )


class ExternalCredentialError(Exception):
    """Error raised when an error has occurred around external credentials.
    """
    def __init__(self, message: str):
        """Initializes with a message.
        """
        self.message = message

    def __str__(self):
        typename = type(self).__name__
        return f'{typename}("{self.message}")'

    def __repr__(self):
        typename = type(self).__name__
        return f'{typename}({repr(self.message)})'


@contextlib.contextmanager
def neo4j_and_postgres(credentials) -> Generator[
    Tuple[neo4j.Driver, Any],
    None,
    None,
]:
    """Connects to neo4j, PostgreSQL, and Twitter.

    Call this function in a ``with`` context.

    :returns: tuple of neo4j.Driver and PostgreSQL connection.
    """
    try:
        LOGGER.debug('connecting to neo4j')
        neo4j_driver = neo4j.GraphDatabase.driver(
            credentials.neo4j_uri,
            auth=credentials.neo4j_cred,
        )
    except neo4j.exceptions.AuthError as exc:
        LOGGER.warning('neo4j connection error: %s', exc)
        raise ExternalCredentialError('failed to connect to neo4j') from exc
    else:
        try:
            LOGGER.debug('connecting to PostgreSQL')
            postgres = psycopg2.connect(credentials.postgres_uri)
        except psycopg2.Error as exc:
            LOGGER.warning('psycopg2 connection error: %s', exc)
            raise ExternalCredentialError('failed to connect to PostgreSQL') from exc
        else:
            try:
                yield neo4j_driver, postgres
            finally:
                LOGGER.debug('disconnecting from PostgreSQL')
                postgres.close()
        finally:
            LOGGER.debug('disconnecting from neo4j')
            neo4j_driver.close()


# loads credentials for external services
if __name__ != '__main__':
    secrets = boto3.client('secretsmanager')
    EXTERNAL_CREDENTIALS_ARN = os.environ['EXTERNAL_CREDENTIALS_ARN']
    EXTERNAL_CREDENTIALS = ExternalCredentials(
        secrets,
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
        LOGGER.debug('upserted account node: %s', account_node)


def lambda_handler(event, _context):
    """Runs on AWS Lambda.

    ``event`` must be a ``dict`` similar to the following,

    .. code-block:: python

        {
            'requesterId': '<requester-id>',
            'twitterUsernameToAdd': '<twitter-username>'
        }
    """
    global EXTERNAL_CREDENTIALS
    requester_id = event['requesterId']
    twitter_username = event['twitterUsernameToAdd']
    LOGGER.debug('upserting a Twitter account: %s', twitter_username)
    try:
        with neo4j_and_postgres(EXTERNAL_CREDENTIALS) as (neo4j_driver, postgres):
            upsert_twitter_account(
                neo4j_driver,
                postgres,
                EXTERNAL_CREDENTIALS.twitter_client_cred,
                requester_id,
                twitter_username,
            )
    except ExternalCredentialError:
        # refreshes the credentials and retries
        LOGGER.debug('refreshing external credentials')
        EXTERNAL_CREDENTIALS.refresh()
        LOGGER.debug('retrying')
        with neo4j_and_postgres(EXTERNAL_CREDENTIALS) as (neo4j_driver, postgres):
            upsert_twitter_account(
                neo4j_driver,
                postgres,
                EXTERNAL_CREDENTIALS.twitter_client_cred,
                requester_id,
                twitter_username,
            )
