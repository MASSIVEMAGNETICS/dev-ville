"""
Company and Project models for Dev-Ville
Includes interactive agentic runtime, user steering, and emotional intelligence.
"""
import json
import os
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from agents import (
    Agent, CEOAgent, PresidentOfOperationsAgent, DeveloperAgent,
    ResearcherAgent, FinalizerAgent, DeploymentAgent, MarketingAgent,
    BetaTesterAgent, EmotionalState, UserSteering,
    SupervisorAgent, RewardSystem, Ticket, DemoRecorder
)


# Constants
COMPLETE_PROGRESS = 100  # Progress percentage for completed projects/tasks


class Project:
    """Represents a software project with user steering support"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.created_at = datetime.now().isoformat()
        self.status = "planning"
        self.tasks = []
        self.progress = 0.0
        self.files = []
        self.steering = UserSteering()
        self.tickets: List[Ticket] = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary"""
        return {
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at,
            'status': self.status,
            'tasks': self.tasks,
            'progress': self.progress,
            'files': self.files,
            'steering': self.steering.to_dict(),
            'tickets': [t.to_dict() for t in self.tickets]
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
        if 'steering' in data:
            project.steering = UserSteering.from_dict(data['steering'])
        project.tickets = [Ticket.from_dict(t) for t in data.get('tickets', [])]
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
        
        self.progress = (completed_work / total_effort) * COMPLETE_PROGRESS
        return self.progress


class Company:
    """Represents the AI software company with interactive agentic runtime.

    Features:
    - User steering: real-time directives that guide agent behavior
    - Emotional intelligence: agents react to workload, feedback, collaboration
    - Interactive runtime: event-driven work cycles with feedback loops
    - Agent-to-agent communication: collaboration between agents
    """

    def __init__(self):
        self.name = "Dev-Ville Inc."
        self.agents: List[Agent] = []
        self.current_project: Optional[Project] = None
        self.time_speed = 1.0
        self.is_running = False
        self.event_listeners: Dict[str, List[Callable]] = {}
        self.runtime_events: List[Dict[str, Any]] = []
        self.reward_system = RewardSystem()
        self.demo_recorder = DemoRecorder()
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
        
        # Supervisor team
        self.agents.append(SupervisorAgent("James O'Brien"))
        self.agents.append(SupervisorAgent("Natasha Volkov"))
        
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

                # Create tickets for all tasks
                for task in tasks:
                    ticket = Ticket(
                        title=task.get('description', 'Untitled'),
                        description=f"Task: {task.get('description', '')} (type: {task.get('type', '')})",
                        ticket_type=task.get('type', 'general'),
                        priority='high' if task.get('type') in ('backend', 'frontend') else 'normal',
                        assigned_to=task.get('assigned_to')
                    )
                    if task.get('assigned_to'):
                        ticket.assign(task['assigned_to'])
                    self.current_project.tickets.append(ticket)

            # Record demo event
            self.demo_recorder.record_event(
                'project_started',
                f'Project started: {directive}',
                {'project_name': self.current_project.name}
            )

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
        """Process one work cycle for all agents with interactive runtime.

        Applies user steering, triggers agent collaboration, processes
        ticket lifecycle, rewards agents, supervisor reviews, and
        fires runtime events for the interactive agentic loop.
        """
        if not self.current_project:
            return

        time_delta *= self.time_speed
        completed_tasks = []

        # Apply pending user steering directives
        self._apply_steering()

        for agent in self.agents:
            if isinstance(agent, SupervisorAgent):
                # Supervisors review tickets instead of normal work
                self._supervisor_review_cycle(agent)
                continue

            completed = agent.work(time_delta)
            if completed:
                completed_tasks.append(completed)

                # Collect generated files from developers
                if isinstance(agent, DeveloperAgent) and agent.code_files:
                    self.current_project.files.extend(agent.code_files)
                    agent.code_files = []

                # Reward the agent
                new_achievements = self.reward_system.record_task_completion(agent.name)
                if new_achievements:
                    for ach in new_achievements:
                        agent.emotional_state.update("positive_feedback")
                        agent.log_activity(f"Achievement unlocked: {ach['name']} (+{ach['points']} pts)")
                        self.demo_recorder.record_event(
                            'achievement', f"{agent.name} earned '{ach['name']}'",
                            {'agent': agent.name, 'achievement': ach['name']}
                        )

                # Update associated ticket
                self._advance_ticket(agent.name, completed)

                # Trigger collaboration when tasks complete
                self._trigger_collaboration(agent, completed)

                self._emit_event("task_completed", {
                    'agent': agent.name,
                    'task': completed.get('description', ''),
                })

                self.demo_recorder.record_event(
                    'task_completed',
                    f"{agent.name} completed: {completed.get('description', '')}",
                    {'agent': agent.name, 'task_type': completed.get('type', '')}
                )

        # Check for special achievements based on agent state
        for agent in self.agents:
            if agent.emotional_state.morale > 0.9:
                self.reward_system.award_special(agent.name, 'high_morale')
            if agent.emotional_state.stress < 0.2:
                self.reward_system.award_special(agent.name, 'low_stress')
            if len(agent.interactions) >= 3:
                self.reward_system.award_special(agent.name, 'collaborator')

        # Reassign tasks if any agents are idle
        idle_tasks = [task for task in self.current_project.tasks
                     if task.get('progress', 0) < task.get('effort', 100)
                     and not task.get('assigned_to')]
        if idle_tasks:
            self.assign_tasks(idle_tasks)

        # Update project progress
        self.current_project.calculate_progress()

        # Update project status
        if self.current_project.progress >= COMPLETE_PROGRESS:
            self.current_project.status = "completed"
            self._emit_event("project_completed", {
                'project': self.current_project.name
            })
            self.demo_recorder.record_event(
                'project_completed',
                f"Project completed: {self.current_project.name}",
                {'progress': self.current_project.progress}
            )
            
    def get_all_logs(self) -> List[str]:
        """Get logs from all agents"""
        all_logs = []
        for agent in self.agents:
            all_logs.extend(agent.export_logs())
        return sorted(all_logs)
        
    def save_project(self, filepath: str):
        """Save current project to file including emotional states, rewards, and recordings"""
        if not self.current_project:
            return

        data = {
            'project': self.current_project.to_dict(),
            'agents': [
                {
                    'name': agent.name,
                    'role': agent.role,
                    'logs': agent.export_logs(),
                    'status': agent.get_status(),
                    'emotional_state': agent.emotional_state.to_dict()
                }
                for agent in self.agents
            ],
            'reward_system': self.reward_system.to_dict(),
            'demo_recorder': self.demo_recorder.to_dict()
        }

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def load_project(self, filepath: str):
        """Load project from file including emotional states, rewards, and recordings"""
        with open(filepath, 'r') as f:
            data = json.load(f)

        self.current_project = Project.from_dict(data['project'])

        # Restore agent logs and emotional states
        agent_data = {a['name']: a for a in data.get('agents', [])}
        for agent in self.agents:
            if agent.name in agent_data:
                agent.log = agent_data[agent.name].get('logs', [])
                if 'emotional_state' in agent_data[agent.name]:
                    agent.emotional_state = EmotionalState.from_dict(
                        agent_data[agent.name]['emotional_state']
                    )

        # Restore reward system
        if 'reward_system' in data:
            self.reward_system = RewardSystem.from_dict(data['reward_system'])

        # Restore demo recorder
        if 'demo_recorder' in data:
            self.demo_recorder = DemoRecorder.from_dict(data['demo_recorder'])
    
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
                task['assigned_to'] = None
            
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

    # --- User Steering ---

    def steer(self, directive: str, priority: str = "normal",
              target_role: Optional[str] = None) -> Dict[str, Any]:
        """Add a user steering directive to guide agent behavior at runtime"""
        if not self.current_project:
            return {'error': 'No active project'}
        entry = self.current_project.steering.add_directive(
            directive, priority, target_role
        )
        self._emit_event("user_steering", {
            'directive': directive,
            'priority': priority,
            'target_role': target_role
        })
        return entry

    def send_feedback(self, feedback: str, sentiment: str = "neutral",
                      target_agent: Optional[str] = None) -> Dict[str, Any]:
        """Send user feedback to agents (positive/neutral/negative)"""
        if not self.current_project:
            return {'error': 'No active project'}
        entry = self.current_project.steering.add_feedback(feedback, sentiment)
        targets = self.agents
        if target_agent:
            targets = [a for a in self.agents if a.name == target_agent]
        for agent in targets:
            agent.receive_feedback(feedback, sentiment)
        self._emit_event("user_feedback", {
            'feedback': feedback,
            'sentiment': sentiment,
            'target': target_agent or 'all'
        })
        return entry

    def set_focus(self, areas: List[str]):
        """Set focus areas that influence agent behavior (e.g. security, performance)"""
        if not self.current_project:
            return
        self.current_project.steering.set_focus(areas)
        self._emit_event("focus_changed", {'areas': areas})

    def _apply_steering(self):
        """Apply pending steering directives to relevant agents"""
        if not self.current_project:
            return
        for agent in self.agents:
            pending = self.current_project.steering.get_pending_directives(agent.role)
            for directive in pending:
                agent.apply_steering(directive)
                self.current_project.steering.mark_applied(directive)

    # --- Agent Collaboration ---

    def _trigger_collaboration(self, completing_agent: Agent,
                               completed_task: Dict[str, Any]):
        """Trigger collaboration between agents when tasks are completed"""
        task_type = completed_task.get('type', '')

        # Developer completes -> notify QA agents
        if isinstance(completing_agent, DeveloperAgent):
            for agent in self.agents:
                if isinstance(agent, FinalizerAgent) and agent.status == "working":
                    completing_agent.interact_with(agent, f"code handoff: {task_type}")
                    break

        # QA completes -> notify Beta Testers
        if isinstance(completing_agent, FinalizerAgent):
            for agent in self.agents:
                if isinstance(agent, BetaTesterAgent) and agent.status == "working":
                    completing_agent.interact_with(agent, f"qa handoff: {task_type}")
                    break

    # --- Interactive Agentic Runtime ---

    def on(self, event_name: str, callback: Callable):
        """Register a listener for a runtime event"""
        if event_name not in self.event_listeners:
            self.event_listeners[event_name] = []
        self.event_listeners[event_name].append(callback)

    def off(self, event_name: str, callback: Optional[Callable] = None):
        """Remove a listener for a runtime event"""
        if event_name in self.event_listeners:
            if callback:
                self.event_listeners[event_name] = [
                    cb for cb in self.event_listeners[event_name]
                    if cb != callback
                ]
            else:
                self.event_listeners[event_name] = []

    def _emit_event(self, event_name: str, data: Dict[str, Any]):
        """Emit a runtime event to all registered listeners"""
        event = {
            'event': event_name,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        self.runtime_events.append(event)
        for callback in self.event_listeners.get(event_name, []):
            callback(event)

    def get_runtime_events(self, event_type: Optional[str] = None,
                           limit: int = 50) -> List[Dict[str, Any]]:
        """Get runtime events, optionally filtered by type"""
        events = self.runtime_events
        if event_type:
            events = [e for e in events if e['event'] == event_type]
        return events[-limit:]

    def get_team_morale(self) -> Dict[str, Any]:
        """Get aggregate emotional state of the team"""
        if not self.agents:
            return {'average_morale': 0, 'average_stress': 0, 'team_emotion': 'neutral'}
        total_morale = sum(a.emotional_state.morale for a in self.agents)
        total_stress = sum(a.emotional_state.stress for a in self.agents)
        total_confidence = sum(a.emotional_state.confidence for a in self.agents)
        count = len(self.agents)
        avg_morale = total_morale / count
        avg_stress = total_stress / count

        if avg_morale > 0.7 and avg_stress < 0.4:
            team_emotion = "thriving"
        elif avg_morale > 0.5:
            team_emotion = "steady"
        elif avg_stress > 0.6:
            team_emotion = "under_pressure"
        else:
            team_emotion = "neutral"

        return {
            'average_morale': round(avg_morale, 2),
            'average_stress': round(avg_stress, 2),
            'average_confidence': round(total_confidence / count, 2),
            'team_emotion': team_emotion,
            'agent_count': count
        }

    def get_beta_test_summary(self) -> Dict[str, Any]:
        """Get a summary of all beta testing results"""
        testers = [a for a in self.agents if isinstance(a, BetaTesterAgent)]
        total_bugs = []
        total_reports = []
        for tester in testers:
            total_bugs.extend(tester.bugs_found)
            total_reports.extend(tester.test_reports)

        severity_counts = {}
        for bug in total_bugs:
            sev = bug.get('severity', 'unknown')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        avg_ux = 0.0
        if total_reports:
            avg_ux = sum(r.get('ux_score', 0) for r in total_reports) / len(total_reports)

        return {
            'total_bugs': len(total_bugs),
            'severity_breakdown': severity_counts,
            'total_test_reports': len(total_reports),
            'average_ux_score': round(avg_ux, 1),
            'testers': len(testers)
        }

    # --- Ticket System ---

    def _advance_ticket(self, agent_name: str, completed_task: Dict[str, Any]):
        """Advance a ticket through the lifecycle when a task completes"""
        if not self.current_project:
            return
        task_desc = completed_task.get('description', '')
        for ticket in self.current_project.tickets:
            if ticket.title == task_desc and ticket.status == 'in_progress':
                ticket.submit_for_review()
                break

    def _supervisor_review_cycle(self, supervisor: 'SupervisorAgent'):
        """Have a supervisor review tickets that are in_review status"""
        if not self.current_project:
            return
        for ticket in self.current_project.tickets:
            if ticket.status == 'in_review':
                review = supervisor.review_ticket(ticket)
                if review['passed']:
                    # If approved and testing is done, mark complete
                    ticket.complete()
                    self.demo_recorder.record_event(
                        'ticket_completed',
                        f"Ticket #{ticket.id} '{ticket.title}' completed",
                        {'ticket_id': ticket.id, 'reviewer': supervisor.name}
                    )
                break  # One review per cycle

    def get_tickets(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get project tickets, optionally filtered by status"""
        if not self.current_project:
            return []
        tickets = self.current_project.tickets
        if status:
            tickets = [t for t in tickets if t.status == status]
        return [t.to_dict() for t in tickets]

    def get_ticket_summary(self) -> Dict[str, Any]:
        """Get summary of all tickets by status"""
        if not self.current_project:
            return {'total': 0, 'by_status': {}}
        tickets = self.current_project.tickets
        by_status: Dict[str, int] = {}
        for t in tickets:
            by_status[t.status] = by_status.get(t.status, 0) + 1
        return {
            'total': len(tickets),
            'by_status': by_status
        }

    # --- Research ---

    def get_research_summary(self) -> Dict[str, Any]:
        """Get a summary of all research findings from researcher agents"""
        researchers = [a for a in self.agents if isinstance(a, ResearcherAgent)]
        all_findings = []
        for researcher in researchers:
            all_findings.extend(researcher.research_findings)

        all_techs = []
        for f in all_findings:
            all_techs.extend(f.get('technologies_evaluated', []))
        unique_techs = list(set(all_techs))

        all_recommendations = []
        for f in all_findings:
            all_recommendations.extend(f.get('recommendations', []))
        unique_recs = list(set(all_recommendations))

        avg_confidence = 0.0
        if all_findings:
            avg_confidence = sum(
                f.get('confidence_score', 0) for f in all_findings
            ) / len(all_findings)

        return {
            'total_findings': len(all_findings),
            'researchers': len(researchers),
            'technologies_evaluated': unique_techs,
            'top_recommendations': unique_recs[:5],
            'average_confidence': round(avg_confidence, 2),
            'findings': all_findings
        }

    # --- Rewards ---

    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Get the agent reward leaderboard"""
        return self.reward_system.get_leaderboard()

    def get_agent_rewards(self, agent_name: str) -> Dict[str, Any]:
        """Get reward details for a specific agent"""
        return self.reward_system.get_agent_rewards(agent_name)

    # --- Supervisor ---

    def get_supervisor_report(self) -> Dict[str, Any]:
        """Get quality report from supervisors"""
        supervisors = [a for a in self.agents if isinstance(a, SupervisorAgent)]
        total_reviews = 0
        total_passed = 0
        all_escalations = []
        for s in supervisors:
            report = s.get_quality_report()
            total_reviews += report['total_reviews']
            total_passed += report['passed']
            all_escalations.extend(s.escalations)

        return {
            'supervisors': len(supervisors),
            'total_reviews': total_reviews,
            'total_passed': total_passed,
            'total_rejected': total_reviews - total_passed,
            'approval_rate': round(total_passed / total_reviews, 2) if total_reviews > 0 else 0.0,
            'open_escalations': sum(1 for e in all_escalations if not e.get('resolved'))
        }

    # --- Demo Recording ---

    def start_demo_recording(self):
        """Start recording demo events"""
        self.demo_recorder.start()

    def stop_demo_recording(self):
        """Stop recording demo events"""
        self.demo_recorder.stop()

    def get_demo_timeline(self) -> List[Dict[str, Any]]:
        """Get the demo recording timeline"""
        return self.demo_recorder.get_timeline()

    def export_demo(self, filepath: str):
        """Export demo recording to a file"""
        self.demo_recorder.export(filepath)
