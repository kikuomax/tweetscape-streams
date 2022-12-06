# -*- coding: utf-8 -*-

"""Provides utilities to connect to external services.
"""

import contextlib
import json
from typing import Any, Dict, Generator, Tuple
import neo4j # type: ignore
import psycopg2 # type: ignore
from .exceptions import LibIndexerException


class ExternalCredentials:
    """Caches credentials for external services.

    You have to call ``refresh`` to discard cached credentials.
    """
    secret_arn: str
    credentials: Dict[str, str]

    def __init__(self, s3_secrets, secret_arn: str):
        """Initializes with the ARN of a secret containing the credentials.

        Loads the credentials from the secret.
        The secret has to be a JSON object similar to the following,

        .. code-block:: python

            {
                'neo4jUri': 'URI of the neo4j database',
                'neo4jUsername': 'username to connect to the neo4j database',
                'neo4jPassword': 'password to connect to the neo4j database',
                'postgresUri': 'URI of the PostgreSQL database',
                'clientId': 'client ID of the Twitter client app',
                'clientSecret': 'client secret of the Twitter client app'
            }

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


class ExternalCredentialError(LibIndexerException):
    """Error raised when an error has occurred around external credentials.
    """


@contextlib.contextmanager
def connect_neo4j_and_postgres(credentials: ExternalCredentials) -> Generator[
    Tuple[neo4j.Driver, Any],
    None,
    None,
]:
    """Connects to neo4j, and PostgreSQL.

    Call this function in a ``with`` context.

    :returns: tuple of neo4j.Driver and PostgreSQL connection.

    :raises ExternalCredentialError: if connection to neo4j or PostgreSQL has
    failed. You should retry after refreshing credentials.
    """
    try:
        neo4j_driver = neo4j.GraphDatabase.driver(
            credentials.neo4j_uri,
            auth=credentials.neo4j_cred,
        )
    except neo4j.exceptions.AuthError as exc:
        raise ExternalCredentialError('failed to connect to neo4j') from exc
    else:
        try:
            postgres = psycopg2.connect(credentials.postgres_uri)
        except psycopg2.Error as exc:
            raise ExternalCredentialError('failed to connect to PostgreSQL') from exc
        else:
            try:
                yield neo4j_driver, postgres
            finally:
                postgres.close()
        finally:
            neo4j_driver.close()
