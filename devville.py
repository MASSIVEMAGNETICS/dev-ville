"""
Dev-Ville: AI Software Company Simulator
Main GUI Application
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import time
import os
from company import Company


class DevVilleApp:
    """Main application window"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Dev-Ville - AI Software Company Simulator")
        self.root.geometry("1200x800")
        
        self.company = Company()
        self.is_running = False
        self.time_speed = 1.0
        self.work_thread = None
        
        self.setup_ui()
        self.update_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Menu bar
        self.create_menu_bar()
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Control panel at top
        self.create_control_panel(main_frame)
        
        # Progress section
        self.create_progress_section(main_frame)
        
        # Main content area with tabs
        self.create_tabbed_content(main_frame)
        
        # Status bar at bottom
        self.create_status_bar(main_frame)
        
    def create_menu_bar(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Project", command=self.new_project_dialog)
        file_menu.add_command(label="Open Project", command=self.open_project)
        file_menu.add_command(label="Save Project", command=self.save_project)
        file_menu.add_separator()
        file_menu.add_command(label="Export All Files", command=self.export_files)
        file_menu.add_command(label="Export All Logs", command=self.export_logs)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        
    def create_control_panel(self, parent):
        """Create control panel with input and time controls"""
        control_frame = ttk.LabelFrame(parent, text="Control Panel", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        control_frame.columnconfigure(0, weight=1)
        
        # Directive input
        input_frame = ttk.Frame(control_frame)
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        input_frame.columnconfigure(1, weight=1)
        
        ttk.Label(input_frame, text="Project Directive:").grid(row=0, column=0, padx=(0, 5))
        self.directive_entry = ttk.Entry(input_frame, width=60)
        self.directive_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        self.directive_entry.insert(0, "Create a modern web application for task management")
        
        ttk.Button(input_frame, text="Start Project", command=self.start_project).grid(row=0, column=2)
        
        # Time controls
        time_frame = ttk.Frame(control_frame)
        time_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        ttk.Label(time_frame, text="Time Control:").grid(row=0, column=0, padx=(0, 10))
        
        self.play_button = ttk.Button(time_frame, text="▶ Play", command=self.play)
        self.play_button.grid(row=0, column=1, padx=2)
        
        self.pause_button = ttk.Button(time_frame, text="⏸ Pause", command=self.pause, state='disabled')
        self.pause_button.grid(row=0, column=2, padx=2)
        
        ttk.Label(time_frame, text="Speed:").grid(row=0, column=3, padx=(20, 5))
        
        self.speed_var = tk.StringVar(value="1x")
        speed_combo = ttk.Combobox(time_frame, textvariable=self.speed_var, 
                                   values=["0.5x", "1x", "2x", "5x", "10x"], 
                                   width=8, state='readonly')
        speed_combo.grid(row=0, column=4, padx=2)
        speed_combo.bind('<<ComboboxSelected>>', self.change_speed)
        
    def create_progress_section(self, parent):
        """Create progress bars section"""
        progress_frame = ttk.LabelFrame(parent, text="Project Progress", padding="10")
        progress_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        # Overall progress
        ttk.Label(progress_frame, text="Overall Progress:").grid(row=0, column=0, sticky=tk.W)
        self.overall_progress = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.overall_progress.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        self.progress_label = ttk.Label(progress_frame, text="0%")
        self.progress_label.grid(row=1, column=1, padx=(5, 0))
        
        # Project info
        self.project_info_label = ttk.Label(progress_frame, text="No active project")
        self.project_info_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
    def create_tabbed_content(self, parent):
        """Create tabbed content area"""
        notebook = ttk.Notebook(parent)
        notebook.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Agents tab
        agents_frame = ttk.Frame(notebook)
        notebook.add(agents_frame, text="Agents")
        self.create_agents_view(agents_frame)
        
        # Activity Log tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="Activity Log")
        self.create_log_view(log_frame)
        
        # Tasks tab
        tasks_frame = ttk.Frame(notebook)
        notebook.add(tasks_frame, text="Tasks")
        self.create_tasks_view(tasks_frame)
        
        # Files tab
        files_frame = ttk.Frame(notebook)
        notebook.add(files_frame, text="Generated Files")
        self.create_files_view(files_frame)
        
    def create_agents_view(self, parent):
        """Create agents view"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        
        # Create treeview for agents
        columns = ('Name', 'Role', 'Status', 'Current Task', 'Queue')
        self.agents_tree = ttk.Treeview(parent, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.agents_tree.heading(col, text=col)
            if col == 'Name':
                self.agents_tree.column(col, width=150)
            elif col == 'Role':
                self.agents_tree.column(col, width=200)
            elif col == 'Status':
                self.agents_tree.column(col, width=100)
            elif col == 'Queue':
                self.agents_tree.column(col, width=80)
            else:
                self.agents_tree.column(col, width=250)
        
        self.agents_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.agents_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.agents_tree.configure(yscrollcommand=scrollbar.set)
        
    def create_log_view(self, parent):
        """Create activity log view"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(parent, wrap=tk.WORD, height=20)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
    def create_tasks_view(self, parent):
        """Create tasks view"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        
        columns = ('Type', 'Description', 'Assigned To', 'Progress', 'Status')
        self.tasks_tree = ttk.Treeview(parent, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.tasks_tree.heading(col, text=col)
            if col == 'Type':
                self.tasks_tree.column(col, width=100)
            elif col == 'Progress':
                self.tasks_tree.column(col, width=100)
            elif col == 'Status':
                self.tasks_tree.column(col, width=100)
            elif col == 'Assigned To':
                self.tasks_tree.column(col, width=150)
            else:
                self.tasks_tree.column(col, width=300)
        
        self.tasks_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.tasks_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.tasks_tree.configure(yscrollcommand=scrollbar.set)
        
    def create_files_view(self, parent):
        """Create files view"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        
        columns = ('Filename', 'Description')
        self.files_tree = ttk.Treeview(parent, columns=columns, show='headings', height=15)
        
        self.files_tree.heading('Filename', text='Filename')
        self.files_tree.heading('Description', text='Description')
        self.files_tree.column('Filename', width=200)
        self.files_tree.column('Description', width=500)
        
        self.files_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.files_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.files_tree.configure(yscrollcommand=scrollbar.set)
        
        # Double-click to view file
        self.files_tree.bind('<Double-1>', self.view_file)
        
    def create_status_bar(self, parent):
        """Create status bar"""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.status_label = ttk.Label(status_frame, text="Ready", relief=tk.SUNKEN)
        self.status_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
    def new_project_dialog(self):
        """Show new project dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Project")
        dialog.geometry("500x200")
        dialog.transient(self.root)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(frame, text="Project Directive:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        directive_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, height=5, width=50)
        directive_text.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        directive_text.insert('1.0', "Create a modern web application for task management with user authentication")
        
        def start():
            directive = directive_text.get('1.0', tk.END).strip()
            if directive:
                self.directive_entry.delete(0, tk.END)
                self.directive_entry.insert(0, directive)
                dialog.destroy()
                self.start_project()
        
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0)
        ttk.Button(button_frame, text="Start Project", command=start).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).grid(row=0, column=1, padx=5)
        
    def start_project(self):
        """Start a new project"""
        directive = self.directive_entry.get().strip()
        if not directive:
            messagebox.showwarning("No Directive", "Please enter a project directive")
            return
            
        self.company.start_project(directive)
        self.status_label.config(text=f"Project started: {directive}")
        self.update_ui()
        messagebox.showinfo("Project Started", 
                          f"Project '{self.company.current_project.name}' has been started!\n\n"
                          f"Click 'Play' to begin work simulation.")
        
    def play(self):
        """Start time simulation"""
        if not self.company.current_project:
            messagebox.showwarning("No Project", "Please start a project first")
            return
            
        self.is_running = True
        self.play_button.config(state='disabled')
        self.pause_button.config(state='normal')
        self.status_label.config(text="Running...")
        
        # Start work thread
        self.work_thread = threading.Thread(target=self.work_loop, daemon=True)
        self.work_thread.start()
        
    def pause(self):
        """Pause time simulation"""
        self.is_running = False
        self.play_button.config(state='normal')
        self.pause_button.config(state='disabled')
        self.status_label.config(text="Paused")
        
    def work_loop(self):
        """Main work loop running in separate thread"""
        while self.is_running:
            self.company.work_cycle(1.0)  # 1 second per cycle
            self.root.after(0, self.update_ui)
            # Adjust sleep based on time speed for accurate fast-forward
            time.sleep(1.0 / self.company.time_speed)
            
    def change_speed(self, event=None):
        """Change simulation speed"""
        speed_str = self.speed_var.get()
        self.company.time_speed = float(speed_str.replace('x', ''))
        self.status_label.config(text=f"Speed: {speed_str}")
        
    def update_ui(self):
        """Update all UI elements"""
        self.update_agents_view()
        self.update_log_view()
        self.update_tasks_view()
        self.update_files_view()
        self.update_progress()
        
    def update_agents_view(self):
        """Update agents view"""
        # Clear existing items
        for item in self.agents_tree.get_children():
            self.agents_tree.delete(item)
            
        # Add agent data
        for agent in self.company.agents:
            status = agent.get_status()
            self.agents_tree.insert('', tk.END, values=(
                status['name'],
                status['role'],
                status['status'],
                status['current_task'],
                status['queue_size']
            ))
            
    def update_log_view(self):
        """Update activity log view"""
        self.log_text.delete('1.0', tk.END)
        logs = self.company.get_all_logs()
        
        # Show last 100 log entries
        for log_entry in logs[-100:]:
            self.log_text.insert(tk.END, log_entry + "\n")
            
        self.log_text.see(tk.END)
        
    def update_tasks_view(self):
        """Update tasks view"""
        # Clear existing items
        for item in self.tasks_tree.get_children():
            self.tasks_tree.delete(item)
            
        if not self.company.current_project:
            return
            
        # Add task data
        for task in self.company.current_project.tasks:
            progress = task.get('progress', 0)
            effort = task.get('effort', 100)
            progress_pct = min(100, (progress / effort) * 100) if effort > 0 else 0
            
            status = "Completed" if progress >= effort else "In Progress" if task.get('assigned_to') else "Pending"
            
            self.tasks_tree.insert('', tk.END, values=(
                task.get('type', 'N/A'),
                task.get('description', 'N/A'),
                task.get('assigned_to', 'Unassigned'),
                f"{progress_pct:.1f}%",
                status
            ))
            
    def update_files_view(self):
        """Update files view"""
        # Clear existing items
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)
            
        if not self.company.current_project:
            return
            
        # Add file data
        for file_info in self.company.current_project.files:
            self.files_tree.insert('', tk.END, values=(
                file_info.get('filename', 'N/A'),
                file_info.get('description', 'N/A')
            ))
            
    def update_progress(self):
        """Update progress bars"""
        if self.company.current_project:
            progress = self.company.current_project.calculate_progress()
            self.overall_progress['value'] = progress
            self.progress_label.config(text=f"{progress:.1f}%")
            
            project = self.company.current_project
            self.project_info_label.config(
                text=f"Project: {project.name} | Status: {project.status} | Files: {len(project.files)}"
            )
        else:
            self.overall_progress['value'] = 0
            self.progress_label.config(text="0%")
            self.project_info_label.config(text="No active project")
            
    def view_file(self, event):
        """View file content on double-click"""
        selection = self.files_tree.selection()
        if not selection:
            return
            
        item = self.files_tree.item(selection[0])
        filename = item['values'][0]
        
        # Find file in project
        if self.company.current_project:
            file_info = next((f for f in self.company.current_project.files 
                            if f['filename'] == filename), None)
            if file_info:
                self.show_file_content(file_info)
                
    def show_file_content(self, file_info):
        """Show file content in a new window"""
        window = tk.Toplevel(self.root)
        window.title(file_info['filename'])
        window.geometry("800x600")
        
        text = scrolledtext.ScrolledText(window, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        text.insert('1.0', file_info['content'])
        text.config(state='disabled')
        
    def save_project(self):
        """Save current project"""
        if not self.company.current_project:
            messagebox.showwarning("No Project", "No active project to save")
            return
            
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"{self.company.current_project.name}.json"
        )
        
        if filepath:
            self.company.save_project(filepath)
            messagebox.showinfo("Success", f"Project saved to {filepath}")
            self.status_label.config(text=f"Project saved: {filepath}")
            
    def open_project(self):
        """Open a saved project"""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filepath:
            try:
                self.company.load_project(filepath)
                self.update_ui()
                messagebox.showinfo("Success", f"Project loaded from {filepath}")
                self.status_label.config(text=f"Project loaded: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load project: {str(e)}")
                
    def export_files(self):
        """Export all project files"""
        if not self.company.current_project:
            messagebox.showwarning("No Project", "No active project to export")
            return
            
        export_dir = filedialog.askdirectory(title="Select Export Directory")
        if export_dir:
            try:
                self.company.export_files(export_dir)
                messagebox.showinfo("Success", 
                                  f"Files exported to {os.path.join(export_dir, self.company.current_project.name)}")
                self.status_label.config(text="Files exported successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export files: {str(e)}")
                
    def export_logs(self):
        """Export all agent logs"""
        export_dir = filedialog.askdirectory(title="Select Export Directory")
        if export_dir:
            try:
                self.company.export_logs(export_dir)
                messagebox.showinfo("Success", f"Logs exported to {export_dir}")
                self.status_label.config(text="Logs exported successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export logs: {str(e)}")
                
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About Dev-Ville",
            "Dev-Ville: AI Software Company Simulator\n\n"
            "An AI agent-based complete end-to-end software company\n"
            "that produces real functional enterprise-grade software.\n\n"
            "Features:\n"
            "- Multi-agent system with specialized roles\n"
            "- Time simulation (play, pause, fast-forward)\n"
            "- Project management and code generation\n"
            "- Export functionality for files and logs\n\n"
            "Version: 1.0.0"
        )


def main():
    """Main entry point"""
    root = tk.Tk()
    app = DevVilleApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
