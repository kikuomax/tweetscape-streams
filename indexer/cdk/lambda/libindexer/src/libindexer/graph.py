# -*- coding: utf-8 -*-

"""Utilities to manipulate the graph database.
"""

import functools
from typing import Any, Dict, Iterable, Optional
from neo4j import Driver, Transaction # type: ignore
from .utils import current_time_string


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
    latest_tweet_id: Optional[str]
    earliest_tweet_id: Optional[str]
    last_follows_index: Optional[str]

    def __init__(
        self,
        account: TwitterAccount,
        latest_tweet_id: Optional[str],
        earliest_tweet_id: Optional[str],
        last_follows_index: Optional[str],
    ):
        """Initializes with seed account attributes.
        """
        super().__init__(account.account_id, account.username)
        self.latest_tweet_id = latest_tweet_id
        self.earliest_tweet_id = earliest_tweet_id
        self.last_follows_index = last_follows_index

    @staticmethod
    def parse_node(node: Dict[str, Any]):
        """Parses a given neo4j node.
        """
        return SeedAccount(
            account=TwitterAccount.parse_node(node),
            latest_tweet_id=node.get('latestTweetId'),
            earliest_tweet_id=node.get('earliestTweetId'),
            last_follows_index=node.get('lastFollowsIndex'),
        )

    def __str__(self):
        return (
            'SeedAccount('
            f'account_id={self.account_id}, '
            f'username={self.username}, '
            f'latest_tweet_id={self.latest_tweet_id}, '
            f'earliest_tweet_id={self.earliest_tweet_id}, '
            f'last_follows_index={self.last_follows_index}'
            ')'
        )

    def __repr__(self):
        return (
            'SeedAccount('
            f'account_id={repr(self.account_id)}, '
            f'username={repr(self.username)}, '
            f'latest_tweet_id={repr(self.latest_tweet_id)}, '
            f'earliest_tweet_id={repr(self.earliest_tweet_id)}, '
            f'last_follows_index={repr(self.last_follows_index)}'
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
    """Obtains the Twitter account node associated with a given ID.
    """
    with driver.session() as session:
        account_node = session.execute_read(
            functools.partial(
                _get_twitter_account_node,
                account_id=account_id,
            ),
        )
        return TwitterAccount.parse_node(account_node)


def get_seed_account_node(driver: Driver, account_id: str) -> SeedAccount:
    """Obtains the seed account node associated with a given ID.
    """
    with driver.session() as session:
        account_node = session.execute_read(
            functools.partial(
                _get_twitter_account_node,
                account_id=account_id,
            ),
        )
        return SeedAccount.parse_node(account_node)


def _get_twitter_account_node(
    tx: Transaction,
    account_id: str,
) -> Dict[str, Any]:
    """Obtains the Twitter account node associated with a given ID.
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
            'MERGE (account:User { id: $a.id })',
            # TODO: replace with _cypher_fragment_copy_account_properties
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


def upsert_twitter_account_nodes(
    driver: Driver,
    accounts: Iterable[Any],
) -> Iterable[TwitterAccount]:
    """Upserts multiple Twitter account nodes.
    """
    with driver.session() as session:
        account_nodes = session.execute_write(
            functools.partial(
                _upsert_twitter_account_nodes,
                accounts=accounts,
            ),
        )
        return [TwitterAccount.parse_node(node) for node in account_nodes]


def _upsert_twitter_account_nodes(
    tx: Transaction,
    accounts: Iterable[Dict[str, Any]],
) -> Iterable[Dict[str, Any]]:
    """Upserts multiple Twitter account nodes.

    Each element of ``accounts`` must be a ``dict`` similar to the following,

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
            'UNWIND $accounts AS a',
            'MERGE (account:User {id: a.id})',
            _cypher_fragment_copy_account_properties('account', 'a'),
            'RETURN account',
        ]),
        accounts=accounts,
    )
    # TODO: handle errors
    return [record['account'] for record in results]


def upsert_twitter_account_nodes_followed_by(
    driver: Driver,
    account_id: str,
    followed_accounts: Iterable[Dict[str, Any]],
) -> Iterable[TwitterAccount]:
    """Upserts Twitter account nodes followed by a given account.

    :param str account_id: ID of a Twitter account who follows
    ``followed_accounts``.

    :param Iterable[Dict[str, Any]]: Twitter accounts followed by
    ``account_id``.
    """
    with driver.session() as session:
        account_nodes = session.execute_write(
            functools.partial(
                _upsert_twitter_account_nodes_followed_by,
                account_id=account_id,
                followed_accounts=followed_accounts,
            ),
        )
        return [TwitterAccount.parse_node(node) for node in account_nodes]


def _upsert_twitter_account_nodes_followed_by(
    tx: Transaction,
    account_id: str,
    followed_accounts: Iterable[Dict[str, Any]],
) -> Iterable[Dict[str, Any]]:
    """Upserts Twitter account nodes followed by a given account.
    """
    results = tx.run(
        '\n'.join([
            'UNWIND $followedAccounts AS followed',
            'MATCH (account:User { id: $accountId })',
            'MERGE (followedNode:User { id: followed.id })',
            _cypher_fragment_copy_account_properties(
                'followedNode',
                'followed',
            ),
            'MERGE (account) -[:FOLLOWS]-> (followedNode)',
            'RETURN followedNode',
        ]),
        accountId=account_id,
        followedAccounts=followed_accounts,
    )
    # TODO: handle errors
    return [record['followedNode'] for record in results]


