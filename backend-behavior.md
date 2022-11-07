# Backend behavior

Focusing on the main (details) pane on the right-hand side for now.

## /routes/index.tsx

### loader

Just redirects to [`/streams`](#routesstreamstsx).

### action

No action.

## /routes/streams.tsx

### loader

#### not logged in (uid == null)

Prompts the user to login with the Tiwtter account.
Please refer to [`/streams/index.tsx`](#routesstreamsindextsx).

This is also the redirect destination for the OAuth on Twitter.
When a Twitter account is authenticated, updates the user info on the PostgreSQL database.
It also pushes user's Twitter token to the PostgreSQL database.

#### already logged in (uid != null)

Requests Twitter for the user info.

- Obtains streams created by the user ([`getUserStreams`](#getuserstreams)).
- Obtains streams created by other users ([`getAllStreams`](#getallstreams)).

### action

No action.

## /routes/streams/index.tsx

### loader

No loader.

#### not logged in (user == null)

Shows a login button.

#### already logged in (user != null)

Shows a new stream button.

### action

- Checks if the stream exists ([`getStreamByName`](#getstreambyname)).
- Obtains the user info from Twitter.
- Creates the user if necessary.
- Creates a Twitter list.
- Creates a new stream ([`createStream`](#createstream)).
- Redirects to [`/streams/$streamName`](#routesstreamsstreamname).

## /routes/streams/$streamName

### loader

- Obtains the stream ([`getStreamByName`](#getstreambyname)).
- Obtains the user info from Twitter.
- Obtains the Twitter list corresponding to the stream.
    - Creates a Twitter list if the stream is legacy and recreates a new stream ([`createStream`](#createstream)).
    - Recreates a Twitter list if it was deleted and recreates a new stream ([`createStrea`](#createstream)).
- Indexes older tweets with [`indexMoreTweets`](#indexmoretweets) if `indexMoreTweets` query parameter is given
- Indexes newer tweets with [`updateStreamTweets`](#updatestreamtweets)
- Obtains the latest indexed 25 tweets in the stream ([`getStreamTweetsNeo4j`](#getstreamtweetsneo4j))

### action

TBD

## /models/streams.server.ts

### getUserStreams

- Gets user's streams.
- Collects recommended accounts for user's streams.
- For now, a recommended account is a commonly followed account among the seed users of a stream.
- Lists at most 5 recommended users.

**No Twitter access**.

### getAllStreams

- Gets streams created by other users.
- Has the same logic as [`getUserStreams`](#getuserstreams) except for the condition to collect streams.

### getStreamByName

- Gets the stream that has a given name.

### createStream

- Creates a new stream

### indexMoreTweets

- Calls [`indexUserOlderTweets`](#indexuseroldertweets) for each seed user

### updateStreamTweets

- Calls [`indexUserNewTweets`](#indexusernewtweets) for each seed user

### addUsers

- Adds or updates given users.
- Returns added or updated user nodes. (I do not think results are used)

### addTweetMedia

- Adds or updates media.
- Returns added or updated media nodes. (I do not think results are used)

### addTweetsFrom

- Adds or updates tweets.
- Adds user nodes of authors if necessary.
- Adds "POSTED" relationships from authors to tweets.
- Adds user nodes of mentioned users if necessary.
- Adds "MENTIONED" relationships from tweets to mentioned users.
- Adds URL nodes if necessary.
- Adds "LINKED" relationships from tweets to URLs.
- Adds annotation nodes if necessary.
- Adds "ANNOTATED" relationships from tweets to annotations.
- Adds domain nodes if necessary.
- Adds "CATEGORY" relationships from tweets to domains.
- Adds entity nodes if necessary.
- Adds "INCLUDED" relationships from tweets to entities.
- Adds hashtag nodes if necessary.
- Adds "TAG" relationships from tweets to hashtags.
- Adds cashtag nodes if necessary.
- Adds "TAG" relationships from tweets to cashtags.
- Adds media nodes if there are attachments.
- Adds "ATTACHED" relationships from tweets to attached media.
- Adds referenced tweet nodes if necessary.
- Adds "REFERENCED" relationships from tweets to referenced tweets.
- Returns added or updated tweet nodes. (I do not think results are used)

### getStreamTweetsNeo4j

- Obtains the latest N indexed tweets from the neo4j database.
    - Leaves only tweets that have one or more entities listed in `tags` if `tags` is specified.
- Optionally retrieves the following,
    - referenced tweets
    - entities
    - attached media
    - annotations
- Returns obtained tweets

### bulkWrites

- Splits a given array into chunks of 100 items.
- Processes each chunk with a given write function.

## /models/user.server.ts

### indexUserOlderTweets

- Pulls the latest 100 tweets before the oldest tweet a given user has indexed ([`pullTweets`](#pulltweets)).
- Pushes the pulled tweets into the neo4j database ([`bulkWrite`](#bulkwrite)).
    - Adds tweet users with [`addUsers`](#addusers). According to the [Twitter API doc](https://developer.twitter.com/en/docs/twitter-api/tweets/timelines/api-reference/get-users-id-tweets#tab0), users may be
        - The Tweet author's user object
        - The user object of the Tweet's author that the original Tweet is responding to
        - Any mentioned users' object
        - Any referenced Tweets' author's user object
    - Adds tweet media with [`addTweetMedia`](#addtweetmedia)
    - Adds referenced tweets with [`addTweetsFrom`](#addtweetsfrom)
    - Adds user's tweets with [`addTweetsFrom`](#addtweetsfrom)
    - Updates indexed tweet range of the user ([`updateUserIndexedTweetIds`](#updateuserindexedtweetids))

See also [`TwitterV2IncludesHelper`](https://github.com/PLhery/node-twitter-api-v2/blob/master/doc/helpers.md#helpers-for-includes-of-v2-api-responses).

### indexUserNewTweets

- Pulls the oldest 100 tweets after the newest tweet a given user has indexed ([`pullTweets`](#pulltweets)).
    - Pulls the latest 100 tweets of the user if the user has not indexed yet.
- Does the same operations on the pulled tweets as [`indexUserOlderTweets`](#indexuseroldertweets).

### pullTweets

Pulls tweets staisfying given conditions from Twitter.

### updateUserIndexedTweetIds

Updates the latest and earliest tweet IDs of a given user.
This information is used to pull further tweets of the user.