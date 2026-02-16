# Dev-Ville: AI Software Company Emulator

An AI agent-based complete end-to-end software company emulator that runs on your PC and produces next-generation, production-grade software artifacts. Features advanced ticket system, supervisor oversight, agent rewards, research findings, emotional intelligence, user steering, real code generation, demo recording, and an interactive agentic runtime.

## Features

- **Multi-Agent System**: Complete software company with 20 specialized AI agents:
  - CEO (Strategic Leadership with intelligent directive analysis)
  - President of Operations (Resource Management)
  - Research Team (Technology Research with structured findings)
  - Frontend Developers (Production-grade UI/UX code generation)
  - Backend Developers (Production-grade API/Service code generation)
  - Finalizers (Quality Assurance with detailed reviews)
  - Beta Testing Team (Structured testing with UX scoring)
  - Deployment Team (CI/CD)
  - Marketing Team (Product Marketing)
  - **Supervisor Team** (Quality oversight, ticket reviews, escalation management)

- **Advanced Ticket System**:
  - Full lifecycle tracking: open → in_progress → in_review → testing → done
  - Priority levels: low, normal, high, critical
  - Supervisor approval/rejection workflow
  - Complete audit history for every ticket
  - Auto-creation from project tasks

- **Agent Supervisor & Quality Oversight**:
  - SupervisorAgent reviews completed work
  - Quality metrics and approval rate tracking
  - Issue escalation system
  - Enforcement of completion standards

- **Agent Reward System**:
  - Performance points for completed tasks
  - Achievement badges (First Task, Workhorse, Veteran, Team Player, etc.)
  - Streak tracking (On a Roll, Unstoppable)
  - Leaderboard ranked by total points
  - Rewards boost agent morale via emotional intelligence integration

- **Research Findings**:
  - Structured technology evaluations from researcher agents
  - Recommended technologies with confidence scores
  - Strategic recommendations for the project
  - Dedicated Research tab/view

- **Emotional Intelligence**:
  - Agents have morale, stress, and confidence levels
  - Emotional state affects productivity (0.5x-1.5x modifier)
  - Emotions respond to task completion, feedback, workload, collaboration, and rewards
  - Team morale dashboard for aggregate emotional state

- **User Steering**:
  - Send real-time directives to guide agent behavior
  - Provide positive/negative feedback that affects agent morale
  - Set focus areas (security, performance, testing, etc.)
  - Target specific roles or individual agents

- **Production-Grade Code Generation**:
  - Frontend: `FrontendController` with middleware pipeline, view caching, event system, health checks, error observability
  - Backend: `BackendService` with rate limiting, circuit breaker, request validation, structured error handling
  - Architecture: `SystemArchitecture` with component/connection modeling
  - Auto-generated companion test files for every artifact
  - Auto-generated configuration files with production settings
  - All code includes proper imports, type hints, logging, docstrings, and error handling

- **Demo Recording**:
  - Record simulation events as a reviewable timeline
  - Start/stop recording at any time
  - View event timeline with timestamps
  - Export recordings to JSON for review and sharing

- **Interactive Agentic Runtime**:
  - Event-driven system with listeners (on/off)
  - Runtime events: task_completed, project_completed, user_steering, user_feedback, focus_changed
  - Agent-to-agent collaboration (developer→QA→beta tester handoffs)
  - Real-time event streaming and filtering

- **Enhanced Beta Testing**:
  - 8 structured test scenarios (normal flow, edge cases, error recovery, etc.)
  - UX scoring (3.0-5.0) with qualitative feedback
  - Bug categorization (functional, UI, performance, security, accessibility)
  - Severity levels: low, medium, high, critical
  - Reproducibility tracking

- **Project Management**:
  - Create, save, and open projects
  - Continue working on saved projects
  - Full state persistence (emotional states, tickets, rewards, recordings)
  - Export all employee logs
  - Export all generated files
  - Real-time progress tracking

- **Time Simulation**:
  - Play, pause, and fast-forward time
  - Simulated work cycles with emotional modulation
  - Agent task processing

- **User Interface**:
  - Clean, intuitive GUI with 8 tabs (Agents, Log, Tasks, Files, Research, Tickets, Rewards, Supervisor)
  - CLI with 24 menu options
  - Input box for giving directives to your company
  - Progress bars for project status
  - Activity log viewer
  - Agent status panel with emotional state

## Installation

```bash
# Clone the repository
git clone https://github.com/MASSIVEMAGNETICS/dev-ville.git
cd dev-ville

# Install dependencies
pip install -r requirements.txt

# Run the GUI application
python devville.py

# Or run the CLI version
python devville_cli.py

# Run the test suite
python test_devville.py
```

## Usage

1. **Start a New Project**: File → New Project (or CLI option 1)
2. **Give Directives**: Type your project requirements in the input box
3. **Steer Agents**: Use steering to guide agents with real-time directives (CLI option 12)
4. **Send Feedback**: Provide positive/negative feedback to boost or adjust morale (CLI option 13)
5. **Set Focus Areas**: Direct agents to focus on security, performance, etc. (CLI option 16)
6. **Control Time**: Use Play/Pause/Fast-Forward buttons
7. **Monitor Progress**: Watch agents work and progress bars update
8. **View Research**: Check technology evaluations and recommendations (CLI option 17)
9. **View Tickets**: Track work through the development lifecycle (CLI option 18)
10. **View Supervisor Report**: Check quality metrics and approval rates (CLI option 19)
11. **View Leaderboard**: See agent rewards and achievements (CLI option 20)
12. **Record Demo**: Capture simulation events for review (CLI options 21-24)
13. **View Team Morale**: Check emotional state of the team (CLI option 14)
14. **View Beta Reports**: See structured testing results (CLI option 15)
15. **Save Progress**: File → Save Project to save your work (full state preserved)
16. **Continue Later**: File → Open Project, then Continue to resume work
17. **Export Results**: File → Export Files to get your generated software

## Architecture

The system uses a multi-agent architecture where each agent has:
- Specific role and expertise
- Task queue and work capacity
- Emotional intelligence (morale, stress, confidence)
- User steering support for real-time guidance
- Communication with other agents via collaboration events
- Real code generation capabilities (developers)
- Event-driven runtime for interactive control
- Reward tracking with achievements and streaks

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

## Testing

23 comprehensive tests covering:
- Core agent and company functionality (tests 1-9)
- Emotional intelligence system (test 10)
- User steering system (test 11)
- Real code generation (test 12)
- Interactive agentic runtime (test 13)
- Enhanced beta testing (test 14)
- Agent collaboration (test 15)
- Emotional state persistence (test 16)
- Research findings (test 17)
- Advanced ticket system (test 18)
- Supervisor agent (test 19)
- Reward system (test 20)
- Demo recording (test 21)
- Production-grade artifacts (test 22)
- Full state persistence (test 23)

```bash
python test_devville.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License