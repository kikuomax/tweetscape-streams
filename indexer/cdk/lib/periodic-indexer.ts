import * as path from 'path';
import { Duration, aws_lambda as lambda } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';

import type { ExternalResources } from './external-resources';

interface Props {
    /** External resources. */
    externalResources: ExternalResources;
}

/** CDK construct that provisions resources for a periodic Indexer. */
export class PeriodicIndexer extends Construct {
    constructor(scope: Construct, id: string, props: Props) {
        super(scope, id);

        const { databaseCredentials } = props.externalResources;

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
                environment: {
                    NEO4J_SECRET_ARN: databaseCredentials.secretArn,
                },
                memorySize: 256,
                timeout: Duration.minutes(15),
            },
        );
        databaseCredentials.grantRead(indexAllStreamsLambda);
    }
}
