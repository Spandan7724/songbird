# songbird/agent/plan_manager.py
"""Plan generation and management for agentic workflows."""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from .planning import AgentPlan, PlanStep, PlanStatus


class PlanManager:
    """Manages plan generation, execution, and updates."""
    
    def __init__(self):
        self.current_plan: Optional[AgentPlan] = None
        self.plan_history: List[AgentPlan] = []
    
    async def generate_plan_prompt(self, user_request: str, context: Dict[str, Any]) -> str:
        """Generate a prompt for the LLM to create an execution plan."""
        

        planning_indicators = [
            # File operations
            "create", "build", "make", "generate", "write", "add", "implement",
            # Multi-step words
            "multiple", "several", "all", "entire", "complete", "full", "and",
            # Project words
            "project", "application", "system", "feature", "module", "setup", "configure", "install",
            # Numbers that suggest multiple items
            "three", "four", "five", "2", "3", "4", "5", "two", "both"
        ]
        
        request_lower = user_request.lower()
        has_planning_indicator = any(indicator in request_lower for indicator in planning_indicators)

        should_plan = (
            has_planning_indicator or  # Contains planning keywords
            len(user_request.split()) >= 8 or  # Reasonably long request
            " and " in request_lower or  # Multiple actions connected by "and"
            request_lower.count(",") >= 1  # Multiple items separated by commas
        )
        
        if not should_plan:
            # Simple single-action request - no planning needed
            return ""
        
        # Generate planning prompt for multi-step requests using centralized template
        from ..prompts import get_planning_prompt_template
        plan_prompt_template = get_planning_prompt_template()
        plan_prompt = plan_prompt_template.format(user_request=user_request)
        return plan_prompt
    
    async def parse_plan_from_response(self, llm_response: str) -> Optional[AgentPlan]:
        """Parse an execution plan from LLM response."""
        try:
            # Extract JSON from response
            response_clean = llm_response.strip()
            
            # Remove any markdown code blocks
            if response_clean.startswith("```"):
                lines = response_clean.split("\n")
                response_clean = "\n".join(lines[1:-1])
            
            # Parse JSON
            plan_data = json.loads(response_clean)
            
            # Validate required fields
            if not all(key in plan_data for key in ["goal", "steps"]):
                return None
            
            # Create plan
            plan = AgentPlan(
                goal=plan_data["goal"],
                created_at=datetime.now().isoformat(),
                metadata={
                    "complexity": plan_data.get("complexity", "moderate"),
                    "requires_planning": plan_data.get("requires_planning", True)
                }
            )
            
            # Add steps
            for step_data in plan_data["steps"]:
                step = PlanStep(
                    action=step_data["action"],
                    args=step_data["args"],
                    description=step_data["description"],
                    step_id=step_data.get("step_id", f"step_{len(plan.steps)}"),
                    dependencies=step_data.get("dependencies", [])
                )
                plan.add_step(step)
            
            return plan
            
        except (json.JSONDecodeError, KeyError, TypeError):
            # Plan parsing failed - return None to fall back to direct execution
            return None
    
    def set_current_plan(self, plan: AgentPlan) -> None:
        """Set the current active plan."""
        if self.current_plan:
            self.plan_history.append(self.current_plan)
        self.current_plan = plan
        plan.status = PlanStatus.IN_PROGRESS
    
    def get_next_step(self) -> Optional[PlanStep]:
        """Get the next step to execute from the current plan."""
        if not self.current_plan:
            return None
        return self.current_plan.get_next_step()
    
    def mark_step_completed(self, step_id: str, result: Dict[str, Any]) -> None:
        """Mark a step as completed with its result."""
        if not self.current_plan:
            return
            
        for step in self.current_plan.steps:
            if step.step_id == step_id:
                step.mark_completed(result)
                break
        
        # Update plan timestamp
        self.current_plan.updated_at = datetime.now().isoformat()
        
        # Check if plan is complete
        if self.current_plan.is_complete():
            self.current_plan.status = PlanStatus.COMPLETED
    
    def mark_step_failed(self, step_id: str, error: str) -> None:
        """Mark a step as failed with error details."""
        if not self.current_plan:
            return
            
        for step in self.current_plan.steps:
            if step.step_id == step_id:
                step.mark_failed(error)
                break
        
        # Update plan timestamp
        self.current_plan.updated_at = datetime.now().isoformat()
    
    def update_plan(self, updates: Dict[str, Any]) -> None:
        """Update the current plan with new information."""
        if not self.current_plan:
            return
        
        # Update goal if provided
        if "goal" in updates:
            self.current_plan.goal = updates["goal"]
        
        # Add new steps if provided
        if "new_steps" in updates:
            for step_data in updates["new_steps"]:
                step = PlanStep(
                    action=step_data["action"],
                    args=step_data["args"],
                    description=step_data["description"],
                    step_id=step_data.get("step_id", f"step_{len(self.current_plan.steps)}"),
                    dependencies=step_data.get("dependencies", [])
                )
                self.current_plan.add_step(step)
        
        # Update metadata if provided
        if "metadata" in updates:
            self.current_plan.metadata.update(updates["metadata"])
        
        self.current_plan.updated_at = datetime.now().isoformat()
    
    def get_plan_progress(self) -> Optional[Dict[str, Any]]:
        """Get progress information for the current plan."""
        if not self.current_plan:
            return None
        return self.current_plan.get_progress()
    
    def is_plan_complete(self) -> bool:
        """Check if the current plan is complete."""
        if not self.current_plan:
            return True  # No plan means no work to do
        return self.current_plan.is_complete()
    
    def has_plan_failed(self) -> bool:
        """Check if the current plan has failed."""
        if not self.current_plan:
            return False
        return self.current_plan.has_failed()
    
    def clear_current_plan(self) -> None:
        """Clear the current plan."""
        if self.current_plan:
            self.plan_history.append(self.current_plan)
        self.current_plan = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert plan manager state to dictionary."""
        return {
            "current_plan": self.current_plan.to_dict() if self.current_plan else None,
            "plan_history": [plan.to_dict() for plan in self.plan_history]
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """Restore plan manager state from dictionary."""
        if data.get("current_plan"):
            self.current_plan = AgentPlan.from_dict(data["current_plan"])
        
        self.plan_history = [
            AgentPlan.from_dict(plan_data) 
            for plan_data in data.get("plan_history", [])
        ]