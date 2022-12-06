# -*- coding: utf-8 -*-

"""Indexes all the Stream nodes on the neo4j database.

You have to specify the following environment variables if you run this function
on AWS,
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
It may be in the current folder or one of parent folders.

You can specify the following optional environment variable,
* ``TIMELINE_PAGE_SIZE``: number of tweets in a timeline page; i.e., tweets
  requested in a single query. 100 by default.
"""

import functools
import itertools
import json
import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple
import libindexer
from libindexer import (
    AccountTwarc2,
    TwitterAccount,
    flatten_twitter_account_properties,
    get_twitter_access_token,
    save_twitter_access_token,
)
from neo4j import Driver, GraphDatabase, Transaction # type: ignore
import psycopg2
# import requests
from twarc import Twarc2 # type: ignore


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

TIMELINE_PAGE_SIZE = int(os.environ.get('TIMELINE_PAGE_SIZE', 100))

# parameters given to Twarc2.timeline
TIMELINE_PARAMETERS = {
    'expansions': ','.join([
        'author_id',
        'in_reply_to_user_id',
        'referenced_tweets.id',
        'referenced_tweets.id.author_id',
        'entities.mentions.username',
        'attachments.poll_ids',
        'attachments.media_keys',
        'geo.place_id',
    ]),
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
    'media_fields': ','.join([
        'alt_text',
        'duration_ms',
        'height',
        'media_key',
        'preview_image_url',
        'type',
        'url',
        'width',
        'public_metrics',
    ]),
    'poll_fields': ','.join([
        'duration_minutes',
        'end_datetime',
        'id',
        'options',
        'voting_status',
    ]),
    'place_fields': ','.join([
        'contained_within',
        'country',
        'country_code',
        'full_name',
        'geo',
        'id',
        'name',
        'place_type',
    ]),
}

