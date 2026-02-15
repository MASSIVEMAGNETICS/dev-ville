"""
Test script for Dev-Ville
Tests core functionality without GUI
"""
import sys
import os
import traceback

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from company import Company
from agents import CEOAgent, DeveloperAgent


def test_agent_creation():
    """Test agent creation"""
    print("Test 1: Agent Creation")
    ceo = CEOAgent("Test CEO")
    assert ceo.name == "Test CEO"
    assert ceo.role == "Chief Executive Officer"
    print("✓ CEO agent created successfully")
    
    dev = DeveloperAgent("Test Dev", "Frontend")
    assert dev.name == "Test Dev"
    assert "Frontend" in dev.role
    print("✓ Developer agent created successfully")
    print()


def test_company_initialization():
    """Test company initialization"""
    print("Test 2: Company Initialization")
    company = Company()
    assert company.name == "Dev-Ville Inc."
    assert len(company.agents) > 0
    print(f"✓ Company created with {len(company.agents)} agents")
    
    # Print agent roles
    roles = {}
    for agent in company.agents:
        role_category = agent.role.split()[0] if agent.role else "Other"
        roles[role_category] = roles.get(role_category, 0) + 1
    
    print("\nAgent Distribution:")
    for role, count in roles.items():
        print(f"  {role}: {count}")
    print()


def test_project_creation():
    """Test project creation"""
    print("Test 3: Project Creation")
    company = Company()
    
    directive = "Create a web application for task management"
    project = company.start_project(directive)
    
    assert project is not None
    assert project.description == directive
    assert len(project.tasks) > 0
    print(f"✓ Project created with {len(project.tasks)} tasks")
    print(f"  Project name: {project.name}")
    print(f"  Description: {project.description}")
    print()


def test_work_simulation():
    """Test work simulation"""
    print("Test 4: Work Simulation")
    company = Company()
    company.start_project("Create a simple website")
    
    initial_progress = company.current_project.progress
    print(f"Initial progress: {initial_progress:.1f}%")
    
    # Run 5 work cycles
    for i in range(5):
        company.work_cycle(1.0)
    
    final_progress = company.current_project.calculate_progress()
    print(f"Progress after 5 cycles: {final_progress:.1f}%")
    
    assert final_progress > initial_progress
    print("✓ Work simulation working correctly")
    print()


def test_task_assignment():
    """Test task assignment"""
    print("Test 5: Task Assignment")
    company = Company()
    company.start_project("Build a mobile app")
    
    assigned_count = sum(1 for task in company.current_project.tasks if task.get('assigned_to'))
    print(f"✓ {assigned_count}/{len(company.current_project.tasks)} tasks assigned")
    print()


def test_file_generation():
    """Test file generation"""
    print("Test 6: File Generation")
    company = Company()
    company.start_project("Create a backend API")
    
    # Run simulation until some files are generated
    max_cycles = 50
    for i in range(max_cycles):
        company.work_cycle(2.0)  # Faster cycles
        if company.current_project.files:
            break
    
    file_count = len(company.current_project.files)
    print(f"✓ {file_count} file(s) generated after {i+1} cycles")
    
    if file_count > 0:
        print(f"  Sample file: {company.current_project.files[0]['filename']}")
    print()


def test_save_load_project():
    """Test save and load project"""
    print("Test 7: Save/Load Project")
    
    # Create and save project
    company1 = Company()
    company1.start_project("Test project for save/load")
    
    # Run some work
    for _ in range(5):
        company1.work_cycle(1.0)
    
    # Save project
    os.makedirs('projects', exist_ok=True)
    save_path = 'projects/test_project.json'
    company1.save_project(save_path)
    print(f"✓ Project saved to {save_path}")
    
    # Load project
    company2 = Company()
    company2.load_project(save_path)
    
    assert company2.current_project is not None
    assert company2.current_project.description == "Test project for save/load"
    print(f"✓ Project loaded successfully")
    print(f"  Progress: {company2.current_project.progress:.1f}%")
    print()


def test_log_export():
    """Test log export"""
    print("Test 8: Log Export")
    company = Company()
    company.start_project("Test logging")
    
    # Generate some activity
    for _ in range(5):
        company.work_cycle(1.0)
    
    logs = company.get_all_logs()
    print(f"✓ {len(logs)} log entries generated")
    
    # Export logs
    os.makedirs('exports', exist_ok=True)
    company.export_logs('exports')
    print("✓ Logs exported successfully")
    print()


