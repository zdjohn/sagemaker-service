from collections import namedtuple
import json
import boto3
import botocore
from sagemaker_svc_wrapper.configs.settings import SYS_CONFIG


sagemaker = boto3.client('sagemaker')

EndpointConfig = namedtuple('EndpointConfig', ['endpoint_config_name', 'arn'])
Endpoint = namedtuple('Endpoint', ['endpoint_name', 'arn'])
SageMakerModel = namedtuple('SageMakerModel', ['model_name', 'arn'])

def create_training_job(job_name,
                        image_train,
                        spec_train,
                        input_data_location,
                        output_model_location,
                        hyperparameters={},
                        input_data_distribution_type='FullyReplicated',
                        max_runtime=3600):

    training_job_payload = {
        'AlgorithmSpecification': {
            'TrainingImage': image_train,
            'TrainingInputMode': 'File'
        },
        'RoleArn': SYS_CONFIG.role,
        'OutputDataConfig': {
            'S3OutputPath': output_model_location
        },
        'ResourceConfig': spec_train,
        'TrainingJobName': job_name,
        'StoppingCondition': {
            'MaxRuntimeInSeconds': max_runtime
        },
        'InputDataConfig': [{
            'ChannelName': 'train',
            'DataSource': {
                'S3DataSource': {
                    'S3DataType': 'S3Prefix',
                    'S3Uri': input_data_location,
                    'S3DataDistributionType': input_data_distribution_type
                }
            },
            'CompressionType': 'None',
            'RecordWrapperType': 'None'
        }]}
    if hyperparameters:
        training_job_payload['HyperParameters'] = hyperparameters

    sagemaker.create_training_job(**training_job_payload)

    status = sagemaker.describe_training_job(TrainingJobName=job_name)['TrainingJobStatus']
    return status


def create_model(model_name, inference_image, model_artifacts=None, enviroment_variable={}):
    """
    docstring here
        :param model_name: name of the model
        :param inference_image: containerized docker image url from ecr
        :param model_artifacts=None: saved model output
        :param enviroment_variable={}: enviroment variables for the serving container

        PrimaryContainer={
        'ContainerHostname': 'string',
        'Image': 'string',
        'ModelDataUrl': 'string',
        'Environment': {
            'string': 'string'
            },
        'ModelPackageName': 'string'
        }

        VpcConfig 
    """

    primary_container = {'Image': inference_image}

    if enviroment_variable:
        primary_container['Environment'] = enviroment_variable

    if model_artifacts == 'sagemaker':
        info = sagemaker.describe_training_job(TrainingJobName=model_name)
        model_artifacts = info['ModelArtifacts']['S3ModelArtifacts']

    if model_artifacts:
        primary_container['ModelDataUrl'] = model_artifacts

    #NOTE: VpcConfig is not used currently
    create_model_response = sagemaker.create_model(
        ModelName=model_name,
        ExecutionRoleArn=SYS_CONFIG.role,
        PrimaryContainer=primary_container)

    return SageMakerModel(model_name, create_model_response.get('ModelArn', ''))


def create_endpoint_config(endpoint_config_name, production_variants=[]):
    # ([{
    #         'InstanceType': 'ml.m4.xlarge',
    #         'InitialInstanceCount': 1,
    #         'ModelName': model_name,
    #         'VariantName':'AllTraffic',
    #         'InitialVariantWeight': 1.0,
    # }])
    create_endpoint_config_response = sagemaker.create_endpoint_config(
        EndpointConfigName=endpoint_config_name,
        ProductionVariants=production_variants,)
    return EndpointConfig(endpoint_config_name, create_endpoint_config_response.get('EndpointConfigArn', ''))


def describe_training_job(job_name):
    status_response = sagemaker.describe_training_job(TrainingJobName=job_name)
    return status_response


def describe_endpoint(endpoint_name):
    try:
        resp = sagemaker.describe_endpoint(EndpointName=endpoint_name)
        if resp.get('EndpointStatus') == 'Failed':
            sagemaker.delete_endpoint(EndpointName=endpoint_name)
            return {}
        return resp
    except:
        return {}


def delete_endpoint(endpoint_name):
    try:
        resp = sagemaker.describe_endpoint(EndpointName=endpoint_name)
        if resp:
            sagemaker.delete_endpoint(EndpointName=endpoint_name)
            return True
    except:
        return False

def update_endpoint(endpoint_name, endpoint_config_name=''):
    if not endpoint_config_name:
        endpoint_config_name = endpoint_name
    sagemaker.update_endpoint(
        EndpointName=endpoint_name,
        EndpointConfigName=endpoint_config_name)
    return sagemaker.describe_endpoint(EndpointName=endpoint_name)


def create_endpoint(endpoint_name, endpoint_config_name=''):
    if not endpoint_config_name:
        endpoint_config_name = endpoint_name
    sagemaker.create_endpoint(EndpointName=endpoint_name, EndpointConfigName=endpoint_config_name)
    return sagemaker.describe_endpoint(EndpointName=endpoint_name)


def upsert_endpoint(endpoint_name, endpoint_config_name, update=True):
    response = {}
    try:
        endpoint = sagemaker.describe_endpoint(EndpointName=endpoint_name)
        if endpoint and update:
            response = sagemaker.update_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name)
    except botocore.exceptions.ClientError:
        response = sagemaker.create_endpoint(
            EndpointName=endpoint_name,
            EndpointConfigName=endpoint_config_name)

    return EndpointConfig(endpoint_name, response.get('EndpointArn', ''))


if __name__ == '__main__':
    print(describe_endpoint('ml-commender-cf-Serve-1548041871'))