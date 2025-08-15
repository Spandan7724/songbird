"""Optimized session manager with batch writes and idle timeout."""

import asyncio
import json
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

from .models import Session, Message


class OptimizedSessionManager:
    """Optimized session manager with batch writes and idle flush."""
    
    def __init__(self, working_directory: str = ".", flush_interval: int = 30, batch_size: int = 10):
        self.working_directory = Path(working_directory).resolve()
        self.project_root = self._find_project_root()
        self.storage_dir = self._get_storage_dir()
        
        # Optimization settings
        self.flush_interval = flush_interval  # Seconds before auto-flush
        self.batch_size = batch_size  # Messages to batch before flush
        
        # In-memory state
        self._sessions: Dict[str, Session] = {}
        self._dirty_sessions: Set[str] = set()
        self._last_activity: Dict[str, float] = {}
        self._message_count_since_flush: Dict[str, int] = {}
        
        # Background flush task
        self._flush_task: Optional[asyncio.Task] = None
        self._shutdown_requested = False
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Start background flush task
        self._start_background_flush()
    
    def _find_project_root(self) -> Path:
        """Find the VCS root (git) or use current directory."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self.working_directory,
                capture_output=True,
                text=True,
                check=True
            )
            return Path(result.stdout.strip()).resolve()
        except Exception:
            return self.working_directory
    
    def _get_storage_dir(self) -> Path:
        project_path_str = str(self.project_root)
        safe_name = project_path_str.replace(os.sep, "-").replace(":", "")
        
        home = Path.home()
        base_dir = home / ".songbird" / "projects" / safe_name
        base_dir.mkdir(parents=True, exist_ok=True)
        
        return base_dir
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            print(f"\nReceived signal {signum}, flushing sessions...")
            self._shutdown_requested = True
            # Synchronous flush for signal handling
            self._flush_all_sessions_sync()
            exit(0)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _start_background_flush(self):
        """Start the background flush task."""
        try:
            loop = asyncio.get_running_loop()
            self._flush_task = loop.create_task(self._background_flush_loop())
        except RuntimeError:
            # No event loop running, flush will be manual only
            pass
    
    async def _background_flush_loop(self):
        """Background task that flushes sessions periodically."""
        while not self._shutdown_requested:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_idle_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in background flush: {e}")
    
    async def _flush_idle_sessions(self):
        """Flush sessions that have been idle for the flush interval."""
        current_time = time.time()
        
        sessions_to_flush = []
        for session_id in self._dirty_sessions.copy():
            last_activity = self._last_activity.get(session_id, 0)
            if current_time - last_activity >= self.flush_interval:
                sessions_to_flush.append(session_id)
        
        for session_id in sessions_to_flush:
            if session_id in self._sessions:
                await self._flush_session(session_id)
    
    def create_session(self) -> Session:
        """Create a new session."""
        session = Session()
        session.project_path = str(self.project_root)
        
        # Add to in-memory cache
        self._sessions[session.id] = session
        self._mark_dirty(session.id)
        
        return session
    
    def _mark_dirty(self, session_id: str):
        """Mark a session as dirty (needs flushing)."""
        self._dirty_sessions.add(session_id)
        self._last_activity[session_id] = time.time()
        
        # Check if we should flush due to batch size
        message_count = self._message_count_since_flush.get(session_id, 0) + 1
        self._message_count_since_flush[session_id] = message_count
        
        if message_count >= self.batch_size:
            # Schedule immediate flush for this session
            try:
                # Try to get the current running loop
                loop = asyncio.get_running_loop()
                loop.create_task(self._flush_session(session_id))
            except RuntimeError:
                # No running event loop, flush synchronously
                self._flush_session_sync(session_id)
    
    async def _flush_session(self, session_id: str):
        """Flush a single session to disk asynchronously."""
        if session_id not in self._sessions:
            return
        
        session = self._sessions[session_id]
        await asyncio.get_event_loop().run_in_executor(
            None, self._write_session_to_disk, session
        )
        
        # Mark as clean
        self._dirty_sessions.discard(session_id)
        self._message_count_since_flush[session_id] = 0
    
    def _flush_session_sync(self, session_id: str):
        """Flush a single session to disk synchronously."""
        if session_id not in self._sessions:
            return
        
        session = self._sessions[session_id]
        self._write_session_to_disk(session)
        
        # Mark as clean
        self._dirty_sessions.discard(session_id)
        self._message_count_since_flush[session_id] = 0
    
    def _write_session_to_disk(self, session: Session):
        """Write session to disk (blocking operation)."""
        session_file = self.storage_dir / f"{session.id}.jsonl"
        
        # Write atomically using a temporary file
        temp_file = session_file.with_suffix('.tmp')
        
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                # Session metadata
                metadata = {
                    "type": "metadata",
                    "id": session.id,
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                    "summary": session.summary,
                    "project_path": session.project_path,
                    "provider_config": session.provider_config
                }
                f.write(json.dumps(metadata) + "\n")
                
                # Messages
                for msg in session.messages:
                    msg_data = {
                        "type": "message",
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "tool_calls": msg.tool_calls,
                        "tool_call_id": msg.tool_call_id,
                        "name": getattr(msg, 'name', None)  # Handle optional name attribute
                    }
                    f.write(json.dumps(msg_data) + "\n")
            
            # Atomic replacement
            temp_file.replace(session_file)
            
        except Exception as e:
            # Clean up temp file on error
            if temp_file.exists():
                temp_file.unlink()
            raise e
    
    def save_session(self, session: Session):
        self._sessions[session.id] = session
        self._mark_dirty(session.id)
    
    async def flush_session(self, session: Session):
        self._sessions[session.id] = session
        self._mark_dirty(session.id)
        
        # Force immediate flush
        await self._flush_session(session.id)
    
    def flush_session_sync(self, session: Session):
        self._sessions[session.id] = session
        self._mark_dirty(session.id)
        
        # Force immediate flush synchronously
        self._flush_session_sync(session.id)
    
    async def flush_all_sessions(self):
        for session_id in list(self._dirty_sessions):
            await self._flush_session(session_id)
    
    def _flush_all_sessions_sync(self):
        for session_id in list(self._dirty_sessions):
            self._flush_session_sync(session_id)
    
    def load_session(self, session_id: str) -> Optional[Session]:
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        # Load from disk
        session = self._load_session_from_disk(session_id)
        if session:
            # Add to cache
            self._sessions[session_id] = session
        
        return session
    
    def _load_session_from_disk(self, session_id: str) -> Optional[Session]:
        """Load session from disk."""
        session_file = self.storage_dir / f"{session_id}.jsonl"
        
        if not session_file.exists():
            return None
        
        session = None
        messages = []
        
        try:
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
                            provider_config=data.get("provider_config", {})
                        )
                    elif data.get("type") == "message":
                        message = Message(
                            role=data["role"],
                            content=data["content"],
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            tool_calls=data.get("tool_calls"),
                            tool_call_id=data.get("tool_call_id")
                        )
                        # Set name attribute if it exists in data (for compatibility)
                        if "name" in data and data["name"] is not None:
                            setattr(message, 'name', data["name"])
                        messages.append(message)
            
            if session:
                session.messages = messages
                return session
                
        except Exception as e:
            print(f"Error loading session {session_id}: {e}")
        
        return None
    
    def get_latest_session(self) -> Optional[Session]:
        """Get the most recent session."""
        sessions = self.list_sessions()
        if not sessions:
            return None
        
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[0]
    
    def list_sessions(self) -> List[Session]:
        """List all sessions for the current project."""
        sessions = []
        
        # Include in-memory sessions
        for session in self._sessions.values():
            sessions.append(session)
        
        # Include disk sessions not in memory
        if self.storage_dir.exists():
            for session_file in self.storage_dir.glob("*.jsonl"):
                session_id = session_file.stem
                if session_id not in self._sessions:
                    # Quick load metadata only
                    try:
                        with open(session_file, "r", encoding="utf-8") as f:
                            first_line = f.readline()
                            if first_line:
                                data = json.loads(first_line)
                                if data.get("type") == "metadata":
                                    session = Session(
                                        id=data["id"],
                                        created_at=datetime.fromisoformat(data["created_at"]),
                                        updated_at=datetime.fromisoformat(data["updated_at"]),
                                        summary=data.get("summary", ""),
                                        project_path=data.get("project_path", ""),
                                        provider_config=data.get("provider_config", {})
                                    )
                                    sessions.append(session)
                    except Exception:
                        continue
        
        # Remove duplicates and sort
        seen = set()
        unique_sessions = []
        for session in sessions:
            if session.id not in seen:
                seen.add(session.id)
                unique_sessions.append(session)
        
        unique_sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return unique_sessions
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        # Remove from memory
        if session_id in self._sessions:
            del self._sessions[session_id]
        self._dirty_sessions.discard(session_id)
        self._last_activity.pop(session_id, None)
        self._message_count_since_flush.pop(session_id, None)
        
        # Remove from disk
        session_file = self.storage_dir / f"{session_id}.jsonl"
        if session_file.exists():
            session_file.unlink()
            return True
        
        return False
    
    def append_message(self, session_id: str, message: Message):
        """Append a message to an existing session."""
        session = self.load_session(session_id)
        if session:
            session.add_message(message)
            # Regenerate summary if needed
            if not session.summary or len(session.messages) <= 5:
                session.summary = session.generate_summary()
            self.save_session(session)
    
    async def shutdown(self):
        """Graceful shutdown - flush all sessions and stop background tasks."""
        self._shutdown_requested = True
        
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Final flush
        await self.flush_all_sessions()
    
    def get_stats(self) -> Dict[str, any]:
        """Get manager statistics."""
        return {
            "cached_sessions": len(self._sessions),
            "dirty_sessions": len(self._dirty_sessions),
            "flush_interval": self.flush_interval,
            "batch_size": self.batch_size,
            "total_sessions_on_disk": len(list(self.storage_dir.glob("*.jsonl"))) if self.storage_dir.exists() else 0
        }