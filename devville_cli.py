"""
Dev-Ville CLI: Command-Line Interface Version
For environments without GUI support.
Includes user steering, emotional intelligence, interactive runtime,
advanced ticket system, supervisor oversight, agent rewards, and demo recording.
"""
import sys
import time
import os
from company import Company, COMPLETE_PROGRESS


class DevVilleCLI:
    """Command-line interface for Dev-Ville"""
    
    def __init__(self):
        self.company = Company()
        self.running = True
        
    def print_banner(self):
        """Print application banner"""
        print("=" * 80)
        print(" " * 25 + "DEV-VILLE")
        print(" " * 12 + "AI Software Company Emulator")
        print(" " * 5 + "Production-Grade Artifacts | Tickets | Supervisor | Rewards")
        print("=" * 80)
        print()
        
    def print_menu(self):
        """Print main menu"""
        print("\nMain Menu:")
        print("1.  Start New Project")
        print("2.  Continue Project")
        print("3.  View Agents Status")
        print("4.  View Activity Log")
        print("5.  View Tasks")
        print("6.  View Generated Files")
        print("7.  Run Simulation (10 cycles)")
        print("8.  Save Project")
        print("9.  Load Project")
        print("10. Export Files")
        print("11. Export Logs")
        print("12. Steer Agents (User Directive)")
        print("13. Send Feedback to Agents")
        print("14. View Team Morale")
        print("15. View Beta Test Summary")
        print("16. Set Focus Areas")
        print("17. View Research Findings")
        print("18. View Tickets")
        print("19. View Supervisor Report")
        print("20. View Leaderboard & Rewards")
        print("21. Start Demo Recording")
        print("22. Stop Demo Recording")
        print("23. View Demo Timeline")
        print("24. Export Demo Recording")
        print("0.  Exit")
        print()
        
    def start_project(self):
        """Start a new project"""
        print("\n--- Start New Project ---")
        print("Enter your project directive (what should the company build?):")
        directive = input("> ")
        
        if directive.strip():
            self.company.start_project(directive)
            print(f"\n✓ Project started: {self.company.current_project.name}")
            print(f"  Description: {directive}")
            print(f"  Tasks created: {len(self.company.current_project.tasks)}")
        else:
            print("✗ No directive provided")
    
    def continue_project(self):
        """Continue working on the current project"""
        if not self.company.current_project:
            print("\n✗ No active project. Please load or start a project first.")
            return
        
        # Check if project is already complete
        if self.company.current_project.progress >= COMPLETE_PROGRESS:
            print("\n✓ This project is already complete!")
            print("  You can still export files or logs.")
            return
        
        # Continue the project
        result = self.company.continue_project()
        
        if result:
            incomplete_count = sum(
                1 for task in self.company.current_project.tasks 
                if task.get('progress', 0) < task.get('effort', 100)
            )
            print(f"\n✓ Project continued!")
            print(f"  {incomplete_count} incomplete task(s) reassigned to agents.")
            print(f"  Use option 7 to run simulation and make progress.")
        else:
            print("\n✗ No incomplete tasks found to continue")
            
    def view_agents(self):
        """View agents status including emotional state"""
        print("\n--- Agents Status ---")
        print(f"{'Name':<25} {'Role':<25} {'Status':<10} {'Emotion':<12} {'Morale':<8} {'Current Task':<30}")
        print("-" * 115)
        
        for agent in self.company.agents:
            status = agent.get_status()
            print(f"{status['name']:<25} {status['role']:<25} {status['status']:<10} "
                  f"{status.get('emotion', 'N/A'):<12} {status.get('morale', 'N/A'):<8} "
                  f"{status['current_task']:<30}")
            
    def view_log(self):
        """View activity log"""
        print("\n--- Activity Log (Last 20 entries) ---")
        logs = self.company.get_all_logs()
        for log in logs[-20:]:
            print(log)
            
    def view_tasks(self):
        """View tasks"""
        if not self.company.current_project:
            print("\n✗ No active project")
            return
            
        print("\n--- Project Tasks ---")
        print(f"{'Type':<15} {'Description':<40} {'Assigned To':<25} {'Progress':<10}")
        print("-" * 95)
        
        for task in self.company.current_project.tasks:
            progress = task.get('progress', 0)
            effort = task.get('effort', 100)
            progress_pct = min(100, (progress / effort) * 100) if effort > 0 else 0
            
            print(f"{task['type']:<15} {task['description'][:40]:<40} {task.get('assigned_to', 'Unassigned'):<25} {progress_pct:>6.1f}%")
            
    def view_files(self):
        """View generated files"""
        if not self.company.current_project:
            print("\n✗ No active project")
            return
            
        print("\n--- Generated Files ---")
        if not self.company.current_project.files:
            print("No files generated yet")
            return
            
        for i, file_info in enumerate(self.company.current_project.files, 1):
            print(f"{i}. {file_info['filename']} - {file_info['description']}")
            
    def run_simulation(self):
        """Run simulation for 10 cycles"""
        if not self.company.current_project:
            print("\n✗ No active project. Please start a project first.")
            return
            
        print("\n--- Running Simulation ---")
        print("Running 10 work cycles...")
        
        for i in range(10):
            self.company.work_cycle(1.0)
            progress = self.company.current_project.calculate_progress()
            morale = self.company.get_team_morale()
            print(f"Cycle {i+1}/10 - Progress: {progress:.1f}% | Team: {morale['team_emotion']}")
            time.sleep(0.5)  # Brief pause for visibility
            
        print("\n✓ Simulation complete")
        print(f"Project Progress: {self.company.current_project.progress:.1f}%")
        print(f"Status: {self.company.current_project.status}")
        print(f"Files Generated: {len(self.company.current_project.files)}")
        
    def save_project(self):
        """Save project"""
        if not self.company.current_project:
            print("\n✗ No active project to save")
            return
            
        filename = input("Enter filename (default: project.json): ").strip()
        if not filename:
            filename = "project.json"
            
        if not filename.endswith('.json'):
            filename += '.json'
            
        filepath = os.path.join('projects', filename)
        self.company.save_project(filepath)
        print(f"✓ Project saved to {filepath}")
        
    def load_project(self):
        """Load project"""
        filename = input("Enter filename to load: ").strip()
        
        if not filename.endswith('.json'):
            filename += '.json'
            
        filepath = os.path.join('projects', filename)
        
        try:
            self.company.load_project(filepath)
            print(f"✓ Project loaded from {filepath}")
            
            # Check if project has incomplete tasks
            if self.company.current_project:
                incomplete_tasks = [
                    task for task in self.company.current_project.tasks 
                    if task.get('progress', 0) < task.get('effort', 100)
                ]
                
                if incomplete_tasks:
                    print(f"  This project has {len(incomplete_tasks)} incomplete task(s).")
                    print(f"  Use option 2 (Continue Project) to resume work.")
                else:
                    print(f"  This project is complete!")
        except FileNotFoundError:
            print(f"✗ File not found: {filepath}")
        except Exception as e:
            print(f"✗ Error loading project: {e}")
            
    def export_files(self):
        """Export files"""
        if not self.company.current_project:
            print("\n✗ No active project to export")
            return
            
        export_dir = input("Enter export directory (default: exports): ").strip()
        if not export_dir:
            export_dir = "exports"
            
        self.company.export_files(export_dir)
        print(f"✓ Files exported to {os.path.join(export_dir, self.company.current_project.name)}")
        
    def export_logs(self):
        """Export logs"""
        export_dir = input("Enter export directory (default: exports): ").strip()
        if not export_dir:
            export_dir = "exports"
            
        self.company.export_logs(export_dir)
        print(f"✓ Logs exported to {export_dir}")

    def steer_agents(self):
        """Send a steering directive to guide agents"""
        if not self.company.current_project:
            print("\n✗ No active project")
            return

        print("\n--- Steer Agents ---")
        print("Enter a directive to guide the agents:")
        directive = input("> ").strip()
        if not directive:
            print("✗ No directive provided")
            return

        priority = input("Priority (low/normal/high/critical) [normal]: ").strip() or "normal"
        target = input("Target role (leave empty for all): ").strip() or None

        result = self.company.steer(directive, priority=priority, target_role=target)
        print(f"✓ Steering directive added: {result['directive']}")
        print(f"  Priority: {result['priority']}, Target: {result.get('target_role', 'all agents')}")

    def send_feedback(self):
        """Send feedback to agents"""
        if not self.company.current_project:
            print("\n✗ No active project")
            return

        print("\n--- Send Feedback ---")
        print("Enter your feedback:")
        feedback = input("> ").strip()
        if not feedback:
            print("✗ No feedback provided")
            return

        sentiment = input("Sentiment (positive/neutral/negative) [neutral]: ").strip() or "neutral"
        target = input("Target agent name (leave empty for all): ").strip() or None

        result = self.company.send_feedback(feedback, sentiment=sentiment, target_agent=target)
        print(f"✓ Feedback sent ({result['sentiment']}): {result['feedback']}")

    def view_team_morale(self):
        """View team morale and emotional state"""
        print("\n--- Team Morale ---")
        morale = self.company.get_team_morale()
        print(f"  Team Emotion:      {morale['team_emotion']}")
        print(f"  Average Morale:    {morale['average_morale']:.2f}")
        print(f"  Average Stress:    {morale['average_stress']:.2f}")
        print(f"  Average Confidence: {morale['average_confidence']:.2f}")
        print(f"  Agent Count:       {morale['agent_count']}")

        print("\n  Individual States:")
        print(f"  {'Name':<25} {'Emotion':<15} {'Morale':<10} {'Stress':<10}")
        print("  " + "-" * 60)
        for agent in self.company.agents:
            es = agent.emotional_state
            print(f"  {agent.name:<25} {es.current_emotion:<15} {es.morale:<10.2f} {es.stress:<10.2f}")

    def view_beta_summary(self):
        """View beta test summary"""
        print("\n--- Beta Test Summary ---")
        summary = self.company.get_beta_test_summary()
        print(f"  Testers:           {summary['testers']}")
        print(f"  Total Bugs:        {summary['total_bugs']}")
        print(f"  Severity:          {summary['severity_breakdown']}")
        print(f"  Test Reports:      {summary['total_test_reports']}")
        print(f"  Average UX Score:  {summary['average_ux_score']}/5.0")

    def set_focus_areas(self):
        """Set focus areas for agents"""
        if not self.company.current_project:
            print("\n✗ No active project")
            return

        print("\n--- Set Focus Areas ---")
        print("Available: security, performance, testing, ui, api, database, analytics, auth")
        areas_input = input("Enter focus areas (comma separated): ").strip()
        if not areas_input:
            print("✗ No focus areas provided")
            return

        areas = [a.strip() for a in areas_input.split(",") if a.strip()]
        self.company.set_focus(areas)
        print(f"✓ Focus areas set: {areas}")

    def view_research(self):
        """View research findings from researcher agents"""
        print("\n--- Research Findings ---")
        summary = self.company.get_research_summary()
        print(f"  Researchers:            {summary['researchers']}")
        print(f"  Total Findings:         {summary['total_findings']}")
        print(f"  Average Confidence:     {summary['average_confidence']}")
        print(f"  Technologies Evaluated: {', '.join(summary['technologies_evaluated'][:8]) or 'None yet'}")
        print(f"\n  Top Recommendations:")
        for i, rec in enumerate(summary['top_recommendations'], 1):
            print(f"    {i}. {rec}")

        if summary['findings']:
            print(f"\n  Detailed Findings:")
            for finding in summary['findings']:
                print(f"    • {finding['task']}")
                print(f"      Recommended: {finding['recommended_technology']} "
                      f"(confidence: {finding['confidence_score']})")
                print(f"      Evaluated: {', '.join(finding['technologies_evaluated'])}")
        elif summary['total_findings'] == 0:
            print("\n  No research findings yet. Run simulation to generate findings.")

    def view_tickets(self):
        """View project tickets"""
        if not self.company.current_project:
            print("\n✗ No active project")
            return

        print("\n--- Project Tickets ---")
        summary = self.company.get_ticket_summary()
        print(f"  Total Tickets: {summary['total']}")
        print(f"  By Status: {summary['by_status']}")
        print()

        tickets = self.company.get_tickets()
        if not tickets:
            print("  No tickets yet.")
            return

        print(f"  {'ID':<5} {'Status':<15} {'Priority':<10} {'Title':<35} {'Assigned To':<20}")
        print("  " + "-" * 85)
        for t in tickets:
            print(f"  {t['id']:<5} {t['status']:<15} {t['priority']:<10} "
                  f"{t['title'][:35]:<35} {t.get('assigned_to') or 'Unassigned':<20}")

    def view_supervisor_report(self):
        """View supervisor quality report"""
        print("\n--- Supervisor Report ---")
        report = self.company.get_supervisor_report()
        print(f"  Supervisors:      {report['supervisors']}")
        print(f"  Total Reviews:    {report['total_reviews']}")
        print(f"  Passed:           {report['total_passed']}")
        print(f"  Rejected:         {report['total_rejected']}")
        print(f"  Approval Rate:    {report['approval_rate']:.0%}")
        print(f"  Open Escalations: {report['open_escalations']}")

    def view_leaderboard(self):
        """View agent leaderboard and rewards"""
        print("\n--- Agent Leaderboard & Rewards ---")
        leaderboard = self.company.get_leaderboard()
        if not leaderboard:
            print("  No rewards recorded yet. Run simulation to earn rewards.")
            return

        print(f"  {'Rank':<5} {'Agent':<25} {'Points':<10} {'Tasks':<8} {'Achievements':<14} {'Streak':<8}")
        print("  " + "-" * 70)
        for i, entry in enumerate(leaderboard, 1):
            print(f"  {i:<5} {entry['agent']:<25} {entry['total_points']:<10} "
                  f"{entry['tasks_completed']:<8} {entry['achievements']:<14} {entry['current_streak']:<8}")

    def start_demo_recording(self):
        """Start demo recording"""
        self.company.start_demo_recording()
        print("\n✓ Demo recording started. Events will be captured during simulation.")

    def stop_demo_recording(self):
        """Stop demo recording"""
        self.company.stop_demo_recording()
        timeline = self.company.get_demo_timeline()
        print(f"\n✓ Demo recording stopped. {len(timeline)} events captured.")

    def view_demo_timeline(self):
        """View demo recording timeline"""
        print("\n--- Demo Timeline ---")
        timeline = self.company.get_demo_timeline()
        if not timeline:
            print("  No events recorded. Start a demo recording first.")
            return

        for event in timeline[-30:]:
            print(f"  [{event['timestamp']}] {event['type']}: {event['message']}")

        if len(timeline) > 30:
            print(f"\n  ... showing last 30 of {len(timeline)} events")

    def export_demo(self):
        """Export demo recording"""
        export_dir = input("Enter export directory (default: exports): ").strip()
        if not export_dir:
            export_dir = "exports"

        filepath = os.path.join(export_dir, "demo_recording.json")
        self.company.export_demo(filepath)
        print(f"✓ Demo recording exported to {filepath}")

    def run(self):
        """Main run loop"""
        self.print_banner()
        
        while self.running:
            self.print_menu()
            choice = input("Select option: ").strip()
            
            try:
                if choice == '1':
                    self.start_project()
                elif choice == '2':
                    self.continue_project()
                elif choice == '3':
                    self.view_agents()
                elif choice == '4':
                    self.view_log()
                elif choice == '5':
                    self.view_tasks()
                elif choice == '6':
                    self.view_files()
                elif choice == '7':
                    self.run_simulation()
                elif choice == '8':
                    self.save_project()
                elif choice == '9':
                    self.load_project()
                elif choice == '10':
                    self.export_files()
                elif choice == '11':
                    self.export_logs()
                elif choice == '12':
                    self.steer_agents()
                elif choice == '13':
                    self.send_feedback()
                elif choice == '14':
                    self.view_team_morale()
                elif choice == '15':
                    self.view_beta_summary()
                elif choice == '16':
                    self.set_focus_areas()
                elif choice == '17':
                    self.view_research()
                elif choice == '18':
                    self.view_tickets()
                elif choice == '19':
                    self.view_supervisor_report()
                elif choice == '20':
                    self.view_leaderboard()
                elif choice == '21':
                    self.start_demo_recording()
                elif choice == '22':
                    self.stop_demo_recording()
                elif choice == '23':
                    self.view_demo_timeline()
                elif choice == '24':
                    self.export_demo()
                elif choice == '0':
                    print("\nThank you for using Dev-Ville!")
                    self.running = False
                else:
                    print("✗ Invalid option")
                    
                if choice != '0':
                    input("\nPress Enter to continue...")
                    
            except KeyboardInterrupt:
                print("\n\nExiting...")
                self.running = False
            except Exception as e:
                print(f"\n✗ Error: {e}")
                input("\nPress Enter to continue...")


def main():
    """Main entry point"""
    cli = DevVilleCLI()
    cli.run()


if __name__ == "__main__":
    main()
