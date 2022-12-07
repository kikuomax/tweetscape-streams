# -*- coding: utf-8 -*-

"""Utilities to manipulate the graph database.
"""

import functools
from typing import Any, Dict, Optional
from neo4j import Driver, Transaction # type: ignore


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
    """Stream on the graph database.
    """
    name: str
    twitter_list_id: str
    # TODO: add creator and seed accounts

    def __init__(
        self,
        name: str,
        twitter_list_id: str,
    ):
        """Initializes with the stream properties.
        """
        self.name = name
        self.twitter_list_id = twitter_list_id

    @staticmethod
    def parse_node(node: Dict[str, Any]):
        """Parses a given neo4j node.
        """
        return Stream(name=node['name'], twitter_list_id=node['twitterListId'])

    def __str__(self):
        """Returns a string representation.
        """
        return (
            'Stream('
            f'name={self.name}, '
            f'twitter_list_id={self.twitter_list_id}'
            ')'
        )

    def __repr__(self):
        return (
            'Stream('
            f'name={repr(self.name)}, '
            f'twitter_list_id={repr(self.twitter_list_id)}'
            ')'
        )


# TODO: add an option to resolve CREATED and CONTAINS relationships
def get_stream_node_by_name(driver: Driver, stream_name: str) -> Stream:
    """Obtains a Stream node associated with a given name.
    """
    with driver.session() as session:
        stream_node = session.execute_read(
            functools.partial(
                _get_stream_node_by_name,
                stream_name=stream_name,
            ),
        )
        return Stream.parse_node(stream_node)


def _get_stream_node_by_name(
    tx: Transaction,
    stream_name: str,
) -> Dict[str, Any]:
    """Obtains a Stream node associated with a given name.
    """
    results = tx.run(
        '\n'.join([
            'MATCH (stream: Stream {name: $streamName})',
            'RETURN stream',
        ]),
        streamName=stream_name,
    )
    # TODO: handle errors
    # TODO: handle no stream
    record = next(results)
    return record['stream']


def add_seed_account_to_stream_node(
    driver: Driver,
    stream_name: str,
    seed_account_id: str,
) -> SeedAccount:
    """Adds a seed Twitter account to a stream.
    """
    with driver.session() as session:
        seed_account_node = session.execute_write(
            functools.partial(
                _add_seed_account_to_stream_node,
                stream_name=stream_name,
                seed_account_id=seed_account_id,
            ),
        )
        return SeedAccount.parse_node(seed_account_node)


def _add_seed_account_to_stream_node(
    tx: Transaction,
    stream_name: str,
    seed_account_id: str,
) -> Dict[str, Any]:
    """Adds a seed Twitter account to a stream.

    :returns: seed Twitter account node.
    """
    results = tx.run(
        '\n'.join([
            'MATCH (stream: Stream { name: $streamName })',
            'MATCH (account: User { id: $accountId })',
            'MERGE (stream) -[:CONTAINS]-> (account)',
            'RETURN account'
        ]),
        streamName=stream_name,
        accountId=seed_account_id,
    )
    # TODO: handle errors
    # TODO: handle no stream
    # TODO: handle no account
    record = next(results)
    return record['account']


def get_twitter_account_node(driver: Driver, account_id: str) -> TwitterAccount:
    """Obtains a Twitter account node associated with a given ID.
    """
    with driver.session() as session:
        account_node = session.execute_read(
            functools.partial(
                _get_twitter_account_node,
                account_id=account_id,
            ),
        )
        return TwitterAccount.parse_node(account_node)


def _get_twitter_account_node(
    tx: Transaction,
    account_id: str,
) -> Dict[str, Any]:
    """Obtains a Twitter account node associated with a given ID.
    """
    results = tx.run(
        '\n'.join([
            'MATCH (account: User { id: $accountId })',
            'RETURN account',
        ]),
        accountId=account_id,
    )
    # TODO: handle errors
    # TODO: handle no account
    record = next(results)
    return record['account']


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
