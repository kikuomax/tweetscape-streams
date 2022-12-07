import * as path from 'path';
import {
    Duration,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as lambda,
    aws_sns as sns,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';

import type { DeploymentStage } from './deployment-stage';
import type { ExternalResources } from './external-resources';
import type { IndexerDependencies } from './indexer-dependencies';

interface Props {
    /** Deployment stage. */
    readonly deploymentStage: DeploymentStage;
    /** External resources. */
    readonly externalResources: ExternalResources;
    /** Dependencies of Indexer. */
    readonly indexerDependencies: IndexerDependencies;
}

/** CDK construct that provisions resources for a periodic Indexer. */
export class PeriodicIndexer extends Construct {
    constructor(scope: Construct, id: string, props: Props) {
        super(scope, id);

        const { deploymentStage } = props;
        const { databaseCredentials } = props.externalResources;
        const {
            commonPackages,
            libIndexer,
            psycopg2,
        } = props.indexerDependencies;

        // TODO: reuse the following SNS topic and SQS queue if necessary
        // SNS topic that receives dead letters
        const deadLetterTopic = new sns.Topic(this, 'DeadLetterTopic', {
            displayName: `Dead-letter topic (${deploymentStage})`,
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
                layers: [commonPackages, libIndexer, psycopg2],
                environment: {
                    EXTERNAL_CREDENTIALS_ARN: databaseCredentials.secretArn,
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
