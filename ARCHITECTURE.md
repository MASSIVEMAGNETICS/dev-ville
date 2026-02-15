# Dev-Ville Architecture

## System Overview

Dev-Ville is a multi-agent simulation system that models a complete software development company. The architecture follows a modular design with clear separation of concerns, featuring emotional intelligence, user steering, real code generation, and an interactive agentic runtime.

## Core Components

### 1. Agent System (`agents.py`)

#### Base Agent Class
The foundation for all company agents, providing:
- Task queue management
- Work processing with progress tracking (modulated by emotional state)
- Activity logging
- Emotional intelligence (morale, stress, confidence)
- User steering support
- Agent-to-agent collaboration

```python
class Agent:
    - name: str
    - role: str
    - expertise: List[str]
    - current_task: Dict
    - task_queue: List[Dict]
    - status: str (idle/working)
    - productivity: float
    - log: List[str]
    - emotional_state: EmotionalState
    - interactions: List[Dict]
```

#### Emotional Intelligence System

```python
class EmotionalState:
    - morale: float (0.0-1.0)
    - stress: float (0.0-1.0)
    - confidence: float (0.0-1.0)
    - current_emotion: str (neutral/motivated/stressed/frustrated/confident/collaborative)
    - history: List[Dict]
```

Events that affect emotional state:
- `task_completed`: ↑ morale, ↓ stress, ↑ confidence
- `task_failed`: ↓ morale, ↑ stress, ↓ confidence
- `positive_feedback`: ↑ morale, ↓ stress, ↑ confidence
- `negative_feedback`: ↓ morale, ↑ stress
- `heavy_workload`: ↑ stress, ↓ morale
- `collaboration`: ↑ morale, ↑ confidence
- `user_steering`: ↑ confidence, ↑ morale

The emotional state produces a `productivity_modifier()` (0.5x-1.5x) that modulates work output.

#### User Steering System

```python
class UserSteering:
    - directives: List[Dict]  # Real-time user guidance
    - focus_areas: List[str]  # e.g., ['security', 'performance']
    - feedback_log: List[Dict]  # User feedback with sentiment
```

#### Specialized Agent Classes

**Executive Agents**:
- `CEOAgent`: Intelligent directive analysis with feature detection and priority assessment
- `PresidentOfOperationsAgent`: Work planning and task creation

**Technical Agents**:
- `ResearcherAgent`: Technology evaluation
- `DeveloperAgent`: Real code generation with context-aware patterns (Frontend/Backend/Architecture)
- `FinalizerAgent`: QA with detailed review tracking
- `BetaTesterAgent`: Structured testing with scenarios, UX scoring, and detailed bug reports ⭐
- `DeploymentAgent`: CI/CD and deployment

**Business Agents**:
- `MarketingAgent`: Marketing material creation

### 2. Company System (`company.py`)

#### Project Class
Manages individual software projects:
- Project metadata (name, description, created_at)
- Task collection with progress tracking
- Generated file storage
- Status management (planning/in-progress/completed)
- Serialization (to/from JSON)

#### Company Class
The central orchestrator with interactive agentic runtime:
- Manages 18 agent instances
- Handles project lifecycle
- Coordinates task assignment
- Processes work cycles with emotional intelligence
- Manages time simulation
- Provides save/load functionality (including emotional states)
- Handles exports (files and logs)
- **User steering**: real-time directives that guide agent behavior
- **Event-driven runtime**: register listeners for task_completed, project_completed, user_steering, etc.
- **Agent collaboration**: automatic handoffs between developers, QA, and beta testers
- **Team morale tracking**: aggregate emotional state of all agents
- **Beta test summaries**: structured reporting with UX scores

**Key Methods**:
- `start_project(directive)`: Initiates new project with intelligent analysis
- `assign_tasks(tasks)`: Distributes work to agents
- `work_cycle(time_delta)`: Processes one simulation step with emotional modulation
- `steer(directive, priority, target_role)`: Add user steering directive
- `send_feedback(feedback, sentiment, target_agent)`: Send feedback to agents
- `set_focus(areas)`: Set focus areas (security, performance, etc.)
- `on(event, callback)` / `off(event, callback)`: Event listener management
- `get_team_morale()`: Aggregate emotional state
- `get_beta_test_summary()`: Structured beta test results
- `save_project(filepath)`: Persists project state with emotions
- `load_project(filepath)`: Restores project state with emotions
- `export_files(dir)`: Exports generated code
- `export_logs(dir)`: Exports activity logs

### 3. User Interfaces

