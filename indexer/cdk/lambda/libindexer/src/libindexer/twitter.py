# -*- coding: utf-8 -*-

"""Utilities related to Twitter.
"""

import datetime
from typing import Any, Callable, Dict, Tuple
import pytz
import requests
from twarc import Twarc2 # type: ignore


class AccessToken:
    """Represents an access token of a specific Twitter account.

    Also includes the refresh token.
    """
    account_id: str
    access_token: str
    refresh_token: str

    def __init__(
        self,
        account_id: str,
        access_token: str,
        refresh_token:str,
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
            'AccessToken('
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
            'AccessToken('
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
    given Twitter account.
    """
    client_id: str
    client_secret: str
    token: AccessToken
    on_token_refreshed: Callable[[AccessToken], None]
    api: Twarc2

    def __init__(
        self,
        client_cred: Tuple[str, str],
        token: AccessToken,
        on_token_refreshed: Callable[[AccessToken], None],
    ):
        """Initializes with a given Twitter client credential, and an access
        token.

        :param Tuple[str, str] client_cred: tuple of a Twitter client ID and
        secret.

        :param AccessToken token: initial access token.

        :param Callable[[AccessToken], None]? on_token_refreshed: function that
        is called when the access token is refreshed. You can use this function
        to save the new access token.
        """
        self.client_id, self.client_secret = client_cred
        self.token = token
        self.on_token_refreshed = on_token_refreshed
        self.api = Twarc2(bearer_token=token.access_token)

    def execute_with_retry_if_unauthorized(self, func: Callable[[Twarc2], Any]):
        """Runs a given function with a retry.

        If ``func`` fails with 401 (unauthorized) status code, this function
        refreshes the access token and calls ``func`` again.
        Retries only once.

        :param Callable[[Twarc2], Any] func: function to access the Twitter API.
        An instance of ``twarc.Twarc2`` with the access token is supplied.

        :returns: any value returned from ``func``.

        :raises requests.exceptions.HTTPError: if there is an error with the
        Twitter API access.
        """
        try:
            return func(self.api)
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 401:
                # refreshes the access token and retries
                try:
                    self.refresh_access_token()
                except requests.exceptions.HTTPError as exc2:
                    if exc2.response.status_code == 400:
                        # refresh token may be out of sync
                        # TODO: raise specific exception
                        print(
                            'refresh token may be out of sync. you have to'
                            ' reset tokens by logging in to the'
                            ' tweetscape-streams app on a browser',
                        )
                    raise
                else:
                    return func(self.api)
            raise

    def refresh_access_token(self):
        """Refreshes the Twitter access token.

        Updates also the refresh token.

        Updates also the Twarc2 instance.

        :raises requests.exception.HTTPError: if there is an error with the
        Twitter API access.
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
        self.token = AccessToken(
            self.token.account_id,
            token_json['access_token'],
            token_json['refresh_token'],
            self.token.created_at,
            current_time_string(),
            token_json['expires_in'],
        )
        self.api = Twarc2(bearer_token=self.token.access_token)
        self.on_token_refreshed(self.token)


def current_time_string():
    """Formats a string that represents the current time.

    Use this function to produce ``updated_at`` of a token record.
    """
    now = datetime.datetime.now(pytz.utc)
    datetime_str = now.strftime('%Y-%m-%d %H:%M:%S')
    microsecond_str = f'{now.microsecond * 0.000001:.6f}'[1:] # drops leading 0
    return f'{datetime_str}{microsecond_str}+00:00'


def get_twitter_access_token(postgres, account_id: str) -> AccessToken:
    """Obtains the access token of a given Twitter account from the PostgreSQL
    database.

    :param psycopg2.connection postgres: connection to the PostgreSQL database.
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
                'account_id': account_id,
            },
        )
        # TODO: handle errors
        record = curs.fetchone()
        return AccessToken(
            record[0],
            record[1],
            record[2],
            record[3],
            record[4],
            record[5],
        )


def save_twitter_access_token(postgres, token: AccessToken):
    """Saves a given access token in the PostgreSQL database.

    :param psycopg2.connection postgres: connection to the PostgreSQL database.
    """
    with postgres.cursor() as curs:
        curs.execute(
            'UPDATE tokens'
            ' SET'
            '  access_token = %(access_token)s,'
            '  refresh_token = %(refresh_token)s,'
            '  expires_in = %(expires_in)s,'
            '  updated_at = %(updated_at)s'
            ' WHERE user_id = %(account_id)s',
            {
                'access_token': token.access_token,
                'refresh_token': token.refresh_token,
                'expires_in': token.expires_in,
                'updated_at': token.updated_at,
                'account_id': token.account_id,
            },
        )
        postgres.commit() # is this necessary?


def flatten_key_value_pairs(
    obj: Dict[str, Any],
    property_name: str,
) -> Dict[str, Any]:
    """Flattens a specified property of a given object.

    This function mutates ``obj``.
    """
    for key, value in obj[property_name].items():
        obj[f'{property_name}.{key}'] = value
    del obj[property_name]
    return obj


def flatten_twitter_account_properties(
    account: Dict[str, Any],
) -> Dict[str, Any]:
    """Flattens properties of a given Twitter account object.

    This function mutates ``account``.

    :param Dict[str, Any] account: account information to flatten.
    """
    account['username'] = account['username'].lower()
    flatten_key_value_pairs(account, 'public_metrics')
    if 'entities' in account:
        del account['entities']
    return account
