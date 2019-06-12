import boto3
import maya
import json
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from ..configs.settings import SYS_CONFIG

project_table = boto3.resource('dynamodb').Table(SYS_CONFIG.project_table)
project_models_table = boto3.resource('dynamodb').Table(SYS_CONFIG.project_models_table)
job_table = boto3.resource('dynamodb').Table(SYS_CONFIG.job_table)
endpoint_table = boto3.resource('dynamodb').Table(SYS_CONFIG.endpoint_table)

def create_project(project_name, variants={'default':1}, is_auto_deploy=True, is_active=True, **kwargs):
    """
    create project into dynamo
        :param project_name: 
        :param variants={'default':1}: 
        :param is_auto_deploy=True: 
        :param is_active=True: 
    """
    project = {
        'project_name': project_name,
        'variants': json.dumps(variants),
        'is_auto_deploy': is_auto_deploy,
        'is_active': is_active,
        'date_created': maya.now().epoch,
    }

    response = project_table.put_item(Item=project)
    if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
        return project['project_name']
    return ''


def get_project(project_name):
    response = project_table.get_item(Key={'project_name': project_name})
    if response.get('Item',{}).get('is_active'):
        return response.get('Item')
    return {}


def update_project(project_name, update_partial):
    """
    docstring here
        :param project_name: 
        :param update_partial={}: 
    """
    item = get_project(project_name)
    for key, value in update_partial.items():
        item[key] = value
    item['time_updated'] = maya.now().epoch
    project_table.put_item(Item=item)


def create_project_model(project_name,
                         variant_name='default',
                         spec_train={},
                         spec_serve=[],
                         env_train={},
                         env_serve={},
                         **kwargs):
    """
    docstring here
        :param project_name: 
        :param variant_name:
        :param image_train: 
        :param image_serve: 
        :param spec_train: 
        :param spec_serve: list of endpoint spects
        
        :param input_data_path: 
        :param output_model_path: 
        :param **kwargs: model artifact path
    """              

    project_model_data = {'project_name': project_name,
                    'variant_name': variant_name,
                    'update_timestamp': maya.now().epoch}

    if spec_serve:
        project_model_data['spec_serve'] = json.dumps(spec_serve)
    if spec_train:
        project_model_data['spec_train'] = json.dumps(spec_train)
    if env_train:
        project_model_data['env_train'] = json.dumps(env_train)
    if env_serve:
        project_model_data['env_serve'] = json.dumps(env_serve)

    project_model_data.update(kwargs)

    response = project_models_table.put_item(Item=project_model_data)
    return response


def get_project_model(project_name, variant_name='default'):
    """
    docstring here
        :param project_name: 
        :param variant_name='default:
    """
    response = project_models_table.get_item(Key={'project_name': project_name, 'variant_name':variant_name})
    return response.get('Item') or {}


def update_project_model(project_name, variant_name, update_partial):
    item = get_project_model(project_name, variant_name)
    for key, value in update_partial.items():
        item[key] = value
    item['time_updated'] = maya.now().epoch
    project_models_table.put_item(Item=item)


def list_project_models(project_name):
    response = project_models_table.query(
        IndexName='project_name-index',
        KeyConditionExpression=Key('project_name').eq(project_name),
        ConsistentRead=False,
    )
    if response:
        return response.get('Items', [])
    return []


def log_job(project_name, job_type, variant_name='default', endpoint_status='ModelCreatedOnly', **kwargs):
    """
    create job based on data and project specs, 
        :param str project_name: project name triggers job
        :param str job_type: job train or job serve
        :param evn_train:
        :param evn_serve:
        :param **kwargs: model_created, endpoint_config_created
    """

    job_item = kwargs
    job_item['job_type'] = job_type
    job_item['project_name'] = project_name
    job_item['variant_name'] = variant_name
    job_item['endpoint_status'] = endpoint_status

    if job_item.get('spec_serve'):
        job_item['spec_serve'] = json.dumps(job_item['spec_serve'])
    if job_item.get('spec_train'):
        job_item['spec_train'] = json.dumps(job_item['spec_train'])
    if job_item.get('env_train'):
        job_item['env_train'] = json.dumps(job_item['env_train'])
    if job_item.get('env_serve'):
        job_item['env_serve'] = json.dumps(job_item['env_serve'])

    response = job_table.put_item(Item=job_item)
    if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
        return job_item['job_name']

    return ''


def get_job(job_name):
    """
    get job status
        :param job_name: 
        :param project_name: 
    """
    response = job_table.get_item(Key={'job_name': job_name})
    return response['Item']


def update_job(job_name, partial_update_item={}):
    """
    docstring here
        :param job_name: 
        :param partial_update_item={}: 
    """
    item = get_job(job_name)
    for key, value in partial_update_item.items():
        item[key] = value
    item['time_updated']=maya.now().epoch
    job_table.put_item(Item=item)


def list_jobs(project_name, variant_name='default'):
    """
    list jobs belongs to same project
        :param project_name: 
        :param variant_name='default': 
    """ 
    #TODO: filter jobs based on variant_name
    response = job_table.query(
        IndexName='project_name-index',
        KeyConditionExpression=Key('project_name').eq(project_name),
        ConsistentRead=False,
    )
    if response:
        return response.get('Items', [])
    return []


def list_jobs_by_status(endpoint_status):
    response = job_table.query(
        IndexName='endpoint_status-index',
        KeyConditionExpression=Key('endpoint_status').eq(endpoint_status),
        ConsistentRead=False,
    )
    if response:
        return response.get('Items', [])
    return []


def create_endpoint(endpoint_name, **kwargs):
    item = kwargs
    item['endpoint_name'] = endpoint_name
    response = endpoint_table.put_item(Item=item)
    return response
