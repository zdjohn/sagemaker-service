# this make file requires:
# python
# pip
# git
# jq, https://stedolan.github.io/jq/ (can be replaced with python scripts alltogether)
# self installable dependencies (using `make install-dependencies` rule)
# tox, https://pypi.python.org/pypi/tox
# awscli, https://pypi.python.org/pypi/awscli

TOX_WORKDIR ?= .tox
TOX_ENV ?= zappa
ZAPPA_STAGE ?= staging
ZAPPA_CMD ?= status

AWS_CF_STACK_NAME ?= 'modelzoo-service'  # TO FILL
AWS_CF_TEMPLATE_FILENAME ?= 'p-cloudformation.yaml'
AWS_CF_TEMPLATE_URL := 'file://$(AWS_CF_TEMPLATE_FILENAME)'

check-dependencies:
	jq --version
	git --version
	python --version
	make --version

install-dependencies:
	pip install tox awscli

zappa:
	tox --workdir $(TOX_WORKDIR) -e $(TOX_ENV) -- $(ZAPPA_CMD) $(ZAPPA_STAGE)

zappa-status:
	tox --workdir $(TOX_WORKDIR) -e $(TOX_ENV) -- status $(ZAPPA_STAGE)

zappa-deploy:
	tox --workdir $(TOX_WORKDIR) -e $(TOX_ENV) -- deploy $(ZAPPA_STAGE)

zappa-update:
	tox --workdir $(TOX_WORKDIR) -e $(TOX_ENV) -- update $(ZAPPA_STAGE)

zappa-create-or-update:
	if tox --workdir $(TOX_WORKDIR) -e $(TOX_ENV) -- status $(ZAPPA_STAGE); then \
		tox --workdir $(TOX_WORKDIR) -e $(TOX_ENV) -- update $(ZAPPA_STAGE); \
	else \
		tox --workdir $(TOX_WORKDIR) -e $(TOX_ENV) -- deploy $(ZAPPA_STAGE); \
	fi

.PHONY: zappa zappa-status zappa-deploy zappa-update

test:
	tox --workdir $(TOX_WORKDIR) -e test

.PHONY: test

aws-cf-stackname:
	@echo $(AWS_CF_STACK_NAME)

aws-cf-filename:
	@echo $(AWS_CF_TEMPLATE_FILENAME)

aws-profile:
	@echo $(AWS_PROFILE)

aws-cf-create:
	aws cloudformation create-stack --stack-name $(AWS_CF_STACK_NAME) --template-body $(AWS_CF_TEMPLATE_URL) --capabilities 'CAPABILITY_IAM'

aws-cf-describe:
	aws cloudformation describe-stacks --stack-name $(AWS_CF_STACK_NAME)

aws-cf-create-or-update:
# the complexity is given by awscli's update-stack which will return a
# non-zero code with "No updates to be performed" string in the
# message when there are no updates to be performed, which will
# normally make CI stop
# others are doing it as well: https://github.com/hashicorp/terraform/issues/5653
# including jenkins plugin we're using
# https://github.com/jenkinsci/pipeline-aws-plugin/blob/pipeline-aws-1.8/src/main/java/de/taimos/pipeline/aws/cloudformation/CloudFormationStack.java#L93
	if aws cloudformation update-stack --stack-name $(AWS_CF_STACK_NAME) --template-body $(AWS_CF_TEMPLATE_URL) --capabilities 'CAPABILITY_IAM' 1>/tmp/stdout.log 2>/tmp/stderr.log; then \
    echo "It seems your Cloudformation stack is getting updated."; \
    echo "Wait until its status is UPDATE_COMPLETE, then update any project files which need to be updated and merge them to your integration branch."; \
    echo "Then watch the status of the CI build triggered by those changes. If you have no changes to your project files, either re-build this build."; \
    cat /tmp/stdout.log; \
    echo "`make aws-cf-describe`"; \
    exit 1; \
  else \
    if grep 'No updates are to be performed' < /tmp/stderr.log; then \
      echo "That ^^ is no error. It's just aws cli's way of saying that no updates are needed ! All good!";\
    elif grep 'Stack.*does not exist' < /tmp/stderr.log; then \
      aws cloudformation create-stack --stack-name $(AWS_CF_STACK_NAME) --template-body $(AWS_CF_TEMPLATE_URL) --capabilities 'CAPABILITY_IAM'; \
      echo "It seems your Cloudformation stack is being created. Check its status with:"; \
      echo "aws cloudformation describe-stacks --stack-name $(AWS_CF_STACK_NAME)"; \
      echo "You might want to wait until its status is CREATED_COMPLETE then update your project files. (at the very least zappa_settings.json needs to be updated with the freshly created IAM Role)."; \
      echo "Once you're done updating, commit your updates and check the status of that new build."; \
      exit 2; \
    else \
      cat /tmp/stderr.log; \
    fi; \
  fi

aws-cf-validate:
	aws cloudformation validate-template --template-body $(AWS_CF_TEMPLATE_URL)

aws-cf-outputs:
# useful on local host. for now jxsq might not be availalbe on Jenkins. Probably a docker image would help.
	aws cloudformation describe-stacks --stack-name $(AWS_CF_STACK_NAME) | jq --monochrome-output 'reduce .Stacks[].Outputs[] as $$output ({}; .[$$output.OutputKey] |= $$output.OutputValue)' > .aws-cf-outputs
	cat .aws-cf-outputs

aws-cf-outputs-update-project: aws-cf-outputs
# for jq's in-place editing see https://github.com/stedolan/jq/wiki/FAQ#general-questions
# alternatively replace jq with python scripts
	@echo 'Still Work In Progress'
	@exit 123
	jq '.$(ZAPPA_STAGE).role_name = "$(shell jq --raw-output .LambdaRoleName < .aws-cf-outputs)"' zappa_settings.json > /tmp/tmp.json && mv /tmp/tmp.json zappa_settings.json
	jq '.$(ZAPPA_STAGE).events[1].event_source.arn = "arn:aws:s3:::$(shell jq --raw-output .MobileLayerExportsBucket < .aws-cf-outputs)"' zappa_settings.json > /tmp/tmp.json && mv /tmp/tmp.json zappa_settings.json
	jq '.$(ZAPPA_STAGE).remote_env = "s3://$(shell jq --raw-output .MobileLayerExportsBucket < .aws-cf-outputs)/secrets/environ.json"' zappa_settings.json > /tmp/tmp.json && mv /tmp/tmp.json zappa_settings.json
	sh 'echo "TODO create a new branch with modifications (if exists) and push it to origin. Would be nice to automatically creata a PR to allow developer to review and merge the modifications "'

.PHONY: aws-cf-stackname aws-cf-filename aws-cf-output aws-cf-outputs-update-project aws-cf-update aws-cf-validate aws-profile
