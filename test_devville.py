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
        test_log_export
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
