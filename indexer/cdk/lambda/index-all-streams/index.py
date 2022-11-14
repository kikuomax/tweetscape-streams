# -*- coding: utf-8 -*-

"""Indexes all the Stream nodes on the neo4j database.

You have to specify the following environment variables,
* ``NEO4J_SECRET_ARN``: ARN of the SecretsManager Secret containing neo4j
  connection parameters.
* ``POSTGRES_SECRET_ARN``: ARN of the SecretsManager Secret containing
  PostgreSQL connection parameters.

If you run this function locally, you need the following environment variables
instead,
* ``NEO4J_URI``
* ``NEO4J_USERNAME``
* ``NEO4J_PASSWORD``
* ``DATABASE_URL``: connection URI for the PostgreSQL database.

You can use ``.env`` file to specify them.
It may be in one of parent folders.
"""

import json
import logging
import os
from typing import List, Tuple
import boto3
from neo4j import Driver, GraphDatabase, Transaction # type: ignore
import psycopg2


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

    def __init__(self, user_id: str, access_token: str, refresh_token: str):
        """Initializes with token values.
        """
        self.user_id = user_id
        self.access_token = access_token
        self.refresh_token = refresh_token

    def __str__(self):
        return f'Token(user_id={self.user_id}, access_token={self.access_token[:8]}..., refresh_token={self.refresh_token[:8]}...)'

    def __repr__(self):
        return f'Token(user_id={repr(self.user_id)}, access_token={repr(self.access_token[:8] + "...")}, refresh_token={repr(self.refresh_token[:8] + "...")})'


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
            '  tokens.refresh_token'
            ' FROM users'
            ' INNER JOIN tokens'
            '  ON users.id = tokens.user_id'
            ' WHERE users.username = %(username)s',
            {
                'username': username,
            },
        )
        record = curs.fetchone()
        return Token(record[0], record[1], record[2])


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


def lambda_handler(_event, _context):
    """Runs as a Lambda function.
    """
    LOGGER.debug('running Lambda')
    neo4j_uri, credential = get_neo4j_parameters()
    postgres_uri = get_postgres_uri()
    LOGGER.debug(
        'connecting to neo4j: URI=%s, username=%s, password=%s',
        neo4j_uri,
        credential[0],
        (credential[1] and '****') or 'None',
    )
    driver = GraphDatabase.driver(neo4j_uri, auth=credential)
    try:
        LOGGER.debug('connecting to PostgreSQL')
        postgres = psycopg2.connect(postgres_uri)
        try:
            streams = fetch_streams(driver)
            for stream in streams:
                token = get_user_token(postgres, stream.creator)
                LOGGER.debug("using token: %s", token)
        finally:
            postgres.close()
    finally:
        driver.close()


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
