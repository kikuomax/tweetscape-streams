# -*- coding: utf-8 -*-

"""Indexes all the Stream nodes on the neo4j database.

You have to specify the following environment variables,
* ``NEO4J_SECRET_ARN``: ARN of the SecretsManager Secret containing neo4j
  connection parameters.

If you run this function locally, you need the following environment variables
instead,
* ``NEO4J_URI``
* ``NEO4J_USERNAME``
* ``NEO4J_PASSWORD``

You can use ``.env`` file to specify them.
It may be in one of parent folders.
"""

import json
import logging
import os
from typing import Tuple
import boto3
from neo4j import Driver, GraphDatabase, Transaction # type: ignore


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

secrets = boto3.client('secretsmanager')


def read_all_streams(tx: Transaction):
    """Reads all streams on the graph database.
    """
    results = tx.run(
        "MATCH (s:Stream)-[:CONTAINS]->(u:User)"
        "RETURN s, collect(u) as seedUsers"
    )
    for record in results:
        stream = record['s']
        seed_users = record['seedUsers']
        print(f'stream: {stream["name"]} with seed users {[u["username"] for u in seed_users]}')


def fetch_streams(driver: Driver):
    """Fetches all streams on the graph database.
    """
    with driver.session() as session:
        session.execute_read(read_all_streams)


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


def lambda_handler(_event, _context):
    """Runs as a Lambda function.
    """
    LOGGER.debug('running Lambda')
    neo4j_uri, credential = get_neo4j_parameters()
    LOGGER.debug(
        'connecting to neo4j: URI=%s, username=%s, password=%s',
        neo4j_uri,
        credential[0],
        (credential[1] and '****') or 'None',
    )
    driver = GraphDatabase.driver(neo4j_uri, auth=credential)
    try:
        fetch_streams(driver)
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
