import os

dev = {
    'role': 'arn:aws:iam::570761704186:role/service-role/AmazonSageMaker-ExecutionRole-20171211T115480',
    'project_table': 's-ml-pipeline-project',
    'job_table': 's-ml-pipeline-job',
    'endpoint_table': 's-ml-pipeline-endpoint',
    'project_models_table': 's-ml-pipeline-project-models',
}

stage = {} or dev

prod = {}

env_config = {
    'dev': dev,
    'stage': stage,
    'prod': prod
}

class SystemConfig:
    def __init__(self, env):
        self.__dict__.update(env_config[env])


SYS_CONFIG = SystemConfig(os.environ.get('config_env') or 'dev')