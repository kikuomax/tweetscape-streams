# Indexer

The [`cdk`](./cdk) folder contains an [AWS Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/) stack that provisions Indexer resources on AWS.

## Prerequisites

### Public PostgreSQL instance

To run Indexer, you have to allow external services to connect to the PostgreSQL database.
I could not make a PostgreSQL instance created with the [`fly postgres` command](https://fly.io/docs/postgres/) public.
My workaround was to manually deploy another PostgreSQL instance using [this template (`flyapps/postgres-standalone`)](https://github.com/fly-apps/postgres-standalone).

## Running locally

To locally run Indexer, you have to install PostgreSQL server on your local machine.
So I recommend to use [Docker](https://www.docker.com) to run it.

### Running on Docker

You can build a Docker image to locally run Indexer.

```sh
docker build -t tweetscape-indexer:latest .
```

#### Indexing all streams

```sh
docker run -it --rm \
    -e NEO4J_URI \
    -e NEO4J_USERNAME \
    -e NEO4J_PASSWORD \
    -e DATABASE_URL \
    -e OAUTH_CLIENT_ID \
    -e OAUTH_CLIENT_SECRET \
    --network host \
    tweetscape-indexer:latest \
    python3 index-all-streams/index.py
```

You have to have the following environment variables defined,
- `NEO4J_URI`
- `NEO4J_USERNAME`
- `NEO4J_PASSWORD`
- `DATABASE_URL`: URL of the PostgreSQL database, which includes the username and password.
- `OAUTH_CLIENT_ID`: Twitter app client ID.
- `OAUTH_CLIENT_SECRET`: Twitter app client secret.

Please refer to the [tips](#loading-env-file-as-environment-variables-on-your-shell) for how to reuse your `.env` file.

### Tips

#### Loading .env file as environment variables on your shell

If you are locally running the tweetscape-streams server, you should have a `.env` file.
You can load your `.env` file with the following command,
```sh
set -a; source .env; set +a
```

Reference: https://andrew.red/posts/how-to-load-dotenv-file-from-shell