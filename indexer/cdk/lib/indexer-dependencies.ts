import * as path from 'path';

import { aws_lambda as lambda } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { PythonLayerVersion } from '@aws-cdk/aws-lambda-python-alpha';

import { PythonLibraryLayer } from 'cdk2-python-library-layer';
import { Psycopg2LambdaLayer } from 'psycopg2-lambda-layer';

/**
 * CDK construct that provisions Lambda layers of reused modules among Indexer
 * components.
 */
export class IndexerDependencies extends Construct {
    /** Lambda layer of `psycopg2`. */
    readonly psycopg2: lambda.ILayerVersion;
    /** Lambda layer of common packages. */
    readonly commonPackages: lambda.ILayerVersion;
    /** Lambda layer of `libindexer`. */
    readonly libIndexer: lambda.ILayerVersion;

    constructor(scope: Construct, id: string) {
        super(scope, id);

        this.psycopg2 = new Psycopg2LambdaLayer(this, 'Psycopg2Layer', {
            description: 'psycopg2 built for Amazon Linux 2 (ARM64)',
            runtime: lambda.Runtime.PYTHON_3_8,
            architecture: lambda.Architecture.ARM_64,
        });

        this.commonPackages = new PythonLayerVersion(
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

        this.libIndexer = new PythonLibraryLayer(this, 'LibIndexerLayer', {
            description: 'Layer of libindexer',
            runtime: lambda.Runtime.PYTHON_3_8,
            compatibleArchitectures: [
                lambda.Architecture.ARM_64,
                lambda.Architecture.X86_64,
            ],
            entry: path.join('lambda', 'libindexer'),
        });
    }
}
