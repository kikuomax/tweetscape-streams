# -*- coding: utf-8 -*-

"""Common code resued in Indexer components.
"""

from .external_services import (
    ExternalCredentialError,
    ExternalCredentials,
    connect_neo4j_and_postgres,
)
from .graph import (
    SeedAccount,
    TwitterAccount,
    add_seed_account_to_stream_node,
    get_seed_account_node,
    get_stream_node_by_name,
    get_twitter_account_node,
    reset_indexed_tweet_ids,
    update_latest_indexed_tweet_id,
    upsert_tweet_nodes,
    upsert_twitter_account_node,
    upsert_twitter_account_nodes,
    upsert_twitter_media_nodes,
)
from .twitter import (
    AccountTwarc2,
    flatten_tweet_properties,
    flatten_twitter_account_properties,
    flatten_twitter_media_properties,
    get_latest_tweets_from,
    get_twitter_access_token,
    save_twitter_access_token,
)


VERSION = '0.1.0'
