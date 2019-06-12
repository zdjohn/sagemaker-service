from flask_restplus import Api

#^[a-zA-Z0-9](-*[a-zA-Z0-9])* sagemaker naming convention regex

API = Api(version='1.0',
          title='ML pipeline service',
          description='ML pipeline service',
          doc='/',)

