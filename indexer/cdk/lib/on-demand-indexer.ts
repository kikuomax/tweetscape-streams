import * as path from 'path';

import {
    Duration,
    aws_lambda as lambda,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfntasks,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';

import type { ExternalResources } from './external-resources';
import type { IndexerDependencies } from './indexer-dependencies';

interface Props {
    /** External resources. */
    readonly externalResources: ExternalResources;
    /** Dependencies of Indexer. */
    readonly indexerDependencies: IndexerDependencies;
}

/** CDK construct that provisions resources for the on-demand Indexer. */
export class OnDemandIndexer extends Construct {
    /** Lambda function that upserts a Twitter account. */
    private upsertTwitterAccountLambda: lambda.IFunction;
    /** Lambda function that adds a seed Twitter account to a stream. */
    private addSeedAccountToStreamLambda: lambda.IFunction;
    /** Lambda function that indexes tweets from a Twitter account. */
    private indexTweetsFromAccountLambda: lambda.IFunction;
    /** Lambda function that indexes following relationships. */
    private indexFollowingLambda: lambda.IFunction;
    /**
     * Workflow (state machine) to add a seed Twitter account to a stream.
     *
     * @remarks
     *
     * You have to provide an input similar to the following,
     *
     * ```js
     * {
     *   requesterId: '<requester-id>',
     *   streamName: '<stream-name>',
     *   twitterUsername: '<twitter-username>'
     * }
     * ```
     */
    readonly addSeedAccountToStreamWorkflow: sfn.IStateMachine;

    constructor(scope: Construct, id: string, props: Props) {
        super(scope, id);

        const { databaseCredentials } = props.externalResources;
        const {
            commonPackages,
            libIndexer,
            psycopg2,
        } = props.indexerDependencies;

        // Lambda functions as building blocks
        // - obtains the information on a Twitter account and
        //   upserts an Account node on the graph database
        this.upsertTwitterAccountLambda = new PythonFunction(
            this,
            'UpsertTwitterAccountLambda',
            {
                description: 'Upserts a Twitter account',
                architecture: lambda.Architecture.ARM_64,
                runtime: lambda.Runtime.PYTHON_3_8,
                entry: path.join('lambda', 'upsert-twitter-account'),
                index: 'index.py',
                handler: 'lambda_handler',
                layers: [commonPackages, libIndexer, psycopg2],
                environment: {
                    EXTERNAL_CREDENTIALS_ARN: databaseCredentials.secretArn,
                },
                memorySize: 256,
                timeout: Duration.minutes(3),
            },
        );
        databaseCredentials.grantRead(this.upsertTwitterAccountLambda);
        // - adds a seed Twitter account to a stream.
        //   also adds the account to the corresponding Twitter list.
        this.addSeedAccountToStreamLambda = new PythonFunction(
            this,
            'AddSeedAccountToStreamLambda',
            {
                description: 'Adds a seed account to a stream',
                architecture: lambda.Architecture.ARM_64,
                runtime: lambda.Runtime.PYTHON_3_8,
                entry: path.join('lambda', 'add-seed-account-to-stream'),
                index: 'index.py',
                handler: 'lambda_handler',
                layers: [commonPackages, libIndexer, psycopg2],
                environment: {
                    EXTERNAL_CREDENTIALS_ARN: databaseCredentials.secretArn,
                },
                memorySize: 256,
                timeout: Duration.minutes(3),
            },
        );
        databaseCredentials.grantRead(this.addSeedAccountToStreamLambda);
        // - indexes tweets from a given Twitter account.
        this.indexTweetsFromAccountLambda = new PythonFunction(
            this,
            'IndexTweetsFromAccountLambda',
            {
                description: 'Indexes tweets from a given account',
                architecture: lambda.Architecture.ARM_64,
                runtime: lambda.Runtime.PYTHON_3_8,
                entry: path.join('lambda', 'index-tweets-from-account'),
                index: 'index.py',
                handler: 'lambda_handler',
                layers: [commonPackages, libIndexer, psycopg2],
                environment: {
                    EXTERNAL_CREDENTIALS_ARN: databaseCredentials.secretArn,
                },
                memorySize: 256,
                timeout: Duration.minutes(15),
            },
        );
        databaseCredentials.grantRead(this.indexTweetsFromAccountLambda);
        // - indexes Twitter accounts whom a specific account is following
        this.indexFollowingLambda = new PythonFunction(
            this,
            'IndexFollowingLambda',
            {
                description: 'Indexes Twitter accounts followed by a specific account',
                architecture: lambda.Architecture.ARM_64,
                runtime: lambda.Runtime.PYTHON_3_8,
                entry: path.join('lambda', 'index-following'),
                index: 'index.py',
                handler: 'lambda_handler',
                layers: [commonPackages, libIndexer, psycopg2],
                environment: {
                    EXTERNAL_CREDENTIALS_ARN: databaseCredentials.secretArn,
                },
                memorySize: 256,
                timeout: Duration.minutes(3),
            },
        );
        databaseCredentials.grantRead(this.indexFollowingLambda);

        // creates the workflow to add a seed Twitter account to a stream
        this.addSeedAccountToStreamWorkflow =
            this.createAddSeedAccountToStreamWorkflow();
    }

    /** Creates a workflow to add a seed Twitter account to a stream. */
    private createAddSeedAccountToStreamWorkflow(): sfn.StateMachine {
        // creates states
        // - invokes UpsertTwitterAccountLambda
        const invokeUpsertTwitterAccount = new sfntasks.LambdaInvoke(
            this,
            'InvokeUpsertTwitterAccount',
            {
                lambdaFunction: this.upsertTwitterAccountLambda,
                comment: 'Upserts a given Tiwtter account',
                payloadResponseOnly: true,
                resultSelector: {
                    requesterId: sfn.JsonPath.stringAt(
                        '$$.Execution.Input.requesterId',
                    ),
                    streamName: sfn.JsonPath.stringAt(
                        '$$.Execution.Input.streamName',
                    ),
                    seedAccountId: sfn.JsonPath.stringAt('$.accountId'),
                },
                resultPath: '$',
                timeout: Duration.minutes(5),
            },
        );
        // - invokes AddSeedAccountToStreamLambda
        const invokeAddSeedAccountToStream = new sfntasks.LambdaInvoke(
            this,
            'InvokeAddSeedAccountToStream',
            {
                lambdaFunction: this.addSeedAccountToStreamLambda,
                comment: 'Adds a given Twitter account to a stream',
                payloadResponseOnly: true,
                resultPath: sfn.JsonPath.DISCARD,
                timeout: Duration.minutes(5),
            },
        );
        // - invokes IndexTweetsFromAccountLambda
        const invokeIndexTweetsFromAccount = new sfntasks.LambdaInvoke(
            this,
            'InvokeIndexTweetsFromAccount',
            {
                lambdaFunction: this.indexTweetsFromAccountLambda,
                comment: 'Indexes tweets from a given Twitter account',
                payloadResponseOnly: true,
                resultPath: sfn.JsonPath.DISCARD,
                timeout: Duration.minutes(20),
            },
        );
        // - invokes IndexFollowingLambda
        const invokeIndexFollowing = new sfntasks.LambdaInvoke(
            this,
            'InvokeIndexFollowing',
            {
                lambdaFunction: this.indexFollowingLambda,
                comment: 'Indexes Twitter accounts followed by a specific account',
                payloadResponseOnly: true,
                payload: sfn.TaskInput.fromObject({
                    requesterId: sfn.JsonPath.stringAt('$.requesterId'),
                    accountId: sfn.JsonPath.stringAt('$.seedAccountId'),
                }),
                resultPath: sfn.JsonPath.DISCARD,
                timeout: Duration.minutes(5),
            },
        );
        // - handles rate limit at IndexFollowingLambda
        this.addRateLimitRetry(invokeIndexFollowing);

        // chains states
        return new sfn.StateMachine(
            this,
            'AddSeedAccountToStreamWorkflow',
            {
                definition: invokeUpsertTwitterAccount
                    .next(invokeAddSeedAccountToStream)
                    .next(invokeIndexTweetsFromAccount)
                    .next(invokeIndexFollowing),
                timeout: Duration.hours(1),
            },
        );
    }

    /** Adds states to handle rate limit for a given Lambda invocation state. */
    private addRateLimitRetry(task: sfntasks.LambdaInvoke) {
        // extracts "Cause"
        const extractRateLimitCause = new sfn.Pass(
            this,
            `ExtractRateLimitCause_${task.id}`,
            {
                comment: `Extracts Cause of a rate limit error of ${task.id}`,
                parameters: {
                    cause: sfn.JsonPath.stringAt('States.StringToJson($.rateLimitError.Cause)'),
                },
                resultPath: '$.rateLimitError',
            },
        );
        // extracts "errorMessage"
        const extractRateLimitMessage = new sfn.Pass(
            this,
            `ExtractRateLimitMessage_${task.id}`,
            {
                comment: `Extracts errorMessage of a rate limit error of ${task.id}`,
                parameters: {
                    message: sfn.JsonPath.stringAt('States.StringToJson($.rateLimitError.cause.errorMessage)'),
                },
                resultPath: '$.rateLimitError',
            },
        );
        // waits until the rate limit reset
        const waitRateLimitReset = new sfn.Wait(
            this,
            `WaitRateLimitReset_${task.id}`,
            {
                comment: `Waits until the rate limit reset to retry ${task.id}`,
                time: sfn.WaitTime.timestampPath('$.rateLimitError.message.rateLimitReset'),
            },
        );

        // chains states
        extractRateLimitCause
            .next(extractRateLimitMessage)
            .next(waitRateLimitReset)
            .next(task);
        task.addCatch(extractRateLimitCause, {
            errors: ['RateLimitError'],
            resultPath: '$.rateLimitError',
        });
    }
}
