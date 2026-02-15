"""
Company and Project models for Dev-Ville
"""
import json
import os
from typing import List, Dict, Any
from datetime import datetime
from agents import (
    Agent, CEOAgent, PresidentOfOperationsAgent, DeveloperAgent,
    ResearcherAgent, FinalizerAgent, DeploymentAgent, MarketingAgent,
    BetaTesterAgent
)


class Project:
    """Represents a software project"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.created_at = datetime.now().isoformat()
        self.status = "planning"
        self.tasks = []
        self.progress = 0.0
        self.files = []
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary"""
        return {
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at,
            'status': self.status,
            'tasks': self.tasks,
            'progress': self.progress,
            'files': self.files
        }
        
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Project':
        """Create project from dictionary"""
        project = Project(data['name'], data['description'])
        project.created_at = data.get('created_at', project.created_at)
        project.status = data.get('status', 'planning')
        project.tasks = data.get('tasks', [])
        project.progress = data.get('progress', 0.0)
        project.files = data.get('files', [])
        return project
        
    def calculate_progress(self) -> float:
        """Calculate overall project progress"""
        if not self.tasks:
            return 0.0
            
        total_effort = sum(task.get('effort', 0) for task in self.tasks)
        if total_effort == 0:
            return 0.0
            
        completed_work = sum(
            min(task.get('progress', 0), task.get('effort', 0))
            for task in self.tasks
        )
        
        self.progress = (completed_work / total_effort) * 100
        return self.progress


