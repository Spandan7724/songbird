"""Session memory manager for Songbird."""
import json
import os
import subprocess
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .models import Session, Message


class SessionManager:
    """Manages chat sessions for Songbird."""
    
    def __init__(self, working_directory: str = "."):
        self.working_directory = Path(working_directory).resolve()
        self.project_root = self._find_project_root()
        self.storage_dir = self._get_storage_dir()
        
    def _find_project_root(self) -> Path:
        """Find the VCS root (git) or use current directory."""
        try:
            # Try to find git root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )
            return Path(result.stdout.strip()).resolve()
        except Exception:
            # Not a git repo or git not available, use current directory
            return self.working_directory
    
    def _get_storage_dir(self) -> Path:
        """Get the storage directory for this project."""
        # Create a safe directory name from the project path
        # Replace path separators with hyphens
        project_path_str = str(self.project_root)
        safe_name = project_path_str.replace(os.sep, "-").replace(":", "")
        
        # Get user's home directory
        home = Path.home()
        base_dir = home / ".songbird" / "projects" / safe_name
        base_dir.mkdir(parents=True, exist_ok=True)
        
        return base_dir
    
    def create_session(self) -> Session:
        """Create a new session."""
        session = Session(project_path=str(self.project_root))
        self.save_session(session)
        return session
    

    def save_session(self, session: Session):
        """Save a session to disk."""
        session_file = self.storage_dir / f"{session.id}.jsonl"

        # Write each message as a separate JSON line
        with open(session_file, "w", encoding="utf-8") as f:
            # First line is session metadata
            metadata = {
                "type": "metadata",
                "id": session.id,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "summary": session.summary,
                "project_path": session.project_path,
                "provider_config": session.provider_config  # ADD THIS LINE
            }
            f.write(json.dumps(metadata) + "\n")

            # Following lines are messages
            for msg in session.messages:
                msg_data = msg.to_dict()
                msg_data["type"] = "message"
                f.write(json.dumps(msg_data) + "\n")
    

    def load_session(self, session_id: str) -> Optional[Session]:
        """Load a session from disk."""
        session_file = self.storage_dir / f"{session_id}.jsonl"

        if not session_file.exists():
            return None

        session = None
        messages = []

        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)

                if data.get("type") == "metadata":
                    session = Session(
                        id=data["id"],
                        created_at=datetime.fromisoformat(data["created_at"]),
                        updated_at=datetime.fromisoformat(data["updated_at"]),
                        summary=data.get("summary", ""),
                        project_path=data.get("project_path", ""),
                        provider_config=data.get(
                            "provider_config", {})  # ADD THIS LINE
                    )
                elif data.get("type") == "message":
                    messages.append(Message.from_dict(data))

        if session:
            session.messages = messages
            return session

        return None
    
    def get_latest_session(self) -> Optional[Session]:
        """Get the most recently updated session."""
        sessions = self.list_sessions()
        if not sessions:
            return None
        
        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[0]
    

    def list_sessions(self) -> List[Session]:
        """List all sessions for the current project."""
        sessions = []

        if not self.storage_dir.exists():
            return sessions

        for session_file in self.storage_dir.glob("*.jsonl"):
            # Read just the metadata line
            with open(session_file, "r", encoding="utf-8") as f:
                first_line = f.readline()
                if not first_line:
                    continue

                data = json.loads(first_line)
                if data.get("type") == "metadata":
                    session = Session(
                        id=data["id"],
                        created_at=datetime.fromisoformat(data["created_at"]),
                        updated_at=datetime.fromisoformat(data["updated_at"]),
                        summary=data.get("summary", ""),
                        project_path=data.get("project_path", ""),
                        provider_config=data.get(
                            "provider_config", {})  # ADD THIS LINE
                    )

                    # Don't load messages for listing - keep empty for metadata only
                    # The message count is available but messages should be loaded separately
                    session.messages = []

                    sessions.append(session)

        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session_file = self.storage_dir / f"{session_id}.jsonl"
        
        if session_file.exists():
            session_file.unlink()
            return True
        
        return False
    
    def append_message(self, session_id: str, message: Message):
        """Append a message to an existing session file."""
        session_file = self.storage_dir / f"{session_id}.jsonl"
        
        if not session_file.exists():
            return
        
        # Update the metadata
        session = self.load_session(session_id)
        if session:
            session.add_message(message)
            # Regenerate summary if needed
            if not session.summary or len(session.messages) <= 5:
                session.summary = session.generate_summary()
            self.save_session(session)
