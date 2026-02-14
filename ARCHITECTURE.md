# Dev-Ville Architecture

## System Overview

Dev-Ville is a multi-agent simulation system that models a complete software development company. The architecture follows a modular design with clear separation of concerns.

## Core Components

### 1. Agent System (`agents.py`)

#### Base Agent Class
The foundation for all company agents, providing:
- Task queue management
- Work processing with progress tracking
- Activity logging
- Status reporting

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
```

#### Specialized Agent Classes

**Executive Agents**:
- `CEOAgent`: Strategic analysis and project approval
- `PresidentOfOperationsAgent`: Work planning and task creation

**Technical Agents**:
- `ResearcherAgent`: Technology evaluation
- `DeveloperAgent`: Code generation (Frontend/Backend specialized)
- `FinalizerAgent`: QA and code review
- `BetaTesterAgent`: User testing with bug detection ⭐
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
The central orchestrator:
- Manages 18 agent instances
- Handles project lifecycle
- Coordinates task assignment
- Processes work cycles
- Manages time simulation
- Provides save/load functionality
- Handles exports (files and logs)

**Key Methods**:
- `start_project(directive)`: Initiates new project
- `assign_tasks(tasks)`: Distributes work to agents
- `work_cycle(time_delta)`: Processes one simulation step
- `save_project(filepath)`: Persists project state
- `load_project(filepath)`: Restores project state
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
For each agent:
    agent.work(time_delta)
    ↓
    Process current_task
    ↓
    Update progress
    ↓
    Complete if progress >= effort
    ↓
    Generate artifacts (code files, etc.)
    ↓
Collect completed tasks
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

### Developer Output
When developers complete tasks:
1. Generate code file with:
   - Descriptive filename (type_timestamp.py)
   - Docstring with task description
   - Basic code structure
   - Attribution to developer
2. Add to agent.code_files
3. Transfer to project.files on completion

### File Structure
```python
{
    'filename': str,
    'content': str,
    'description': str
}
```

## Beta Testing System ⭐

### Bug Detection
Beta testers simulate real-world usage:
1. Complete assigned beta_testing tasks
2. Randomly generate 0-3 bugs per task
3. Classify by severity (low/medium/high)
4. Log findings in agent.log
5. Store in agent.bugs_found for analysis

### Bug Data Structure
```python
{
    'severity': str ('low'|'medium'|'high'),
    'description': str,
    'task': str
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
        "files": [...]
    },
    "agents": [
        {
            "name": str,
            "role": str,
            "logs": [...],
            "status": {...}
        }
    ]
}
```

## Scalability Considerations

### Current Limits
- 18 agents (practical limit for UI display)
- Single project at a time
- In-memory processing

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
