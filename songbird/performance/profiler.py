# songbird/performance/profiler.py
"""Performance profiling and optimization utilities for Songbird."""

import time
import asyncio
import functools
import statistics
from typing import Dict, List, Optional, Callable, Any
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from collections import defaultdict
import psutil
import sys
from pathlib import Path


@dataclass
class PerformanceMetric:
    """Single performance measurement."""
    operation: str
    duration: float
    memory_delta: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceReport:
    """Comprehensive performance analysis report."""
    metrics: List[PerformanceMetric]
    total_duration: float
    avg_duration: float
    memory_peak: float
    memory_avg: float
    operations_count: int
    
    def get_slowest_operations(self, count: int = 5) -> List[PerformanceMetric]:
        """Get the slowest operations."""
        return sorted(self.metrics, key=lambda m: m.duration, reverse=True)[:count]
    
    def get_memory_intensive_operations(self, count: int = 5) -> List[PerformanceMetric]:
        """Get the most memory-intensive operations."""
        return sorted(self.metrics, key=lambda m: m.memory_delta, reverse=True)[:count]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "total_duration": self.total_duration,
            "avg_duration": self.avg_duration,
            "memory_peak": self.memory_peak,
            "memory_avg": self.memory_avg,
            "operations_count": self.operations_count,
            "slowest_operations": [
                {
                    "operation": m.operation,
                    "duration": m.duration,
                    "memory_delta": m.memory_delta,
                    "metadata": m.metadata
                }
                for m in self.get_slowest_operations()
            ],
            "memory_intensive_operations": [
                {
                    "operation": m.operation,
                    "duration": m.duration,
                    "memory_delta": m.memory_delta,
                    "metadata": m.metadata
                }
                for m in self.get_memory_intensive_operations()
            ]
        }


