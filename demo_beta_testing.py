"""
Demo script for Dev-Ville showcasing the Beta Testing Team
"""
from company import Company


def extract_log_message(log_entry):
    """Extract message from log entry, handling various formats"""
    if ']' in log_entry:
        parts = log_entry.split('] ', 1)
        return parts[1] if len(parts) > 1 else log_entry
    return log_entry


def main():
    print("=" * 80)
    print(" " * 20 + "DEV-VILLE BETA TESTING DEMO")
    print("=" * 80)
    print()
    
    # Create company
    company = Company()
    print(f"✓ {company.name} initialized with {len(company.agents)} agents")
    
    # Show beta testing team
    print("\n--- Beta Testing Team ---")
    beta_testers = [a for a in company.agents if 'Beta' in a.role]
    for tester in beta_testers:
        print(f"  • {tester.name} - {tester.role}")
        print(f"    Expertise: {', '.join(tester.expertise)}")
    
    # Start a project
    print("\n--- Starting Project ---")
    directive = "Create a modern e-commerce platform with payment integration"
    project = company.start_project(directive)
    print(f"✓ Project: {project.name}")
    print(f"  Directive: {directive}")
    print(f"  Total tasks: {len(project.tasks)}")
    
    # Show beta testing task
    beta_tasks = [t for t in project.tasks if t['type'] == 'beta_testing']
    print(f"\n--- Beta Testing Tasks ({len(beta_tasks)}) ---")
    for task in beta_tasks:
        print(f"  • {task['description']}")
        print(f"    Effort: {task['effort']} units")
        print(f"    Assigned to: {task.get('assigned_to', 'Unassigned')}")
    
    # Run simulation
    print("\n--- Running Work Simulation ---")
    print("Simulating 30 work cycles...")
    
    for i in range(30):
        company.work_cycle(2.0)
        if (i + 1) % 10 == 0:
            progress = project.calculate_progress()
            print(f"  Cycle {i+1}: Progress {progress:.1f}%")
    
    # Show beta testing results
    print("\n--- Beta Testing Results ---")
    for tester in beta_testers:
        if tester.log:
            print(f"\n{tester.name}:")
            beta_logs = [log for log in tester.log if 'Beta testing' in log]
            for log in beta_logs:
                print(f"  {extract_log_message(log)}")
            
            if hasattr(tester, 'bugs_found') and tester.bugs_found:
                print(f"\n  Bugs Found: {len(tester.bugs_found)}")
                for bug in tester.bugs_found:
                    print(f"    • [{bug['severity'].upper()}] {bug['description']}")
    
    # Final project status
    print("\n--- Project Status ---")
    print(f"  Overall Progress: {project.progress:.1f}%")
    print(f"  Status: {project.status}")
    print(f"  Files Generated: {len(project.files)}")
    print(f"  Completed Tasks: {sum(1 for t in project.tasks if t.get('progress', 0) >= t.get('effort', 100))}/{len(project.tasks)}")
    
    print("\n" + "=" * 80)
    print("Demo Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