def test_continue_project():
    """Test continue project functionality"""
    print("Test 9: Continue Project")
    
    # Create and partially complete a project
    company1 = Company()
    company1.start_project("Test project for continue")
    
    # Run some work but don't complete
    for _ in range(10):
        company1.work_cycle(1.0)
    
    initial_progress = company1.current_project.progress
    print(f"Initial progress: {initial_progress:.1f}%")
    
    # Save project
    os.makedirs('projects', exist_ok=True)
    save_path = 'projects/test_continue_project.json'
    company1.save_project(save_path)
    print(f"✓ Project saved to {save_path}")
    
    # Load project in new company
    company2 = Company()
    company2.load_project(save_path)
    print(f"✓ Project loaded")
    
    # Continue the project
    result = company2.continue_project()
    assert result == True, "Continue should return True when there are incomplete tasks"
    print(f"✓ Project continued successfully")
    
    # Verify agents have tasks
    agents_with_tasks = sum(1 for agent in company2.agents 
                           if agent.current_task or agent.task_queue)
    print(f"  {agents_with_tasks} agents have tasks assigned")
    
    # Run more work
    for _ in range(10):
        company2.work_cycle(1.0)
    
    final_progress = company2.current_project.progress
    print(f"Progress after continuing: {final_progress:.1f}%")
    
    assert final_progress > initial_progress, "Progress should increase after continuing"
    print("✓ Work continued and progressed correctly")
    print()


def test_emotional_intelligence():
    """Test emotional intelligence system"""
    print("Test 10: Emotional Intelligence")
    from agents import EmotionalState

    # Test emotional state initialization
    state = EmotionalState()
    assert state.morale == 0.75
    assert state.stress == 0.2
    assert state.current_emotion == "neutral"
    print("✓ Emotional state initialized correctly")

    # Test task completion boosts morale
    state.update("task_completed")
    assert state.morale > 0.75
    assert state.stress < 0.2
    print(f"✓ After task completion: morale={state.morale:.2f}, stress={state.stress:.2f}")

    # Test negative feedback
    state.update("negative_feedback")
    prev_morale = state.morale
    state.update("negative_feedback")
    assert state.morale < prev_morale
    print(f"✓ Negative feedback reduces morale: {state.morale:.2f}")

    # Test productivity modifier
    modifier = state.productivity_modifier()
    assert 0.5 <= modifier <= 1.5
    print(f"✓ Productivity modifier: {modifier:.2f}")

    # Test agent emotional state integration
    company = Company()
    company.start_project("Build a test app")
    for _ in range(10):
        company.work_cycle(1.0)

    # Check that agents have emotional states
    for agent in company.agents:
        assert hasattr(agent, 'emotional_state')
        assert isinstance(agent.emotional_state, EmotionalState)
    print("✓ All agents have emotional states")

    # Check team morale
    morale = company.get_team_morale()
    assert 'average_morale' in morale
    assert 'team_emotion' in morale
    print(f"✓ Team morale: {morale['average_morale']:.2f}, emotion: {morale['team_emotion']}")

    # Test emotional state serialization
    state_dict = state.to_dict()
    restored = EmotionalState.from_dict(state_dict)
    assert abs(restored.morale - state.morale) < 0.01
    assert restored.current_emotion == state.current_emotion
    print("✓ Emotional state serialization works")
    print()


def test_user_steering():
    """Test user steering system"""
    print("Test 11: User Steering")

    company = Company()
    company.start_project("Create a web app with security features")

    # Add a steering directive
    result = company.steer("Focus on security best practices", priority="high")
    assert result['directive'] == "Focus on security best practices"
    assert result['priority'] == "high"
    print("✓ Steering directive added")

    # Add targeted directive
    result = company.steer("Use React for frontend", target_role="Developer")
    assert result['target_role'] == "Developer"
    print("✓ Targeted steering directive added")

    # Set focus areas
    company.set_focus(["security", "performance"])
    assert company.current_project.steering.focus_areas == ["security", "performance"]
    print("✓ Focus areas set")

    # Run work cycle to apply steering
    company.work_cycle(1.0)

    # Verify directives were applied
    all_applied = all(
        d['applied'] for d in company.current_project.steering.directives
    )
    assert all_applied, "All directives should be applied after work cycle"
    print("✓ Steering directives applied during work cycle")

    # Test feedback
    entry = company.send_feedback("Great progress!", sentiment="positive")
    assert entry['sentiment'] == "positive"
    print("✓ User feedback sent to agents")

    # Check feedback affected morale
    for agent in company.agents:
        assert agent.emotional_state.morale >= 0.7  # Should stay high with positive feedback
    print("✓ Positive feedback maintained high morale")
    print()


