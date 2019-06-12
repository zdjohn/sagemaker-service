import boto3
from sagemaker_svc_wrapper.handlers import dynamo_handler, sagemaker_handler


def jobs_update():
    job_status = ['Creating', 'Updating']
    for status in job_status:
        for job in dynamo_handler.list_jobs_by_status(status):
            endpoint = sagemaker_handler.describe_endpoint(job.get('job_name'))
            if endpoint.get('EndpointStatus') == 'InService':
                # update job status
                dynamo_handler.update_job(job.get('job_name'), {'endpoint_status': 'InService'})

                existing_project_model = dynamo_handler.get_project_model(job.get('project_name'), job.get('variant_name'))
                #retire existing model
                if existing_project_model.get('latest_model'):
                    sagemaker_handler.delete_endpoint(existing_project_model['latest_model'])
                    dynamo_handler.update_job(existing_project_model['latest_model'], {'endpoint_status': 'Retired'})
                # update project model latest
                dynamo_handler.update_project_model(job.get('project_name'), job.get('variant_name'), {'latest_model': job.get('job_name')})
                # update project pointer
                dynamo_handler.update_project(job.get('project_name'), {'serving_endpoint': job.get('job_name')})
            elif endpoint.get('EndpointStatus') == 'Failed':
                # update job status
                dynamo_handler.update_job(job.get('job_name'), {'endpoint_status': 'Failed'})
            else:
                pass
            print(endpoint)


# if __name__ == '__main__':
#     get_jobs_in_progress()
