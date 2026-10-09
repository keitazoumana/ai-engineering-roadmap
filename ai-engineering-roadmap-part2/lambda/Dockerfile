# AWS base image for Python Lambda. --platform selects arm64 to match the function.
FROM --platform=linux/arm64 public.ecr.aws/lambda/python:3.12

# A recent boto3, so the bedrock-agentcore client is always available.
RUN pip install --no-cache-dir boto3

# Function code into the Lambda task root.
COPY handler.py ${LAMBDA_TASK_ROOT}/

# "<module>.<function>" is the Lambda handler.
CMD ["handler.handler"]