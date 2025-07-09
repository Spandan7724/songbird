"""Planning data structures for the agent core."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class PlanStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step in an agent plan."""
    action: str  # Tool name (e.g., "file_read", "shell_exec")
    args: Dict[str, Any]  # Tool arguments
    description: str  # Human-readable description
    step_id: Optional[str] = None
    status: PlanStatus = PlanStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list) 
    
    def mark_completed(self, result: Dict[str, Any]) -> None:
        self.status = PlanStatus.COMPLETED
        self.result = result
    
    def mark_failed(self, error: str) -> None:
        self.status = PlanStatus.FAILED
        self.error = error
    
    def can_execute(self, completed_steps: List[str]) -> bool:
        return all(dep_id in completed_steps for dep_id in self.dependencies)


@dataclass
class AgentPlan:
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    current_step_index: int = 0
    status: PlanStatus = PlanStatus.PENDING
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"  # Version for serialization compatibility
    
    def add_step(self, step: PlanStep) -> None:
        if not step.step_id:
            step.step_id = f"step_{len(self.steps)}"
        self.steps.append(step)
    
    def get_next_step(self) -> Optional[PlanStep]:
        completed_step_ids = [
            step.step_id for step in self.steps 
            if step.status == PlanStatus.COMPLETED and step.step_id
        ]
        
        for i, step in enumerate(self.steps):
            if step.status == PlanStatus.PENDING and step.can_execute(completed_step_ids):
                self.current_step_index = i
                return step
        
        return None
    
    def get_current_step(self) -> Optional[PlanStep]:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def is_complete(self) -> bool:
        return all(step.status in [PlanStatus.COMPLETED, PlanStatus.SKIPPED] for step in self.steps)
    
    def has_failed(self) -> bool:
        return any(step.status == PlanStatus.FAILED for step in self.steps)
    
    def get_progress(self) -> Dict[str, Any]:
        """Get plan progress information."""
        total_steps = len(self.steps)
        completed_steps = len([step for step in self.steps if step.status == PlanStatus.COMPLETED])
        failed_steps = len([step for step in self.steps if step.status == PlanStatus.FAILED])
        
        return {
            "total": total_steps,
            "completed": completed_steps,
            "failed": failed_steps,
            "remaining": total_steps - completed_steps - failed_steps,
            "progress_percentage": (completed_steps / total_steps * 100) if total_steps > 0 else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [
                {
                    "action": step.action,
                    "args": step.args,
                    "description": step.description,
                    "step_id": step.step_id,
                    "status": step.status.value,
                    "result": step.result,
                    "error": step.error,
                    "dependencies": step.dependencies
                }
                for step in self.steps
            ],
            "current_step_index": self.current_step_index,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "schema_version": self.schema_version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentPlan':
        """Create plan from dictionary."""
        plan = cls(
            goal=data["goal"],
            current_step_index=data.get("current_step_index", 0),
            status=PlanStatus(data.get("status", "pending")),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            metadata=data.get("metadata", {}),
            schema_version=data.get("schema_version", "1.0")  # Default to 1.0 for compatibility
        )
        
        for step_data in data.get("steps", []):
            step = PlanStep(
                action=step_data["action"],
                args=step_data["args"],
                description=step_data["description"],
                step_id=step_data.get("step_id"),
                status=PlanStatus(step_data.get("status", "pending")),
                result=step_data.get("result"),
                error=step_data.get("error"),
                dependencies=step_data.get("dependencies", [])
            )
            plan.add_step(step)
        
        return plan