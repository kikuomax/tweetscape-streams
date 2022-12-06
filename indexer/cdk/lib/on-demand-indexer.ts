import * as path from 'path';

import { Duration, aws_lambda as lambda } from 'aws-cdk-lib';
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
    constructor(scope: Construct, id: string, props: Props) {
        super(scope, id);

        const { databaseCredentials } = props.externalResources;
        const {
            commonPackages,
            libIndexer,
            psycopg2,
        } = props.indexerDependencies;

        // Lambda functions
        // - obtains the information on a Twitter account and
        //   upserts an Account node on the graph database
        const upsertTwitterAccountLambda = new PythonFunction(
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
        databaseCredentials.grantRead(upsertTwitterAccountLambda);
    }
}
