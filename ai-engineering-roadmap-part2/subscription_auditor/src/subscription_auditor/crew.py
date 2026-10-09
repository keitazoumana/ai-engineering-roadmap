import os

from crewai import Agent, Crew, LLM, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from subscription_auditor.tools.custom_tool import StatementReaderTool
from subscription_auditor.tools.ocr_tool import BedrockOCRTool


def build_bedrock_llm() -> LLM:
    """LLM backed by Amazon Bedrock.

    Locally, credentials come from .env. In AgentCore Runtime, they come from the
    runtime's IAM execution role: no access keys are ever baked into the image.
    """
    return LLM(
        model=os.getenv("MODEL", "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        region_name=os.getenv("AWS_REGION_NAME") or os.getenv("AWS_REGION") or "us-east-1",
        temperature=0,
    )


@CrewBase
class SubscriptionAuditor():
    """Finds forgotten subscriptions, price increases and duplicate charges."""

    agents: list[BaseAgent]
    tasks: list[Task]

    @agent
    def statement_extractor(self) -> Agent:
        return Agent(
            config=self.agents_config['statement_extractor'],
            tools=[StatementReaderTool(), BedrockOCRTool()],
            llm=build_bedrock_llm(),
            verbose=True,
        )

    @agent
    def subscription_detective(self) -> Agent:
        return Agent(config=self.agents_config['subscription_detective'], llm=build_bedrock_llm(), verbose=True)

    @agent
    def savings_reviewer(self) -> Agent:
        return Agent(config=self.agents_config['savings_reviewer'], llm=build_bedrock_llm(), verbose=True)

    # No output_file here: results are returned from crew.kickoff(), so two
    # audits running at the same time can never overwrite each other's files.
    @task
    def extract_task(self) -> Task:
        return Task(config=self.tasks_config['extract_task'])

    @task
    def detect_task(self) -> Task:
        return Task(config=self.tasks_config['detect_task'])

    @task
    def review_task(self) -> Task:
        return Task(config=self.tasks_config['review_task'])

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