def test_real_code_generation():
    """Test real coding AI code generation"""
    print("Test 12: Real Code Generation")

    from agents import DeveloperAgent

    # Test frontend code generation
    frontend_dev = DeveloperAgent("Test Frontend Dev", "Frontend")
    frontend_task = {
        'type': 'frontend',
        'description': 'Build user dashboard',
        'effort': 5,
        'progress': 0,
        'focus_areas': ['security']
    }
    frontend_dev.assign_task(frontend_task)

    for _ in range(10):
        result = frontend_dev.work(1.0)
        if result:
            break

    assert len(frontend_dev.code_files) > 0, "Should generate code files"
    code = frontend_dev.code_files[0]['content']
    assert 'class FrontendController' in code
    assert 'def initialize' in code
    assert 'def render_view' in code
    print("✓ Frontend code generates real classes with methods")

    # Test backend code generation
    backend_dev = DeveloperAgent("Test Backend Dev", "Backend")
    backend_task = {
        'type': 'backend',
        'description': 'Build API service',
        'effort': 5,
        'progress': 0,
        'focus_areas': ['analytics']
    }
    backend_dev.assign_task(backend_task)

    for _ in range(10):
        result = backend_dev.work(1.0)
        if result:
            break

    assert len(backend_dev.code_files) > 0
    code = backend_dev.code_files[0]['content']
    assert 'class BackendService' in code
    assert 'def process_request' in code
    assert 'def health_check' in code
    print("✓ Backend code generates real service classes")

    # Test architecture code generation
    arch_dev = DeveloperAgent("Test Arch Dev", "Backend")
    arch_task = {
        'type': 'design',
        'description': 'Design system architecture',
        'effort': 5,
        'progress': 0
    }
    arch_dev.assign_task(arch_task)

    for _ in range(10):
        result = arch_dev.work(1.0)
        if result:
            break

    assert len(arch_dev.code_files) > 0
    code = arch_dev.code_files[0]['content']
    assert 'class SystemArchitecture' in code
    print("✓ Architecture code generates design module")
    print()


def test_interactive_runtime():
    """Test interactive agentic runtime"""
    print("Test 13: Interactive Agentic Runtime")

    company = Company()
    company.start_project("Create a web dashboard")

    # Test event registration
    events_received = []

    def on_task_completed(event):
        events_received.append(event)

    company.on("task_completed", on_task_completed)
    print("✓ Event listener registered")

    # Run simulation until a task completes
    for _ in range(30):
        company.work_cycle(2.0)
        if events_received:
            break

    assert len(events_received) > 0, "Should have received task_completed events"
    assert events_received[0]['event'] == "task_completed"
    assert 'agent' in events_received[0]['data']
    print(f"✓ Received {len(events_received)} runtime events")

    # Test runtime event retrieval
    all_events = company.get_runtime_events()
    assert len(all_events) > 0
    print(f"✓ Runtime events logged: {len(all_events)}")

    # Test filtered events
    tc_events = company.get_runtime_events(event_type="task_completed")
    assert len(tc_events) > 0
    print(f"✓ Filtered task_completed events: {len(tc_events)}")

    # Test event removal
    company.off("task_completed", on_task_completed)
    prev_count = len(events_received)
    company.work_cycle(2.0)
    assert len(events_received) == prev_count  # no new events after unsubscribe
    print("✓ Event listener removed successfully")
    print()


