import * as path from 'path';
import {
    Duration,
    aws_apigateway as apigateway,
    aws_lambda as lambda,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';

import { RestApiWithSpec } from 'cdk-rest-api-with-spec';

import type { DeploymentStage } from './deployment-stage';
import type { OnDemandIndexer } from './on-demand-indexer';

/** Constructor properties for `IndexerApi`. */
export interface Props {
    /** Deployment stage. */
    readonly deploymentStage: DeploymentStage;
    /** On-demand Indexer. */
    readonly onDemandIndexer: OnDemandIndexer;
}

/** CDK construct that provisions the Indexer API. */
export class IndexerApi extends Construct {
    /** Indexer API. */
    readonly api: RestApiWithSpec;

    constructor(scope: Construct, id: string, props: Props) {
        super(scope, id);

        const { deploymentStage, onDemandIndexer } = props;
        const { addSeedAccountToStreamWorkflow } = onDemandIndexer;

        // Lambda functions
        // - triggers a workflow to add a seed account to a stream
        const triggerAddSeedAccountToStreamLambda = new PythonFunction(
            this,
            'TriggerAddSeedAccountToStreamLambda',
            {
                description: 'Triggers a workflow to add a seed account to a stream',
                architecture: lambda.Architecture.ARM_64,
                runtime: lambda.Runtime.PYTHON_3_8,
                entry: path.join(
                    'lambda',
                    'trigger-add-seed-account-to-stream',
                ),
                index: 'index.py',
                handler: 'lambda_handler',
                environment: {
                    WORKFLOW_ARN: addSeedAccountToStreamWorkflow.stateMachineArn,
                },
                memorySize: 128,
                timeout: Duration.seconds(30),
            },
        );
        addSeedAccountToStreamWorkflow.grantStartExecution(
            triggerAddSeedAccountToStreamLambda,
        );
        // - obtains the status of a given task
        const getTaskStatusLambda = new PythonFunction(
            this,
            'GetTaskStatusLambda',
            {
                description: 'Obtains the status of a given task',
                architecture: lambda.Architecture.ARM_64,
                runtime: lambda.Runtime.PYTHON_3_8,
                entry: path.join('lambda', 'get-task-status'),
                index: 'index.py',
                handler: 'lambda_handler',
                memorySize: 128,
                timeout: Duration.seconds(30),
            },
        );
        addSeedAccountToStreamWorkflow.grantRead(getTaskStatusLambda);

        this.api = new RestApiWithSpec(this, `IndexerApi`, {
            description: `API to interact with Indexer (${deploymentStage})`,
            openApiInfo: {
                version: '0.0.1',
            },
            openApiOutputPath: path.join(
                'openapi',
                `spec-${deploymentStage}.json`,
            ),
            defaultCorsPreflightOptions: {
                allowOrigins: apigateway.Cors.ALL_ORIGINS,
                // allows all methods, and default headers
            },
            deployOptions: {
                stageName: 'staging',
                description: `Latest stage for ${deploymentStage}`,
                loggingLevel: apigateway.MethodLoggingLevel.INFO,
                // TODO: loose throttling for production
                throttlingRateLimit: 100,
                throttlingBurstLimit: 50,
            },
            cloudWatchRole: false, // DO NOT turn on
            retainDeployments: true,
        });

        // /user
        const users = this.api.root.addResource('user');
        // /user/{accountId}
        const user = users.addResource('{accountId}');
        // /user/{accountId}/stream
        const streams = user.addResource('stream');
        // /user/{accountId}/stream/{streamName}
        const stream = streams.addResource('{streamName}');
        // /user/{accountId}/stream/{streamName}/seed_account
        const seed_accounts = stream.addResource('seed_account');
        // - POST: adds a seed account to a stream
        seed_accounts.addMethod(
            'POST',
            new apigateway.LambdaIntegration(
                triggerAddSeedAccountToStreamLambda,
                {
                    proxy: false,
                    passthroughBehavior: apigateway.PassthroughBehavior.NEVER,
                    requestTemplates: {
                        'application/json': `{
                          "requesterId": "$util.escapeJavaScript($input.params('accountId'))",
                          "streamName": "$util.escapeJavaScript($input.params('streamName'))",
                          "twitterUsername": $input.json('$.twitterUsername')
                        }`,
                    },
                    integrationResponses: [
                        {
                            statusCode: '200',
                        },
                    ],
                },
            ),
            {
                operationName: 'addSeedAccount',
                summary: 'Adds a new seed account',
                description: 'Adds a given seed account to a specified stream',
                methodResponses: [
                    {
                        statusCode: '200',
                        description: 'succeeded to add a seed account',
                    },
                ],
            },
        );
        // /task
        const tasks = this.api.root.addResource('task');
        // /task/{taskId}
        const task = tasks.addResource('{taskId}');
        // - GET: obtains the status of a task
        task.addMethod(
            'GET',
            new apigateway.LambdaIntegration(getTaskStatusLambda, {
                proxy: false,
                passthroughBehavior: apigateway.PassthroughBehavior.NEVER,
                requestTemplates: {
                    'application/json': `{
                        "executionArn": "$util.escapeJavaScript($util.urlDecode($input.params('taskId')))"
                    }`,
                },
                integrationResponses: [
                    {
                        statusCode: '200',
                    },
                ],
            }),
            {
                operationName: 'getTaskStatus',
                summary: 'Returns the status of a task',
                description: 'Returns the status of a task',
                methodResponses: [
                    {
                        statusCode: '200',
                        description: 'succeeded to obtain the task status',
                    },
                ],
            },
        );
    }
}
