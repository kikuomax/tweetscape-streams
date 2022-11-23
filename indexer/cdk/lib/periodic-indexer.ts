import * as path from 'path';
import {
    Duration,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as lambda,
    aws_sns as sns,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
    PythonFunction,
    PythonLayerVersion,
} from '@aws-cdk/aws-lambda-python-alpha';

import { Psycopg2LambdaLayer } from 'psycopg2-lambda-layer';

import type { DeploymentStage } from './deployment-stage';
import type { ExternalResources } from './external-resources';

interface Props {
    /** Deployment stage. */
    deploymentStage: DeploymentStage;
    /** External resources. */
    externalResources: ExternalResources;
}

/** CDK construct that provisions resources for a periodic Indexer. */
export class PeriodicIndexer extends Construct {
    constructor(scope: Construct, id: string, props: Props) {
        super(scope, id);

        const { deploymentStage } = props;
        const { databaseCredentials } = props.externalResources;

        // TODO: reuse the following SNS topic and SQS queue if necessary
        // SNS topic that receives dead letters
        const deadLetterTopic = new sns.Topic(this, 'DeadLetterTopic', {
            displayName: `Dead-letter topic (${deploymentStage})`,
        });

        // dependencies of Indexer
        const dependenciesLayer = new PythonLayerVersion(
            this,
            'DependenciesLayer',
            {
                description: 'Layer of Indexer dependencies',
                entry: path.join('lambda', 'indexer-dependencies'),
                compatibleRuntimes: [
                    lambda.Runtime.PYTHON_3_8,
                    lambda.Runtime.PYTHON_3_9,
                ],
                compatibleArchitectures: [
                    lambda.Architecture.ARM_64,
                    lambda.Architecture.X86_64,
                ],
            },
        );

        const psycopg2Layer = new Psycopg2LambdaLayer(this, 'Psycopg2Layer', {
            description: 'psycopg2 built for Amazon Linux 2 (ARM64)',
            runtime: lambda.Runtime.PYTHON_3_8,
            architecture: lambda.Architecture.ARM_64,
        });

        const indexAllStreamsLambda = new PythonFunction(
            this,
            'IndexAllStreamsLambda',
            {
                description: 'Indexes all streams',
                entry: path.join('lambda', 'index-all-streams'),
                runtime: lambda.Runtime.PYTHON_3_8,
                architecture: lambda.Architecture.ARM_64,
                index: 'index.py',
                handler: 'lambda_handler',
                layers: [dependenciesLayer, psycopg2Layer],
                environment: {
                    NEO4J_SECRET_ARN: databaseCredentials.secretArn,
                    POSTGRES_SECRET_ARN: databaseCredentials.secretArn,
                    TWITTER_SECRET_ARN: databaseCredentials.secretArn,
                },
                memorySize: 256,
                timeout: Duration.minutes(15),
                // no retry as this function is frequently invoked
                // but immediately sends a message to the dead-letter topic
                retryAttempts: 0,
                deadLetterTopic,
            },
        );
        databaseCredentials.grantRead(indexAllStreamsLambda);

        // runs Indexer every 15 minutes.
        // you have to enable this rule after provisioning it.
        new events.Rule(this, 'RunPeriodicIndexer', {
            description: `Periodically runs Indexer (${deploymentStage})`,
            enabled: false,
            targets: [
                new targets.LambdaFunction(indexAllStreamsLambda, {
                    // no need for a lot of retries
                    // next quarter comes soon
                    retryAttempts: 2,
                    maxEventAge: Duration.minutes(5),
                    // TODO: configure the dead-letter queue
                }),
            ],
            schedule: events.Schedule.cron({
                minute: '0/15', // every 15 minutes
            }),
        });
    }
}