def test_beta_testing_enhanced():
    """Test enhanced beta testing with structured reports"""
    print("Test 14: Enhanced Beta Testing")

    company = Company()
    company.start_project("Create a web application for user management")

    # Run enough cycles to complete beta testing
    for _ in range(100):
        company.work_cycle(3.0)
        if company.current_project.progress >= 100:
            break

    # Get beta test summary
    summary = company.get_beta_test_summary()
    assert 'total_bugs' in summary
    assert 'severity_breakdown' in summary
    assert 'average_ux_score' in summary
    assert summary['testers'] == 3
    print(f"✓ Beta test summary: {summary['total_bugs']} bugs found")
    print(f"  Severity breakdown: {summary['severity_breakdown']}")
    print(f"  Average UX score: {summary['average_ux_score']}/5.0")
    print(f"  Test reports: {summary['total_test_reports']}")

    # Check testers have detailed reports
    from agents import BetaTesterAgent
    testers = [a for a in company.agents if isinstance(a, BetaTesterAgent)]
    for tester in testers:
        for report in tester.test_reports:
            assert 'scenarios_tested' in report
            assert 'ux_score' in report
            assert 'feedback' in report

    if any(t.test_reports for t in testers):
        print("✓ Beta test reports contain scenarios, UX scores, and feedback")
    else:
        print("✓ Beta testers initialized (no tasks completed in this run)")
    print()


def test_agent_collaboration():
    """Test agent-to-agent collaboration"""
    print("Test 15: Agent Collaboration")

    from agents import DeveloperAgent, FinalizerAgent

    dev = DeveloperAgent("Dev A", "Backend")
    qa = FinalizerAgent("QA B")

    # Test collaboration
    dev.interact_with(qa, "code review")

    assert len(dev.interactions) == 1
    assert dev.interactions[0]['with'] == "QA B"
    assert dev.interactions[0]['context'] == "code review"
    print("✓ Agent collaboration recorded")

    assert len(qa.interactions) == 1
    assert qa.interactions[0]['with'] == "Dev A"
    print("✓ Bidirectional interaction tracked")

    # Collaboration should improve emotional state
    assert dev.emotional_state.morale > 0.75  # collaboration boosts morale
    print(f"✓ Collaboration improved morale: {dev.emotional_state.morale:.2f}")
    print()


def test_save_load_with_emotions():
    """Test save/load preserves emotional states and steering"""
    print("Test 16: Save/Load with Emotions & Steering")

    company1 = Company()
    company1.start_project("Test emotional persistence")

    # Add steering and feedback
    company1.steer("Focus on testing")
    company1.send_feedback("Good work!", sentiment="positive")

    # Run some work
    for _ in range(10):
        company1.work_cycle(1.0)

    # Save emotional states
    original_morale = company1.agents[0].emotional_state.morale
    original_emotion = company1.agents[0].emotional_state.current_emotion

    os.makedirs('projects', exist_ok=True)
    save_path = 'projects/test_emotions_project.json'
    company1.save_project(save_path)
    print("✓ Project saved with emotional states")

    # Load and verify
    company2 = Company()
    company2.load_project(save_path)

    loaded_morale = company2.agents[0].emotional_state.morale
    assert (abs(loaded_morale - original_morale) < 0.01), (
        f"Morale should be preserved: {loaded_morale} vs {original_morale}"
    )
    print(f"✓ Emotional state preserved: morale={loaded_morale:.2f}")

    # Verify steering was preserved
    assert len(company2.current_project.steering.directives) > 0
    assert len(company2.current_project.steering.feedback_log) > 0
    print("✓ Steering directives and feedback preserved")
    print()


def test_research_findings():
    """Test research findings system"""
    print("Test 17: Research Findings")
    from agents import ResearcherAgent

    company = Company()
    company.start_project("Create a web application with analytics")

    # Run enough cycles to complete research
    for _ in range(30):
        company.work_cycle(2.0)

    summary = company.get_research_summary()
    assert 'total_findings' in summary
    assert 'researchers' in summary
    assert summary['researchers'] == 2
    print(f"✓ Research summary: {summary['total_findings']} findings from {summary['researchers']} researchers")

    if summary['total_findings'] > 0:
        assert len(summary['technologies_evaluated']) > 0
        assert summary['average_confidence'] > 0
        print(f"✓ Technologies evaluated: {summary['technologies_evaluated'][:3]}")
        print(f"  Confidence: {summary['average_confidence']}")

        # Check individual findings
        for finding in summary['findings']:
            assert 'recommended_technology' in finding
            assert 'technologies_evaluated' in finding
            assert 'confidence_score' in finding
            assert 'recommendations' in finding
        print("✓ Findings contain structured data")
    else:
        print("✓ Research system initialized (findings generated during task completion)")
    print()


