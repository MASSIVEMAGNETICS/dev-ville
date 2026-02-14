"""
Dev-Ville CLI: Command-Line Interface Version
For environments without GUI support
"""
import sys
import time
import os
from company import Company


class DevVilleCLI:
    """Command-line interface for Dev-Ville"""
    
    def __init__(self):
        self.company = Company()
        self.running = True
        
    def print_banner(self):
        """Print application banner"""
        print("=" * 80)
        print(" " * 25 + "DEV-VILLE")
        print(" " * 15 + "AI Software Company Simulator")
        print("=" * 80)
        print()
        
    def print_menu(self):
        """Print main menu"""
        print("\nMain Menu:")
        print("1. Start New Project")
        print("2. View Agents Status")
        print("3. View Activity Log")
        print("4. View Tasks")
        print("5. View Generated Files")
        print("6. Run Simulation (10 cycles)")
        print("7. Save Project")
        print("8. Load Project")
        print("9. Export Files")
        print("10. Export Logs")
        print("0. Exit")
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
            
    def view_agents(self):
        """View agents status"""
        print("\n--- Agents Status ---")
        print(f"{'Name':<25} {'Role':<30} {'Status':<12} {'Current Task':<30}")
        print("-" * 100)
        
        for agent in self.company.agents:
            status = agent.get_status()
            print(f"{status['name']:<25} {status['role']:<30} {status['status']:<12} {status['current_task']:<30}")
            
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
            print(f"Cycle {i+1}/10 - Progress: {progress:.1f}%")
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
                    self.view_agents()
                elif choice == '3':
                    self.view_log()
                elif choice == '4':
                    self.view_tasks()
                elif choice == '5':
                    self.view_files()
                elif choice == '6':
                    self.run_simulation()
                elif choice == '7':
                    self.save_project()
                elif choice == '8':
                    self.load_project()
                elif choice == '9':
                    self.export_files()
                elif choice == '10':
                    self.export_logs()
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
