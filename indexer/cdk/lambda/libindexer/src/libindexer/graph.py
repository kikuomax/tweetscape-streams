# -*- coding: utf-8 -*-

"""Utilities to manipulate the graph database.
"""

from typing import Any, Dict
from neo4j import Transaction # type: ignore


class TwitterAccount:
    """Twitter account on the graph database.
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


def upsert_twitter_account_node(
    tx: Transaction,
    account: Dict[str, Any],
) -> TwitterAccount:
    """Upserts a single Twitter account node.

    ``account`` should be a ``dict`` similar to the following,

    .. code-block:: python

        {
            'id': '66780587',
            'created_at': '2009-08-18T19:52:16.000Z',
            'verified': True,
            'profile_image_url': 'https://pbs.twimg.com/profile_images/1594006230397091840/dC0hcgTQ_normal.png',
            'name': 'Amazon Web Services',
            'username': 'awscloud',
            'url': 'https://t.co/Ig9jO3HXAd',
            'description': 'AWS #reInvent | Nov 28. - Dec. 2 | For support, please visit @AWSSupport.',
            'public_metrics.followers_count': 2117917,
            'public_metrics.following_count': 1004,
            'public_metrics.tweet_count': 38104,
            'public_metrics.listed_count': 9433
        }
    """
    results = tx.run(
        '\n'.join([
            'MERGE (account:User {id: $a.id})',
            'SET account.id = $a.id,'
            '    account.created_at = $a.created_at,'
            '    account.verified = $a.verified,'
            '    account.profile_image_url = $a.profile_image_url,'
            '    account.name = $a.name,'
            '    account.username = $a.username,'
            '    account.url = $a.url,'
            '    account.description = $a.description,'
            '    account.`public_metrics.followers_count` = $a.`public_metrics.followers_count`,'
            '    account.`public_metrics.following_count` = $a.`public_metrics.following_count`,'
            '    account.`public_metrics.tweet_count` = $a.`public_metrics.tweet_count`,'
            '    account.`public_metrics.listed_count` = $a.`public_metrics.listed_count`',
            'RETURN account',
        ]),
        a=account,
    )
    # TODO: handle errors
    record = next(results)
    return TwitterAccount.parse_node(record['account'])