def test_ticket_system():
    """Test advanced ticket system"""
    print("Test 18: Advanced Ticket System")
    from agents import Ticket

    # Test ticket creation
    ticket = Ticket("Build API", "Create REST API endpoints", "backend", priority="high")
    assert ticket.status == 'open'
    assert ticket.priority == 'high'
    assert ticket.id > 0
    print(f"✓ Ticket created: #{ticket.id} '{ticket.title}'")

    # Test ticket lifecycle
    ticket.assign("Michael Brown")
    assert ticket.status == 'in_progress'
    assert ticket.assigned_to == "Michael Brown"
    print("✓ Ticket assigned and moved to in_progress")

    ticket.submit_for_review()
    assert ticket.status == 'in_review'
    print("✓ Ticket submitted for review")

    ticket.approve("James O'Brien", "Looks good")
    assert ticket.status == 'testing'
    assert ticket.reviewed_by == "James O'Brien"
    print("✓ Ticket approved by supervisor")

    ticket.complete()
    assert ticket.status == 'done'
    assert ticket.completed_at is not None
    print("✓ Ticket completed")

    # Test history
    assert len(ticket.history) == 5  # created, assigned, submitted, approved, completed
    print(f"✓ Ticket history: {len(ticket.history)} entries")

    # Test rejection flow
    ticket2 = Ticket("Fix Bug", "Fix login issue", "frontend")
    ticket2.assign("Emily Zhang")
    ticket2.submit_for_review()
    ticket2.reject("Natasha Volkov", "Needs more error handling")
    assert ticket2.status == 'in_progress'
    print("✓ Ticket rejection flow works")

    # Test serialization
    ticket_dict = ticket.to_dict()
    restored = Ticket.from_dict(ticket_dict)
    assert restored.id == ticket.id
    assert restored.status == 'done'
    assert restored.title == "Build API"
    print("✓ Ticket serialization/deserialization works")

    # Test tickets in company
    company = Company()
    company.start_project("Build a web app")
    assert len(company.current_project.tickets) > 0
    print(f"✓ {len(company.current_project.tickets)} tickets created for project")

    ticket_summary = company.get_ticket_summary()
    assert ticket_summary['total'] > 0
    print(f"✓ Ticket summary: {ticket_summary}")
    print()


def test_supervisor_agent():
    """Test supervisor agent"""
    print("Test 19: Supervisor Agent")
    from agents import SupervisorAgent, Ticket

    supervisor = SupervisorAgent("Test Supervisor")
    assert supervisor.role == "Supervisor"
    print("✓ Supervisor agent created")

    # Test ticket review
    ticket = Ticket("Test Task", "Test description", "backend")
    ticket.assign("Dev Agent")
    ticket.submit_for_review()

    review = supervisor.review_ticket(ticket, quality_pass=True)
    assert review['passed'] == True
    assert ticket.status == 'testing'
    print("✓ Supervisor approved ticket")

    # Test rejection
    ticket2 = Ticket("Test Task 2", "Another task", "frontend")
    ticket2.assign("Dev Agent 2")
    ticket2.submit_for_review()

    review2 = supervisor.review_ticket(ticket2, quality_pass=False)
    assert review2['passed'] == False
    assert ticket2.status == 'in_progress'
    print("✓ Supervisor rejected ticket")

    # Test quality report
    report = supervisor.get_quality_report()
    assert report['total_reviews'] == 2
    assert report['passed'] == 1
    assert report['rejected'] == 1
    print(f"✓ Quality report: {report['approval_rate']:.0%} approval rate")

    # Test escalation
    escalation = supervisor.escalate_issue("Critical bug in production", severity="critical")
    assert escalation['severity'] == 'critical'
    assert not escalation['resolved']
    print("✓ Issue escalation recorded")

    # Test supervisor in company
    company = Company()
    company.start_project("Build a dashboard")
    for _ in range(30):
        company.work_cycle(2.0)

    supervisor_report = company.get_supervisor_report()
    assert 'supervisors' in supervisor_report
    assert supervisor_report['supervisors'] == 2
    print(f"✓ Company supervisor report: {supervisor_report['total_reviews']} reviews")
    print()


