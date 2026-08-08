"""Company-compatible facade routing Dev-Ville GUI mutations through Victor."""
from __future__ import annotations

from typing import Optional, Sequence

from victor_driver import VictorDriver


class VictorDriverCompanyFacade:
    """Expose Company-shaped controls while keeping Victor on the authority path."""

    def __init__(self, driver: VictorDriver):
        object.__setattr__(self, "driver", driver)

    @property
    def vehicle(self):
        return self.driver.vehicle

    @property
    def current_project(self):
        return self.vehicle.current_project

    @property
    def agents(self):
        return self.vehicle.agents

    @property
    def time_speed(self):
        return self.vehicle.time_speed

    @time_speed.setter
    def time_speed(self, value):
        self.vehicle.time_speed = value

    def start_project(self, directive: str):
        return self.driver.start_project(directive)

    def work_cycle(self, time_delta: float):
        return self.driver.heartbeat(time_delta)

    def steer(self, directive: str, priority: str = "normal", target_role: Optional[str] = None):
        return self.driver.steer(directive, priority, target_role)

    def send_feedback(self, feedback: str, sentiment: str = "neutral", target_agent: Optional[str] = None):
        return self.driver.send_feedback(feedback, sentiment, target_agent)

    def set_focus(self, areas: Sequence[str]):
        return self.driver.set_focus(areas)

    def continue_project(self):
        return self.driver.continue_project()

    def save_project(self, path: str):
        return self.driver.save_project(path)

    def load_project(self, path: str):
        return self.driver.load_project(path)

    def export_files(self, path: str):
        return self.driver.export_files(path)

    def export_logs(self, path: str):
        return self.driver.export_logs(path)

    def __getattr__(self, name: str):
        return getattr(self.vehicle, name)
