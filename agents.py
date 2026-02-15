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
    """Developer Agent - Generates real, structured, functional code.

    Uses context-aware code generation with proper patterns,
    error handling, type hints, and documentation.
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
        """Complete task and generate real structured code"""
        super().complete_task(task)

        code_file = {
            'filename': f"{task['type']}_{int(time.time())}.py",
            'content': self.generate_code(task),
            'description': task['description']
        }
        self.code_files.append(code_file)
        self.log_activity(f"Generated code file: {code_file['filename']}")

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
        """Generate frontend module code"""
        security_section = ""
        if "security" in focus or "auth" in focus:
            security_section = '''
    def sanitize_input(self, user_input: str) -> str:
        """Sanitize user input to prevent XSS and injection attacks"""
        import html
        return html.escape(user_input.strip())

    def validate_session(self, token: str) -> bool:
        """Validate user session token"""
        return bool(token and len(token) >= 32)
'''

        return f'''"""
{description}
Generated by {self.name}
Module: Frontend Interface
"""
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FrontendController:
    """Handles frontend rendering, user input, and state management"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {{}}
        self.state: Dict[str, Any] = {{}}
        self.components: List[str] = []
        self._initialized = False
        logger.info("FrontendController initialized")

    def initialize(self) -> bool:
        """Initialize frontend components and state"""
        try:
            self.state = {{"loaded": True, "timestamp": datetime.now().isoformat()}}
            self.components = ["header", "navigation", "main_content", "footer"]
            self._initialized = True
            logger.info("Frontend initialized with %d components", len(self.components))
            return True
        except Exception as e:
            logger.error("Frontend initialization failed: %s", e)
            return False

    def render_view(self, view_name: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Render a view with the given data context"""
        if not self._initialized:
            raise RuntimeError("Frontend not initialized - call initialize() first")
        context = {{
            "view": view_name,
            "data": data or {{}},
            "components": self.components,
            "rendered_at": datetime.now().isoformat()
        }}
        logger.info("Rendered view: %s", view_name)
        return context

    def handle_user_action(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a user action and return the result"""
        logger.info("User action: %s", action)
        result = {{"action": action, "status": "processed", "payload": payload or {{}}}}
        self.state["last_action"] = action
        return result

    def get_state(self) -> Dict[str, Any]:
        """Return the current frontend state"""
        return dict(self.state)
{security_section}

def main():
    """Frontend entry point"""
    controller = FrontendController()
    controller.initialize()
    result = controller.render_view("home", {{"title": "Welcome"}})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''

    def _generate_backend(self, description: str, focus: List[str]) -> str:
        """Generate backend service code"""
        analytics_section = ""
        if "analytics" in focus:
            analytics_section = '''
    def record_metric(self, metric_name: str, value: float):
        """Record a metric data point for analytics"""
        entry = {{"metric": metric_name, "value": value,
                 "timestamp": datetime.now().isoformat()}}
        self._metrics.append(entry)
        logger.info("Metric recorded: %s = %s", metric_name, value)
'''

        return f'''"""
{description}
Generated by {self.name}
Module: Backend Service
"""
import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BackendService:
    """Core backend service with data processing and business logic"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {{}}
        self._data_store: Dict[str, Any] = {{}}
        self._metrics: List[Dict[str, Any]] = []
        self._started = False
        logger.info("BackendService created")

    def start(self) -> bool:
        """Start the backend service"""
        try:
            self._started = True
            logger.info("BackendService started at %s", datetime.now().isoformat())
            return True
        except Exception as e:
            logger.error("Failed to start BackendService: %s", e)
            return False

    def process_request(self, method: str, path: str,
                        data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process an incoming request"""
        if not self._started:
            return {{"error": "Service not started", "status": 503}}

        logger.info("Processing %s %s", method, path)

        if method.upper() == "GET":
            return self._handle_get(path)
        elif method.upper() == "POST":
            return self._handle_post(path, data or {{}})
        elif method.upper() == "PUT":
            return self._handle_put(path, data or {{}})
        elif method.upper() == "DELETE":
            return self._handle_delete(path)
        else:
            return {{"error": f"Unsupported method: {{method}}", "status": 405}}

    def _handle_get(self, path: str) -> Dict[str, Any]:
        """Handle GET requests"""
        key = path.strip("/")
        if key in self._data_store:
            return {{"data": self._data_store[key], "status": 200}}
        return {{"error": "Not found", "status": 404}}

    def _handle_post(self, path: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle POST requests"""
        key = path.strip("/")
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
        """Return service health status"""
        return {{
            "status": "healthy" if self._started else "stopped",
            "uptime": datetime.now().isoformat(),
            "data_count": len(self._data_store)
        }}
{analytics_section}

def main():
    """Backend service entry point"""
    service = BackendService()
    service.start()
    result = service.process_request("POST", "/users", {{"name": "test"}})
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


class ResearcherAgent(Agent):
    """Researcher Agent - Conducts technology research"""
    
    def __init__(self, name: str = "Researcher"):
        super().__init__(name, "Researcher", ["Research", "Analysis", "Technology Evaluation"])
        
    def complete_task(self, task: Dict[str, Any]):
        """Complete research task"""
        super().complete_task(task)
        self.log_activity(f"Research findings documented for: {task['description']}")


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
