"""
Performance monitoring utility for tracking endpoint performance and bottlenecks.
"""

import time
import threading
import logging
from contextlib import contextmanager
from functools import wraps
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Class for tracking performance metrics."""

    operation_name: str
    duration: float
    timestamp: float
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class PerformanceMonitor:
    """Thread-safe performance monitoring utility."""

    def __init__(self, max_metrics_per_operation: int = 1000):
        self.max_metrics_per_operation = max_metrics_per_operation
        self.metrics: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_metrics_per_operation)
        )
        self.lock = threading.RLock()

    def record_metric(self, metric: PerformanceMetric):
        """Record a performance metric."""
        with self.lock:
            self.metrics[metric.operation_name].append(metric)

    @contextmanager
    def measure(self, operation_name: str, metadata: Optional[Dict] = None):
        """Context manager for measuring operation duration."""
        start_time = time.time()
        success = True
        error_message = None

        try:
            yield
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time

            metric = PerformanceMetric(
                operation_name=operation_name,
                duration=duration,
                timestamp=start_time,
                success=success,
                error_message=error_message,
                metadata=metadata or {},
            )

            self.record_metric(metric)

    def get_stats(self, operation_name: str) -> Dict:
        """Get statistics for a specific operation."""
        with self.lock:
            metrics = list(self.metrics.get(operation_name, []))

        if not metrics:
            return {"error": "No metrics found for operation"}

        durations = [m.duration for m in metrics if m.success]
        success_count = sum(1 for m in metrics if m.success)
        error_count = len(metrics) - success_count

        if not durations:
            return {
                "operation": operation_name,
                "total_calls": len(metrics),
                "success_count": success_count,
                "error_count": error_count,
                "success_rate": 0.0,
                "error": "No successful operations",
            }

        return {
            "operation": operation_name,
            "total_calls": len(metrics),
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": success_count / len(metrics),
            "avg_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "p50_duration": self._percentile(durations, 0.5),
            "p95_duration": self._percentile(durations, 0.95),
            "p99_duration": self._percentile(durations, 0.99),
        }

    def get_all_stats(self) -> Dict:
        """Get statistics for all tracked operations."""
        with self.lock:
            operations = list(self.metrics.keys())

        return {op: self.get_stats(op) for op in operations}

    def get_recent_errors(self, operation_name: str, limit: int = 10) -> List[Dict]:
        """Get recent errors for an operation."""
        with self.lock:
            metrics = list(self.metrics.get(operation_name, []))

        errors = [
            {
                "timestamp": m.timestamp,
                "error_message": m.error_message,
                "metadata": m.metadata,
            }
            for m in metrics
            if not m.success
        ]

        return errors[-limit:]

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of a list of numbers."""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = int(percentile * (len(sorted_data) - 1))
        return sorted_data[index]

    def reset_metrics(self, operation_name: Optional[str] = None):
        """Reset metrics for a specific operation or all operations."""
        with self.lock:
            if operation_name:
                if operation_name in self.metrics:
                    self.metrics[operation_name].clear()
            else:
                self.metrics.clear()

    def export_metrics(self, operation_name: Optional[str] = None) -> str:
        """Export metrics to JSON format."""
        if operation_name:
            stats = self.get_stats(operation_name)
        else:
            stats = self.get_all_stats()

        return json.dumps(stats, indent=2, default=str)


# Global performance monitor instance
monitor = PerformanceMonitor()


def track_performance(operation_name: str, include_args: bool = False):
    """Decorator for tracking function performance."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            metadata = {}

            if include_args:
                # Be careful about sensitive data in args
                metadata["args_count"] = len(args)
                metadata["kwargs_keys"] = list(kwargs.keys())

            with monitor.measure(operation_name, metadata):
                return func(*args, **kwargs)

        return wrapper

    return decorator


@contextmanager
def measure_time(operation_name: str):
    """Simple context manager for measuring time."""
    with monitor.measure(operation_name):
        yield


# Convenience functions for common operations
def log_performance_summary():
    """Log a performance summary for all operations."""
    stats = monitor.get_all_stats()

    logger.info("=== Performance Summary ===")
    for operation, stat in stats.items():
        if "error" not in stat:
            logger.info(
                f"{operation}: "
                f"avg={stat['avg_duration']:.3f}s, "
                f"p95={stat['p95_duration']:.3f}s, "
                f"success_rate={stat['success_rate']:.2%}, "
                f"calls={stat['total_calls']}"
            )
        else:
            logger.info(f"{operation}: {stat['error']}")


def get_performance_report() -> Dict:
    """Get a comprehensive performance report."""
    return {
        "summary": monitor.get_all_stats(),
        "timestamp": time.time(),
        "total_operations": len(monitor.metrics),
    }