if __name__ != '__main__':
    import boto3
    secrets = boto3.client('secretsmanager')


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
    seed_accounts: List[SeedAccount]

    def __init__(
        self,
        name: str,
        creator: TwitterAccount,
        seed_accounts: List[SeedAccount],
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


class TweetsPage:
    """Wraps a tweets page objects with handy properties.
    """
    page: Dict[str, Any]

    def __init__(self, page: Dict[str, Any]):
        """Initializes with a given tweets page object.
        """
        self.page = page

    @property
    def tweets(self) -> Iterable[Any]:
        """Tweets in this page.
        """
        return self.page['data']

    @property
    def includes(self) -> Dict[str, Any]:
        """"includes" object.

        An empty ``dict`` if this page has no "includes" object.
        """
        return self.page.get('includes') or {}

    @property
    def included_users(self) -> Iterable[Any]:
        """Users (Twitter accounts) included in this page.

        An empty iterable if this page includes no users.
        """
        return self.includes.get('users') or []

    @property
    def included_tweets(self) -> Iterable[Any]:
        """Tweets included in this page.

        An empty iterable if this page includes no tweets.
        """
        return self.includes.get('tweets') or []

    @property
    def included_media(self) -> Iterable[Any]:
        """Media included in this page.

        An empty iterable if this page includes no media.
        """
        return self.includes.get('media') or []


class TweetsRange:
    """Iterates over pages of tweets and remembers the tweet ID range.

    You can use an instance of this class as an iterator of tweets.
    """
    pages: Iterable[Any]
    _latest_tweet_id: Optional[str]
    _earliest_tweet_id: Optional[str]
    exhausted: bool

    def __init__(self, pages: Iterable[Any]):
        """Initializes with an iterable of tweet pages.
        """
        self.pages = pages
        self._latest_tweet_id = None
        self._earliest_tweet_id = None
        self.exhausted = False

    def __iter__(self):
        """Returns an iterator of all the items.
        """
        for page in self.pages:
            page_data = page['data']
            if self._latest_tweet_id is None:
                self._latest_tweet_id = page_data[0]['id']
            self._earliest_tweet_id = page_data[-1]['id']
            yield TweetsPage(page)
        self.exhausted = True

    @property
    def latest_tweet_id(self) -> str:
        """Latest tweet ID.

        :raises AttributeError: if the iteration over tweets has not done yet,
        or if no page was given.
        """
        if not self.exhausted:
            raise AttributeError('tweet iteration has not done yet!')
        latest_tweet_id = self._latest_tweet_id
        if latest_tweet_id is None:
            raise AttributeError(
                'latest tweet ID is not available because no page was given',
            )
        return latest_tweet_id

    @property
    def earliest_tweet_id(self) -> str:
        """Earliest tweet ID.

        :raises AttributeError: if the iteration over tweets has not done yet,
        or if no page was given.
        """
        if not self.exhausted:
            raise AttributeError('tweet iteration has not done yet!')
        earliest_tweet_id = self._earliest_tweet_id
        if earliest_tweet_id is None:
            raise AttributeError(
                'earliest tweet ID is not available because no page was given',
            )
        return earliest_tweet_id


def flatten_twitter_media_properties(media: Dict[str, Any]) -> Dict[str, Any]:
    """Flattens properties of a given Twitter media object.

    This function modifies ``media``.
    """
    if 'public_metrics' in media:
        libindexer.twitter.flatten_key_value_pairs(media, 'public_metrics')
    return media


def flatten_tweet_properties(tweet: Dict[str, Any]) -> Dict[str, Any]:
    """Flattens properties of a given tweet object.

    This function modifies ``tweet``.
    """
    return libindexer.twitter.flatten_key_value_pairs(tweet, 'public_metrics')


def read_all_streams(tx: Transaction) -> List[Stream]:
    """Reads all streams on the graph database.
    """
    results = tx.run('\n'.join([
        "MATCH (s:Stream)-[:CONTAINS]->(u:User)",
        "MATCH (c:User)-[:CREATED]->(s)",
        "RETURN s as stream, collect(c) as creator, collect(u) as seedAccounts",
    ]))
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
        return streams


def write_twitter_accounts(tx: Transaction, accounts: Iterable[Any]):
    """Writes given Twitter accounts to the graph database.
    """
    results = tx.run(
        '\n'.join([
            'UNWIND $accounts AS a',
            'MERGE (account:User {username: a.username})',
            'SET account.id = a.id,',
            '    account.created_at = a.created_at,',
            '    account.verified = a.verified,',
            '    account.profile_image_url = a.profile_image_url,',
            '    account.name = a.name,',
            '    account.username = a.username,',
            '    account.url = a.url,',
            '    account.description = a.description,',
            '    account.`public_metrics.followers_count` = a.`public_metrics.followers_count`,',
            '    account.`public_metrics.following_count` = a.`public_metrics.following_count`,',
            '    account.`public_metrics.tweet_count` = a.`public_metrics.tweet_count`,',
            '    account.`public_metrics.listed_count` = a.`public_metrics.listed_count`',
            'RETURN account',
        ]),
        accounts=accounts,
    )
    for record in results:
        account_node = record['account']
        LOGGER.debug('added user: %s', TwitterAccount.parse_node(account_node))


def add_twitter_accounts(driver: Driver, accounts: Iterable[Any]):
    """Adds given Twitter accounts to the graph database.
    """
    with driver.session() as session:
        session.execute_write(
            functools.partial(write_twitter_accounts, accounts=accounts),
        )


def write_media(tx: Transaction, media_list: Iterable[Any]):
    """Writes given media objects to the graph database.
    """
    results = tx.run(
        '\n'.join([
            'UNWIND $media AS m',
            'MERGE (mediaNode:Media {media_key: m.media_key})',
            'SET mediaNode = m',
            'RETURN mediaNode',
        ]),
        media=media_list,
    )
    for record in results:
        media_node = record['mediaNode']
        LOGGER.debug(
            'added media: key=%s, type=%s',
            media_node['media_key'],
            media_node['type'],
        )


def add_media(driver: Driver, media_list: Iterable[Any]):
    """Adds given media objects to the graph database.
    """
    with driver.session() as session:
        session.execute_write(
            functools.partial(write_media, media_list=media_list),
        )


def write_tweets_from(tx: Transaction, tweet_list: Iterable[Any]):
    """Writes given tweet objects to the graph database.
    """
    results = tx.run(
        '\n'.join([
            'UNWIND $tweets AS t',
            'MERGE (tweet:Tweet {id: t.id})',
            'SET tweet.id = t.id,'
            '    tweet.conversation_id = t.conversation_id,'
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
            'MERGE (author:User {id: t.author_id})',
            'MERGE (author)-[:POSTED]->(tweet)',
            'FOREACH (m IN t.entities.mentions |',
            '    MERGE (mentioned:User {username: m.username})',
            '    MERGE (tweet)-[:MENTIONED]->(mentioned)',
            ')',
            'FOREACH (u IN t.entities.urls |',
            '    MERGE (url:Link {url: u.url})',
            '    SET url.start = u.start,'
            '        url.end = u.end,'
            '        url.url = u.url,'
            '        url.expanded_url = u.expanded_url,'
            '        url.display_url = u.display_url,'
            '        url.media_key = u.media_key',
            '    MERGE (tweet)-[:LINKED]->(url)',
            ')',
            'FOREACH (a IN t.entities.annotations |',
            '    MERGE (annotation:Annotation {'
            '        probability: a.probability,'
            '        type: a.type,'
            '        normalized_text: a.normalized_text'
            '    })',
            '    MERGE (tweet)-[:ANNOTATED]->(annotation)',
            ')',
            'FOREACH (ca IN t.context_annotations |',
            '    MERGE (domain:Domain {id: ca.domain.id})',
            '    SET domain = ca.domain',
            '    MERGE (entity:Entity {id: ca.entity.id})',
            '    SET entity = ca.entity',
            '    MERGE (tweet)-[:INCLUDED]->(entity)',
            '    MERGE (entity)-[:CATEGORY]->(domain)',
            ')',
            'FOREACH (h IN t.entities.hashtags |',
            '    MERGE (hashtag:Hashtag {tag: h.tag})',
            '    MERGE (tweet)-[:TAG]->(hashtag)',
            ')',
            'FOREACH (c IN t.entities.cashtags |',
            '    MERGE (cashtag:Cashtag {tag: c.tag})',
            '    MERGE (tweet)-[:TAG]->(cashtag)',
            ')',
            'FOREACH (a IN t.attachments |',
            '    FOREACH (media_key in a.media_keys |',
            '        MERGE (media:Media {media_key: media_key})',
            '        MERGE (tweet)-[:ATTACHED]->(media)',
            '    )',
            ')',
            'FOREACH (r IN t.referenced_tweets |',
            '    MERGE (ref_t:Tweet {id: r.id})',
            '    MERGE (tweet)-[:REFERENCED{type:r.type}]->(ref_t)',
            ')',
            'RETURN tweet',
        ]),
        tweets=tweet_list,
    )
    for record in results:
        tweet_node = record['tweet']
        LOGGER.debug(
            'added tweet: id=%s, text=%s',
            tweet_node['id'],
            tweet_node.get('text', ''),
        )


def add_tweets_from(driver: Driver, tweet_list: Iterable[Any]):
    """Adds given tweet objects to the graph database.
    """
    with driver.session() as session:
        session.execute_write(
            functools.partial(write_tweets_from, tweet_list=tweet_list),
        )


def write_indexed_tweet_ids(
    tx: Transaction,
    account_id: str,
    latest_tweet_id: str,
    earliest_tweet_id: str,
):
    """Writes indexed tweet IDs of a given seed account to the graph database.
    """
    results = tx.run(
        '\n'.join([
            'MERGE (a:User {id: $accountId})',
            'SET a.latestTweetId = $latestTweetId',
            'SET a.earliestTweetId = $earliestTweetId',
            'RETURN a',
        ]),
        accountId=account_id,
        latestTweetId=latest_tweet_id,
        earliestTweetId=earliest_tweet_id,
    )
    for record in results:
        LOGGER.debug(
            'wrote indexed tweet IDs: %s',
            SeedAccount.parse_node(record['a']),
        )


def reset_indexed_tweet_ids(
    driver: Driver,
    account: SeedAccount,
    latest_tweet_id: str,
    earliest_tweet_id: str,
):
    """Resets the indexed tweet range of a given seed account on the graph
    database.
    """
    LOGGER.debug('resetting indexed tweet range of %s', account.username)
    with driver.session() as session:
        session.execute_write(
            functools.partial(
                write_indexed_tweet_ids,
                account_id=account.account_id,
                latest_tweet_id=latest_tweet_id,
                earliest_tweet_id=earliest_tweet_id,
            )
        )


def update_latest_indexed_tweet_id(
    driver: Driver,
    account: SeedAccount,
    latest_tweet_id: str,
):
    """Updates the latest indexed tweet ID of a given seed account on the graph
    database.
    """
    LOGGER.debug('updating indexed tweet ID of %s', account.username)
    assert account.earliest_tweet_id is not None
    with driver.session() as session:
        session.execute_write(
            functools.partial(
                write_indexed_tweet_ids,
                account_id=account.account_id,
                latest_tweet_id=latest_tweet_id,
                earliest_tweet_id=account.earliest_tweet_id,
            )
        )


def pull_tweets(
    twitter: Twarc2,
    account_id: str,
    since_id: Optional[str]=None,
    page_size=TIMELINE_PAGE_SIZE,
) -> TweetsRange:
    """Obtains tweets posted since a given tweet ID.

    Pulls as many tweets as possible regardless of ``page_size`` if ``since_id``
    is specified. Since the Twitter API orders tweets from newer to older, all
    the tweets since ``since_id`` may not fit in a single page.

    Pulls a single page of tweets if ``since_id`` is omitted.

    :param int page_size: maximum number of tweets included in a single page.
    Must be ≥ 5.

    :raises requests.exceptions.HTTPError: if there is an error to access the
    Twitter API.
    """
    # TODO: support until_id
    res = twitter.timeline(
        user=account_id,
        max_results=page_size,
        since_id=since_id,
        **TIMELINE_PARAMETERS,
    )
    if since_id is None:
        pages = itertools.islice(res, 1) # at most one page
    else:
        pages = res
    return TweetsRange(pages)


def get_latest_tweets(twitter: Twarc2, account: SeedAccount) -> TweetsRange:
    """Obtains the latest tweets of a given seed Twitter account.

    :raises requests.exceptions.HTTPError: If there is an error to access the
    Twitter API.
    """
    latest_tweet_id = account.latest_tweet_id
    if account.earliest_tweet_id is None:
        # resets a half-open range with the latest tweets
        latest_tweet_id = None
    return pull_tweets(
        twitter,
        account.account_id,
        since_id=latest_tweet_id,
    )


def index_latest_tweets_from(
    twitter: Twarc2,
    neo4j_driver: Driver,
    account: SeedAccount,
):
    """Indexes the latest tweets from a given seed account.

    :raises request.exceptions.HTTPError: If there is an error to access the
    Twitter API.
    """
    tweets_range = get_latest_tweets(twitter, account)
    # processes tweets and included objects
    # TODO: make them async
    updated = False
    for tweets_page in tweets_range:
        add_twitter_accounts(
            neo4j_driver,
            [flatten_twitter_account_properties(a)
                for a in tweets_page.included_users],
        )
        add_media(
            neo4j_driver,
            [flatten_twitter_media_properties(m)
                for m in tweets_page.included_media],
        )
        add_tweets_from(
            neo4j_driver,
            [flatten_tweet_properties(t)
                for t in tweets_page.included_tweets],
        )
        add_tweets_from(
            neo4j_driver,
            [flatten_tweet_properties(t) for t in tweets_page.tweets],
        )
        updated = True
    # updates the indexed tweet range of the seed account
    if updated:
        if account.earliest_tweet_id is None:
            # resets the full range
            reset_indexed_tweet_ids(
                neo4j_driver,
                account=account,
                latest_tweet_id=tweets_range.latest_tweet_id,
                earliest_tweet_id=tweets_range.earliest_tweet_id,
            )
        else:
            # updates only the latest
            update_latest_indexed_tweet_id(
                neo4j_driver,
                account,
                tweets_range.latest_tweet_id,
            )
    else:
        LOGGER.debug('no newer tweets from %s', account.username)


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
    # TODO: handle rate limit.
    # and we should equally distribute rate limit to streams.
    # how about to randomly choose streams?
    for stream in streams:
        LOGGER.debug('processing stream: %s', stream)
        token = get_twitter_access_token(postgres, stream.creator.account_id)
        LOGGER.debug("using token: %s", token)
        twitter = AccountTwarc2(
            twitter_cred,
            token,
            functools.partial(save_twitter_access_token, postgres)
        )
        # TODO: de-duplicate seed accounts
        for seed_account in stream.seed_accounts:
            LOGGER.debug('getting latest tweets from %s', seed_account.username)
            twitter.execute_with_retry_if_unauthorized(
                functools.partial(
                    index_latest_tweets_from,
                    neo4j_driver=neo4j_driver,
                    account=seed_account,
                ),
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
