import time
import json
import shutil

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.logger import get_logger
from src.factory import MCPServiceFactory
from src.model_config import ModelConfig
from src.results_reporter import EvaluationReport, ResultsReporter, TaskResult
from src.agent import MCPAgent

PIPELINE_RETRY_ERRORS: List[str] = [
    "State Duplication Error",
    "MCP Network Error",
]

# Initialize logger
logger = get_logger(__name__)


class MCPEvaluator:
    def __init__(
        self,
        service: str,
        model: str,
        timeout: int = 300,
        exp_name: str = "test-run",
        output_dir: Path = None,
    ):
        # Main configuration
        self.service = service
        self.model = model
        self.timeout = timeout

        # Initialize model configuration
        model_config = ModelConfig(model)
        self.actual_model_name = model_config.actual_model_name
        self.base_url = model_config.base_url
        self.api_key = model_config.api_key

        # Initialize agent for LLM and MCP server management
        self.agent = MCPAgent(
            model_name=self.actual_model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            service=service,
            timeout=timeout,
        )
        
        # Initialize managers using the factory pattern (simplified)
        self.task_manager = MCPServiceFactory.create_task_manager(service)
        self.state_manager = MCPServiceFactory.create_state_manager(service)

        # Initialize results reporter
        self.results_reporter = ResultsReporter()

        # Output directory handling
        model_slug = self.model.replace(".", "-")
        self.base_experiment_dir = output_dir / exp_name / f"{service}_{model_slug}"
        self.base_experiment_dir.mkdir(parents=True, exist_ok=True)

    def _get_task_output_dir(self, task) -> Path:
        """Return the directory path for storing this task's reports."""
        # Replace underscores with hyphens inside the category name
        category_slug = (
            task.category.replace("_", "-") if task.category else "uncategorized"
        )
        task_slug = f"task-{task.task_id}"

        return self.base_experiment_dir / f"{category_slug}_{task_slug}"

    # ------------------------------------------------------------------
    # Resuming helpers
    # ------------------------------------------------------------------

    def _load_latest_task_result(self, task) -> Optional[TaskResult]:
        """Return the most recent TaskResult for *task* if it has been run before."""
        task_dir = self._get_task_output_dir(task)
        if not task_dir.exists():
            return None

        meta_path = task_dir / "meta.json"
        if not meta_path.exists():
            return None

        try:
            with meta_path.open("r", encoding="utf-8") as f:
                meta_data = json.load(f)

            # Reconstruct TaskResult from meta.json
            return TaskResult(
                task_name=meta_data["task_name"],
                success=meta_data["execution_result"]["success"],
                execution_time=meta_data["execution_time"],
                error_message=meta_data["execution_result"]["error_message"],
                category=task.category,
                task_id=task.task_id,
                # We don't need model_output for resume functionality
                model_output=None,
            )
        except Exception as exc:
            logger.warning("Failed to load existing result for %s: %s", task.name, exc)
        return None

    def _gather_all_task_results(self) -> List[TaskResult]:
        """Scan *all* task sub-directories and collect the latest TaskResult from each."""
        results: list[TaskResult] = []
        if not self.base_experiment_dir.exists():
            return results

        for task_dir in self.base_experiment_dir.iterdir():
            if not task_dir.is_dir():
                continue
            meta_path = task_dir / "meta.json"
            if not meta_path.exists():
                continue
            try:
                with meta_path.open("r", encoding="utf-8") as f:
                    meta_data = json.load(f)

                # Extract category and task_id from directory name
                # Format: category_task-N
                dir_parts = task_dir.name.split("_task-")
                if len(dir_parts) == 2:
                    category = dir_parts[0].replace("-", "_")
                    task_id = int(dir_parts[1])
                else:
                    category = "unknown"
                    task_id = 0

                result = TaskResult(
                    task_name=meta_data["task_name"],
                    success=meta_data["execution_result"]["success"],
                    execution_time=meta_data["execution_time"],
                    error_message=meta_data["execution_result"]["error_message"],
                    category=category,
                    task_id=task_id,
                    model_output=None,
                )
                results.append(result)
            except Exception as exc:
                logger.warning("Failed to parse existing report in %s: %s", task_dir, exc)
        return results

    def _run_single_task(self, task) -> TaskResult:
        """
        Runs a single task, including setup, agent execution, verification, and cleanup.
        """
        # Stage 1: Set up the initial state for the task
        setup_start_time = time.time()
        logger.info("==================== Stage 1: Setting Up Task ====================")
        setup_success = self.state_manager.set_up(task)
        setup_time = time.time() - setup_start_time

        if not setup_success:
            logger.error(f"State setup failed for task: {task.name}")
            return TaskResult(
                task_name=task.name,
                success=False,
                execution_time=setup_time,
                error_message="State Duplication Error",
                category=task.category,
                task_id=task.task_id,
            )

        # Stage 2: Execute the task using the agent
        logger.info("\n==================== Stage 2: Executing Task =======================")
        
        # Get task instruction from task manager
        task_instruction = self.task_manager.get_task_instruction(task)
        
        # Get service-specific configuration from state manager
        service_config = self.state_manager.get_service_config_for_agent()
        
        # Execute with agent
        agent_result = self.agent.execute_sync(task_instruction, **service_config)
        
        # Stage 3: Verify the task result using task manager
        logger.info("\n==================== Stage 3: Verifying Task =======================")
        result = self.task_manager.execute_task(task, agent_result)
        
        # Stage 4: Clean up the temporary task state
        logger.info("\n==================== Stage 4: Cleaning Up =========================")
        self.state_manager.clean_up(task)

        return result
    

    def run_evaluation(self, task_filter: str) -> EvaluationReport:
        """
        Runs the full evaluation for the specified tasks.
        """
        tasks = self.task_manager.filter_tasks(task_filter)
        pipeline_start_time = time.time()

        results = []

        for task in tasks:
            # ------------------------ Resume check ------------------------
            existing_result = self._load_latest_task_result(task)

            # ------------------------------------------------------
            # Decide whether to skip or retry this task based on the
            # previous result and retryable pipeline errors.
            # ------------------------------------------------------
            retry_due_to_error = (
                existing_result is not None
                and not existing_result.success
                and existing_result.error_message in PIPELINE_RETRY_ERRORS
            )

            if existing_result and not retry_due_to_error:
                # Existing result is either successful or failed with a non-retryable error – skip.
                logger.info("↩️  Skipping already-completed task (resume): %s", task.name)
                results.append(existing_result)
                continue

            if retry_due_to_error:
                # Clean previous artifacts so that new results fully replace them.
                task_output_dir = self._get_task_output_dir(task)
                if task_output_dir.exists():
                    shutil.rmtree(task_output_dir)
                logger.info(
                    "🔄 Retrying task due to pipeline error (%s): %s",
                    existing_result.error_message,
                    task.name,
                )

            # -------------------- Execute new task -----------------------
            task_start = time.time()
            task_result = self._run_single_task(task)
            task_end = time.time()

            results.append(task_result)

            # ----------------------------------------------------------
            # Save results for this single task immediately for resume
            # ----------------------------------------------------------
            # Prepare directory & save
            task_output_dir = self._get_task_output_dir(task)
            task_output_dir.mkdir(parents=True, exist_ok=True)

            # Save messages.json (conversation trajectory)
            messages_path = task_output_dir / "messages.json"
            # Extract messages from model_output if available
            messages = task_result.model_output if hasattr(task_result, 'model_output') and task_result.model_output else []
            self.results_reporter.save_messages_json(messages, messages_path)

            # Save meta.json (all other metadata)
            meta_path = task_output_dir / "meta.json"
            model_config = {
                "service": self.service,
                "base_url": self.base_url,
                "model_name": self.actual_model_name,
                "timeout": self.timeout,
            }
            self.results_reporter.save_meta_json(
                task_result,
                model_config,
                datetime.fromtimestamp(task_start),
                datetime.fromtimestamp(task_end),
                meta_path,
            )

        pipeline_end_time = time.time()

        # --------------------------------------------------------------
        # Aggregate results – combine current `results` with any previously
        # saved TaskResults that ALSO match the current task_filter.
        # --------------------------------------------------------------

        # Helper: determine if a TaskResult matches the filter string
        def _matches_filter(tr: TaskResult, flt: str) -> bool:
            if flt.lower() == "all":
                return True
            if "/" in flt:
                # specific task (category/task_N)
                return tr.task_name == flt
            # category level
            return tr.category == flt

        # Pull existing reports from disk and merge
        existing_results = [
            r
            for r in self._gather_all_task_results()
            if _matches_filter(r, task_filter)
        ]

        # Merge, giving preference to fresh `results` (avoids duplicates)
        merged: dict[str, TaskResult] = {r.task_name: r for r in existing_results}
        merged.update({r.task_name: r for r in results})  # overwrite with latest run

        final_results = list(merged.values())

        aggregated_report = EvaluationReport(
            model_name=self.model,
            model_config={
                "service": self.service,
                "base_url": self.base_url,
                "model_name": self.actual_model_name,
                "timeout": self.timeout,
            },
            start_time=datetime.fromtimestamp(pipeline_start_time),
            end_time=datetime.fromtimestamp(pipeline_end_time),
            total_tasks=len(final_results),
            successful_tasks=sum(1 for r in final_results if r.success),
            failed_tasks=sum(1 for r in final_results if not r.success),
            task_results=final_results,
            tasks_filter=task_filter,
        )

        # Save model-level summary
        summary_path = self.base_experiment_dir / "summary.json"
        self.results_reporter.save_model_summary(aggregated_report, summary_path)

        logger.info("\n==================== Evaluation Summary ===========================")
        logger.info(
            f"✓ Tasks: {aggregated_report.successful_tasks}/{aggregated_report.total_tasks} passed ({aggregated_report.success_rate:.1f}%)"
        )
        logger.info(f"✓ Total time: {aggregated_report.execution_time.total_seconds():.1f}s")

        return aggregated_report