def _cypher_fragment_copy_account_properties(dest: str, src: str):
    """Returns a cypher fragment that copies properties of a Twitter account.

    ``id`` is not copied because ``dest`` should have been identified with
    ``id``.
    """
    return (
        f'SET {dest}.created_at = {src}.created_at,'
        f'    {dest}.verified = {src}.verified,'
        f'    {dest}.profile_image_url = {src}.profile_image_url,'
        f'    {dest}.name = {src}.name,'
        f'    {dest}.username = {src}.username,'
        f'    {dest}.url = {src}.url,'
        f'    {dest}.description = {src}.description,'
        f'    {dest}.`public_metrics.followers_count` = {src}.`public_metrics.followers_count`,'
        f'    {dest}.`public_metrics.following_count` = {src}.`public_metrics.following_count`,'
        f'    {dest}.`public_metrics.tweet_count` = {src}.`public_metrics.tweet_count`,'
        f'    {dest}.`public_metrics.listed_count` = {src}.`public_metrics.listed_count`'
    )


def update_last_follows_index(driver: Driver, account_id: str) -> SeedAccount:
    """Updates ``lastFollowsIndex`` of a given account.
    """
    with driver.session() as session:
        account_node = session.execute_write(
            functools.partial(
                _update_last_follows_index,
                account_id=account_id,
            ),
        )
        return SeedAccount.parse_node(account_node)


def _update_last_follows_index(
    tx: Transaction,
    account_id: str,
) -> Dict[str, Any]:
    """Updates ``lastFollowsIndex`` of a given account.
    """
    result = tx.run(
        '\n'.join([
            'MERGE (account:User {id: $accountId})',
            'SET account.lastFollowsIndex = $lastFollowsIndex',
            'RETURN account',
        ]),
        accountId=account_id,
        lastFollowsIndex=current_time_string(),
    )
    # TODO: handle errors
    # TODO: handle no account
    return next(result)['account']


def delete_follows_relationships_from(driver: Driver, account_id: str) -> int:
    """Deletes all the "FOLLOWS" relationships from a given Twitter account
    node.

    :returns: number of deleted "FOLLOWS" relationships.
    """
    with driver.session() as session:
        return session.execute_write(
            functools.partial(
                _delete_follows_relationships_from,
                account_id=account_id,
            ),
        )


def _delete_follows_relationships_from(tx: Transaction, account_id: str) -> int:
    """Deletes all the "FOLLOWS" relationships from a given Twitter_ account
    node.

    :returns: number of deleted "FOLLOWS" relationships.
    """
    results = tx.run(
        '\n'.join([
            'MATCH (account:User {id: $accountId})-[r:FOLLOWS]->(:User)',
            'DELETE r',
            'RETURN count(*) AS numDeleted',
        ]),
        accountId=account_id,
    )
    # TODO: handle error
    return next(results)['numDeleted']


def upsert_twitter_media_nodes(
    driver: Driver,
    media_list: Iterable[Dict[str, Any]],
) -> Iterable[Dict[str, Any]]:
    """Upserts multiple Twitter media nodes.
    """
    with driver.session() as session:
        return session.execute_write(
            functools.partial(
                _upsert_twitter_media_nodes,
                media_list=media_list,
            ),
        )


def _upsert_twitter_media_nodes(
    tx: Transaction,
    media_list: Iterable[Dict[str, Any]],
) -> Iterable[Dict[str, Any]]:
    """Upserts multiple Twitter media nodes.
    """
    results = tx.run(
        '\n'.join([
            'UNWIND $media AS m',
            'MERGE (mediaNode:Media { media_key: m.media_key })',
            'SET mediaNode = m',
            'RETURN mediaNode',
        ]),
        media=media_list,
    )
    # TODO: handle errors
    return [record['mediaNode'] for record in results]


def upsert_tweet_nodes(
    driver: Driver,
    tweets: Iterable[Dict[str, Any]],
) -> Iterable[Dict[str, Any]]:
    """Upserts multiple tweet nodes.
    """
    with driver.session() as session:
        return session.execute_write(
            functools.partial(
                _upsert_tweet_nodes,
                tweets=tweets,
            ),
        )


