"""Async orchestrator for the 6-manager BRD generation pipeline using deepagents native subagents.

Architecture:
- 6 manager agents: Drool, Model, Outbound, Transformation, Inbound, Reviewer
- Each manager has specialized sub-agents (Analysis, Synthesis, Writer, Review)
- Deepagents framework handles sub-agent delegation and orchestration internally
- Execution flow:
  1. Drool and Model run IN PARALLEL (asyncio.gather)
  2. Outbound → Transformation → Inbound run SEQUENTIALLY
  3. Reviewer runs and validates completeness
  4. If gaps found, managers reprocess with feedback (max 2 retries)

Features:
- Pure async/await (no asyncio.run() inside async functions)
- asyncio.gather() for parallel execution of independent managers
- Execution time tracking per manager
- Token usage tracking with cost accounting
- Graceful error handling with fallback to partial results
- Structured logging with standard logging
- ExecutionResult with full context and summary

Sub-Agent Orchestration (via deepagents native support):
- Each manager agent is created with a `subagents` parameter
- Subagents are defined as dictionaries with name, description, system_prompt, tools
- Deepagents framework automatically handles:
  * Sub-agent invocation and delegation
  * Context passing between sub-agents
  * Output aggregation from sub-agents
  * Sequential or parallel sub-agent execution based on agent logic
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from langchain.chat_models import BaseChatModel, init_chat_model

from src.config import get_config
from src.guardrails import get_input_guardrail
from src.tools.llm_client import get_llm_client
from src.models import (
    ExecutionContext,
    ExecutionResult,
    AgentMessage,
    MessageStatus,
    AgentType,
    SubAgentType,
    TokenTracker,
    TokenAccount,
    ReprocessRequest,
)
from src.agents.agent_definitions import create_all_managers

# Configure structured logging
logger = logging.getLogger(__name__)


class BRDOrchestrator:
    """Comprehensive asyncio-based orchestrator for 6-manager BRD generation pipeline."""

    def __init__(self):
        """Initialize orchestrator with config, model, and agent dependencies."""
        self.config = get_config()
        self.guardrail = get_input_guardrail()

        # Initialize LLM model using multi-provider factory
        self.model: BaseChatModel = get_llm_client()

        # Manager agents (will be created per pipeline run)
        self.managers: Dict[str, Any] = {}

        # Execution context (per pipeline run)
        self.context: Optional[ExecutionContext] = None

        logger.info(
            f"BRDOrchestrator initialized with provider '{self.config.llm_provider}' "
            f"and model '{self.config.llm_model}'"
        )

    async def run_pipeline(
        self,
        user_query: str,
        corpus_files: List[str],
        golden_brd_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ) -> ExecutionResult:
        """
        Main entry point for the BRD generation pipeline.

        Execution flow:
        1. Drool + Model run in parallel
        2. Outbound → Transformation → Inbound run sequentially
        3. Reviewer runs and validates
        4. If gaps found, request reprocessing (max 2 retries)

        Args:
            user_query: User's input query
            corpus_files: List of corpus files to analyze
            golden_brd_path: Optional path to golden BRD for reference
            output_dir: Output directory for results

        Returns:
            ExecutionResult with status, messages, tokens, and execution metadata
        """
        # Validate input
        is_valid, violations = self.guardrail.validate_input(user_query)
        if not is_valid:
            logger.error("Input validation failed")
            violation_summary = self.guardrail.get_violation_summary(violations)
            return ExecutionResult(
                status=MessageStatus.ERROR,
                errors=[violation_summary],
                execution_id=str(uuid.uuid4()),
            )

        # Initialize execution context
        output_dir = output_dir or self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        self.context = ExecutionContext(
            user_query=user_query,
            corpus_files=corpus_files,
            output_dir=output_dir,
            max_timeout_sec=self.config.agent_timeout_sec,
            retry_count=self.config.max_retries,
            execution_id=str(uuid.uuid4()),
        )

        # Create all manager agents
        self.managers = create_all_managers(self.model)

        logger.info("=" * 80)
        logger.info("BRD Generation Pipeline (6-Manager Orchestration)")
        logger.info("=" * 80)
        logger.info(f"Execution ID: {self.context.execution_id}")
        logger.info(f"Query: {user_query}")
        logger.info(f"Corpus files: {len(corpus_files)}")
        logger.info(f"Model: {self.config.openai_model}")

        try:
            # ================================================================
            # PHASE 1: Drool + Model in PARALLEL
            # ================================================================
            logger.info("\n[PHASE 1] Running Drool and Model in parallel...")
            drool_msg, model_msg = await self._run_drool_and_model_parallel()

            if drool_msg:
                self.context.add_message(drool_msg)
                logger.info(
                    f"✓ Drool completed in {drool_msg.duration_ms:.2f}ms"
                )
            else:
                logger.warning("Drool manager produced no output")

            if model_msg:
                self.context.add_message(model_msg)
                logger.info(f"✓ Model completed in {model_msg.duration_ms:.2f}ms")
            else:
                logger.warning("Model manager produced no output")

            # ================================================================
            # PHASE 2: Sequential Cascade (Outbound → Transformation → Inbound)
            # ================================================================
            logger.info("\n[PHASE 2] Running sequential cascade...")
            cascade_messages = await self._run_sequential_cascade()
            for msg in cascade_messages:
                if msg:
                    self.context.add_message(msg)
                    logger.info(
                        f"✓ {msg.agent_id} completed in {msg.duration_ms:.2f}ms"
                    )

            # ================================================================
            # PHASE 3: Reviewer Validation with Feedback Loop
            # ================================================================
            logger.info("\n[PHASE 3] Running Reviewer with feedback loop...")
            reviewer_msg = await self._run_reviewer_with_feedback_loop()
            if reviewer_msg:
                self.context.add_message(reviewer_msg)
                logger.info(
                    f"✓ Reviewer completed in {reviewer_msg.duration_ms:.2f}ms"
                )

            # ================================================================
            # PHASE 4: Finalize Results
            # ================================================================
            logger.info("\n[PHASE 4] Finalizing results...")
            elapsed_time = self.context.get_elapsed_time_sec()

            logger.info("\n" + "=" * 80)
            logger.info(f"✓ Pipeline completed successfully in {elapsed_time:.2f}s")
            logger.info(f"Total messages: {len(self.context.all_messages)}")
            logger.info(
                f"Token summary: {self.context.token_tracker.get_summary()}"
            )
            logger.info("=" * 80)

            return ExecutionResult(
                status=MessageStatus.SUCCESS,
                all_messages=self.context.all_messages,
                token_summary=self.context.token_tracker.get_summary(),
                execution_time_sec=elapsed_time,
                execution_id=self.context.execution_id,
                warnings=self._collect_warnings(),
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            elapsed_time = self.context.get_elapsed_time_sec()

            return ExecutionResult(
                status=MessageStatus.ERROR,
                all_messages=self.context.all_messages,
                token_summary=self.context.token_tracker.get_summary(),
                execution_time_sec=elapsed_time,
                errors=[str(e)],
                execution_id=self.context.execution_id,
            )

    async def _run_drool_and_model_parallel(
        self,
    ) -> Tuple[Optional[AgentMessage], Optional[AgentMessage]]:
        """Run Drool and Model managers in parallel using asyncio.gather.

        Returns:
            Tuple of (drool_message, model_message)
        """
        try:
            # Create tasks for parallel execution
            drool_task = asyncio.create_task(self._execute_manager("drool"))
            model_task = asyncio.create_task(self._execute_manager("model"))

            # Wait for both to complete
            drool_msg, model_msg = await asyncio.gather(
                drool_task, model_task, return_exceptions=False
            )

            return drool_msg, model_msg

        except Exception as e:
            logger.error(f"Parallel phase failed: {e}", exc_info=True)
            return None, None

    async def _run_sequential_cascade(
        self,
    ) -> List[Optional[AgentMessage]]:
        """Run Outbound → Transformation → Inbound sequentially.

        Returns:
            List of messages from [outbound, transformation, inbound]
        """
        results = []

        try:
            # Sequential managers (run one after another)
            for manager_name in ["outbound", "transformation", "inbound"]:
                logger.info(f"  → Starting {manager_name}...")
                msg = await self._execute_manager(manager_name)
                results.append(msg)

                if msg and msg.status == MessageStatus.ERROR:
                    logger.warning(
                        f"Manager {manager_name} encountered an error: "
                        f"{msg.metadata.get('error', 'Unknown error')}"
                    )

            return results

        except Exception as e:
            logger.error(f"Sequential cascade failed: {e}", exc_info=True)
            return results

    async def _run_reviewer_with_feedback_loop(self) -> Optional[AgentMessage]:
        """Run Reviewer with feedback loop for gap detection and reprocessing.

        The Reviewer:
        1. Synthesizes all manager outputs
        2. Validates completeness
        3. If gaps detected, sends feedback to specific managers
        4. Reruns affected managers (max 2 retries)
        5. Reruns Reviewer to validate again

        Returns:
            Final reviewer message
        """
        max_feedback_iterations = self.config.max_retries
        current_iteration = 0

        while current_iteration <= max_feedback_iterations:
            logger.info(
                f"  → Reviewer iteration {current_iteration + 1}/"
                f"{max_feedback_iterations + 1}"
            )

            # Run reviewer
            reviewer_msg = await self._execute_manager("reviewer")

            if not reviewer_msg:
                logger.warning("Reviewer produced no output")
                return None

            current_iteration += 1

            # Check for gaps in metadata
            gaps = reviewer_msg.metadata.get("gaps", [])

            if not gaps or current_iteration > max_feedback_iterations:
                logger.info(f"✓ Reviewer validation complete (iteration {current_iteration})")
                return reviewer_msg

            # Process feedback - rerun affected managers
            logger.info(
                f"  → Gaps detected ({len(gaps)}). "
                f"Requesting reprocessing... (Iteration {current_iteration}/{max_feedback_iterations})"
            )

            await self._process_manager_feedback(gaps)

        logger.warning(
            f"Max feedback iterations ({max_feedback_iterations}) reached"
        )
        return reviewer_msg

    async def _execute_manager(
        self,
        manager_name: str,
        feedback_request: Optional[ReprocessRequest] = None,
    ) -> Optional[AgentMessage]:
        """Execute a single manager agent with timeout and error handling.

        Args:
            manager_name: Name of manager ('drool', 'model', 'outbound', etc.)
            feedback_request: Optional feedback request for reprocessing

        Returns:
            AgentMessage with execution results or None on error
        """
        if manager_name not in self.managers:
            logger.error(f"Unknown manager: {manager_name}")
            return None

        manager = self.managers[manager_name]
        start_time = time.time()

        try:
            # Build context for agent invocation
            prior_messages = self.context.all_messages

            # Prepare prompts with context
            user_message = self._build_manager_prompt(
                manager_name, prior_messages, feedback_request
            )

            # Execute manager with timeout
            try:
                result = await asyncio.wait_for(
                    self._invoke_manager_async(manager, user_message),
                    timeout=self.config.agent_timeout_sec,
                )
            except asyncio.TimeoutError:
                logger.error(f"Manager {manager_name} timed out")
                return AgentMessage(
                    agent_id=manager_name,
                    agent_type=AgentType.MANAGER,
                    status=MessageStatus.TIMEOUT,
                    markdown_content="",
                    metadata={"error": f"Timeout after {self.config.agent_timeout_sec}s"},
                    duration_ms=(time.time() - start_time) * 1000,
                )

            # Extract content and metadata
            content = result.get("content", "")
            metadata = result.get("metadata", {})

            # Record token usage if available
            if self.config.track_tokens:
                token_data = result.get("token_data", {})
                if token_data:
                    self.context.token_tracker.record_estimate(
                        agent_id=manager_name,
                        input_tokens=token_data.get("input_tokens", 0),
                        output_tokens=token_data.get("output_tokens", 0),
                    )

            # Create AgentMessage
            duration_ms = (time.time() - start_time) * 1000

            message = AgentMessage(
                agent_id=manager_name,
                agent_type=AgentType.MANAGER,
                markdown_content=content,
                metadata=metadata,
                duration_ms=duration_ms,
                status=MessageStatus.SUCCESS,
            )

            logger.debug(
                f"Manager {manager_name} executed successfully "
                f"({len(content)} chars, {duration_ms:.2f}ms)"
            )

            return message

        except Exception as e:
            logger.error(f"Manager {manager_name} failed: {e}", exc_info=True)
            duration_ms = (time.time() - start_time) * 1000

            return AgentMessage(
                agent_id=manager_name,
                agent_type=AgentType.MANAGER,
                status=MessageStatus.ERROR,
                markdown_content="",
                metadata={"error": str(e)},
                duration_ms=duration_ms,
            )

    async def _invoke_manager_async(
        self, manager: Any, user_message: str
    ) -> Dict[str, Any]:
        """Invoke a manager agent asynchronously.

        Args:
            manager: The manager agent instance
            user_message: The input message

        Returns:
            Dictionary with 'content' and optional 'metadata' and 'token_data'
        """
        # Run agent invocation in executor to avoid blocking
        loop = asyncio.get_event_loop()

        def invoke_sync():
            try:
                result = manager.invoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": user_message,
                            }
                        ]
                    }
                )

                # Extract content from result
                content = ""
                metadata = {}

                if isinstance(result, dict):
                    # DeepAgents returns dict with 'messages' key
                    if "messages" in result:
                        messages = result["messages"]
                        if isinstance(messages, list) and len(messages) > 0:
                            last_msg = messages[-1]
                            if isinstance(last_msg, dict):
                                content = last_msg.get("content", "")
                            else:
                                content = str(last_msg)
                    else:
                        content = str(result)
                else:
                    content = str(result)

                return {
                    "content": content,
                    "metadata": metadata,
                    "token_data": result.get("token_data", {})
                    if isinstance(result, dict)
                    else {},
                }

            except Exception as e:
                logger.error(f"Error invoking manager: {e}")
                return {
                    "content": "",
                    "metadata": {"error": str(e)},
                    "token_data": {},
                }

        return await loop.run_in_executor(None, invoke_sync)

    async def _process_manager_feedback(
        self, gaps: List[Dict[str, Any]]
    ) -> None:
        """Process feedback from Reviewer and request manager reruns.

        Args:
            gaps: List of gap dictionaries with 'agent_id', 'domain', 'feedback'
        """
        if not gaps:
            logger.info("No gaps to process")
            return

        # Group gaps by agent
        gaps_by_agent = {}
        for gap in gaps:
            agent_id = gap.get("agent_id", "unknown")
            if agent_id not in gaps_by_agent:
                gaps_by_agent[agent_id] = []
            gaps_by_agent[agent_id].append(gap)

        logger.info(f"Processing gaps for {len(gaps_by_agent)} manager(s)")

        # Reprocess affected managers
        for agent_id, agent_gaps in gaps_by_agent.items():
            if agent_id not in self.managers:
                logger.warning(f"Unknown manager for feedback: {agent_id}")
                continue

            # Create reprocess request
            feedback = "\n".join([g.get("feedback", "") for g in agent_gaps])
            missing_items = []
            for g in agent_gaps:
                missing_items.extend(g.get("missing_items", []))

            reprocess_request = ReprocessRequest(
                agent_id=agent_id,
                domain=agent_gaps[0].get("domain", ""),
                feedback=feedback,
                context="Feedback from Reviewer after initial validation",
                missing_items=missing_items,
                retry_count=1,
            )

            logger.info(
                f"  → Reprocessing {agent_id} with feedback "
                f"({len(agent_gaps)} gaps identified)"
            )

            # Rerun the manager with feedback
            rerrun_msg = await self._execute_manager(
                agent_id, feedback_request=reprocess_request
            )

            if rerrun_msg:
                self.context.add_message(rerrun_msg)
                logger.info(f"  ✓ {agent_id} reprocessed")

    def _build_manager_prompt(
        self,
        manager_name: str,
        prior_messages: List[AgentMessage],
        feedback_request: Optional[ReprocessRequest] = None,
    ) -> str:
        """Build context-aware prompt for a manager agent.

        Args:
            manager_name: Name of the manager
            prior_messages: All previous messages in execution
            feedback_request: Optional feedback for reprocessing

        Returns:
            Full prompt text with context
        """
        # Get prior outputs relevant to this manager
        prior_context = self._extract_context_for_manager(manager_name, prior_messages)

        base_prompt = f"""You are the {manager_name.upper()} Manager Agent for BRD generation.

