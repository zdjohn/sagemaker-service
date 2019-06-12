import json
from enum import Enum
import requests
import maya
from flask import request, abort
from flask_restplus import Resource, Namespace, fields
from ..handlers import sagemaker_handler, dynamo_handler

class JobStatus(Enum):
    """
    job status
    """
    Inactive = 0
    Running = 1
    Ready = 2

class JobType(Enum):
    Train = "Train"
    Serve = "Serve"


job_ns = Namespace('job', description='sagemaker training job', strict_slashes=False)

TRAIN_JOB_PAYLOAD = job_ns.model('job', model={
    'project_name': fields.String(required=True, description='project name'),
    'data_input': fields.String(required=True, description='input data s3 path for training'),
    'model_output': fields.String(required=False, description='trained model output s3 path'),
    'image_train': fields.String(required=False),
    'spec_train': fields.Raw(required=False),
    'variant_name': fields.String(required=True, default='default'),
    # TODO: hyper parameters tuning not enabled
    # 'hyperparameters': fields.Raw(required=False),
})

SERVE_JOB_PAYLOAD = job_ns.model('job', model={
    'image_serve': fields.String(required=True, description='serving docker container from ECS'),
    'model_artifacts': fields.String(required=False, description='saved model artifacts'),
    'env_serve': fields.Raw(required=False),
    'variant_name': fields.String(required=True, default='default'),
})


@job_ns.route('/<string:job_name>', defaults={'job_name':''})
class Job(Resource):
    """
    """
    def get(self, job_name):
        response = dynamo_handler.get_job(job_name)
        if response:
            return response
        abort(404)


@job_ns.route('/<string:project_name>/train')
class JobTrain(Resource):
    """"""
    # NOTE: WIP
    @staticmethod
    @job_ns.expect(TRAIN_JOB_PAYLOAD, validate=True)
    def post(project_name):
        job_request = request.json
        project_name = job_request['project_name']
        project_description = dynamo_handler.get_project_model(project_name)
        if not job_request.get('image_train'):
            job_request['image_train'] = json.loads(project_description.get('image_train'))
        if not job_request.get('spec_train'):
            job_request['spec_train'] = json.loads(project_description.get('spec_train'))
        
        timestamp = maya.now().epoch
        job_type = JobType.Train.value
        job_request['project_name'] = project_name
        job_request['timestamp_queued'] = timestamp
        job_name = f'{project_name}-{job_type}-{timestamp}'

        sagemaker_handler.create_training_job(job_name=job_name,
                                              image_train=job_request['image_train'],
                                              spec_train=job_request['spec_train'],
                                              input_data_location=job_request['data_input'],
                                              output_model_location=job_request['model_output'],
                                              hyperparameters=job_request.get('hyperparameters', {}),)
        job_request['status'] = JobStatus.Running.value

        job_name = dynamo_handler.log_job(project_name, JobType.Train.value, **job_request)
        if job_name:
            return {'project_name':job_name}, 201
        abort(500, "job not created")


