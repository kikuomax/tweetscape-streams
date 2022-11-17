# -*- coding: utf-8 -*-

"""Indexes all the Stream nodes on the neo4j database.

You have to specify the following environment variables,
* ``NEO4J_SECRET_ARN``: ARN of the SecretsManager Secret containing neo4j
  connection parameters.
* ``POSTGRES_SECRET_ARN``: ARN of the SecretsManager Secret containing
  PostgreSQL connection parameters.
* ``TWITTER_SECRET_ARN``: ARN of the SecretsManager Secret containing Twitter
  credentials.

If you run this function locally, you need the following environment variables
instead,
* ``NEO4J_URI``
* ``NEO4J_USERNAME``
* ``NEO4J_PASSWORD``
* ``DATABASE_URL``: connection URI for the PostgreSQL database.
* ``OAUTH_CLIENT_ID``: Twitter app client ID
* ``OAUTH_CLIENT_SECRET``: Twitter app client secret

You can use ``.env`` file to specify them.
It may be in one of parent folders.
"""

import functools
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
from neo4j import Driver, GraphDatabase, Transaction # type: ignore
import psycopg2
import requests
from twarc import Twarc2 # type: ignore


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

if __name__ != '__main__':
    import boto3
    secrets = boto3.client('secretsmanager')


class TwitterAccount:
    """Twitter account.
    """
    account_id: str
    username: str

    def __init__(self, account_id: str, username: str):
        """Initializes with ID and name.
        """
        self.account_id = account_id
        self.username = username

    @staticmethod
    def parse_node(node: Dict[str, Any]):
        """Parses a given neo4j node.
        """
        return TwitterAccount(
            account_id=node['id'],
            username=node['username'],
        )

    def __str__(self):
        return (
            'TwitterAccount('
            f'account_id={self.account_id}, '
            f'username={self.username}'
            ')'
        )

    def __repr__(self):
        return (
            'TwitterAccount('
            f'account_id={repr(self.account_id)}, '
            f'username={repr(self.username)}'
            ')'
        )


class SeedAccount(TwitterAccount):
    """Seed Twitter account.
    """
    latestTweetId: Optional[str]
    earliestTweetId: Optional[str]

    def __init__(
        self,
        account: TwitterAccount,
        latest_tweet_id: Optional[str],
        earliest_tweet_id: Optional[str],
    ):
        """Initializes with seed account attributes.
        """
        super().__init__(account.account_id, account.username)
        self.latest_tweet_id = latest_tweet_id
        self.earliest_tweet_id = earliest_tweet_id

    @staticmethod
    def parse_node(node: Dict[str, Any]):
        """Parses a given neo4j node.
        """
        return SeedAccount(
            account=TwitterAccount.parse_node(node),
            latest_tweet_id=node.get('latestTweetId'),
            earliest_tweet_id=node.get('earliestTweetId'),
        )

    def __str__(self):
        return (
            'SeedAccount('
            f'account_id={self.account_id}, '
            f'username={self.username}, '
            f'latest_tweet_id={self.latest_tweet_id}, '
            f'earliest_tweet_id={self.earliest_tweet_id}'
            ')'
        )

    def __repr__(self):
        return (
            'SeedAccount('
            f'account_id={repr(self.account_id)}, '
            f'username={repr(self.username)}, '
            f'latest_tweet_id={repr(self.latest_tweet_id)}, '
            f'earliest_tweet_id={repr(self.earliest_tweet_id)}'
            ')'
        )


class Stream:
    """Stream.
    """
    name: str
    creator: TwitterAccount
    seed_accounts: List[TwitterAccount]

    def __init__(
        self,
        name: str,
        creator: TwitterAccount,
        seed_accounts: List[TwitterAccount],
    ):
        """Initializes with the stream name, creator, and seed accounts.
        """
        self.name = name
        self.creator = creator
        self.seed_accounts = seed_accounts

    def __str__(self):
        """Returns a string representation.
        """
        return (
            'Stream('
            f'name={self.name}, '
            f'creator={self.creator}, '
            f'seed_accounts={self.seed_accounts}'
            ')'
        )

    def __repr__(self):
        return (
            'Stream('
            f'name={repr(self.name)}, '
            f'creator={repr(self.creator)}, '
            f'seed_accounts={repr(self.seed_accounts)}'
            ')'
        )


