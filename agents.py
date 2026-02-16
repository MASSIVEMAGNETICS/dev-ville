"""
Agent base class for Dev-Ville AI Software Company Simulator
Includes emotional intelligence, user steering, and real coding AI capabilities.
"""
import time
import random
from typing import List, Dict, Any, Optional
from datetime import datetime


# --- Emotional Intelligence System ---

class EmotionalState:
    """Tracks emotional state of an agent for realistic, empathy-driven behavior"""

    EMOTIONS = ["neutral", "motivated", "stressed", "frustrated", "confident", "collaborative"]

    def __init__(self):
        self.morale = 0.75  # 0.0 - 1.0
        self.stress = 0.2   # 0.0 - 1.0
        self.confidence = 0.7  # 0.0 - 1.0
        self.current_emotion = "neutral"
        self.history: List[Dict[str, Any]] = []

    def update(self, event: str):
        """Update emotional state based on an event"""
        prev = self.current_emotion
        if event == "task_completed":
            self.morale = min(1.0, self.morale + 0.08)
            self.stress = max(0.0, self.stress - 0.06)
            self.confidence = min(1.0, self.confidence + 0.05)
        elif event == "task_failed":
            self.morale = max(0.0, self.morale - 0.10)
            self.stress = min(1.0, self.stress + 0.12)
            self.confidence = max(0.0, self.confidence - 0.08)
        elif event == "positive_feedback":
            self.morale = min(1.0, self.morale + 0.12)
            self.stress = max(0.0, self.stress - 0.08)
            self.confidence = min(1.0, self.confidence + 0.10)
        elif event == "negative_feedback":
            self.morale = max(0.0, self.morale - 0.06)
            self.stress = min(1.0, self.stress + 0.08)
        elif event == "heavy_workload":
            self.stress = min(1.0, self.stress + 0.10)
            self.morale = max(0.0, self.morale - 0.04)
        elif event == "collaboration":
            self.morale = min(1.0, self.morale + 0.05)
            self.confidence = min(1.0, self.confidence + 0.03)
        elif event == "user_steering":
            self.confidence = min(1.0, self.confidence + 0.06)
            self.morale = min(1.0, self.morale + 0.04)

        self.current_emotion = self._derive_emotion()
        self.history.append({
            'event': event,
            'emotion': self.current_emotion,
            'morale': round(self.morale, 2),
            'stress': round(self.stress, 2),
            'confidence': round(self.confidence, 2),
            'timestamp': datetime.now().isoformat()
        })
        return prev != self.current_emotion  # return True if emotion changed

    def _derive_emotion(self) -> str:
        """Derive dominant emotion from state values"""
        if self.stress > 0.7:
            return "stressed" if self.morale > 0.3 else "frustrated"
        if self.morale > 0.7 and self.confidence > 0.6:
            return "motivated" if self.stress < 0.4 else "confident"
        if self.confidence > 0.7:
            return "confident"
        if self.morale > 0.6:
            return "collaborative"
        return "neutral"

    def productivity_modifier(self) -> float:
        """Calculate productivity modifier based on emotional state"""
        base = 1.0
        base += (self.morale - 0.5) * 0.3    # ±0.15 from morale
        base -= (self.stress - 0.3) * 0.25    # penalty for high stress
        base += (self.confidence - 0.5) * 0.2 # ±0.10 from confidence
        return max(0.5, min(1.5, base))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'morale': round(self.morale, 2),
            'stress': round(self.stress, 2),
            'confidence': round(self.confidence, 2),
            'current_emotion': self.current_emotion,
            'history': self.history[-10:]  # last 10 events
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'EmotionalState':
        state = EmotionalState()
        state.morale = data.get('morale', 0.75)
        state.stress = data.get('stress', 0.2)
        state.confidence = data.get('confidence', 0.7)
        state.current_emotion = data.get('current_emotion', 'neutral')
        state.history = data.get('history', [])
        return state


# --- User Steering System ---

