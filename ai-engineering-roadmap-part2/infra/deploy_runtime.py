"""Create the AgentCore Runtime, or update it if it already exists.

Same settings as the console steps in 5.2: serverless, an ECR container image, IAM
inbound auth, a public network, and the two environment variables the crew needs.

Usage:
    AWS_PROFILE=auditor-admin python infra/deploy_runtime.py \
        --image <IMAGE_URI> --role-arn <RUNTIME_ROLE_ARN>

The image URI is the ECR tag you pushed (for example .../subscription-auditor:v1).
The role ARN is SubscriptionAuditorRuntimeRole from step 5.1.
"""
from __future__ import annotations

import argparse
import os
import sys

import boto3
from botocore.exceptions import ClientError

RUNTIME_NAME = "subscription_auditor"


def region_from_arn(arn: str) -> str | None:
    parts = arn.split(":")
    return parts[3] if len(parts) > 3 and parts[3] else None


def find_runtime(client, name: str) -> str | None:
    """Return the agentRuntimeId of the runtime with this name, or None."""
    paginator_input = {}
    while True:
        result = client.list_agent_runtimes(**paginator_input)
        for runtime in result.get("agentRuntimes", []):
            if runtime.get("agentRuntimeName") == name:
                return runtime.get("agentRuntimeId")
        token = result.get("nextToken")
        if not token:
            return None
        paginator_input = {"nextToken": token}


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy the SubscriptionAuditor AgentCore Runtime.")
    parser.add_argument("--image", required=True, help="ECR image URI, for example .../subscription-auditor:v1")
    parser.add_argument("--role-arn", required=True, help="Execution role ARN (SubscriptionAuditorRuntimeRole)")
    parser.add_argument("--name", default=RUNTIME_NAME, help="Runtime name (default: subscription_auditor)")
    args = parser.parse_args()

    region = region_from_arn(args.role_arn) or os.environ.get("AWS_REGION_NAME") or os.environ.get("AWS_REGION")
    if not region:
        print("Could not determine the region. Set AWS_REGION_NAME or AWS_REGION.", file=sys.stderr)
        return 1

    client = boto3.client("bedrock-agentcore-control", region_name=region)

    artifact = {"containerConfiguration": {"containerUri": args.image}}
    environment = {
        "MODEL": "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "AWS_REGION_NAME": region,
    }
    common = {
        "agentRuntimeArtifact": artifact,
        "roleArn": args.role_arn,
        "networkConfiguration": {"networkMode": "PUBLIC"},
        "environmentVariables": environment,
    }

    try:
        existing_id = find_runtime(client, args.name)
        if existing_id:
            print(f"Updating runtime {args.name} ({existing_id}) with image {args.image} ...")
            result = client.update_agent_runtime(agentRuntimeId=existing_id, **common)
        else:
            print(f"Creating runtime {args.name} with image {args.image} ...")
            result = client.create_agent_runtime(agentRuntimeName=args.name, **common)
    except ClientError as error:
        print(f"AgentCore request failed: {error}", file=sys.stderr)
        return 1

    arn = result.get("agentRuntimeArn", "")
    print("Done.")
    if arn:
        print(f"RUNTIME_ARN={arn}")
        print(f"RUNTIME_ID={arn.rsplit('/', 1)[-1]}")
    print("Wait for the status to reach Ready, then test with scripts/invoke_runtime.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
