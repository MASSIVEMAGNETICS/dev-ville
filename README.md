# Dev-Ville: AI Software Company Simulator

An AI agent-based complete end-to-end software company simulator that runs on your PC and produces real functional enterprise-grade software and applications. Features emotional intelligence, user steering, real code generation, and an interactive agentic runtime.

## Features

- **Multi-Agent System**: Complete software company with 18 specialized AI agents:
  - CEO (Strategic Leadership with intelligent directive analysis)
  - President of Operations (Resource Management)
  - Research Team (Technology Research)
  - Frontend Developers (Real UI/UX code generation)
  - Backend Developers (Real API/Service code generation)
  - Finalizers (Quality Assurance with detailed reviews)
  - Beta Testing Team (Structured testing with UX scoring)
  - Deployment Team (CI/CD)
  - Marketing Team (Product Marketing)

- **Emotional Intelligence**:
  - Agents have morale, stress, and confidence levels
  - Emotional state affects productivity (0.5x-1.5x modifier)
  - Emotions respond to task completion, feedback, workload, and collaboration
  - Team morale dashboard for aggregate emotional state

- **User Steering**:
  - Send real-time directives to guide agent behavior
  - Provide positive/negative feedback that affects agent morale
  - Set focus areas (security, performance, testing, etc.)
  - Target specific roles or individual agents

- **Real Code Generation**:
  - Frontend: `FrontendController` classes with rendering, state management, user actions
  - Backend: `BackendService` classes with full CRUD, health checks, error handling
  - Architecture: `SystemArchitecture` classes with component/connection modeling
  - All code includes proper imports, type hints, logging, docstrings, and error handling

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
  - Emotional states and steering data persist across save/load
  - Export all employee logs
  - Export all generated files
  - Real-time progress tracking

- **Time Simulation**:
  - Play, pause, and fast-forward time
  - Simulated work cycles with emotional modulation
  - Agent task processing

- **User Interface**:
  - Clean, intuitive GUI with emotion display
  - CLI with 16 menu options including steering and morale
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
8. **View Team Morale**: Check emotional state of the team (CLI option 14)
9. **View Beta Reports**: See structured testing results (CLI option 15)
10. **Save Progress**: File → Save Project to save your work (including emotional states)
11. **Continue Later**: File → Open Project, then Continue to resume work
12. **Export Results**: File → Export Files to get your generated software

## Architecture

The system uses a multi-agent architecture where each agent has:
- Specific role and expertise
- Task queue and work capacity
- Emotional intelligence (morale, stress, confidence)
- User steering support for real-time guidance
- Communication with other agents via collaboration events
- Real code generation capabilities (developers)
- Event-driven runtime for interactive control

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system design.

## Testing

16 comprehensive tests covering:
- Core agent and company functionality (tests 1-9)
- Emotional intelligence system (test 10)
- User steering system (test 11)
- Real code generation (test 12)
- Interactive agentic runtime (test 13)
- Enhanced beta testing (test 14)
- Agent collaboration (test 15)
- Emotional state persistence (test 16)

```bash
python test_devville.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License