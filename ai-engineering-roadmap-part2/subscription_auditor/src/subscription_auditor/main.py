#!/usr/bin/env python
import os
import sys
import warnings

from datetime import datetime

from dotenv import load_dotenv # type: ignore[index]

from subscription_auditor.crew import SubscriptionAuditor

load_dotenv()

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def check_required_env() -> None:
    """Fail early with a clear message if the .env is not set up for Bedrock."""
    required = ["MODEL", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION_NAME"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise Exception(
            "Missing required environment variables in .env: "
            + ", ".join(missing)
        )


def run():
    """
    Run the crew.
    """
    check_required_env()

    inputs = {
        'statement_path': os.getenv('STATEMENT_PATH', 'data/bluepine_statement_2026Q3.pdf')
    }

    try:
        SubscriptionAuditor().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        "topic": "AI LLMs",
        'current_year': str(datetime.now().year)
    }
    try:
        SubscriptionAuditor().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        SubscriptionAuditor().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        "topic": "AI LLMs",
        "current_year": str(datetime.now().year)
    }

    try:
        SubscriptionAuditor().crew().test(n_iterations=int(sys.argv[1]), eval_llm=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")

def run_with_trigger():
    """
    Run the crew with trigger payload.
    """
    import json

    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")

    inputs = {
        "crewai_trigger_payload": trigger_payload,
        "topic": "",
        "current_year": ""
    }

    try:
        result = SubscriptionAuditor().crew().kickoff(inputs=inputs)
        return result
    except Exception as e:
        raise Exception(f"An error occurred while running the crew with trigger: {e}")
