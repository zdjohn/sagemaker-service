from flask import request, abort
from flask_restplus import Resource, Namespace, fields
from ..handlers import dynamo_handler, util_handler

project_model_ns = Namespace('models', description='models per project', strict_slashes=False)


spec_train = project_model_ns.model('train_spec', model={
    'InstanceCount': fields.Integer(required=True, default=1),
    'InstanceType': fields.String(required=True, description='instance type'),
    'VolumeSizeInGB': fields.Integer(required=True, default=50),
    'HyperParameters': fields.Raw(required=False),
    })


spec_serve = project_model_ns.model('serve_spec', model={
    'InitialInstanceCount': fields.Integer(required=True, default=1),
    'InstanceType': fields.String(required=True, description='instance type', default='ml.m4.xlarge'),
    })


model_payload = project_model_ns.model('model', model={
    'variant_name': fields.String(required=True, default='default'),
    'spec_train': fields.Nested(required=False, model=spec_train, description='training'),
    'spec_serve': fields.Nested(required=False, model=spec_serve, description='serving'),
    'env_train': fields.Raw(required=False, description='training enviroment variable'),
    'env_serve': fields.Raw(required=False, description='serving enviroment variable'),
    })


@project_model_ns.route('/<string:project_name>')
class ProjectModel(Resource):
    @staticmethod
    @project_model_ns.expect(model_payload, validate=True)
    def post(project_name):
        """
        create new model under project
            :param project_name: project name
        """
        if not util_handler.is_valid_sagemaker_naming(project_name):
            abort(400, "bad endpoint name")
        new_project_model = request.json
        new_project_model['project_name'] = project_name
        new_project_model['variant_name'] = new_project_model.get('variant_name', 'default')
        response = dynamo_handler.create_project_model(**new_project_model)
        if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
            return {'project_name':project_name}, 201
        abort(500, response)


@project_model_ns.route('/<string:project_name>/<string:variant_name>')
class ProjectModelDetails(Resource):
    @staticmethod
    def get(project_name, variant_name):
        if not util_handler.is_valid_sagemaker_naming(project_name):
            abort(400, "bad endpoint name")
        response = dynamo_handler.get_project_model(project_name, variant_name=variant_name)
        return util_handler.dynamo_item_json_parser(response or {}), 200