def test_reward_system():
    """Test agent reward system"""
    print("Test 20: Reward System")
    from agents import RewardSystem

    rs = RewardSystem()

    # Test task completion rewards
    achievements = rs.record_task_completion("Agent A")
    assert rs.total_points["Agent A"] >= 10
    assert any(a['name'] == 'First Task Complete' for a in achievements)
    print("✓ First task achievement earned")

    # Record more completions for streak
    for _ in range(4):
        achievements = rs.record_task_completion("Agent A")

    assert rs.streaks["Agent A"] == 5
    assert 'five_tasks' in rs.achievements["Agent A"]
    assert 'streak_3' in rs.achievements["Agent A"]
    assert 'streak_5' in rs.achievements["Agent A"]
    print(f"✓ Streak and milestone achievements: {rs.achievements['Agent A']}")

    # Test leaderboard
    rs.record_task_completion("Agent B")
    leaderboard = rs.get_leaderboard()
    assert len(leaderboard) == 2
    assert leaderboard[0]['agent'] == "Agent A"  # Agent A has more points
    print(f"✓ Leaderboard: {leaderboard[0]['agent']} leads with {leaderboard[0]['total_points']} pts")

    # Test special award
    award = rs.award_special("Agent B", "high_morale")
    assert award is not None
    assert award['name'] == 'Team Spirit'
    print("✓ Special achievement awarded")

    # Test no duplicate awards
    duplicate = rs.award_special("Agent B", "high_morale")
    assert duplicate is None
    print("✓ Duplicate awards prevented")

    # Test agent rewards summary
    summary = rs.get_agent_rewards("Agent A")
    assert summary['total_points'] > 0
    assert summary['tasks_completed'] == 5
    print(f"✓ Agent rewards summary: {summary['total_points']} pts, {summary['tasks_completed']} tasks")

    # Test serialization
    rs_dict = rs.to_dict()
    restored = RewardSystem.from_dict(rs_dict)
    assert restored.total_points["Agent A"] == rs.total_points["Agent A"]
    print("✓ Reward system serialization works")

    # Test rewards in company work cycle
    company = Company()
    company.start_project("Build a test app")
    for _ in range(50):
        company.work_cycle(2.0)

    leaderboard = company.get_leaderboard()
    if leaderboard:
        print(f"✓ Company leaderboard: {len(leaderboard)} agents with rewards")
        print(f"  Top agent: {leaderboard[0]['agent']} ({leaderboard[0]['total_points']} pts)")
    else:
        print("✓ Company reward system initialized")
    print()


def test_demo_recording():
    """Test demo recording system"""
    print("Test 21: Demo Recording")
    from agents import DemoRecorder

    dr = DemoRecorder()

    # Test start/stop
    dr.start()
    assert dr.is_recording == True
    assert dr.started_at is not None
    print("✓ Demo recording started")

    # Test event recording
    dr.record_event('test_event', 'Test message', {'key': 'value'})
    assert len(dr.events) == 2  # start event + test event
    print("✓ Event recorded")

    # Events not recorded when not recording
    dr.stop()
    assert dr.is_recording == False
    dr.record_event('should_not_record', 'This should not be recorded')
    assert len(dr.events) == 3  # start + test + stop (not the 4th one)
    print("✓ Events not recorded when stopped")

    # Test timeline
    timeline = dr.get_timeline()
    assert len(timeline) == 3
    assert timeline[0]['type'] == 'recording_started'
    assert timeline[1]['type'] == 'test_event'
    assert timeline[2]['type'] == 'recording_stopped'
    print("✓ Timeline retrieved correctly")

    # Test export
    os.makedirs('/tmp/test_demo', exist_ok=True)
    dr.export('/tmp/test_demo/demo.json')
    assert os.path.exists('/tmp/test_demo/demo.json')
    print("✓ Demo exported to file")

    # Test serialization
    dr_dict = dr.to_dict()
    restored = DemoRecorder.from_dict(dr_dict)
    assert len(restored.events) == len(dr.events)
    print("✓ Demo recorder serialization works")

    # Test company demo recording
    company = Company()
    company.start_demo_recording()
    company.start_project("Build a dashboard")
    for _ in range(20):
        company.work_cycle(2.0)
    company.stop_demo_recording()

    timeline = company.get_demo_timeline()
    assert len(timeline) > 2  # at least start and stop
    print(f"✓ Company demo: {len(timeline)} events recorded")
    print()