#### GUI Application (`devville.py`)
Full-featured Tkinter interface with:

**Main Window Components**:
- Menu bar (File operations)
- Control panel (directive input, time controls)
- Progress section (visual feedback)
- Tabbed content area:
  - Agents tab: TreeView showing all 18 agents
  - Activity Log tab: Scrolled text with real-time updates
  - Tasks tab: TreeView with task progress
  - Generated Files tab: TreeView with file listings
- Status bar

**Threading**:
- Main UI thread for responsive interface
- Worker thread for simulation (prevents UI freezing)
- Thread-safe UI updates using `root.after()`

#### CLI Application (`devville_cli.py`)
Terminal-based interface for headless environments:
- Text-based menu system
- All core functionality available
- No external dependencies beyond Python stdlib

### 4. Testing (`test_devville.py`)

Comprehensive test suite covering:
1. Agent creation and initialization
2. Company setup with all agents
3. Project creation from directives
4. Work simulation and progress
5. Task assignment logic
6. File generation by developers
7. Save/load persistence
8. Log export functionality
9. Continue project functionality
10. Emotional intelligence (morale, stress, productivity modifier)
11. User steering (directives, feedback, focus areas)
12. Real code generation (frontend, backend, architecture modules)
13. Interactive agentic runtime (events, listeners)
14. Enhanced beta testing (scenarios, UX scores, reports)
15. Agent collaboration (bidirectional interaction tracking)
16. Save/load with emotional states and steering data

## Data Flow

### Project Creation Flow
```
User Directive
    ↓
CEO Agent (analyze_directive)
    ↓
Project Object Created
    ↓
President of Operations (create_work_plan)
    ↓
Tasks Generated
    ↓
Company (assign_tasks)
    ↓
Tasks Assigned to Agents
```

### Work Cycle Flow
```
work_cycle(time_delta) called
    ↓
Apply pending user steering directives
    ↓
For each agent:
    agent.work(time_delta * emotional_modifier)
    ↓
    Process current_task
    ↓
    Update progress (modulated by morale/stress/confidence)
    ↓
    Complete if progress >= effort
    ↓
    Generate artifacts (real code files, etc.)
    ↓
    Trigger collaboration (developer→QA→beta tester handoffs)
    ↓
Collect completed tasks
    ↓
Emit runtime events (task_completed, project_completed)
    ↓
Update project progress
    ↓
Reassign idle tasks
    ↓
Update project status
```

### Task Assignment Logic
```
For each unassigned task:
    Determine task type
    ↓
    Find appropriate agent by:
        - Agent type (isinstance check)
        - Role match
        - Status (prefer idle)
    ↓
    Assign task to agent
    ↓
    Update task.assigned_to
```

## Agent Specialization

### Task Type → Agent Type Mapping

| Task Type | Agent Type | Count |
|-----------|-----------|-------|
| research | ResearcherAgent | 2 |
| design | DeveloperAgent (any) | 5 |
| frontend | DeveloperAgent (Frontend) | 2 |
| backend | DeveloperAgent (Backend) | 3 |
| testing | FinalizerAgent | 2 |
| beta_testing | BetaTesterAgent | 3 ⭐ |
| deployment | DeploymentAgent | 2 |
| marketing | MarketingAgent | 2 |

## Time Simulation

### Time Speed Multiplier
- Affects work_cycle progress calculation
- Affects sleep duration in GUI work loop
- Range: 0.5x to 10x speed

### Work Units
- Each task has an "effort" value (time units to complete)
- Each work_cycle processes: `time_delta * productivity * time_speed`
- Typical effort values: 20-60 units
- Full project: ~270 total effort units

## File Generation

### Developer Output — Real Coding AI
When developers complete tasks, they generate real, structured, functional code:
1. **Frontend tasks**: `FrontendController` class with initialization, rendering, user action handling, state management, and optional security methods
2. **Backend tasks**: `BackendService` class with full CRUD request handling (GET/POST/PUT/DELETE), health checks, and optional analytics
3. **Design tasks**: `SystemArchitecture` class with component/connection modeling and blueprint generation
4. **General tasks**: Context-aware module classes with initialization, execution, and status methods

All generated code includes:
- Proper imports and type hints
- Logging with `logging` module
- Error handling with try/except
- Docstrings and documentation
- `main()` entry point
- Clean Python structure

### File Structure
```python
{
    'filename': str,
    'content': str,
    'description': str
}
```

## Beta Testing System ⭐

### Structured Test Scenarios
Beta testers run structured test scenarios from a pool of 8 scenario types:
- Normal usage flow, edge cases (empty input, large data), error recovery
- Concurrent access, accessibility, performance under load, mobile responsiveness

