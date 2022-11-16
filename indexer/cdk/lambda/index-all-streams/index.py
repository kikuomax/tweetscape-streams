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

You can use ``.env`` file to specify them.
It may be in one of parent folders.
"""

import functools
import json
import logging
import os
from typing import Any, Callable, List, Optional, Tuple
import boto3
from neo4j import Driver, GraphDatabase, Transaction # type: ignore
import psycopg2
import requests
from twarc import Twarc2 # type: ignore


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

secrets = boto3.client('secretsmanager')


class Stream:
    """Stream.
    """
    name: str
    creator: str
    seed_usernames: List[str]

    def __init__(self, name: str, creator: str, seed_usernames: List[str]):
        """Initializes with the stream name and creator.
        """
        self.name = name
        self.creator = creator
        self.seed_usernames = seed_usernames

    def __str__(self):
        """Returns a string representation.
        """
        return f'Stream(name={self.name}, creator={self.creator}, seed_usernames={self.seed_usernames})'

    def __repr__(self):
        return f'Stream(name={repr(self.name)}, creator={repr(self.creator)}, seed_usernames={repr(self.seed_usernames)})'


class Token:
    """Token.
    """
    user_id: str
    access_token: str
    refresh_token: str

    def __init__(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str,
        created_at,
        updated_at,
        expires_in,
    ):
        """Initializes with token values.
        """
        self.user_id = user_id
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.created_at = created_at
        self.updated_at = updated_at
        self.expires_in = expires_in

    def __str__(self):
        return f'Token(user_id={self.user_id}, access_token={self.access_token[:8]}..., refresh_token={self.refresh_token[:8]}..., created_at={self.created_at}, updated_at={self.updated_at}, expires_in={self.expires_in})'

    def __repr__(self):
        return f'Token(user_id={repr(self.user_id)}, access_token={repr(self.access_token[:8] + "...")}, refresh_token={repr(self.refresh_token[:8] + "...")}, created_at={repr(self.created_at)}, updated_at={repr(self.updated_at)}, expires_in={repr(self.expires_in)})'


class UserTwarc2:
    """Container of a ``Twarc2`` instance that makes requests on user's behalf.
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
        """Initializes with a given user token.

        :param str client_id: Twitter app client ID.

        :param str client_secret: Twitter app client secret.

        :param Token token: user token.

        :param Callable[[Token], None]? on_token_refreshed: optional function
        that is called when the user token is refreshed. You can use this
        function to save the new token.
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
            self.token.user_id,
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
        "RETURN s as stream, collect(c) as creator, collect(u) as seed_users"
    )
    def extract(record) -> Stream:
        stream = record['stream']
        creator = record['creator'][0] # should be one
        seed_users = record['seed_users']
        seed_usernames = [u['username'] for u in seed_users]
        return Stream(stream['name'], creator['username'], seed_usernames)
    return [extract(r) for r in results]


def fetch_streams(driver: Driver) -> List[Stream]:
    """Fetches all streams on the graph database.
    """
    with driver.session() as session:
        streams = session.execute_read(read_all_streams)
        LOGGER.debug('streams: %s', streams)
        return streams


def get_user_token(postgres, username: str) -> Token:
    """Queries the user token of a given user.
    """
    with postgres.cursor() as curs:
        curs.execute(
            'SELECT'
            '  users.id,'
            '  tokens.access_token,'
            '  tokens.refresh_token,'
            '  tokens.created_at,'
            '  tokens.updated_at,'
            '  tokens.expires_in'
            ' FROM users'
            ' INNER JOIN tokens'
            '  ON users.id = tokens.user_id'
            ' WHERE users.username = %(username)s',
            {
                'username': username,
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


def save_user_token(postgres, token: Token):
    """Saves a given user token in the database.
    """
    LOGGER.debug('saving user token: %s', token)
    with postgres.cursor() as curs:
        curs.execute(
            'UPDATE tokens'
            ' SET'
            '  access_token = %(access_token)s,'
            '  refresh_token = %(refresh_token)s,'
            '  expires_in = %(expires_in)s'
            ' WHERE user_id = %(user_id)s',
            {
                'access_token': token.access_token,
                'refresh_token': token.refresh_token,
                'expires_in': token.expires_in,
                'user_id': token.user_id,
            },
        )
        postgres.commit() # TODO: is this necessary?


def get_latest_tweets(twitter: Twarc2, user_id: str):
    """Obtains the latest tweets of a given user.

    :raises requests.exceptions.HTTPError: If there is an error to access the
    Twitter API.
    """
    res = twitter.timeline(
        user=user_id,
        max_results=5,
    )
    for num, tweet in enumerate(res):
        LOGGER.debug('tweet[%d]: %s', num, tweet)


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
        token = get_user_token(postgres, stream.creator)
        LOGGER.debug("using token: %s", token)
        client_id, client_secret = twitter_cred
        twitter = UserTwarc2(
            client_id,
            client_secret,
            token,
            functools.partial(save_user_token, postgres)
        )
        twitter.execute_with_retry_if_unauthorized(
            functools.partial(get_latest_tweets, user_id=token.user_id)
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
    LOGGER.debug('running locally')
    from dotenv import load_dotenv
    logging.basicConfig(level=logging.DEBUG)
    load_dotenv()
    neo4j_uri = os.environ['NEO4J_URI']
    neo4j_username = os.environ['NEO4J_USERNAME']
    neo4j_password = os.environ['NEO4J_PASSWORD']
    driver = GraphDatabase.driver(
        neo4j_uri,
        auth=(neo4j_username, neo4j_password),
    )
    try:
        fetch_streams(driver)
    finally:
        driver.close()


if __name__ == '__main__':
    run_local()