def test_production_grade_artifacts():
    """Test production-grade code generation"""
    print("Test 22: Production-Grade Artifacts")

    from agents import DeveloperAgent

    # Test frontend produces production code
    frontend_dev = DeveloperAgent("Test Frontend Dev", "Frontend")
    frontend_task = {
        'type': 'frontend',
        'description': 'Build user dashboard',
        'effort': 5,
        'progress': 0,
        'focus_areas': ['security']
    }
    frontend_dev.assign_task(frontend_task)

    for _ in range(10):
        result = frontend_dev.work(1.0)
        if result:
            break

    assert len(frontend_dev.code_files) >= 2, "Should generate main file + test file"
    code = frontend_dev.code_files[0]['content']
    assert 'class FrontendController' in code
    assert 'class FrontendMiddleware' in code
    assert 'def get_health' in code
    assert 'VERSION = "2.0.0"' in code
    assert 'Dev-Ville Emulator' in code
    print("✓ Frontend generates production-grade code with middleware, caching, health checks")

    # Check companion test file was generated
    test_file = next((f for f in frontend_dev.code_files if f['filename'].startswith('test_')), None)
    assert test_file is not None
    assert 'unittest' in test_file['content']
    print("✓ Companion test file generated")

    # Check config file was generated
    config_file = next((f for f in frontend_dev.code_files if f['filename'].endswith('.json')), None)
    assert config_file is not None
    assert '"environment": "production"' in config_file['content']
    print("✓ Configuration file generated")

    # Test backend produces production code
    backend_dev = DeveloperAgent("Test Backend Dev", "Backend")
    backend_task = {
        'type': 'backend',
        'description': 'Build API service',
        'effort': 5,
        'progress': 0,
        'focus_areas': ['analytics']
    }
    backend_dev.assign_task(backend_task)

    for _ in range(10):
        result = backend_dev.work(1.0)
        if result:
            break

    assert len(backend_dev.code_files) >= 2
    code = backend_dev.code_files[0]['content']
    assert 'class BackendService' in code
    assert 'class RateLimiter' in code
    assert 'class CircuitBreaker' in code
    assert 'def health_check' in code
    assert 'VERSION = "2.0.0"' in code
    print("✓ Backend generates production-grade code with rate limiter, circuit breaker")
    print()


def test_save_load_full_state():
    """Test save/load preserves all new state (rewards, tickets, demo)"""
    print("Test 23: Save/Load Full State")

    company1 = Company()
    company1.start_demo_recording()
    company1.start_project("Test full persistence")

    for _ in range(30):
        company1.work_cycle(2.0)

    company1.stop_demo_recording()

    # Capture state before save
    original_ticket_count = len(company1.current_project.tickets)
    original_leaderboard = company1.get_leaderboard()
    original_timeline_len = len(company1.get_demo_timeline())

    os.makedirs('projects', exist_ok=True)
    save_path = 'projects/test_full_state.json'
    company1.save_project(save_path)
    print("✓ Full state saved")

    # Load and verify
    company2 = Company()
    company2.load_project(save_path)

    assert len(company2.current_project.tickets) == original_ticket_count
    print(f"✓ Tickets preserved: {len(company2.current_project.tickets)}")

    loaded_leaderboard = company2.get_leaderboard()
    if original_leaderboard:
        assert loaded_leaderboard[0]['agent'] == original_leaderboard[0]['agent']
        print(f"✓ Rewards preserved: top agent = {loaded_leaderboard[0]['agent']}")

    loaded_timeline = company2.get_demo_timeline()
    assert len(loaded_timeline) == original_timeline_len
    print(f"✓ Demo recording preserved: {len(loaded_timeline)} events")
    print()


def run_all_tests():
    """Run all tests"""
    print("=" * 80)
    print(" " * 25 + "DEV-VILLE TEST SUITE")
    print("=" * 80)
    print()
    
    tests = [
        test_agent_creation,
        test_company_initialization,
        test_project_creation,
        test_work_simulation,
        test_task_assignment,
        test_file_generation,
        test_save_load_project,
        test_log_export,
        test_continue_project,
        test_emotional_intelligence,
        test_user_steering,
        test_real_code_generation,
        test_interactive_runtime,
        test_beta_testing_enhanced,
        test_agent_collaboration,
        test_save_load_with_emotions,
        test_research_findings,
        test_ticket_system,
        test_supervisor_agent,
        test_reward_system,
        test_demo_recording,
        test_production_grade_artifacts,
        test_save_load_full_state,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ Test failed: {e}")
            traceback.print_exc()
            failed += 1
            print()
    
    print("=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
