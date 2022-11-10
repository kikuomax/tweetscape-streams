# Processing queue

## Scenario: Processing an arbitary set of accounts

1. A person (`seeder`) wants to process tweets from an arbitrary set of Twitter `accounts`.
2. The `seeder` asks `Indexer` to process the `accounts`.
    - TBC: the `seeder` should offer seeder's rate limit for processing.
3. `Indexer` creates a new `task` that processes the `accounts`.
4. `Indexer` puts the `task` into the `task database`.
5. `Indexer` pushes a request (`processing request`) for processing of the `task` to the `processing queue`.
6. `Indexer` tells the `seeder` the ID (`task ID`) of the `task`.
7. The `processing queue` picks the `processing request` for processing.
8. The `processing queue` triggers a workflow (`account processing workflow`) to process the `task`.
9. The `account processing workflow` fetches the information on the `task` from the `task database`.
10. The `account processing workflow` marks the `task` "processing" in the `task database`.
11. The `account processing workflow` processes the `accounts` one by one.
    - [Subscenario: Processing a single account](#subscenario-processing-a-single-account)
12. The `account processing workflow` marks the `task` "done" in the `task database`.
13. The `seeder` asks `Indexer` for the status of the `task` associated with the `task ID`.
14. `Indexer` tells the `seeder` the `task` has done.

### Subscenario: Processing a single account

**Given**:
- A `seeder` who requested the processing.
    - TBC: the `seeder` is supposed to donate the rate limit.
- A `account` to be processed.
- A `account processing workflow` to process the `account`.

1. The `account processing workflow` obtains the Twitter `access token` of the `seeder` from the `tweetscape user database`.
    - `tweetscape user database`: PostgreSQL database
2. The `account processing workflow` obtains the information of the `account` from Twitter.
3. The `account processing workflow` creates a new `Account` node for the `account` in the `graph database`.
4. The `account processing workflow` pulls the latest `tweets` of the `account` from Twitter.
    - Twitter access is authenticated with the `access token`.
5. The `account processing workflow` creates `Account` nodes for the accounts in the `tweets` in the `graph database`.
6. The `account processing workflow` creates `Media` nodes for the media in the `tweets` in the `graph database`.
7. The `account processing workflow` creates `Tweet` nodes for the tweets referenced in the `tweets` in the `graph database`.
    - While making relationships\* between the `Tweet` nodes and related nodes.
8. The `account processing workflow` creates `Tweet` nodes for the `tweets` in the `graph database`.
    - While making relationships\* between the `Tweet` nodes and related nodes.
9. The `account processing workflow` updates the indexed tweet range of the `account` in the `graph database`.

\* Relationships include the following,
- `POSTED`: `Account` &rightarrow; `Tweet`
- `MENTIONED`: `Tweet` &rightarrow; `Account`
- `LINKED`: `Tweet` &rightarrow; `Link`
- `ANNOTATED`: `Tweet` &rightarrow; `Annotation`
- `CATEGORY`: `Tweet` &rightarrow; `Domain`
- `INCLUDED`: `Tweet` &rightarrow; `Entity`
- `TAG`: `Tweet` &rightarrow; `Hashtag` or `Cashtag`
- `ATTACHED`: `Tweet` &rightarrow; `Media`
- `REFERENCED`: `Tweet` &rightarrow; `Tweet`

#### Exception-2-A: Exceeding the Twitter rate limit

**Condition**:
- Step 2 fails because the Twitter rate limit has been reached.

1. The `account processing workflow` waits for 15 minutes.
2. The `account processing workflow` starts over the subscenario from Step 1.

#### Exception-4-A: Exceeding the Twitter rate limit

**Condition**:
- Step 4 fails because the Twitter rate limit has been reached.

1. The `account processing workflow` waits for 15 minutes.
2. The `account processing workflow` starts over the subscenario from Step 1.