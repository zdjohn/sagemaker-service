from flask import request, abort
from flask_restplus import Resource, Namespace, fields
from ..handlers import dynamo_handler, util_handler

project_ns = Namespace('project', description='ML pipeline service', strict_slashes=False)


project_payload = project_ns.model('project', model={
    'variants': fields.Raw(),
    'is_auto_deploy': fields.Boolean(required=True, default=True),
    'is_active': fields.Boolean(required=True, default=True),
    })


@project_ns.route('/<string:project_name>/jobs')
class ProjectJobs(Resource):
    def get(self, project_name):
        # variant_name = request.args.get('variant_name', 'default')
        response = dynamo_handler.list_jobs(project_name)
        return [util_handler.dynamo_item_json_parser(r) for r in response]


@project_ns.route('/<string:project_name>/models')
class ProjectModels(Resource):
    def get(self, project_name):
        # variant_name = request.args.get('variant_name', 'default')
        response = dynamo_handler.list_project_models(project_name)
        return [util_handler.dynamo_item_json_parser(r) for r in response]


@project_ns.route('/<string:project_name>')
class Project(Resource):
    @staticmethod
    def get(project_name):
        response = dynamo_handler.get_project(project_name)
        return util_handler.dynamo_item_json_parser(response), 200

    @staticmethod
    @project_ns.expect(project_payload)
    def post(project_name):
        request_item = request.json
        response_name = dynamo_handler.create_project(project_name, **request_item)
        if response_name:
            return project_name, 200
        return f'unable to create project {project_name}', 400
