# Indexer CDK stack

The [AWS Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/home.html) stack that provisions AWS resources for Indexer.

## Getting started

### Preparing configuration files

You have to create the following files that contain connection parameters for external databases.
- `configs/postgres.ts`
- `configs/neo4j.ts`

These files are never pushed to this repository.
Please refer to examples [`configs/postgres.example.ts`](./configs/postgres.example.ts) and [`configs/neo4j.example.ts`](./configs/neo4j.example.ts) respectively.

DO NOT store actual passwords in the above configuration files because they are exposed on a CloudFormation template.
Instead, configure them on AWS console or via AWS CLI.
Please refer to [Section "Configuring database credentials"](#configuring-database-credentials) for more details.

### Resolving dependencies

```sh
npm ci
```

### Setting AWS_PROFILE

This document supposes you have set the [`AWS_PROFILE`](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html) environment variable to a profile with sufficient privileges.

Example:
```sh
export AWS_PROFILE=tweetscape-us
```

### Setting the toolkit stack name

```sh
TOOLKIT_STACK_NAME=tweetscape-toolkit-stack
```

### Setting the synthesizer qualifier

```sh
BOOTSTRAP_QUALIFIER=tscape2022
```

### Provisioning the toolkit stack

You do not have to run the following command if the toolkit stack has already been provisioned.

```sh
npx cdk bootstrap --toolkit-stack-name $TOOLKIT_STACK_NAME --qualifier $BOOTSTRAP_QUALIFIER
```

### Synthesizing a CloudFormation template

You should check a CloudFormation template before [deploying the CDK stack](#deploying-the-cdk-stack).

For development:
```sh
npx cdk synth -c "@aws-cdk/core:bootstrapQualifier=$BOOTSTRAP_QUALIFIER"
```

For production:
```sh
npx cdk synth -c "@aws-cdk/core:bootstrapQualifier=$BOOTSTRAP_QUALIFIER" -c tweetscape:stage=production
```

### Deploying the CDK stack

For development:
```sh
npx cdk deploy --toolkit-stack-name $TOOLKIT_STACK_NAME -c "@aws-cdk/core:bootstrapQualifier=$BOOTSTRAP_QUALIFIER"
```

For production:
```sh
npx cdk deploy --toolkit-stack-name $TOOLKIT_STACK_NAME -c "@aws-cdk/core:bootstrapQualifier=$BOOTSTRAP_QUALIFIER" -c tweetscape:stage=production
```

### Configuring database credentials

Connection parameters including passwords are stored in an [AWS SecretsManager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html) secret.
After deploying this CDK stack, you have to configure passwords to connect to the PostgreSQL and neo4j databases.

The secret has the following keys,
- `postgresUri`
- `neo4jUri`
- `neo4jUsername`
- `neo4jPassword`

Please edit the values of the keys `postgresUri` and `neo4jPassword` on AWS console or via AWS CLI.

#### External connection to PostgreSQL

You have to allow public access to the PostgreSQL instance.
Although the [documentation on Fly.io explains how to do this](https://fly.io/docs/postgres/the-basics/connecting/#connecting-external-services), I could not make it.
So I decided to deploy a PostgreSQL instance from [this template (`fly-apps/postgres-standalone`)](https://github.com/fly-apps/postgres-standalone).
Securing connection to the PostgreSQL database is another issue.

### Periodically running Indexer

This CDK stack provisions an [Amazon EventBridge](https://aws.amazon.com/eventbridge/) rule that runs Indexer every 15 minutes.
The rule is disabled by default.
Please turn it on if you want to schedule Indexer.

## Running locally

You can locally run Indexer.
Please refer to [`README.md` in the parent folder](../README.md).

## AWS Charges

As of Nov 11, 2022 in N. Virginia (us-east-1) region.

### Passive charges

The following resources charge you every month even if no processing has run.
- AWS SecretsManager secret: $0.40 / secret