class Company:
    """Represents the AI software company"""
    
    def __init__(self):
        self.name = "Dev-Ville Inc."
        self.agents: List[Agent] = []
        self.current_project: Project = None
        self.time_speed = 1.0  # 1.0 = normal, 2.0 = 2x speed, etc.
        self.is_running = False
        self.initialize_agents()
        
    def initialize_agents(self):
        """Initialize all company agents"""
        # Executive team
        self.agents.append(CEOAgent("Alexandra Chen"))
        self.agents.append(PresidentOfOperationsAgent("Marcus Rodriguez"))
        
        # Research team
        self.agents.append(ResearcherAgent("Dr. Sarah Kim"))
        self.agents.append(ResearcherAgent("Dr. James Wilson"))
        
        # Frontend team
        self.agents.append(DeveloperAgent("Emily Zhang", "Frontend"))
        self.agents.append(DeveloperAgent("Chris Taylor", "Frontend"))
        
        # Backend team
        self.agents.append(DeveloperAgent("Michael Brown", "Backend"))
        self.agents.append(DeveloperAgent("Jessica Martinez", "Backend"))
        self.agents.append(DeveloperAgent("David Lee", "Backend"))
        
        # QA team
        self.agents.append(FinalizerAgent("Lisa Anderson"))
        self.agents.append(FinalizerAgent("Robert Thompson"))
        
        # Beta Testing team
        self.agents.append(BetaTesterAgent("Ryan Mitchell"))
        self.agents.append(BetaTesterAgent("Priya Sharma"))
        self.agents.append(BetaTesterAgent("Carlos Santos"))
        
        # DevOps team
        self.agents.append(DeploymentAgent("Kevin Patel"))
        self.agents.append(DeploymentAgent("Michelle Wong"))
        
        # Marketing team
        self.agents.append(MarketingAgent("Sophie Laurent"))
        self.agents.append(MarketingAgent("Daniel Cooper"))
        
    def start_project(self, directive: str) -> Project:
        """Start a new project based on user directive"""
        # CEO analyzes the directive
        ceo = next((a for a in self.agents if isinstance(a, CEOAgent)), None)
        if ceo:
            project_plan = ceo.analyze_directive(directive)
            
            # Create project
            self.current_project = Project(
                name=f"Project-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                description=directive
            )
            
            # President creates work plan
            president = next((a for a in self.agents if isinstance(a, PresidentOfOperationsAgent)), None)
            if president:
                tasks = president.create_work_plan(project_plan)
                self.current_project.tasks = tasks
                self.assign_tasks(tasks)
                
        return self.current_project
        
    def assign_tasks(self, tasks: List[Dict[str, Any]]):
        """Assign tasks to appropriate agents"""
        for task in tasks:
            task_type = task.get('type')
            
            # Find appropriate agent
            if task_type == 'research':
                agent = next((a for a in self.agents if isinstance(a, ResearcherAgent) and a.status == 'idle'), None)
            elif task_type == 'frontend':
                agent = next((a for a in self.agents if isinstance(a, DeveloperAgent) and 'Frontend' in a.role and a.status == 'idle'), None)
            elif task_type == 'backend':
                agent = next((a for a in self.agents if isinstance(a, DeveloperAgent) and 'Backend' in a.role and a.status == 'idle'), None)
            elif task_type == 'testing':
                agent = next((a for a in self.agents if isinstance(a, FinalizerAgent) and a.status == 'idle'), None)
            elif task_type == 'beta_testing':
                agent = next((a for a in self.agents if isinstance(a, BetaTesterAgent) and a.status == 'idle'), None)
            elif task_type == 'deployment':
                agent = next((a for a in self.agents if isinstance(a, DeploymentAgent) and a.status == 'idle'), None)
            elif task_type == 'marketing':
                agent = next((a for a in self.agents if isinstance(a, MarketingAgent) and a.status == 'idle'), None)
            else:
                # Default to any idle developer
                agent = next((a for a in self.agents if isinstance(a, DeveloperAgent) and a.status == 'idle'), None)
                
            if agent:
                agent.assign_task(task)
                task['assigned_to'] = agent.name
                
    def work_cycle(self, time_delta: float):
        """Process one work cycle for all agents"""
        if not self.current_project:
            return
            
        time_delta *= self.time_speed
        completed_tasks = []
        
        for agent in self.agents:
            completed = agent.work(time_delta)
            if completed:
                completed_tasks.append(completed)
                
                # Collect generated files from developers
                if isinstance(agent, DeveloperAgent) and agent.code_files:
                    self.current_project.files.extend(agent.code_files)
                    agent.code_files = []
                    
        # Reassign tasks if any agents are idle
        idle_tasks = [task for task in self.current_project.tasks 
                     if task.get('progress', 0) < task.get('effort', 100) 
                     and not task.get('assigned_to')]
        if idle_tasks:
            self.assign_tasks(idle_tasks)
            
        # Update project progress
        self.current_project.calculate_progress()
        
        # Update project status
        if self.current_project.progress >= 100:
            self.current_project.status = "completed"
            
    def get_all_logs(self) -> List[str]:
        """Get logs from all agents"""
        all_logs = []
        for agent in self.agents:
            all_logs.extend(agent.export_logs())
        return sorted(all_logs)
        
    def save_project(self, filepath: str):
        """Save current project to file"""
        if not self.current_project:
            return
            
        data = {
            'project': self.current_project.to_dict(),
            'agents': [
                {
                    'name': agent.name,
                    'role': agent.role,
                    'logs': agent.export_logs(),
                    'status': agent.get_status()
                }
                for agent in self.agents
            ]
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            
    def load_project(self, filepath: str):
        """Load project from file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        self.current_project = Project.from_dict(data['project'])
        
        # Restore agent logs
        agent_data = {a['name']: a for a in data.get('agents', [])}
        for agent in self.agents:
            if agent.name in agent_data:
                agent.log = agent_data[agent.name].get('logs', [])
    
    def continue_project(self):
        """Continue working on the current project by reassigning incomplete tasks"""
        if not self.current_project:
            return False
        
        # Reset all agents to idle state if not already
        for agent in self.agents:
            if not agent.current_task and not agent.task_queue:
                agent.status = "idle"
        
        # Find incomplete tasks and reassign them
        incomplete_tasks = [
            task for task in self.current_project.tasks 
            if task.get('progress', 0) < task.get('effort', 100)
        ]
        
        if incomplete_tasks:
            # Clear old assignments first
            for task in incomplete_tasks:
                task.pop('assigned_to', None)
            
            # Reassign tasks
            self.assign_tasks(incomplete_tasks)
            
            # Log that we're continuing
            for agent in self.agents:
                if agent.current_task or agent.task_queue:
                    agent.log_activity(f"Continuing work on project: {self.current_project.name}")
            
            return True
        
        return False
                
    def export_files(self, export_dir: str):
        """Export all project files"""
        if not self.current_project:
            return
            
        project_dir = os.path.join(export_dir, self.current_project.name)
        os.makedirs(project_dir, exist_ok=True)
        
        # Export code files
        for file_info in self.current_project.files:
            filepath = os.path.join(project_dir, file_info['filename'])
            with open(filepath, 'w') as f:
                f.write(file_info['content'])
                
        # Export project info
        with open(os.path.join(project_dir, 'PROJECT_INFO.json'), 'w') as f:
            json.dump(self.current_project.to_dict(), f, indent=2)
            
    def export_logs(self, export_dir: str):
        """Export all agent logs"""
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(export_dir, f'company_logs_{timestamp}.txt')
        
        with open(log_file, 'w') as f:
            f.write(f"Dev-Ville Inc. - Company Logs\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            for log_entry in self.get_all_logs():
                f.write(log_entry + "\n")