@job_ns.route('/<string:project_name>/serve')
class JobServe(Resource):
    """"""
    @staticmethod
    @job_ns.expect(SERVE_JOB_PAYLOAD, validate=True)
    def post(project_name):

        job_request = request.json
        variant_name = job_request.get('variant_name', 'default')
        # formated job name versioned by timestamp
        timestamp = maya.now().epoch
        job_type = JobType.Serve.value
        job_name = f'{project_name}-{job_type}-{timestamp}'

        project_model_settings = dynamo_handler.get_project_model(project_name, variant_name)
        if not project_model_settings:
            abort(400, f'no model: {project_name} found')

        project = dynamo_handler.get_project(project_name)
        if not project:
            abort(400, f'no project: {project_name} found')

        if not job_request.get('image_serve') and project_model_settings.get('image_serve'):
            job_request['image_serve'] = json.loads(project_model_settings['image_serve'])
        if not job_request.get('env_serve') and project_model_settings.get('env_serve'):
            job_request['env_serve'] = json.loads(project_model_settings['env_serve'])

        # creating model
        job_request['timestamp_queued'] = timestamp
        job_request['job_name'] = job_name


        sagemaker_model = sagemaker_handler.create_model(job_name,
                                                         job_request['image_serve'],
                                                         model_artifacts=job_request.get('model_artifacts'),
                                                         enviroment_variable=job_request.get('env_serve')
                                                        )
        if not sagemaker_model or not sagemaker_model.arn:
            return "unable to create model", 400

        variants = json.loads(project['variants'])
        config_variants = []

        if project.get('is_auto_deploy') and (variant_name in variants):
            #deploy is required
            for variant, weight in variants.items():
                project_model_settings = dynamo_handler.get_project_model(project_name, variant)
                if project_model_settings.get('spec_serve'):
                    job_spec_serve = json.loads(project_model_settings['spec_serve'])
                    job_spec_serve['VariantName'] = variant
                    job_spec_serve['InitialVariantWeight'] = weight
                    if variant == variant_name:
                        job_spec_serve['ModelName'] = sagemaker_model.model_name
                        config_variants.append(job_spec_serve)
                    elif project_model_settings.get('latest_model'):
                        job_spec_serve['ModelName'] = project_model_settings['latest_model']
                        config_variants.append(job_spec_serve)

        if config_variants:
            endpoint_config_arn = sagemaker_handler.create_endpoint_config(job_name, config_variants)
            if not endpoint_config_arn:
                return abort(400, 'endpoint config failed')
            else:
                job_request['endpoint_config_arn'] = endpoint_config_arn.arn
                job_request['endpoint_config'] = json.dumps(config_variants)
            # check exiting endpoint status
            endpoint_status = sagemaker_handler.describe_endpoint(job_name)
            if endpoint_status:
                status = endpoint_status.get('EndpointStatus')
                if status in ['Creating', 'Updating']:
                    #NOTE: when sagemaker endpoint is in update or creating status, 
                    #endpoints are unable to respond to other command
                    return {'status': f'endpoint is {status}'}, 400
                #update existing
                endpoint_status = sagemaker_handler.update_endpoint(job_name)
            else:
                endpoint_status = sagemaker_handler.create_endpoint(job_name)

            if endpoint_status:
                job_request['endpoint_status'] = endpoint_status.get('EndpointStatus')
        else:
            #TODO: TBD when to promote to project model level
            # job_request['endpoint_status'] = 'ModelCreatedOnly'
            # dynamo_handler.update_project_model(project_name, variant_name, {'latest_model': job_name})
            pass

        response = dynamo_handler.log_job(project_name, JobType.Serve.value, **job_request)
        if response:
            return response, 200

        return abort(500, 'somthing went wrong in creating endpoint')


@job_ns.route('/rerun')
class JobRerun(Resource):
    @staticmethod
    def post():
        job_request = request.json
        job_item = dynamo_handler.get_job(job_request['job_name'])
        job_name = job_item['job_name']
        print(job_item)
        if job_item['job_type'] == 'Serve':
            # check exiting endpoint status
            endpoint_status = sagemaker_handler.describe_endpoint(job_name)
            if endpoint_status:
                if endpoint_status.get('EndpointStatus') in ['Creating', 'Updating']:
                    return {'status': endpoint_status.get('EndpointStatus')}, 200
                #update existing
                endpoint_status = sagemaker_handler.update_endpoint(job_name)
            else:
                endpoint_status = sagemaker_handler.create_endpoint(job_name)
        elif job_item['job_type'] == 'Train':
            #TODO: need more details on the training rerun
            pass

        dynamo_handler.update_job(job_name, {'endpoint_status': endpoint_status.get('EndpointStatus')})

        return "rerun triggered", 201