class PerformanceProfiler:
    """Performance profiler for tracking system performance."""
    
    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.start_time: Optional[float] = None
        self.start_memory: Optional[float] = None
        self.enabled = False
        self.operation_counts = defaultdict(int)
        
        # Get current process for memory monitoring
        self.process = psutil.Process()
    
    def enable(self):
        """Enable performance profiling."""
        self.enabled = True
        self.start_time = time.time()
        self.start_memory = self._get_memory_usage()
    
    def disable(self):
        """Disable performance profiling."""
        self.enabled = False
    
    def clear(self):
        """Clear all collected metrics."""
        self.metrics.clear()
        self.operation_counts.clear()
        self.start_time = None
        self.start_memory = None
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            return self.process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    @contextmanager
    def profile_operation(self, operation_name: str, **metadata):
        """Context manager for profiling synchronous operations."""
        if not self.enabled:
            yield
            return
        
        start_time = time.time()
        start_memory = self._get_memory_usage()
        
        try:
            yield
        finally:
            end_time = time.time()
            end_memory = self._get_memory_usage()
            
            duration = end_time - start_time
            memory_delta = end_memory - start_memory
            
            metric = PerformanceMetric(
                operation=operation_name,
                duration=duration,
                memory_delta=memory_delta,
                timestamp=start_time,
                metadata=metadata
            )
            
            self.metrics.append(metric)
            self.operation_counts[operation_name] += 1
    
    @asynccontextmanager
    async def profile_async_operation(self, operation_name: str, **metadata):
        """Context manager for profiling asynchronous operations."""
        if not self.enabled:
            yield
            return
        
        start_time = time.time()
        start_memory = self._get_memory_usage()
        
        try:
            yield
        finally:
            end_time = time.time()
            end_memory = self._get_memory_usage()
            
            duration = end_time - start_time
            memory_delta = end_memory - start_memory
            
            metric = PerformanceMetric(
                operation=operation_name,
                duration=duration,
                memory_delta=memory_delta,
                timestamp=start_time,
                metadata=metadata
            )
            
            self.metrics.append(metric)
            self.operation_counts[operation_name] += 1
    
    def profile_function(self, operation_name: Optional[str] = None):
        """Decorator for profiling functions."""
        def decorator(func: Callable) -> Callable:
            name = operation_name or f"{func.__module__}.{func.__name__}"
            
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    async with self.profile_async_operation(name):
                        return await func(*args, **kwargs)
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.profile_operation(name):
                        return func(*args, **kwargs)
                return sync_wrapper
        
        return decorator
    
    def generate_report(self) -> PerformanceReport:
        """Generate comprehensive performance report."""
        if not self.metrics:
            return PerformanceReport(
                metrics=[],
                total_duration=0.0,
                avg_duration=0.0,
                memory_peak=0.0,
                memory_avg=0.0,
                operations_count=0
            )
        
        durations = [m.duration for m in self.metrics]
        memory_deltas = [m.memory_delta for m in self.metrics]
        
        return PerformanceReport(
            metrics=self.metrics.copy(),
            total_duration=sum(durations),
            avg_duration=statistics.mean(durations),
            memory_peak=max(memory_deltas) if memory_deltas else 0.0,
            memory_avg=statistics.mean(memory_deltas) if memory_deltas else 0.0,
            operations_count=len(self.metrics)
        )
    
    def get_operation_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics by operation type."""
        operation_metrics = defaultdict(list)
        
        for metric in self.metrics:
            operation_metrics[metric.operation].append(metric)
        
        stats = {}
        for operation, metrics in operation_metrics.items():
            durations = [m.duration for m in metrics]
            memory_deltas = [m.memory_delta for m in metrics]
            
            stats[operation] = {
                "count": len(metrics),
                "total_duration": sum(durations),
                "avg_duration": statistics.mean(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "avg_memory_delta": statistics.mean(memory_deltas) if memory_deltas else 0.0,
                "max_memory_delta": max(memory_deltas) if memory_deltas else 0.0
            }
        
        return stats


# Global profiler instance
_global_profiler = PerformanceProfiler()


def get_profiler() -> PerformanceProfiler:
    """Get the global profiler instance."""
    return _global_profiler


def enable_profiling():
    """Enable global performance profiling."""
    _global_profiler.enable()


def disable_profiling():
    """Disable global performance profiling."""
    _global_profiler.disable()


def clear_profiling():
    """Clear all profiling data."""
    _global_profiler.clear()


def profile_operation(operation_name: str, **metadata):
    """Context manager for profiling operations using global profiler."""
    return _global_profiler.profile_operation(operation_name, **metadata)


def profile_async_operation(operation_name: str, **metadata):
    """Async context manager for profiling operations using global profiler."""
    return _global_profiler.profile_async_operation(operation_name, **metadata)


def profile_function(operation_name: Optional[str] = None):
    """Function decorator for profiling using global profiler."""
    return _global_profiler.profile_function(operation_name)


class OptimizationSuggestions:
    """Analyze performance data and suggest optimizations."""
    
    @staticmethod
    def analyze_report(report: PerformanceReport) -> List[str]:
        """Analyze performance report and suggest optimizations."""
        suggestions = []
        
        # Check for slow operations
        slowest = report.get_slowest_operations(3)
        if slowest and slowest[0].duration > 1.0:  # Operations taking more than 1 second
            suggestions.append(
                f"Slow operation detected: '{slowest[0].operation}' took {slowest[0].duration:.2f}s. "
                "Consider optimization or caching."
            )
        
        # Check for memory intensive operations
        memory_intensive = report.get_memory_intensive_operations(3)
        if memory_intensive and memory_intensive[0].memory_delta > 50:  # More than 50MB
            suggestions.append(
                f"Memory-intensive operation: '{memory_intensive[0].operation}' used "
                f"{memory_intensive[0].memory_delta:.1f}MB. Consider memory optimization."
            )
        
        # Check average performance
        if report.avg_duration > 0.5:
            suggestions.append(
                f"Average operation time is {report.avg_duration:.2f}s. "
                "Consider overall system optimization."
            )
        
        # Check for high memory usage
        if report.memory_peak > 100:  # More than 100MB peak
            suggestions.append(
                f"Peak memory usage: {report.memory_peak:.1f}MB. "
                "Consider implementing memory management strategies."
            )
        
        # Check operation frequency
        if report.operations_count > 100:
            suggestions.append(
                f"High operation count ({report.operations_count}). "
                "Consider batching or reducing operation frequency."
            )
        
        if not suggestions:
            suggestions.append("Performance looks good! No immediate optimizations needed.")
        
        return suggestions
    
    @staticmethod
    def suggest_tool_optimizations(profiler: PerformanceProfiler) -> List[str]:
        """Suggest tool-specific optimizations based on profiling data."""
        suggestions = []
        operation_stats = profiler.get_operation_stats()
        
        # File operation optimizations
        file_ops = [op for op in operation_stats.keys() if 'file_' in op.lower()]
        if file_ops:
            total_file_time = sum(operation_stats[op]["total_duration"] for op in file_ops)
            if total_file_time > 2.0:
                suggestions.append(
                    f"File operations take {total_file_time:.2f}s total. "
                    "Consider file caching or batch operations."
                )
        
        # Search operation optimizations
        search_ops = [op for op in operation_stats.keys() if 'search' in op.lower()]
        if search_ops:
            search_count = sum(operation_stats[op]["count"] for op in search_ops)
            if search_count > 10:
                suggestions.append(
                    f"Many search operations ({search_count}). "
                    "Consider indexing or search result caching."
                )
        
        # LLM call optimizations
        llm_ops = [op for op in operation_stats.keys() if any(
            keyword in op.lower() for keyword in ['chat', 'llm', 'provider', 'model']
        )]
        if llm_ops:
            llm_time = sum(operation_stats[op]["total_duration"] for op in llm_ops)
            llm_count = sum(operation_stats[op]["count"] for op in llm_ops)
            if llm_time > 5.0:
                suggestions.append(
                    f"LLM operations take {llm_time:.2f}s total across {llm_count} calls. "
                    "Consider response caching or batch processing."
                )
        
        return suggestions


def save_performance_report(report: PerformanceReport, filepath: str):
    """Save performance report to file."""
    import json
    
    with open(filepath, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)


def load_performance_report(filepath: str) -> Dict[str, Any]:
    """Load performance report from file."""
    import json
    
    with open(filepath, 'r') as f:
        return json.load(f)