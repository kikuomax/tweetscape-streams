import * as path from 'path';
import {
    Duration,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as lambda,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
    PythonFunction,
    PythonLayerVersion,
} from '@aws-cdk/aws-lambda-python-alpha';

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

        // TODO: build psycopg2 from the source code
        // currently, the `psycopg2` folder contains binary I manually built.
        // however, we can automate the build process.
        const psycopg2Layer = new lambda.LayerVersion(
            this,
            'Psycopg2Layer',
            {
                description: 'psycopg2 built for Amazon Linux 2 (ARM64)',
                code: lambda.Code.fromAsset(path.join('lambda', 'psycopg2')),
                compatibleRuntimes: [lambda.Runtime.PYTHON_3_8],
                compatibleArchitectures: [lambda.Architecture.ARM_64],
            },
        );

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
                    retryAttempts: 0, // no retry
                    maxEventAge: Duration.minutes(5), // does this matter?
                    // TODO: configure the dead-letter queue
                }),
            ],
            schedule: events.Schedule.cron({
                minute: '0/15', // every 15 minutes
            }),
        });
    }
}