def _upsert_tweet_nodes(
    tx: Transaction,
    tweets: Iterable[Dict[str, Any]],
) -> Iterable[Dict[str, Any]]:
    """Upserts multiple tweet nodes.
    """
    results = tx.run(
        '\n'.join([
            'UNWIND $tweets AS t',
            'MERGE (tweet:Tweet { id: t.id })',
            'SET tweet.conversation_id = t.conversation_id,'
            '    tweet.possibly_sensitive = t.possibly_sensitive,'
            '    tweet.in_reply_to_user_id = t.in_reply_to_user_id,'
            '    tweet.lang = t.lang,'
            '    tweet.text = t.text,'
            '    tweet.created_at = t.created_at,'
            '    tweet.reply_settings = t.reply_settings,'
            '    tweet.author_id = t.author_id,'
            '    tweet.`public_metrics.retweet_count` = t.`public_metrics.retweet_count`,'
            '    tweet.`public_metrics.reply_count` = t.`public_metrics.reply_count`,'
            '    tweet.`public_metrics.like_count` = t.`public_metrics.like_count`,'
            '    tweet.`public_metrics.quote_count` = t.`public_metrics.quote_count`',
            'MERGE (author:User { id: t.author_id })',
            'MERGE (author) -[:POSTED]-> (tweet)',
            'FOREACH (m IN t.entities.mentions |',
            '    MERGE (mentioned:User { username: m.username })',
            '    MERGE (tweet) -[:MENTIONED]-> (mentioned)',
            ')',
            'FOREACH (u IN t.entities.urls |',
            '    MERGE (url:Link { url: u.url })',
            '    SET url.start = u.start,'
            '        url.end = u.end,'
            '        url.expanded_url = u.expanded_url,'
            '        url.display_url = u.display_url,'
            '        url.media_key = u.media_key',
            '    MERGE (tweet) -[:LINKED]-> (url)',
            ')',
            'FOREACH (a IN t.entities.annotations |',
            '    MERGE (annotation:Annotation {'
            '        probability: a.probability,'
            '        type: a.type,'
            '        normalized_text: a.normalized_text'
            '    })',
            '    MERGE (tweet) -[:ANNOTATED]-> (annotation)',
            ')',
            'FOREACH (ca IN t.context_annotations |',
            '    MERGE (domain:Domain { id: ca.domain.id })',
            '    SET domain = ca.domain',
            '    MERGE (entity:Entity { id: ca.entity.id })',
            '    SET entity = ca.entity',
            '    MERGE (tweet) -[:INCLUDED]-> (entity)',
            '    MERGE (entity) -[:CATEGORY]-> (domain)',
            ')',
            'FOREACH (h IN t.entities.hashtags |',
            '    MERGE (hashtag:Hashtag { tag: h.tag })',
            '    MERGE (tweet) -[:TAG]-> (hashtag)',
            ')',
            'FOREACH (c IN t.entities.cashtags |',
            '    MERGE (cashtag:Cashtag { tag: c.tag })',
            '    MERGE (tweet) -[:TAG]-> (cashtag)',
            ')',
            'FOREACH (a IN t.attachments |',
            '    FOREACH (media_key in a.media_keys |',
            '        MERGE (media:Media { media_key: media_key })',
            '        MERGE (tweet) -[:ATTACHED]-> (media)',
            '    )',
            ')',
            'FOREACH (r IN t.referenced_tweets |',
            '    MERGE (ref_t:Tweet { id: r.id })',
            '    MERGE (tweet) -[:REFERENCED{type:r.type}]-> (ref_t)',
            ')',
            'RETURN tweet',
        ]),
        tweets=tweets,
    )
    # TODO: handle errors
    return [record['tweet'] for record in results]


def reset_indexed_tweet_ids(
    driver: Driver,
    account: SeedAccount,
    latest_tweet_id: str,
    earliest_tweet_id: str,
) -> SeedAccount:
    """Resets the indexed tweet range of a given seed account on the graph
    database.
    """
    with driver.session() as session:
        account_node = session.execute_write(
            functools.partial(
                _update_indexed_tweet_ids,
                account_id=account.account_id,
                latest_tweet_id=latest_tweet_id,
                earliest_tweet_id=earliest_tweet_id,
            )
        )
        return SeedAccount.parse_node(account_node)


def update_latest_indexed_tweet_id(
    driver: Driver,
    account: SeedAccount,
    latest_tweet_id: str,
) -> SeedAccount:
    """Updates the latest indexed tweet ID of a given seed account on the graph
    database.

    :raises ValueError: if ``account`` does not have ``earliest_tweet_id``.
    """
    if account.earliest_tweet_id is None:
        raise ValueError('accound must have earliest_tweet_id')
    with driver.session() as session:
        account_node = session.execute_write(
            functools.partial(
                _update_indexed_tweet_ids,
                account_id=account.account_id,
                latest_tweet_id=latest_tweet_id,
                earliest_tweet_id=account.earliest_tweet_id,
            )
        )
        return SeedAccount.parse_node(account_node)


def _update_indexed_tweet_ids(
    tx: Transaction,
    account_id: str,
    latest_tweet_id: str,
    earliest_tweet_id: str,
) -> Dict[str, Any]:
    """Writes indexed tweet IDs of a given seed account to the graph database.
    """
    results = tx.run(
        '\n'.join([
            'MATCH (account:User { id: $accountId })',
            'SET account.latestTweetId = $latestTweetId',
            'SET account.earliestTweetId = $earliestTweetId',
            'RETURN account',
        ]),
        accountId=account_id,
        latestTweetId=latest_tweet_id,
        earliestTweetId=earliest_tweet_id,
    )
    # TODO: handle errors
    # TODO: handle no account
    record = next(results)
    return record['account']