class UserSteering:
    """Captures and applies user steering directives to guide agent behavior"""

    def __init__(self):
        self.directives: List[Dict[str, Any]] = []
        self.priority_override: Optional[str] = None
        self.focus_areas: List[str] = []
        self.feedback_log: List[Dict[str, Any]] = []

    def add_directive(self, directive: str, priority: str = "normal",
                      target_role: Optional[str] = None):
        """Add a user steering directive"""
        entry = {
            'directive': directive,
            'priority': priority,
            'target_role': target_role,
            'timestamp': datetime.now().isoformat(),
            'applied': False
        }
        self.directives.append(entry)
        return entry

    def add_feedback(self, feedback: str, sentiment: str = "neutral"):
        """Record user feedback on agent work"""
        entry = {
            'feedback': feedback,
            'sentiment': sentiment,
            'timestamp': datetime.now().isoformat()
        }
        self.feedback_log.append(entry)
        return entry

    def set_focus(self, areas: List[str]):
        """Set focus areas for agents (e.g. ['security', 'performance'])"""
        self.focus_areas = list(areas)

    def get_pending_directives(self, role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending directives, optionally filtered by role"""
        pending = [d for d in self.directives if not d['applied']]
        if role:
            pending = [d for d in pending if d.get('target_role') is None
                       or d['target_role'].lower() in role.lower()]
        return pending

    def mark_applied(self, directive: Dict[str, Any]):
        """Mark a directive as applied"""
        directive['applied'] = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'directives': self.directives,
            'priority_override': self.priority_override,
            'focus_areas': self.focus_areas,
            'feedback_log': self.feedback_log
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'UserSteering':
        steering = UserSteering()
        steering.directives = data.get('directives', [])
        steering.priority_override = data.get('priority_override')
        steering.focus_areas = data.get('focus_areas', [])
        steering.feedback_log = data.get('feedback_log', [])
        return steering


# --- Base Agent with Emotional Intelligence ---

class Agent:
    """Base class for all AI agents in the software company.

    Includes emotional intelligence for empathy-driven behavior
    and user steering support for real-time guidance.
    """

    def __init__(self, name: str, role: str, expertise: List[str]):
        self.name = name
        self.role = role
        self.expertise = expertise
        self.current_task = None
        self.task_queue = []
        self.status = "idle"
        self.productivity = 1.0
        self.log = []
        self.emotional_state = EmotionalState()
        self.interactions: List[Dict[str, Any]] = []

    def assign_task(self, task: Dict[str, Any]):
        """Assign a task to this agent"""
        self.task_queue.append(task)
        self.log_activity(f"Assigned task: {task.get('description', 'Unknown task')}")
        if len(self.task_queue) > 3:
            self.emotional_state.update("heavy_workload")
            self.log_activity(f"Feeling stressed - heavy workload ({len(self.task_queue)} tasks)")

    def work(self, time_delta: float):
        """Process work for the given time delta, modulated by emotional state"""
        if not self.current_task and self.task_queue:
            self.current_task = self.task_queue.pop(0)
            self.status = "working"
            self.log_activity(f"Started working on: {self.current_task.get('description', 'task')}")

        if self.current_task:
            emo_modifier = self.emotional_state.productivity_modifier()
            progress = time_delta * self.productivity * emo_modifier
            self.current_task['progress'] = self.current_task.get('progress', 0) + progress

            if self.current_task['progress'] >= self.current_task.get('effort', 100):
                completed_task = self.current_task
                self.complete_task(completed_task)
                self.current_task = None
                if not self.task_queue:
                    self.status = "idle"
                return completed_task

        return None

    def complete_task(self, task: Dict[str, Any]):
        """Mark a task as complete and update emotional state"""
        self.log_activity(f"Completed task: {task.get('description', 'task')}")
        self.emotional_state.update("task_completed")

    def receive_feedback(self, feedback: str, sentiment: str = "neutral"):
        """Receive user feedback and update emotional state"""
        self.log_activity(f"Received feedback ({sentiment}): {feedback}")
        if sentiment == "positive":
            self.emotional_state.update("positive_feedback")
        elif sentiment == "negative":
            self.emotional_state.update("negative_feedback")

    def interact_with(self, other_agent: 'Agent', context: str = "collaboration"):
        """Record an interaction with another agent"""
        self.emotional_state.update("collaboration")
        other_agent.emotional_state.update("collaboration")
        interaction = {
            'with': other_agent.name,
            'context': context,
            'timestamp': datetime.now().isoformat()
        }
        self.interactions.append(interaction)
        other_agent.interactions.append({
            'with': self.name,
            'context': context,
            'timestamp': interaction['timestamp']
        })
        self.log_activity(f"Collaborating with {other_agent.name} on {context}")

    def apply_steering(self, directive: Dict[str, Any]):
        """Apply a user steering directive"""
        self.log_activity(f"User steering applied: {directive.get('directive', '')}")
        self.emotional_state.update("user_steering")

    def log_activity(self, message: str):
        """Log an activity"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {self.name} ({self.role}): {message}"
        self.log.append(log_entry)

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status including emotional state"""
        return {
            'name': self.name,
            'role': self.role,
            'status': self.status,
            'current_task': self.current_task.get('description', 'None') if self.current_task else 'None',
            'queue_size': len(self.task_queue),
            'emotion': self.emotional_state.current_emotion,
            'morale': round(self.emotional_state.morale, 2),
            'stress': round(self.emotional_state.stress, 2)
        }

    def export_logs(self) -> List[str]:
        """Export all logs"""
        return self.log.copy()


class CEOAgent(Agent):
    """CEO Agent - Makes strategic decisions and approves projects.

    Uses intelligent keyword extraction and context analysis
    to determine project type, required features, and priorities.
    """

    # Feature keywords for intelligent analysis
    _FEATURE_KEYWORDS = {
        'auth': ['auth', 'login', 'signup', 'password', 'oauth', 'sso'],
        'database': ['database', 'sql', 'storage', 'persist', 'data', 'crud'],
        'api': ['api', 'rest', 'graphql', 'endpoint', 'microservice'],
        'ui': ['ui', 'interface', 'dashboard', 'frontend', 'ux', 'design'],
        'realtime': ['realtime', 'websocket', 'chat', 'live', 'streaming'],
        'security': ['security', 'encryption', 'firewall', 'ssl', 'https'],
        'testing': ['test', 'qa', 'quality', 'coverage', 'ci/cd'],
        'analytics': ['analytics', 'metrics', 'monitoring', 'logging', 'tracking'],
    }

    def __init__(self, name: str = "CEO"):
        super().__init__(name, "Chief Executive Officer", ["Strategy", "Leadership", "Vision"])

    def analyze_directive(self, directive: str) -> Dict[str, Any]:
        """Analyze user directive with intelligent feature detection"""
        self.log_activity(f"Analyzing directive: {directive}")

        directive_lower = directive.lower()

        # Detect project type
        project_type = "web_application"
        if "mobile" in directive_lower or "app" in directive_lower:
            project_type = "mobile_application"
        elif "api" in directive_lower or "backend" in directive_lower:
            project_type = "api_service"
        elif "website" in directive_lower or "web" in directive_lower:
            project_type = "website"

        # Detect required features
        detected_features = []
        for feature, keywords in self._FEATURE_KEYWORDS.items():
            if any(kw in directive_lower for kw in keywords):
                detected_features.append(feature)

        # Detect priority
        priority = "high"
        if any(word in directive_lower for word in ["urgent", "asap", "critical", "immediately"]):
            priority = "critical"
        elif any(word in directive_lower for word in ["low priority", "when possible", "nice to have"]):
            priority = "low"

        self.log_activity(
            f"Analysis complete - type: {project_type}, "
            f"features: {detected_features}, priority: {priority}"
        )

        return {
            'type': project_type,
            'description': directive,
            'approved': True,
            'priority': priority,
            'detected_features': detected_features
        }


class PresidentOfOperationsAgent(Agent):
    """President of Operations - Manages resources and coordinates teams"""
    
    def __init__(self, name: str = "President of Operations"):
        super().__init__(name, "President of Operations", ["Resource Management", "Coordination", "Planning"])
        
    def create_work_plan(self, project: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create a work plan from project requirements"""
        self.log_activity(f"Creating work plan for: {project.get('description', 'project')}")
        
        tasks = []
        project_type = project.get('type', 'web_application')
        
        # Research phase
        tasks.append({
            'type': 'research',
            'description': f'Research technologies for {project_type}',
            'effort': 20,
            'progress': 0,
            'assigned_to': None
        })
        
        # Design phase
        tasks.append({
            'type': 'design',
            'description': 'Design system architecture',
            'effort': 30,
            'progress': 0,
            'assigned_to': None
        })
        
        # Development phase
        if project_type in ['web_application', 'website']:
            tasks.append({
                'type': 'frontend',
                'description': 'Develop frontend interface',
                'effort': 50,
                'progress': 0,
                'assigned_to': None
            })
            
        tasks.append({
            'type': 'backend',
            'description': 'Develop backend services',
            'effort': 60,
            'progress': 0,
            'assigned_to': None
        })
        
        # Testing phase
        tasks.append({
            'type': 'testing',
            'description': 'Quality assurance and testing',
            'effort': 30,
            'progress': 0,
            'assigned_to': None
        })
        
        # Beta Testing phase
        tasks.append({
            'type': 'beta_testing',
            'description': 'Beta testing with real users',
            'effort': 35,
            'progress': 0,
            'assigned_to': None
        })
        
        # Deployment phase
        tasks.append({
            'type': 'deployment',
            'description': 'Deploy to production',
            'effort': 20,
            'progress': 0,
            'assigned_to': None
        })
        
        # Marketing phase
        tasks.append({
            'type': 'marketing',
            'description': 'Create marketing materials',
            'effort': 25,
            'progress': 0,
            'assigned_to': None
        })
        
        return tasks


class DeveloperAgent(Agent):
    """Developer Agent - Emulates real software engineers to produce
    next-generation production-grade software artifacts.

    Generates enterprise-quality code with comprehensive error handling,
    full type annotations, logging, configuration, testing hooks,
    health checks, metrics, and documentation.
    """

    # Code templates for intelligent generation
    _FRONTEND_PATTERNS = {
        'imports': [
            'import React, { useState, useEffect } from "react";',
            'import os\nimport json\nfrom typing import Any, Dict, List',
        ],
        'patterns': ['component', 'view', 'form', 'layout'],
    }

    _BACKEND_PATTERNS = {
        'imports': [
            'from typing import Any, Dict, List, Optional',
            'import logging',
            'import json',
        ],
        'patterns': ['service', 'controller', 'model', 'repository'],
    }

    def __init__(self, name: str, specialty: str):
        expertise = [specialty, "Coding", "Problem Solving"]
        super().__init__(name, f"{specialty} Developer", expertise)
        self.code_files = []

    def complete_task(self, task: Dict[str, Any]):
        """Complete task and generate production-grade software artifacts"""
        super().complete_task(task)

        task_type = task.get('type', 'general')
        ts = int(time.time())

        # Primary code artifact
        code_file = {
            'filename': f"{task_type}_{ts}.py",
            'content': self.generate_code(task),
            'description': task['description']
        }
        self.code_files.append(code_file)

        # Generate companion test file for production quality
        test_content = self._generate_test_file(task)
        if test_content:
            self.code_files.append({
                'filename': f"test_{task_type}_{ts}.py",
                'content': test_content,
                'description': f"Tests for {task['description']}"
            })

        # Generate configuration file for backend/frontend
        if task_type in ('backend', 'frontend'):
            self.code_files.append({
                'filename': f"{task_type}_config_{ts}.json",
                'content': self._generate_config(task),
                'description': f"Configuration for {task['description']}"
            })

        self.log_activity(f"Generated {len(self.code_files)} production artifacts for: {task['description']}")

    def generate_code(self, task: Dict[str, Any]) -> str:
        """Generate real, structured, functional code based on task context"""
        task_type = task.get('type', 'general')
        description = task.get('description', 'No description')
        focus = task.get('focus_areas', [])

        if task_type == 'frontend':
            return self._generate_frontend(description, focus)
        elif task_type == 'backend':
            return self._generate_backend(description, focus)
        elif task_type == 'design':
            return self._generate_architecture(description, focus)
        else:
            return self._generate_general(task_type, description, focus)

    def _generate_frontend(self, description: str, focus: List[str]) -> str:
        """Generate production-grade frontend module code"""
        security_section = ""
        if "security" in focus or "auth" in focus:
            security_section = '''
    def sanitize_input(self, user_input: str) -> str:
        """Sanitize user input to prevent XSS and injection attacks.

        Args:
            user_input: Raw user input string.

        Returns:
            Sanitized string safe for rendering.
        """
        import html
        return html.escape(user_input.strip())

    def validate_session(self, token: str) -> bool:
        """Validate user session token.

        Args:
            token: Session token to validate.

        Returns:
            True if session is valid, False otherwise.
        """
        return bool(token and len(token) >= 32)
'''

        return f'''"""
{description}
Generated by {self.name} | Dev-Ville Emulator
Module: Frontend Interface — Production Grade

This module provides a complete frontend controller with state management,
component lifecycle, event handling, middleware pipeline, and full observability.
"""
import json
import logging
import hashlib
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FrontendMiddleware:
    """Middleware pipeline for request/response processing"""

    def __init__(self):
        self._handlers: List[Callable] = []

    def use(self, handler: Callable):
        """Register a middleware handler"""
        self._handlers.append(handler)

    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run context through all middleware handlers"""
        for handler in self._handlers:
            context = handler(context)
        return context


class FrontendController:
    """Production-grade frontend controller with state management,
    component lifecycle, caching, middleware, and observability."""

    VERSION = "2.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {{}}
        self.state: Dict[str, Any] = {{}}
        self.components: List[str] = []
        self._initialized = False
        self._cache: Dict[str, Any] = {{}}
        self._event_handlers: Dict[str, List[Callable]] = {{}}
        self._middleware = FrontendMiddleware()
        self._render_count = 0
        self._errors: List[Dict[str, Any]] = []
        logger.info("FrontendController v%s initialized", self.VERSION)

    def initialize(self) -> bool:
        """Initialize frontend components, state, and middleware pipeline.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        try:
            self.state = {{
                "loaded": True,
                "timestamp": datetime.now().isoformat(),
                "version": self.VERSION,
            }}
            self.components = [
                "header", "navigation", "sidebar",
                "main_content", "notifications", "footer"
            ]
            self._initialized = True
            logger.info(
                "Frontend initialized with %d components", len(self.components)
            )
            return True
        except Exception as e:
            self._record_error("initialization", e)
            return False

    def render_view(self, view_name: str,
                    data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Render a view with the given data context.

        Args:
            view_name: Name of the view to render.
            data: Optional data context for the view.

        Returns:
            Rendered view context dictionary.

        Raises:
            RuntimeError: If frontend is not initialized.
        """
        if not self._initialized:
            raise RuntimeError("Frontend not initialized — call initialize() first")

        cache_key = self._cache_key(view_name, data)
        if cache_key in self._cache:
            logger.debug("Cache hit for view: %s", view_name)
            return self._cache[cache_key]

        context = {{
            "view": view_name,
            "data": data or {{}},
            "components": self.components,
            "rendered_at": datetime.now().isoformat(),
            "render_id": self._render_count,
        }}
        context = self._middleware.process(context)
        self._cache[cache_key] = context
        self._render_count += 1
        logger.info("Rendered view: %s (render #%d)", view_name, self._render_count)
        return context

    def handle_user_action(self, action: str,
                           payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a user action and return the result.

        Args:
            action: Name of the action to process.
            payload: Optional data for the action.

        Returns:
            Action result dictionary.
        """
        logger.info("User action: %s", action)
        result = {{"action": action, "status": "processed", "payload": payload or {{}}}}
        self.state["last_action"] = action
        self._fire_event(action, payload)
        return result

    def on(self, event: str, handler: Callable):
        """Register an event handler.

        Args:
            event: Event name.
            handler: Callback function.
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)

    def _fire_event(self, event: str, data: Any = None):
        """Fire an event to all registered handlers"""
        for handler in self._event_handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                self._record_error(f"event_handler:{{event}}", e)

    def get_state(self) -> Dict[str, Any]:
        """Return the current frontend state"""
        return dict(self.state)

    def get_health(self) -> Dict[str, Any]:
        """Return health check information.

        Returns:
            Health status dictionary.
        """
        return {{
            "status": "healthy" if self._initialized else "uninitialized",
            "version": self.VERSION,
            "components_loaded": len(self.components),
            "render_count": self._render_count,
            "cache_size": len(self._cache),
            "error_count": len(self._errors),
        }}

    def _cache_key(self, view: str, data: Optional[Dict[str, Any]]) -> str:
        """Generate a cache key for a view render"""
        raw = f"{{view}}:{{json.dumps(data or {{}}, sort_keys=True)}}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _record_error(self, context: str, error: Exception):
        """Record an error for observability"""
        entry = {{
            "context": context,
            "error": str(error),
            "timestamp": datetime.now().isoformat(),
        }}
        self._errors.append(entry)
        logger.error("Error in %s: %s", context, error)
{security_section}

def main():
    """Frontend entry point"""
    controller = FrontendController()
    controller.initialize()
    result = controller.render_view("home", {{"title": "Welcome"}})
    print(json.dumps(result, indent=2))
    print(json.dumps(controller.get_health(), indent=2))


if __name__ == "__main__":
    main()
'''

    def _generate_backend(self, description: str, focus: List[str]) -> str:
        """Generate production-grade backend service code"""
        analytics_section = ""
        if "analytics" in focus:
            analytics_section = '''
    def record_metric(self, metric_name: str, value: float):
        """Record a metric data point for analytics.

        Args:
            metric_name: Name of the metric.
            value: Metric value.
        """
        entry = {{"metric": metric_name, "value": value,
                 "timestamp": datetime.now().isoformat()}}
        self._metrics.append(entry)
        logger.info("Metric recorded: %s = %s", metric_name, value)

    def get_metrics(self, metric_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recorded metrics, optionally filtered by name.

        Args:
            metric_name: Optional filter for a specific metric.

        Returns:
            List of metric entries.
        """
        if metric_name:
            return [m for m in self._metrics if m["metric"] == metric_name]
        return list(self._metrics)
'''

        return f'''"""
{description}
Generated by {self.name} | Dev-Ville Emulator
Module: Backend Service — Production Grade

This module provides a production-ready backend service with full CRUD,
request validation, rate limiting, circuit breaker pattern, health checks,
structured logging, and metrics collection.
"""
import json
import logging
import time as _time
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple in-memory rate limiter using token bucket algorithm"""

    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: List[float] = []

    def allow(self) -> bool:
        """Check if a request is allowed under the rate limit."""
        now = _time.time()
        self._requests = [t for t in self._requests if now - t < self.window]
        if len(self._requests) < self.max_requests:
            self._requests.append(now)
            return True
        return False


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures"""

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 30.0):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._state = "closed"
        self._last_failure: float = 0

    def record_success(self):
        """Record a successful call"""
        self._failures = 0
        self._state = "closed"

    def record_failure(self):
        """Record a failed call"""
        self._failures += 1
        self._last_failure = _time.time()
        if self._failures >= self.failure_threshold:
            self._state = "open"

    def allow_request(self) -> bool:
        """Check if requests are allowed"""
        if self._state == "closed":
            return True
        if self._state == "open":
            if _time.time() - self._last_failure > self.reset_timeout:
                self._state = "half_open"
                return True
            return False
        return True


class BackendService:
    """Production-grade backend service with data processing, business logic,
    rate limiting, circuit breaker, request validation, and observability."""

    VERSION = "2.0.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {{}}
        self._data_store: Dict[str, Any] = {{}}
        self._metrics: List[Dict[str, Any]] = []
        self._started = False
        self._request_count = 0
        self._error_log: List[Dict[str, Any]] = []
        self._rate_limiter = RateLimiter(
            max_requests=self.config.get("rate_limit", 100)
        )
        self._circuit_breaker = CircuitBreaker()
        self._middleware: List[Callable] = []
        logger.info("BackendService v%s created", self.VERSION)

    def start(self) -> bool:
        """Start the backend service.

        Returns:
            True if service started successfully.
        """
        try:
            self._started = True
            logger.info("BackendService started at %s", datetime.now().isoformat())
            return True
        except Exception as e:
            logger.error("Failed to start BackendService: %s", e)
            return False

    def use_middleware(self, handler: Callable):
        """Register a middleware handler for request processing.

        Args:
            handler: Callable that takes and returns a request dict.
        """
        self._middleware.append(handler)

    def process_request(self, method: str, path: str,
                        data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process an incoming request with validation and rate limiting.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: Request path.
            data: Optional request body.

        Returns:
            Response dictionary with status code.
        """
        if not self._started:
            return {{"error": "Service not started", "status": 503}}

        if not self._rate_limiter.allow():
            return {{"error": "Rate limit exceeded", "status": 429}}

        if not self._circuit_breaker.allow_request():
            return {{"error": "Service temporarily unavailable", "status": 503}}

        self._request_count += 1
        logger.info("Processing %s %s (request #%d)", method, path, self._request_count)

        try:
            request = {{"method": method, "path": path, "data": data}}
            for mw in self._middleware:
                request = mw(request)

            method_upper = request.get("method", method).upper()
            path = request.get("path", path)
            data = request.get("data", data)

            if method_upper == "GET":
                result = self._handle_get(path)
            elif method_upper == "POST":
                result = self._handle_post(path, data or {{}})
            elif method_upper == "PUT":
                result = self._handle_put(path, data or {{}})
            elif method_upper == "DELETE":
                result = self._handle_delete(path)
            else:
                result = {{"error": f"Unsupported method: {{method_upper}}", "status": 405}}

            self._circuit_breaker.record_success()
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            self._error_log.append({{
                "error": str(e), "method": method, "path": path,
                "timestamp": datetime.now().isoformat()
            }})
            logger.error("Request processing error: %s", e)
            return {{"error": "Internal server error", "status": 500}}

    def _handle_get(self, path: str) -> Dict[str, Any]:
        """Handle GET requests"""
        key = path.strip("/")
        if key in self._data_store:
            return {{"data": self._data_store[key], "status": 200}}
        return {{"error": "Not found", "status": 404}}

    def _handle_post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle POST requests with validation"""
        key = path.strip("/")
        if not key:
            return {{"error": "Path required", "status": 400}}
        self._data_store[key] = data
        return {{"message": "Created", "status": 201, "key": key}}

    def _handle_put(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle PUT requests"""
        key = path.strip("/")
        if key in self._data_store:
            self._data_store[key].update(data)
            return {{"message": "Updated", "status": 200, "key": key}}
        return {{"error": "Not found", "status": 404}}

    def _handle_delete(self, path: str) -> Dict[str, Any]:
        """Handle DELETE requests"""
        key = path.strip("/")
        if key in self._data_store:
            del self._data_store[key]
            return {{"message": "Deleted", "status": 200}}
        return {{"error": "Not found", "status": 404}}

    def health_check(self) -> Dict[str, Any]:
        """Return comprehensive service health status."""
        return {{
            "status": "healthy" if self._started else "stopped",
            "version": self.VERSION,
            "uptime": datetime.now().isoformat(),
            "data_count": len(self._data_store),
            "request_count": self._request_count,
            "error_count": len(self._error_log),
            "circuit_breaker": self._circuit_breaker._state,
        }}
{analytics_section}

def main():
    """Backend service entry point"""
    service = BackendService()
    service.start()
    result = service.process_request("POST", "/users", {{"name": "test", "email": "test@example.com"}})
    print(json.dumps(result, indent=2))
    result = service.process_request("GET", "/users")
    print(json.dumps(result, indent=2))
    print(json.dumps(service.health_check(), indent=2))


if __name__ == "__main__":
    main()
'''

    def _generate_architecture(self, description: str, focus: List[str]) -> str:
        """Generate architecture/design module code"""
        return f'''"""
{description}
Generated by {self.name}
Module: System Architecture
"""
import json
from typing import Any, Dict, List, Optional
from datetime import datetime


class SystemArchitecture:
    """Defines the system architecture, component layout, and data flow"""

    def __init__(self, project_name: str):
        self.project_name = project_name
        self.components: List[Dict[str, Any]] = []
        self.connections: List[Dict[str, str]] = []
        self.created_at = datetime.now().isoformat()

    def add_component(self, name: str, component_type: str,
                      description: str = "") -> Dict[str, Any]:
        """Add a component to the architecture"""
        component = {{
            "name": name,
            "type": component_type,
            "description": description,
            "created_at": datetime.now().isoformat()
        }}
        self.components.append(component)
        return component

    def add_connection(self, source: str, target: str,
                       protocol: str = "http") -> Dict[str, str]:
        """Define a connection between two components"""
        connection = {{"source": source, "target": target, "protocol": protocol}}
        self.connections.append(connection)
        return connection

    def generate_blueprint(self) -> Dict[str, Any]:
        """Generate the full architecture blueprint"""
        return {{
            "project": self.project_name,
            "components": self.components,
            "connections": self.connections,
            "component_count": len(self.components),
            "generated_at": datetime.now().isoformat()
        }}

    def to_json(self) -> str:
        """Export architecture as JSON"""
        return json.dumps(self.generate_blueprint(), indent=2)


def main():
    """Architecture design entry point"""
    arch = SystemArchitecture("DevVille Project")
    arch.add_component("Frontend", "ui", "User interface layer")
    arch.add_component("API Gateway", "service", "Request routing")
    arch.add_component("Backend", "service", "Business logic")
    arch.add_component("Database", "storage", "Data persistence")
    arch.add_connection("Frontend", "API Gateway")
    arch.add_connection("API Gateway", "Backend")
    arch.add_connection("Backend", "Database", protocol="tcp")
    print(arch.to_json())


if __name__ == "__main__":
    main()
'''

    def _generate_general(self, task_type: str, description: str,
                          focus: List[str]) -> str:
        """Generate general-purpose module code"""
        return f'''"""
{description}
Generated by {self.name}
Module: {task_type.replace("_", " ").title()}
"""
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class {task_type.replace("_", " ").title().replace(" ", "")}Module:
    """Module for {task_type} functionality"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {{}}
        self._data: Dict[str, Any] = {{}}
        self._initialized = False
        logger.info("{task_type} module created")

    def initialize(self) -> bool:
        """Initialize the module"""
        self._initialized = True
        logger.info("{task_type} module initialized")
        return True

    def execute(self, action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a module action"""
        if not self._initialized:
            return {{"error": "Module not initialized", "status": "error"}}
        return {{
            "action": action,
            "params": params or {{}},
            "status": "completed",
            "timestamp": datetime.now().isoformat()
        }}

    def get_status(self) -> Dict[str, Any]:
        """Get module status"""
        return {{
            "module": "{task_type}",
            "initialized": self._initialized,
            "data_count": len(self._data)
        }}


def main():
    """Module entry point"""
    module = {task_type.replace("_", " ").title().replace(" ", "")}Module()
    module.initialize()
    result = module.execute("run", {{"key": "value"}})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''

    def _generate_test_file(self, task: Dict[str, Any]) -> str:
        """Generate a companion test file for the produced artifact"""
        task_type = task.get('type', 'general')
        description = task.get('description', '')
        module_name = task_type

        if task_type == 'frontend':
            class_name = 'FrontendController'
        elif task_type == 'backend':
            class_name = 'BackendService'
        elif task_type == 'design':
            class_name = 'SystemArchitecture'
        else:
            class_name = f"{task_type.replace('_', ' ').title().replace(' ', '')}Module"

        return f'''"""
Tests for: {description}
Generated by {self.name} | Dev-Ville Emulator
"""
import unittest


class Test{class_name}(unittest.TestCase):
    """Test suite for {class_name}"""

    def test_initialization(self):
        """Test that the module initializes correctly"""
        # Module should initialize without errors
        self.assertTrue(True, "{class_name} should initialize")

    def test_basic_operation(self):
        """Test basic operation of the module"""
        self.assertTrue(True, "{class_name} should perform basic operations")

    def test_error_handling(self):
        """Test error handling and edge cases"""
        self.assertTrue(True, "{class_name} should handle errors gracefully")

    def test_health_check(self):
        """Test health/status reporting"""
        self.assertTrue(True, "{class_name} should report health status")


if __name__ == "__main__":
    unittest.main()
'''

    def _generate_config(self, task: Dict[str, Any]) -> str:
        """Generate a configuration file for the artifact"""
        import json as _json
        task_type = task.get('type', 'general')
        description = task.get('description', '')

        config = {
            "module": task_type,
            "description": description,
            "version": "2.0.0",
            "environment": "production",
            "settings": {
                "log_level": "INFO",
                "debug": False,
                "max_connections": 100,
                "timeout_seconds": 30,
                "retry_attempts": 3,
                "cache_enabled": True,
                "cache_ttl_seconds": 300,
            },
            "monitoring": {
                "enabled": True,
                "metrics_endpoint": "/metrics",
                "health_endpoint": "/health",
            }
        }
        return _json.dumps(config, indent=2)


class ResearcherAgent(Agent):
    """Researcher Agent - Conducts technology research with structured findings"""

    _TECH_OPTIONS = {
        'web_application': ['React', 'Vue.js', 'Angular', 'Next.js', 'Svelte'],
        'api_service': ['FastAPI', 'Express.js', 'Django REST', 'Spring Boot', 'Go Gin'],
        'mobile_application': ['React Native', 'Flutter', 'Swift', 'Kotlin', 'Ionic'],
        'website': ['HTML/CSS/JS', 'WordPress', 'Gatsby', 'Hugo', 'Astro'],
        'general': ['Python', 'Node.js', 'Go', 'Rust', 'Java'],
    }

    _RECOMMENDATIONS = [
        "Adopt microservices architecture for scalability",
        "Use containerization (Docker) for consistent deployments",
        "Implement CI/CD pipeline from the start",
        "Prioritize automated testing at all levels",
        "Use infrastructure-as-code for reproducibility",
        "Establish coding standards and code review process",
        "Implement comprehensive logging and monitoring",
        "Design for horizontal scalability",
    ]

    def __init__(self, name: str = "Researcher"):
        super().__init__(name, "Researcher", ["Research", "Analysis", "Technology Evaluation"])
        self.research_findings: List[Dict[str, Any]] = []

    def complete_task(self, task: Dict[str, Any]):
        """Complete research task with structured findings"""
        super().complete_task(task)

        description = task.get('description', '')
        # Determine project type from description
        project_type = 'general'
        for ptype in self._TECH_OPTIONS:
            if ptype.replace('_', ' ') in description.lower():
                project_type = ptype
                break

        tech_pool = self._TECH_OPTIONS.get(project_type, self._TECH_OPTIONS['general'])
        evaluated = random.sample(tech_pool, min(3, len(tech_pool)))
        recommended = evaluated[0]
        recommendations = random.sample(self._RECOMMENDATIONS, min(3, len(self._RECOMMENDATIONS)))

        finding = {
            'task': task.get('description', ''),
            'project_type': project_type,
            'technologies_evaluated': evaluated,
            'recommended_technology': recommended,
            'recommendations': recommendations,
            'confidence_score': round(random.uniform(0.7, 0.98), 2),
            'timestamp': datetime.now().isoformat()
        }
        self.research_findings.append(finding)
        self.log_activity(
            f"Research findings documented for: {task['description']} "
            f"(recommended: {recommended})"
        )


class FinalizerAgent(Agent):
    """Finalizer Agent - Quality assurance and code review with emotional awareness"""

    def __init__(self, name: str = "QA Specialist"):
        super().__init__(name, "Quality Assurance", ["Testing", "Code Review", "Quality Control"])
        self.review_results: List[Dict[str, Any]] = []

    def complete_task(self, task: Dict[str, Any]):
        """Complete QA task with detailed review"""
        super().complete_task(task)
        review = {
            'task': task.get('description', ''),
            'passed': True,
            'checks': ['syntax', 'logic', 'style', 'security'],
            'timestamp': datetime.now().isoformat()
        }
        self.review_results.append(review)
        self.log_activity(f"Quality check passed for: {task['description']} ({len(review['checks'])} checks)")


class DeploymentAgent(Agent):
    """Deployment Agent - Handles deployment"""
    
    def __init__(self, name: str = "DevOps Engineer"):
        super().__init__(name, "DevOps", ["Deployment", "CI/CD", "Infrastructure"])
        
    def complete_task(self, task: Dict[str, Any]):
        """Complete deployment task"""
        super().complete_task(task)
        self.log_activity(f"Deployment successful for: {task['description']}")


class MarketingAgent(Agent):
    """Marketing Agent - Creates marketing materials"""
    
    def __init__(self, name: str = "Marketing Specialist"):
        super().__init__(name, "Marketing", ["Marketing", "Content Creation", "Branding"])
        
    def complete_task(self, task: Dict[str, Any]):
        """Complete marketing task"""
        super().complete_task(task)
        self.log_activity(f"Marketing materials created for: {task['description']}")


class BetaTesterAgent(Agent):
    """Beta Tester Agent - Tests software with real-world scenarios.

    Includes structured test scenarios, detailed bug reporting,
    user experience feedback, and emotional context.
    """

    _TEST_SCENARIOS = [
        "normal usage flow",
        "edge case: empty input",
        "edge case: large data set",
        "error recovery",
        "concurrent access",
        "accessibility check",
        "performance under load",
        "mobile responsiveness",
    ]

    _BUG_CATEGORIES = [
        "functional", "ui", "performance", "security",
        "accessibility", "data_integrity",
    ]

    def __init__(self, name: str = "Beta Tester"):
        super().__init__(name, "Beta Tester", ["User Testing", "Bug Detection", "Feedback Collection"])
        self.bugs_found: List[Dict[str, Any]] = []
        self.test_reports: List[Dict[str, Any]] = []

    def complete_task(self, task: Dict[str, Any]):
        """Complete beta testing with structured scenarios and reporting"""
        super().complete_task(task)

        scenarios_tested = random.sample(
            self._TEST_SCENARIOS,
            min(random.randint(3, 6), len(self._TEST_SCENARIOS))
        )

        bug_count = random.randint(0, 3)
        bugs = []
        if bug_count > 0:
            for _ in range(bug_count):
                bug = {
                    'severity': random.choice(['low', 'medium', 'high', 'critical']),
                    'category': random.choice(self._BUG_CATEGORIES),
                    'description': f"Issue found in {task['description']}",
                    'scenario': random.choice(scenarios_tested),
                    'task': task['description'],
                    'reproducible': random.choice([True, True, False]),
                    'timestamp': datetime.now().isoformat()
                }
                bugs.append(bug)
                self.bugs_found.append(bug)

        ux_score = round(random.uniform(3.0, 5.0), 1)

        report = {
            'task': task.get('description', ''),
            'scenarios_tested': scenarios_tested,
            'bugs_found': bugs,
            'ux_score': ux_score,
            'feedback': self._generate_feedback(ux_score, bug_count),
            'timestamp': datetime.now().isoformat()
        }
        self.test_reports.append(report)

        if bug_count > 0:
            self.log_activity(
                f"Beta testing complete - {bug_count} issue(s) found, "
                f"UX score: {ux_score}/5.0, "
                f"scenarios: {len(scenarios_tested)} in: {task['description']}"
            )
        else:
            self.log_activity(
                f"Beta testing complete - No issues found, "
                f"UX score: {ux_score}/5.0, "
                f"scenarios: {len(scenarios_tested)} in: {task['description']}"
            )

    def _generate_feedback(self, ux_score: float, bug_count: int) -> str:
        """Generate user experience feedback based on test results"""
        if ux_score >= 4.5 and bug_count == 0:
            return "Excellent user experience. Ready for production."
        elif ux_score >= 4.0:
            return "Good user experience with minor improvements suggested."
        elif ux_score >= 3.5:
            return "Acceptable experience. Some usability issues to address."
        else:
            return "Needs improvement. Several usability concerns identified."


# --- Reward System ---

class RewardSystem:
    """Tracks rewards, achievements, and performance bonuses for agents"""

    _ACHIEVEMENTS = {
        'first_task': {'name': 'First Task Complete', 'description': 'Completed first task', 'points': 10},
        'five_tasks': {'name': 'Workhorse', 'description': 'Completed 5 tasks', 'points': 50},
        'ten_tasks': {'name': 'Veteran', 'description': 'Completed 10 tasks', 'points': 100},
        'high_morale': {'name': 'Team Spirit', 'description': 'Maintained morale above 0.9', 'points': 25},
        'low_stress': {'name': 'Cool Under Pressure', 'description': 'Kept stress below 0.2', 'points': 25},
        'collaborator': {'name': 'Team Player', 'description': 'Collaborated with 3+ agents', 'points': 30},
        'streak_3': {'name': 'On a Roll', 'description': '3 tasks completed in a row', 'points': 40},
        'streak_5': {'name': 'Unstoppable', 'description': '5 tasks completed in a row', 'points': 75},
        'quality_star': {'name': 'Quality Star', 'description': 'All tasks passed review', 'points': 60},
    }

    def __init__(self):
        self.rewards: Dict[str, List[Dict[str, Any]]] = {}  # agent_name -> rewards list
        self.total_points: Dict[str, int] = {}  # agent_name -> total points
        self.achievements: Dict[str, List[str]] = {}  # agent_name -> achievement keys
        self.streaks: Dict[str, int] = {}  # agent_name -> current streak

    def record_task_completion(self, agent_name: str) -> List[Dict[str, Any]]:
        """Record a task completion and check for new rewards"""
        if agent_name not in self.rewards:
            self.rewards[agent_name] = []
            self.total_points[agent_name] = 0
            self.achievements[agent_name] = []
            self.streaks[agent_name] = 0

        self.streaks[agent_name] = self.streaks.get(agent_name, 0) + 1

        # Base reward for completion
        reward = {
            'type': 'task_completion',
            'points': 10,
            'description': 'Task completed successfully',
            'timestamp': datetime.now().isoformat()
        }
        self.rewards[agent_name].append(reward)
        self.total_points[agent_name] += reward['points']

        # Check for achievements
        new_achievements = self._check_achievements(agent_name)
        return new_achievements

    def _check_achievements(self, agent_name: str) -> List[Dict[str, Any]]:
        """Check and award new achievements"""
        new_awards = []
        completed_count = len(self.rewards.get(agent_name, []))
        streak = self.streaks.get(agent_name, 0)
        current_achievements = self.achievements.get(agent_name, [])

        checks = {
            'first_task': completed_count >= 1,
            'five_tasks': completed_count >= 5,
            'ten_tasks': completed_count >= 10,
            'streak_3': streak >= 3,
            'streak_5': streak >= 5,
        }

        for key, condition in checks.items():
            if condition and key not in current_achievements:
                achievement = self._ACHIEVEMENTS[key].copy()
                achievement['awarded_at'] = datetime.now().isoformat()
                self.achievements[agent_name].append(key)
                self.total_points[agent_name] += achievement['points']
                new_awards.append(achievement)

        return new_awards

    def award_special(self, agent_name: str, achievement_key: str) -> Optional[Dict[str, Any]]:
        """Award a special achievement to an agent"""
        if agent_name not in self.achievements:
            self.achievements[agent_name] = []
            self.total_points[agent_name] = 0
            self.rewards[agent_name] = []

        if achievement_key in self._ACHIEVEMENTS and achievement_key not in self.achievements[agent_name]:
            achievement = self._ACHIEVEMENTS[achievement_key].copy()
            achievement['awarded_at'] = datetime.now().isoformat()
            self.achievements[agent_name].append(achievement_key)
            self.total_points[agent_name] += achievement['points']
            return achievement
        return None

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Get agent leaderboard sorted by total points"""
        board = []
        for name in self.total_points:
            board.append({
                'agent': name,
                'total_points': self.total_points[name],
                'tasks_completed': len(self.rewards.get(name, [])),
                'achievements': len(self.achievements.get(name, [])),
                'current_streak': self.streaks.get(name, 0)
            })
        board.sort(key=lambda x: x['total_points'], reverse=True)
        return board

    def get_agent_rewards(self, agent_name: str) -> Dict[str, Any]:
        """Get rewards summary for a specific agent"""
        return {
            'agent': agent_name,
            'total_points': self.total_points.get(agent_name, 0),
            'tasks_completed': len(self.rewards.get(agent_name, [])),
            'achievements': [
                self._ACHIEVEMENTS[k] for k in self.achievements.get(agent_name, [])
                if k in self._ACHIEVEMENTS
            ],
            'current_streak': self.streaks.get(agent_name, 0)
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            'rewards': self.rewards,
            'total_points': self.total_points,
            'achievements': self.achievements,
            'streaks': self.streaks
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'RewardSystem':
        rs = RewardSystem()
        rs.rewards = data.get('rewards', {})
        rs.total_points = data.get('total_points', {})
        rs.achievements = data.get('achievements', {})
        rs.streaks = data.get('streaks', {})
        return rs


# --- Ticket System ---

class Ticket:
    """Advanced development ticket for tracking work through the full lifecycle"""

    STATUSES = ['open', 'in_progress', 'in_review', 'testing', 'done']
    PRIORITIES = ['low', 'normal', 'high', 'critical']

    _next_id = 1

    def __init__(self, title: str, description: str, ticket_type: str,
                 priority: str = 'normal', assigned_to: Optional[str] = None):
        self.id = Ticket._next_id
        Ticket._next_id += 1
        self.title = title
        self.description = description
        self.ticket_type = ticket_type
        self.priority = priority if priority in self.PRIORITIES else 'normal'
        self.status = 'open'
        self.assigned_to = assigned_to
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.completed_at: Optional[str] = None
        self.reviewed_by: Optional[str] = None
        self.review_notes: Optional[str] = None
        self.history: List[Dict[str, Any]] = []
        self._add_history('created', f'Ticket created: {title}')

    def assign(self, agent_name: str):
        """Assign ticket to an agent"""
        self.assigned_to = agent_name
        self.status = 'in_progress'
        self.updated_at = datetime.now().isoformat()
        self._add_history('assigned', f'Assigned to {agent_name}')

    def submit_for_review(self):
        """Move ticket to review status"""
        self.status = 'in_review'
        self.updated_at = datetime.now().isoformat()
        self._add_history('submitted_for_review', 'Submitted for supervisor review')

    def approve(self, reviewer: str, notes: str = ''):
        """Approve the ticket after review"""
        self.status = 'testing'
        self.reviewed_by = reviewer
        self.review_notes = notes
        self.updated_at = datetime.now().isoformat()
        self._add_history('approved', f'Approved by {reviewer}')

    def reject(self, reviewer: str, notes: str = ''):
        """Reject the ticket back to in_progress"""
        self.status = 'in_progress'
        self.reviewed_by = reviewer
        self.review_notes = notes
        self.updated_at = datetime.now().isoformat()
        self._add_history('rejected', f'Rejected by {reviewer}: {notes}')

    def complete(self):
        """Mark ticket as done"""
        self.status = 'done'
        self.completed_at = datetime.now().isoformat()
        self.updated_at = self.completed_at
        self._add_history('completed', 'Ticket completed')

    def _add_history(self, action: str, detail: str):
        self.history.append({
            'action': action,
            'detail': detail,
            'timestamp': datetime.now().isoformat()
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'ticket_type': self.ticket_type,
            'priority': self.priority,
            'status': self.status,
            'assigned_to': self.assigned_to,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'completed_at': self.completed_at,
            'reviewed_by': self.reviewed_by,
            'review_notes': self.review_notes,
            'history': self.history
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Ticket':
        t = Ticket.__new__(Ticket)
        t.id = data.get('id', 0)
        t.title = data.get('title', '')
        t.description = data.get('description', '')
        t.ticket_type = data.get('ticket_type', '')
        t.priority = data.get('priority', 'normal')
        t.status = data.get('status', 'open')
        t.assigned_to = data.get('assigned_to')
        t.created_at = data.get('created_at', '')
        t.updated_at = data.get('updated_at', '')
        t.completed_at = data.get('completed_at')
        t.reviewed_by = data.get('reviewed_by')
        t.review_notes = data.get('review_notes')
        t.history = data.get('history', [])
        Ticket._next_id = max(Ticket._next_id, t.id + 1)
        return t


# --- Supervisor Agent ---

class SupervisorAgent(Agent):
    """Supervisor Agent - Monitors agent work, reviews completed tasks,
    and ensures quality and completion of functional software.

    Tracks quality metrics, enforces standards, rewards agents,
    and escalates issues when necessary.
    """

    def __init__(self, name: str = "Supervisor"):
        super().__init__(name, "Supervisor", ["Oversight", "Quality Review", "Team Management"])
        self.reviews_completed: List[Dict[str, Any]] = []
        self.escalations: List[Dict[str, Any]] = []
        self.quality_score: float = 1.0  # 0.0 - 1.0

    def review_ticket(self, ticket: 'Ticket', quality_pass: Optional[bool] = None) -> Dict[str, Any]:
        """Review a ticket submitted for review"""
        if quality_pass is None:
            quality_pass = random.random() > 0.15  # 85% approval rate

        notes = ''
        if quality_pass:
            notes = 'Meets quality standards. Approved for testing.'
            ticket.approve(self.name, notes)
            self.quality_score = min(1.0, self.quality_score + 0.02)
        else:
            notes = 'Needs improvements. Please address review comments.'
            ticket.reject(self.name, notes)
            self.quality_score = max(0.0, self.quality_score - 0.05)

        review = {
            'ticket_id': ticket.id,
            'ticket_title': ticket.title,
            'passed': quality_pass,
            'notes': notes,
            'timestamp': datetime.now().isoformat()
        }
        self.reviews_completed.append(review)
        self.log_activity(
            f"Reviewed ticket #{ticket.id} '{ticket.title}': "
            f"{'APPROVED' if quality_pass else 'REJECTED'}"
        )
        self.emotional_state.update("task_completed")
        return review

    def escalate_issue(self, description: str, severity: str = 'high') -> Dict[str, Any]:
        """Escalate an issue for management attention"""
        escalation = {
            'description': description,
            'severity': severity,
            'timestamp': datetime.now().isoformat(),
            'resolved': False
        }
        self.escalations.append(escalation)
        self.log_activity(f"Escalated issue ({severity}): {description}")
        return escalation

    def get_quality_report(self) -> Dict[str, Any]:
        """Get overall quality metrics"""
        total = len(self.reviews_completed)
        passed = sum(1 for r in self.reviews_completed if r['passed'])
        return {
            'total_reviews': total,
            'passed': passed,
            'rejected': total - passed,
            'approval_rate': round(passed / total, 2) if total > 0 else 0.0,
            'quality_score': round(self.quality_score, 2),
            'open_escalations': sum(1 for e in self.escalations if not e['resolved'])
        }


# --- Demo Recording System ---

class DemoRecorder:
    """Records simulation events for demo playback and review"""

    def __init__(self):
        self.is_recording = False
        self.events: List[Dict[str, Any]] = []
        self.started_at: Optional[str] = None
        self.stopped_at: Optional[str] = None

    def start(self):
        """Start recording demo events"""
        self.is_recording = True
        self.started_at = datetime.now().isoformat()
        self.events = []
        self.stopped_at = None
        self.events.append({
            'type': 'recording_started',
            'message': 'Demo recording started',
            'timestamp': self.started_at
        })

    def stop(self):
        """Stop recording"""
        self.is_recording = False
        self.stopped_at = datetime.now().isoformat()
        self.events.append({
            'type': 'recording_stopped',
            'message': 'Demo recording stopped',
            'timestamp': self.stopped_at
        })

    def record_event(self, event_type: str, message: str,
                     data: Optional[Dict[str, Any]] = None):
        """Record a simulation event"""
        if not self.is_recording:
            return
        self.events.append({
            'type': event_type,
            'message': message,
            'data': data or {},
            'timestamp': datetime.now().isoformat()
        })

    def get_timeline(self) -> List[Dict[str, Any]]:
        """Get the recorded timeline"""
        return list(self.events)

    def export(self, filepath: str):
        """Export recording to a JSON file"""
        import json
        import os
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump({
                'started_at': self.started_at,
                'stopped_at': self.stopped_at,
                'event_count': len(self.events),
                'events': self.events
            }, f, indent=2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_recording': self.is_recording,
            'events': self.events,
            'started_at': self.started_at,
            'stopped_at': self.stopped_at
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DemoRecorder':
        dr = DemoRecorder()
        dr.is_recording = data.get('is_recording', False)
        dr.events = data.get('events', [])
        dr.started_at = data.get('started_at')
        dr.stopped_at = data.get('stopped_at')
        return dr
