"""
Agent base class for Dev-Ville AI Software Company Simulator
"""
import time
from typing import List, Dict, Any
from datetime import datetime


class Agent:
    """Base class for all AI agents in the software company"""
    
    def __init__(self, name: str, role: str, expertise: List[str]):
        self.name = name
        self.role = role
        self.expertise = expertise
        self.current_task = None
        self.task_queue = []
        self.status = "idle"
        self.productivity = 1.0
        self.log = []
        
    def assign_task(self, task: Dict[str, Any]):
        """Assign a task to this agent"""
        self.task_queue.append(task)
        self.log_activity(f"Assigned task: {task.get('description', 'Unknown task')}")
        
    def work(self, time_delta: float):
        """Process work for the given time delta"""
        if not self.current_task and self.task_queue:
            self.current_task = self.task_queue.pop(0)
            self.status = "working"
            self.log_activity(f"Started working on: {self.current_task.get('description', 'task')}")
            
        if self.current_task:
            progress = time_delta * self.productivity
            self.current_task['progress'] = self.current_task.get('progress', 0) + progress
            
            if self.current_task['progress'] >= self.current_task.get('effort', 100):
                completed_task = self.current_task
                self.complete_task(completed_task)
                self.current_task = None
                if not self.task_queue:
                    self.status = "idle"
                return completed_task
        
        return None
    
    def complete_task(self, task: Dict[str, Any]):
        """Mark a task as complete"""
        self.log_activity(f"Completed task: {task.get('description', 'task')}")
        
    def log_activity(self, message: str):
        """Log an activity"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {self.name} ({self.role}): {message}"
        self.log.append(log_entry)
        
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            'name': self.name,
            'role': self.role,
            'status': self.status,
            'current_task': self.current_task.get('description', 'None') if self.current_task else 'None',
            'queue_size': len(self.task_queue)
        }
        
    def export_logs(self) -> List[str]:
        """Export all logs"""
        return self.log.copy()


class CEOAgent(Agent):
    """CEO Agent - Makes strategic decisions and approves projects"""
    
    def __init__(self, name: str = "CEO"):
        super().__init__(name, "Chief Executive Officer", ["Strategy", "Leadership", "Vision"])
        
    def analyze_directive(self, directive: str) -> Dict[str, Any]:
        """Analyze user directive and create project plan"""
        self.log_activity(f"Analyzing directive: {directive}")
        
        # Simple keyword-based analysis
        project_type = "web_application"
        if "mobile" in directive.lower() or "app" in directive.lower():
            project_type = "mobile_application"
        elif "api" in directive.lower() or "backend" in directive.lower():
            project_type = "api_service"
        elif "website" in directive.lower() or "web" in directive.lower():
            project_type = "website"
            
        return {
            'type': project_type,
            'description': directive,
            'approved': True,
            'priority': 'high'
        }


class PresidentOfOperationsAgent(Agent):
    """President of Operations - Manages resources and coordinates teams"""
    
    def __init__(self, name: str = "President of Operations"):
        super().__init__(name, "President of Operations", ["Resource Management", "Coordination", "Planning"])
        
    def create_work_plan(self, project: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create a work plan from project requirements"""
        self.log_activity(f"Creating work plan for: {project.get('description', 'project')}")
        
        tasks = []
        project_type = project.get('type', 'web_application')
        
        # Research phase
        tasks.append({
            'type': 'research',
            'description': f'Research technologies for {project_type}',
            'effort': 20,
            'progress': 0,
            'assigned_to': None
        })
        
        # Design phase
        tasks.append({
            'type': 'design',
            'description': 'Design system architecture',
            'effort': 30,
            'progress': 0,
            'assigned_to': None
        })
        
        # Development phase
        if project_type in ['web_application', 'website']:
            tasks.append({
                'type': 'frontend',
                'description': 'Develop frontend interface',
                'effort': 50,
                'progress': 0,
                'assigned_to': None
            })
            
        tasks.append({
            'type': 'backend',
            'description': 'Develop backend services',
            'effort': 60,
            'progress': 0,
            'assigned_to': None
        })
        
        # Testing phase
        tasks.append({
            'type': 'testing',
            'description': 'Quality assurance and testing',
            'effort': 30,
            'progress': 0,
            'assigned_to': None
        })
        
        # Beta Testing phase
        tasks.append({
            'type': 'beta_testing',
            'description': 'Beta testing with real users',
            'effort': 35,
            'progress': 0,
            'assigned_to': None
        })
        
        # Deployment phase
        tasks.append({
            'type': 'deployment',
            'description': 'Deploy to production',
            'effort': 20,
            'progress': 0,
            'assigned_to': None
        })
        
        # Marketing phase
        tasks.append({
            'type': 'marketing',
            'description': 'Create marketing materials',
            'effort': 25,
            'progress': 0,
            'assigned_to': None
        })
        
        return tasks


