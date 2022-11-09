# Processing queue

## Scenario: Processing an arbitary set of users

1. A person (`seeder`) wants to process tweets from an arbitrary set of Twitter `users`.
2. The `seeder` asks `Indexer` to process the `users`.
    - TBC: the `seeder` should offer seeder's rate limit for processing.
3. `Indexer` creates a new `task` that processes the `users`.
4. `Indexer` puts the `task` into the `task database`.
5. `Indexer` pushes a request (`processing request`) for processing of the `task` to the `processing queue`.
6. `Indexer` tells the `seeder` the ID (`task ID`) of the `task`.
7. The `processing queue` picks the `processing request` for processing.
8. The `processing queue` triggers a workflow (`user processing workflow`) to process the `task`.
9. The `user processing workflow` fetches the information on the `task` from the `task database`.
10. The `user processing workflow` marks the `task` "processing" in the `task database`.
11. The `user processing workflow` processes the `users` one by one.
    - [Subscenario: Processing a single user](#subscenario-processing-a-single-user)
12. The `user processing workflow` marks the `task` "done" in the `task database`.
13. The `seeder` asks `Indexer` for the status of the `task` associated with the `task ID`.
14. `Indexer` tells the `seeder` the `task` has done.

### Subscenario: Processing a single user

**Given**:
- A `seeder` who requested the processing.
    - TBC: the `seeder` is supposed to donate the rate limit.
- A `user` to be processed.
- A `user processing workflow` to process the `user`.

1. The `user processing workflow` obtains the Twitter `access token` of the `seeder` from the `user database`.
    - `user database`: PostgreSQL database
2. The `user processing workflow` obtains the information of the `user` from Twitter.
3. The `user processing workflow` creates a new `User` node for the `user` in the `graph database`.
4. The `user processing workflow` pulls the latest `tweets` of the `user` from Twitter.
    - Twitter access is authenticated with the `access token`.
5. The `user processing workflow` creates `User` nodes for the users in the `tweets` in the `graph database`.
6. The `user processing workflow` creates `Media` nodes for the media in the `tweets` in the `graph database`.
7. The `user processing workflow` creates `Tweet` nodes for the tweets referenced in the `tweets` in the `graph database`.
    - While making relationships\* between the `Tweet` nodes and related nodes.
8. The `user processing workflow` creates `Tweet` nodes for the `tweets` in the `graph database`.
    - While making relationships\* between the `Tweet` nodes and related nodes.
9. The `user processing workflow` updates the indexed tweet range of the `user` in the `graph database`.

\* Relationships include the following,
- `POSTED`: `User` &rightarrow; `Tweet`
- `MENTIONED`: `Tweet` &rightarrow; `User`
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

1. The `user processing workflow` waits for 15 minutes.
2. The `user processing workflow` starts over the subscenario from Step 1.

#### Exception-4-A: Exceeding the Twitter rate limit

**Condition**:
- Step 4 fails because the Twitter rate limit has been reached.

1. The `user processing workflow` waits for 15 minutes.
2. The `user processing workflow` starts over the subscenario from Step 1.