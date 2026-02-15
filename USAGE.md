# Dev-Ville Usage Guide

## Quick Start

### Running the GUI Application (Recommended)

```bash
python devville.py
```

**Note**: Requires a desktop environment with Tkinter support. If you get an error about Tkinter not being available, use the CLI version instead.

### Running the CLI Application

For headless environments or when GUI is not available:

```bash
python devville_cli.py
```

### Running the Demo

To see the beta testing team in action:

```bash
python demo_beta_testing.py
```

### Running Tests

To verify everything is working correctly:

```bash
python test_devville.py
```

## Complete Workflow Example

### 1. Start a New Project

**GUI**: 
- Click "File" → "New Project"
- Enter your project directive (e.g., "Create a web application for managing recipes")
- Click "Start Project"

**CLI**:
- Select option 1 "Start New Project"
- Enter your directive when prompted

### 2. Run the Simulation

**GUI**:
- Click the "▶ Play" button
- Use the speed dropdown to adjust simulation speed (1x, 2x, 5x, 10x)
- Watch agents work in real-time in the "Agents" tab
- Monitor progress bars

**CLI**:
- Select option 6 "Run Simulation (10 cycles)"
- Repeat as needed to complete the project

### 3. Monitor Progress

**GUI Tabs**:
- **Agents**: See all 18 employees and their current status
- **Activity Log**: View real-time activity from all agents
- **Tasks**: See project tasks and their progress
- **Generated Files**: Browse all code files created

**CLI Options**:
- Option 2: View Agents Status
- Option 3: View Activity Log
- Option 4: View Tasks
- Option 5: View Generated Files

### 4. Save Your Project

**GUI**: 
- Click "File" → "Save Project"
- Choose location and filename

**CLI**: 
- Select option 8 "Save Project"
- Enter filename (default: project.json)

### 5. Resume Work on a Saved Project

**GUI**:
- Click "File" → "Open Project"
- Select your saved project file
- The system will notify you if there are incomplete tasks
- Click "File" → "Continue Project" (or use the Continue button)
- Tasks will be reassigned to agents
- Click "▶ Play" to resume work

**CLI**:
- Select option 9 "Load Project"
- Enter the project filename
- Select option 2 "Continue Project" to resume work
- Select option 7 "Run Simulation" to make progress

**Note**: The Continue functionality ensures all incomplete tasks are properly reassigned to idle agents, allowing you to seamlessly resume work from where you left off.

### 6. Export Results

**GUI**:
- "File" → "Export All Files" - Get all generated code
- "File" → "Export All Logs" - Get complete activity logs

**CLI**:
- Option 10: Export Files
- Option 11: Export Logs

## Understanding Your Company

### Executive Team
- **CEO (Alexandra Chen)**: Analyzes your directives and approves projects
- **President of Operations (Marcus Rodriguez)**: Creates work plans and assigns tasks

### Research Team (2 members)
- Research technologies and best practices
- Evaluate technical approaches

### Development Teams
- **Frontend Developers (2)**: Build user interfaces
- **Backend Developers (3)**: Create APIs and server logic

### Quality Teams
- **QA Specialists (2)**: Perform code reviews and testing
- **Beta Testers (3)**: Conduct real-world user testing and find bugs

### Operations Teams
- **DevOps Engineers (2)**: Handle deployment and infrastructure
- **Marketing Specialists (2)**: Create marketing materials

## Project Types

The CEO will analyze your directive and determine the project type:

- **Web Application**: Keywords like "web app", "website", "web"
- **Mobile Application**: Keywords like "mobile", "app"
- **API Service**: Keywords like "api", "backend", "service"

## Tips for Best Results

1. **Be Specific**: Give detailed directives for better project plans
   - Good: "Create a web application for task management with user authentication and team collaboration"
   - Less good: "Make an app"

2. **Monitor Beta Testing**: Check the beta testers' logs for discovered bugs
   - They simulate real user testing and may find issues

3. **Adjust Speed**: Use fast-forward (5x or 10x) when you want to see results quickly

4. **Save Often**: Save your project periodically, especially during long simulations

5. **Use Continue**: When resuming a saved project, always use the Continue functionality
   - This ensures tasks are properly reassigned to agents
   - Without continuing, agents won't have work assigned

6. **Export Files**: Use the export feature to get your generated code in a clean directory structure

## Common Workflows

### Working Across Multiple Sessions

1. Start a new project with your directive
2. Click Play and let it run for a while
3. Pause the simulation
4. Save your project (File → Save Project)
5. Close the application
6. Later, reopen the application
7. Load your project (File → Open Project)
8. Continue the project (File → Continue Project or Continue button)
9. Click Play to resume work

### Experimenting with Different Approaches

1. Start a project and run it for a while
2. Save the project
3. Continue working and try different time speeds
4. If you want to try a different approach, close and reload the saved version
5. Continue from the saved point with different settings

## Project Lifecycle

A typical project goes through these phases:

1. **Research** (20 effort units): Technology evaluation
2. **Design** (30 effort units): Architecture planning
3. **Frontend Development** (50 effort units): UI implementation
4. **Backend Development** (60 effort units): Server/API creation
5. **QA Testing** (30 effort units): Quality assurance
6. **Beta Testing** (35 effort units): Real-world user testing ⭐ NEW!
7. **Deployment** (20 effort units): Production deployment
8. **Marketing** (25 effort units): Marketing materials

Total: ~270 effort units

At normal speed (1x), this takes approximately 270 cycles to complete.

## Troubleshooting

### "No module named 'tkinter'"
Use the CLI version instead: `python devville_cli.py`

### Project not progressing
Make sure you clicked "Play" button or selected "Run Simulation" in CLI

### No files being generated
Files are generated by developers. Wait for development tasks to complete (around 100 cycles at 1x speed)

### Can't find saved project
Projects are saved in the `projects/` directory by default

## Advanced Usage

### Custom Time Speeds

The time_speed multiplier affects how quickly agents work:
- 0.5x: Slower, for detailed observation
- 1x: Normal speed
- 2x: Twice as fast
- 5x: Five times faster
- 10x: Maximum speed for quick completion

### Reading Generated Code

Generated files include:
- Python scripts with basic structure
- Comments indicating the purpose
- Attribution to the developer who created them

### Analyzing Beta Testing Results

Beta testers track bugs they find:
- Check individual tester logs in the Activity Log
- Look for "Beta testing complete" messages
- Bug counts and severity levels are logged

## Example Directives

Try these sample directives to see different project types:

```
Create a modern web application for managing personal finances with charts and budgeting tools

Build a mobile app for tracking fitness activities with GPS integration and social features

Develop a RESTful API for an e-commerce platform with payment processing and inventory management

Create a real-time chat application with video calling capabilities

Build a content management system for blogs with markdown support and SEO optimization
```

## Getting Help

- Check the "About" menu in the GUI for version information
- Run tests to verify your installation: `python test_devville.py`
- Review agent logs for detailed information about what's happening

## Next Steps

After your project completes:

1. Review the generated files in the "Generated Files" tab
2. Export all files to get a clean copy
3. Check the beta testing logs for any issues found
4. Review the complete activity log for the entire development process
5. Start a new project or iterate on the current one!