class DeveloperAgent(Agent):
    """Developer Agent - Writes code"""
    
    def __init__(self, name: str, specialty: str):
        expertise = [specialty, "Coding", "Problem Solving"]
        super().__init__(name, f"{specialty} Developer", expertise)
        self.code_files = []
        
    def complete_task(self, task: Dict[str, Any]):
        """Complete task and generate code"""
        super().complete_task(task)
        
        # Generate code file
        code_file = {
            'filename': f"{task['type']}_{int(time.time())}.py",
            'content': self.generate_code(task),
            'description': task['description']
        }
        self.code_files.append(code_file)
        self.log_activity(f"Generated code file: {code_file['filename']}")
        
    def generate_code(self, task: Dict[str, Any]) -> str:
        """Generate code for the task"""
        task_type = task.get('type', 'general')
        description = task.get('description', 'No description')
        
        code = f'''"""
{description}
Generated by {self.name}
"""

def main():
    """Main function for {task_type}"""
    print("Implementing {task_type} functionality")
    # TODO: Implement actual logic
    pass

if __name__ == "__main__":
    main()
'''
        return code


class ResearcherAgent(Agent):
    """Researcher Agent - Conducts technology research"""
    
    def __init__(self, name: str = "Researcher"):
        super().__init__(name, "Researcher", ["Research", "Analysis", "Technology Evaluation"])
        
    def complete_task(self, task: Dict[str, Any]):
        """Complete research task"""
        super().complete_task(task)
        self.log_activity(f"Research findings documented for: {task['description']}")


class FinalizerAgent(Agent):
    """Finalizer Agent - Quality assurance and code review"""
    
    def __init__(self, name: str = "QA Specialist"):
        super().__init__(name, "Quality Assurance", ["Testing", "Code Review", "Quality Control"])
        
    def complete_task(self, task: Dict[str, Any]):
        """Complete QA task"""
        super().complete_task(task)
        self.log_activity(f"Quality check passed for: {task['description']}")


class DeploymentAgent(Agent):
    """Deployment Agent - Handles deployment"""
    
    def __init__(self, name: str = "DevOps Engineer"):
        super().__init__(name, "DevOps", ["Deployment", "CI/CD", "Infrastructure"])
        
    def complete_task(self, task: Dict[str, Any]):
        """Complete deployment task"""
        super().complete_task(task)
        self.log_activity(f"Deployment successful for: {task['description']}")


class MarketingAgent(Agent):
    """Marketing Agent - Creates marketing materials"""
    
    def __init__(self, name: str = "Marketing Specialist"):
        super().__init__(name, "Marketing", ["Marketing", "Content Creation", "Branding"])
        
    def complete_task(self, task: Dict[str, Any]):
        """Complete marketing task"""
        super().complete_task(task)
        self.log_activity(f"Marketing materials created for: {task['description']}")


class BetaTesterAgent(Agent):
    """Beta Tester Agent - Tests software with real-world scenarios"""
    
    def __init__(self, name: str = "Beta Tester"):
        super().__init__(name, "Beta Tester", ["User Testing", "Bug Detection", "Feedback Collection"])
        self.bugs_found = []
        
    def complete_task(self, task: Dict[str, Any]):
        """Complete beta testing task"""
        super().complete_task(task)
        
        # Simulate finding bugs (random for realism)
        import random
        bug_count = random.randint(0, 3)
        
        if bug_count > 0:
            for i in range(bug_count):
                bug = {
                    'severity': random.choice(['low', 'medium', 'high']),
                    'description': f"Issue found in {task['description']}",
                    'task': task['description']
                }
                self.bugs_found.append(bug)
            self.log_activity(f"Beta testing complete - {bug_count} issue(s) found in: {task['description']}")
        else:
            self.log_activity(f"Beta testing complete - No issues found in: {task['description']}")