class Token:
    """Token associated with a Twitter account.
    """
    account_id: str
    access_token: str
    refresh_token: str

    def __init__(
        self,
        account_id: str,
        access_token: str,
        refresh_token: str,
        created_at,
        updated_at,
        expires_in,
    ):
        """Initializes with token values.
        """
        self.account_id = account_id
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.created_at = created_at
        self.updated_at = updated_at
        self.expires_in = expires_in

    def __str__(self):
        return (
            'Token('
            f'account_id={self.account_id}, '
            f'access_token={self.access_token[:8]}..., '
            f'refresh_token={self.refresh_token[:8]}..., '
            f'created_at={self.created_at}, '
            f'updated_at={self.updated_at}, '
            f'expires_in={self.expires_in}'
            ')'
        )

    def __repr__(self):
        return (
            'Token('
            f'account_id={repr(self.account_id)}, '
            f'access_token={repr(self.access_token[:8] + "...")}, '
            f'refresh_token={repr(self.refresh_token[:8] + "...")}, '
            f'created_at={repr(self.created_at)}, '
            f'updated_at={repr(self.updated_at)}, '
            f'expires_in={repr(self.expires_in)}'
            ')'
        )


class AccountTwarc2:
    """Container of a ``Twarc2`` instance that makes requests on behalf of a
    Twitter account.
    """
    client_id: str
    client_secret: str
    token: Token
    on_token_refreshed: Optional[Callable[[Token], None]]
    api: Twarc2

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token: Token,
        on_token_refreshed: Optional[Callable[[Token], None]] = None,
    ):
        """Initializes with a given token.

        :param str client_id: Twitter app client ID.

        :param str client_secret: Twitter app client secret.

        :param Token token: initial token.

        :param Callable[[Token], None]? on_token_refreshed: optional function
        that is called when the token is refreshed. You can use this function
        to save the new token.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = token
        self.on_token_refreshed = on_token_refreshed
        self.api = Twarc2(bearer_token=token.access_token)

    def execute_with_retry_if_unauthorized(self, func: Callable[[Twarc2], Any]):
        """Runs a given function with a retry when the request is not
        authorized.
        """
        try:
            return func(self.api)
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 401:
                # refreshes the access token and retries
                LOGGER.debug('refreshing token')
                try:
                    self.refresh_tokens()
                except requests.exceptions.HTTPError as exc2:
                    if exc2.response.status_code == 400:
                        # refresh token may be out of sync
                        LOGGER.warning(
                            'refresh token may be out of sync. you have to'
                            ' reset tokens by logging in to the'
                            ' tweetscape-streams app on a browser',
                        )
                    raise
                else:
                    LOGGER.debug('retrying with token: %s', self.token)
                    self.api = Twarc2(bearer_token=self.token.access_token)
                    return func(self.api)
            raise

    def refresh_tokens(self):
        """Refreshes the Twitter account tokens.

        :raise requests.exceptions.HTTPError: if the update of the Twitter
        account tokens has failed.
        """
        client = requests.Session()
        client.headers.update({
            'Content-Type': 'application/x-www-form-urlencoded',
        })
        res = client.post(
            'https://api.twitter.com/2/oauth2/token',
            {
                'refresh_token': self.token.refresh_token,
                'grant_type': 'refresh_token',
                'client_id': self.client_id,
            },
            auth=(self.client_id, self.client_secret), # basic authentication
        )
        res.raise_for_status()
        token_json = res.json()
        self.token = Token(
            self.token.account_id,
            token_json['access_token'],
            token_json['refresh_token'],
            self.token.created_at,
            self.token.updated_at, # TODO: set the current time (format matters?)
            token_json['expires_in'],
        )
        if self.on_token_refreshed:
            self.on_token_refreshed(self.token)


def read_all_streams(tx: Transaction) -> List[Stream]:
    """Reads all streams on the graph database.
    """
    results = tx.run(
        "MATCH (s:Stream)-[:CONTAINS]->(u:User)"
        "MATCH (c:User)-[:CREATED]->(s)"
        "RETURN s as stream, collect(c) as creator, collect(u) as seedAccounts"
    )
    def extract(record) -> Stream:
        stream = record['stream']
        creator = TwitterAccount.parse_node(record['creator'][0]) # should be one
        seed_account_nodes = record['seedAccounts']
        seed_accounts = [SeedAccount.parse_node(a) for a in seed_account_nodes]
        return Stream(
            stream['name'],
            creator,
            seed_accounts,
        )
    return [extract(r) for r in results]


def fetch_streams(driver: Driver) -> List[Stream]:
    """Fetches all streams on the graph database.
    """
    with driver.session() as session:
        streams = session.execute_read(read_all_streams)
        LOGGER.debug('streams: %s', streams)
        return streams


def get_twitter_account_token(postgres, account: TwitterAccount) -> Token:
    """Queries the token of a given Twitter account.
    """
    with postgres.cursor() as curs:
        curs.execute(
            'SELECT'
            '  user_id,'
            '  access_token,'
            '  refresh_token,'
            '  created_at,'
            '  updated_at,'
            '  expires_in'
            ' FROM tokens'
            ' WHERE user_id = %(account_id)s',
            {
                'account_id': account.account_id,
            },
        )
        record = curs.fetchone()
        return Token(
            record[0],
            record[1],
            record[2],
            record[3],
            record[4],
            record[5],
        )


def save_twitter_account_token(postgres, token: Token):
    """Saves a given token in the database.
    """
    LOGGER.debug('saving Twitter account token: %s', token)
    with postgres.cursor() as curs:
        curs.execute(
            'UPDATE tokens'
            ' SET'
            '  access_token = %(access_token)s,'
            '  refresh_token = %(refresh_token)s,'
            '  expires_in = %(expires_in)s'
            ' WHERE user_id = %(account_id)s',
            {
                'access_token': token.access_token,
                'refresh_token': token.refresh_token,
                'expires_in': token.expires_in,
                'account_id': token.account_id,
            },
        )
        postgres.commit() # TODO: is this necessary?


def get_latest_tweets(twitter: Twarc2, account: SeedAccount, max_results=5):
    """Obtains the latest tweets of a given seed Twitter account.

    :raises requests.exceptions.HTTPError: If there is an error to access the
    Twitter API.
    """
    latest_tweet_id = account.latest_tweet_id
    if account.earliest_tweet_id is None:
        # resets a half-open range
        latest_tweet_id = None
    # TODO: define pull_tweets function
    res = twitter.timeline(
        user=account.account_id,
        max_results=max_results,
        since_id=latest_tweet_id,
    )
    # DO NOT iterate over res.
    # it will try to retrieve as many tweets as possible.
    # https://twarc-project.readthedocs.io/en/latest/api/library/#working-with-generators
    page = next(res, None)
    if page is not None:
        for num, tweet in enumerate(page['data']):
            LOGGER.debug('latest tweet[%d]: %s', num, tweet)
    else:
        LOGGER.debug('no newer tweets from %s', account.username)
    # TODO: update the indexed tweet range of the account


def index_all_streams(
    neo4j_driver: Driver,
    postgres,
    twitter_cred: Tuple[str, str],
):
    """Indexes all streams.

    This is the main routine of the periodic Indexer.

    :param Tuple[str,str] twitter_cred: A tuple of Twitter app client ID and
    secret.
    """
    streams = fetch_streams(neo4j_driver)
    for stream in streams:
        token = get_twitter_account_token(postgres, stream.creator)
        LOGGER.debug("using token: %s", token)
        client_id, client_secret = twitter_cred
        twitter = AccountTwarc2(
            client_id,
            client_secret,
            token,
            functools.partial(save_twitter_account_token, postgres)
        )
        for seed_account in stream.seed_accounts:
            LOGGER.debug('getting latest tweets from %s', seed_account.username)
            twitter.execute_with_retry_if_unauthorized(
                functools.partial(
                    get_latest_tweets,
                    account=seed_account,
                )
            )


def get_neo4j_parameters() -> Tuple[str, Tuple[str, str]]:
    """Returns connection parameters for the neo4j database.

    :return: tuple of a neo4j URI and credential.
    A credential is a tuple of a username and password.
    """
    neo4j_secret_arn = os.environ['NEO4J_SECRET_ARN']
    res = secrets.get_secret_value(SecretId=neo4j_secret_arn)
    parsed = json.loads(res['SecretString'])
    neo4j_uri = str(parsed['neo4jUri'])
    neo4j_username = str(parsed['neo4jUsername'])
    neo4j_password = str(parsed['neo4jPassword'])
    return neo4j_uri, (neo4j_username, neo4j_password)


def get_postgres_uri() -> str:
    """Returns the connection URI for the PostgreSQL database.
    """
    postgres_secret_arn = os.environ['POSTGRES_SECRET_ARN']
    res = secrets.get_secret_value(SecretId=postgres_secret_arn)
    parsed = json.loads(res['SecretString'])
    postgres_uri = str(parsed['postgresUri'])
    return postgres_uri


def get_twitter_credential() -> Tuple[str, str]:
    """Returns the credential for Twitter.
    """
    twitter_secret_arn = os.environ['TWITTER_SECRET_ARN']
    res = secrets.get_secret_value(SecretId=twitter_secret_arn)
    parsed = json.loads(res['SecretString'])
    client_id = str(parsed['clientId'])
    client_secret = str(parsed['clientSecret'])
    return client_id, client_secret


def lambda_handler(_event, _context):
    """Runs as a Lambda function.
    """
    LOGGER.debug('running Lambda')
    neo4j_uri, neo4j_cred = get_neo4j_parameters()
    postgres_uri = get_postgres_uri()
    twitter_cred = get_twitter_credential()
    LOGGER.debug(
        'connecting to neo4j: URI=%s, username=%s, password=%s',
        neo4j_uri,
        neo4j_cred[0],
        (neo4j_cred[1] and '****') or 'None',
    )
    neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=neo4j_cred)
    try:
        LOGGER.debug('connecting to PostgreSQL')
        postgres = psycopg2.connect(postgres_uri)
        try:
            index_all_streams(neo4j_driver, postgres, twitter_cred)
        finally:
            postgres.close()
    finally:
        neo4j_driver.close()


def run_local():
    """Runs locally.
    """
    neo4j_uri = os.environ['NEO4J_URI']
    neo4j_username = os.environ['NEO4J_USERNAME']
    neo4j_password = os.environ['NEO4J_PASSWORD']
    postgres_uri = os.environ['DATABASE_URL']
    twitter_cred = (
        os.environ['OAUTH_CLIENT_ID'],
        os.environ['OAUTH_CLIENT_SECRET'],
    )
    LOGGER.debug(
        'connecting to neo4j: URI=%s, username=%s, password=%s',
        neo4j_uri,
        neo4j_username,
        (neo4j_password and '****') or 'None',
    )
    neo4j_driver = GraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_username, neo4j_password),
    )
    try:
        LOGGER.debug('connecting to PostgreSQL')
        postgres = psycopg2.connect(postgres_uri)
        try:
            index_all_streams(neo4j_driver, postgres, twitter_cred)
        finally:
            postgres.close()
    finally:
        neo4j_driver.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    LOGGER.debug('running locally')
    from dotenv import load_dotenv
    load_dotenv()
    run_local()