User Query: {self.context.user_query}
Corpus Files: {', '.join(self.context.corpus_files[:10])}

"""

        if prior_context:
            base_prompt += f"""Previous Analysis Context:
{prior_context}

"""

        if feedback_request:
            base_prompt += f"""REPROCESSING REQUEST:
Domain: {feedback_request.domain}
Feedback: {feedback_request.feedback}
Missing Items: {', '.join(feedback_request.missing_items)}

Please reprocess and address the gaps identified above.
"""
        else:
            base_prompt += """Please analyze the query and corpus files to generate comprehensive output for your domain."""

        return base_prompt

    def _extract_context_for_manager(
        self, manager_name: str, messages: List[AgentMessage]
    ) -> str:
        """Extract relevant context from prior messages for a specific manager.

        Args:
            manager_name: Name of the manager
            messages: All prior messages

        Returns:
            Context string with relevant prior outputs
        """
        relevant_agents = self._get_manager_dependencies(manager_name)

        context_parts = []
        for prior_msg in messages:
            if prior_msg.agent_id in relevant_agents:
                if prior_msg.markdown_content:
                    context_parts.append(
                        f"## {prior_msg.agent_id.upper()} Output:\n{prior_msg.markdown_content[:1000]}"
                    )

        return "\n\n".join(context_parts) if context_parts else ""

    @staticmethod
    def _get_manager_dependencies(manager_name: str) -> List[str]:
        """Get list of managers whose outputs this manager depends on.

        Args:
            manager_name: Name of the manager

        Returns:
            List of dependency manager names
        """
        dependencies = {
            "drool": [],
            "model": [],
            "outbound": ["drool", "model"],
            "transformation": ["drool", "model", "outbound"],
            "inbound": ["drool", "model", "outbound", "transformation"],
            "reviewer": ["drool", "model", "outbound", "transformation", "inbound"],
        }
        return dependencies.get(manager_name, [])

    def _collect_warnings(self) -> List[str]:
        """Collect warnings from execution context.

        Returns:
            List of warning messages
        """
        warnings = []

        # Check for messages with errors or timeouts
        for msg in self.context.all_messages:
            if msg.status == MessageStatus.TIMEOUT:
                warnings.append(f"{msg.agent_id} timed out")
            elif msg.status == MessageStatus.PARTIAL:
                warnings.append(f"{msg.agent_id} produced partial results")
            elif msg.status == MessageStatus.FALLBACK:
                warnings.append(f"{msg.agent_id} fell back to default behavior")

        # Check token usage
        token_summary = self.context.token_tracker.get_summary()
        if token_summary.get("total_cost_estimate", 0) > 10:
            warnings.append(
                f"High token cost: ${token_summary['total_cost_estimate']:.2f}"
            )

        return warnings


async def main():
    """Example usage of the BRDOrchestrator."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    orchestrator = BRDOrchestrator()

    result = await orchestrator.run_pipeline(
        user_query="Create a BRD for a user authentication system with OAuth2 integration",
        corpus_files=[
            "requirements.md",
            "api_spec.md",
            "features.md",
        ],
    )

    print("\n" + "=" * 80)
    print("EXECUTION RESULT")
    print("=" * 80)
    print(f"Status: {result.status.value}")
    print(f"Execution ID: {result.execution_id}")
    print(f"Execution Time: {result.execution_time_sec:.2f}s")
    print(f"Messages Generated: {len(result.all_messages)}")
    print(f"Token Summary: {result.token_summary}")
    if result.warnings:
        print(f"Warnings: {result.warnings}")
    if result.errors:
        print(f"Errors: {result.errors}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
