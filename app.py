import json
from decimal import Decimal
from flask.json import JSONEncoder
from flask import Flask, Response
from sagemaker_svc_wrapper.api.projects import project_ns as projects
from sagemaker_svc_wrapper.api.jobs import job_ns as jobs
from sagemaker_svc_wrapper.api.project_models import project_model_ns as modles
from sagemaker_svc_wrapper.api import API

def init():
    app = Flask(__name__)
    API.add_namespace(modles)
    API.add_namespace(jobs)
    API.add_namespace(projects)
    API.init_app(app)
    return app


app = init()


if __name__ == '__main__':
    app.run()
