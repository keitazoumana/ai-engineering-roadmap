import os

from crewai import Agent, Crew, LLM, Process, Task # type: ignore[index]
from crewai.project import CrewBase, agent, crew, task # type: ignore[index]
from crewai.agents.agent_builder.base_agent import BaseAgent # type: ignore[index]
from crewai_tools import OCRTool # type: ignore[index]
from dotenv import load_dotenv # type: ignore[index]

from subscription_auditor.tools.custom_tool import StatementReaderTool

# Load .env so MODEL and AWS_* are available to the code below.
load_dotenv()


def build_bedrock_llm() -> LLM:
    """LLM backed by AWS Bedrock, configured from .env (MODEL, AWS_REGION_NAME)."""
    return LLM(
        model=os.getenv("MODEL", "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        aws_region_name=os.getenv("AWS_REGION_NAME", "us-east-1"),
    )


@CrewBase
class SubscriptionAuditor():
    """Finds forgotten subscriptions, price increases and duplicate charges."""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def statement_extractor(self) -> Agent:
        return Agent(
            config=self.agents_config['statement_extractor'],  # type: ignore[index]
            tools=[StatementReaderTool(), OCRTool()],
            llm=build_bedrock_llm(),
            verbose=True,
        )

    @agent
    def subscription_detective(self) -> Agent:
        return Agent(
            config=self.agents_config['subscription_detective'],  # type: ignore[index]
            llm=build_bedrock_llm(),
            verbose=True,
        )

    @agent
    def savings_reviewer(self) -> Agent:
        return Agent(
            config=self.agents_config['savings_reviewer'],  # type: ignore[index]
            llm=build_bedrock_llm(),
            verbose=True,
        )

    @task
    def extract_task(self) -> Task:
        return Task(
            config=self.tasks_config['extract_task'],  # type: ignore[index]
            output_file='transactions.csv',
        )

    @task
    def detect_task(self) -> Task:
        return Task(config=self.tasks_config['detect_task'])  # type: ignore[index]

    @task
    def review_task(self) -> Task:
        return Task(
            config=self.tasks_config['review_task'],  # type: ignore[index]
            output_file='report.md',
        )

    @crew
    def crew(self) -> Crew:
        """Creates the SubscriptionAuditor crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