### Bug Detection
1. Complete assigned beta_testing tasks
2. Randomly test 3-6 scenarios per task
3. Generate 0-3 bugs per task with detailed categorization
4. Classify by severity (low/medium/high/critical) and category (functional/ui/performance/security/accessibility/data_integrity)
5. Track reproducibility

### UX Scoring
Each test produces a UX score (3.0-5.0) with qualitative feedback:
- 4.5+: "Excellent user experience. Ready for production."
- 4.0+: "Good user experience with minor improvements suggested."
- 3.5+: "Acceptable experience. Some usability issues to address."
- <3.5: "Needs improvement. Several usability concerns identified."

### Bug Data Structure
```python
{
    'severity': str ('low'|'medium'|'high'|'critical'),
    'category': str ('functional'|'ui'|'performance'|'security'|...),
    'description': str,
    'scenario': str,
    'task': str,
    'reproducible': bool,
    'timestamp': str
}
```

### Test Report Structure
```python
{
    'task': str,
    'scenarios_tested': List[str],
    'bugs_found': List[Dict],
    'ux_score': float,
    'feedback': str,
    'timestamp': str
}
```

## Persistence

### Project Save Format (JSON)
```json
{
    "project": {
        "name": str,
        "description": str,
        "created_at": ISO8601,
        "status": str,
        "tasks": [...],
        "progress": float,
        "files": [...],
        "steering": {
            "directives": [...],
            "focus_areas": [...],
            "feedback_log": [...]
        }
    },
    "agents": [
        {
            "name": str,
            "role": str,
            "logs": [...],
            "status": {...},
            "emotional_state": {
                "morale": float,
                "stress": float,
                "confidence": float,
                "current_emotion": str,
                "history": [...]
            }
        }
    ]
}
```

## Scalability Considerations

### Current Limits
- 18 agents (practical limit for UI display)
- Single project at a time
- In-memory processing

### Recently Implemented
- ✅ Emotional intelligence with productivity modulation
- ✅ User steering with real-time directives and focus areas
- ✅ Real code generation (Frontend, Backend, Architecture modules)
- ✅ Interactive agentic runtime with event system
- ✅ Agent-to-agent collaboration
- ✅ Structured beta testing with UX scoring
- ✅ Detailed bug categorization and reporting

### Potential Enhancements
- Add more agent types (Documentation, UX Research, etc.)
- Support multiple concurrent projects
- Persistent database instead of JSON
- Agent skill progression over time
- More sophisticated task dependencies
- Integration with real LLM APIs for actual code generation

## Security

### Current State
- No network access
- Local file system only
- No external API calls
- No credential management needed

### CodeQL Analysis
- 0 security alerts found
- All code follows Python best practices

## Dependencies

### Minimal Requirements
- Python 3.7+
- Standard library only (json, os, datetime, time, threading)
- Optional: Tkinter for GUI (pre-installed on most systems)

### No External Packages
The system is designed to be self-contained and dependency-free for maximum portability.

## Extension Points

### Adding New Agent Types
1. Create class inheriting from `Agent`
2. Override `complete_task()` for specialized behavior
3. Add instances in `Company.initialize_agents()`
4. Update `Company.assign_tasks()` for task routing

### Adding New Task Types
1. Extend `PresidentOfOperationsAgent.create_work_plan()`
2. Add task type to `Company.assign_tasks()` logic
3. Create or assign to appropriate agent type

### Custom UI
The company module is UI-agnostic:
- Import `Company` class
- Call methods directly
- Build any interface (web, mobile, etc.)

## Design Principles

1. **Modularity**: Clear separation between agents, company, and UI
2. **Extensibility**: Easy to add new agent types and behaviors
3. **Testability**: Core logic independent of UI
4. **Simplicity**: No complex dependencies or frameworks
5. **Transparency**: Full activity logging for observability
6. **Realism**: Models actual software development workflows

## Future Architecture Considerations

### Microservices Approach
Could be refactored as:
- Agent Service (manages all agents)
- Task Service (handles task queue)
- Project Service (manages projects)
- UI Service (web frontend)
- Event Bus (for inter-service communication)

### AI Integration
Replace rule-based logic with actual AI:
- CEO: LLM for requirement analysis
- Developers: Code generation models
- Beta Testers: Automated testing frameworks
- Marketing: Content generation AI

### Distributed Simulation
- Run agents as separate processes
- Message queue for task distribution
- Horizontal scaling for more agents
- Real-time collaboration features
