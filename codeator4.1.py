import ast
import os
import pydot
import tkinter as tk
from tkinter import filedialog
from tkinter import scrolledtext
import math
import subprocess
import re
import tempfile
import json

FILE_EXTENSIONS = {
    '.json', '.txt', '.csv', '.ini', '.cfg', '.log', '.dat', '.yaml', '.yml', 
    '.sqlite', '.db', '.png', '.jpg', '.jpeg', '.gif', '.mp3', '.ogg', '.wav', 
    '.pdf', '.docx', '.xlsx', '.bin'
}
LOAD_KEYWORDS = {'load', 'dump', 'read', 'write', 'json', 'map', 'config', 'data', 'file', 'db'}
COLOR_PALETTE = {
    "module":   {"fill": "#dae8fc", "border": "#6c8ebf"},
    "group":    {"fill": "#f5f5f5", "border": "#333333"},
    "class":    {"fill": "#ffe6cc", "border": "#d79b00"},
    "method":   {"fill": "#d5e8d4", "border": "#82b366"},
    "function": {"fill": "#f8cecc", "border": "#b85450"},
    "data":     {"fill": "#fff2cc", "border": "#d6b656"},        # Static files (Yellow/Brown)
    "dynamic_data": {"fill": "#cce5ff", "border": "#007bff"}, # Dynamic files (Blue)
    "edge":     {"fill": "#999999"}
}
def make_safe_id(s: str):
    return re.sub(r'[^A-Za-z0-9_]', '_', s)
def get_file_path_description(arg_node):
    if isinstance(arg_node, ast.Constant) and isinstance(arg_node.value, str):
        return arg_node.value
    if isinstance(arg_node, ast.JoinedStr):
        parts = []
        for val in arg_node.values:
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                parts.append(val.value)
            elif isinstance(val, ast.FormattedValue):
                if isinstance(val.value, ast.Name):
                    parts.append(f"<{val.value.id.upper()}>") 
                elif isinstance(val.value, ast.Call):
                    parts.append("<CALL_RESULT>")
                else:
                    parts.append("<DYNAMIC_PART>")
            else:
                parts.append("<COMPLEX_EXPR>")
        return "".join(parts)
    if isinstance(arg_node, ast.Name):
        return f"<{arg_node.id.upper()}>"
    return "DYNAMIC_ARGUMENT"
def extract_structure_from_file(path: str):
    items = []
    sources = {}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        try:
            tree = ast.parse(content, filename=path)
        except Exception:
            return [], {}
    module_name = os.path.basename(path).replace(".py", "")
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            full_id = f"{module_name}.{node.name}"
            items.append(("module", node.name, "function"))
            sources[full_id] = ast.get_source_segment(content, node)
        elif isinstance(node, ast.ClassDef):
            class_id = f"{module_name}.{node.name}"
            items.append(("module", node.name, "class"))
            sources[class_id] = ast.get_source_segment(content, node)
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    method_id = f"{module_name}.{node.name}.{sub.name}"
                    items.append((node.name, sub.name, "method"))
                    sources[method_id] = ast.get_source_segment(content, sub)
    return items, sources
def scan_path_for_structure(path: str):
    graph = {}
    deps = {}
    master_sources = {}
    master_data_file_nodes = set() 
    master_data_callers = {} 
    paths = [path] if os.path.isfile(path) and path.endswith(".py") else []
    if os.path.isdir(path):
        for dirpath, _, files in os.walk(path):
            for file in files:
                if file.endswith(".py"):
                    paths.append(os.path.join(dirpath, file))
    for full in paths:
        mod_name = os.path.relpath(full, os.path.dirname(path)).replace(os.sep, ".")[:-3]
        if os.path.isfile(path) and path == full:
            mod_name = os.path.basename(path).replace(".py", "")
        structure, sources = extract_structure_from_file(full)
        base_mod = os.path.basename(full).replace(".py", "")
        fixed_sources = {}
        for k, v in sources.items():
            suffix = k[len(base_mod):]
            fixed_sources[f"{mod_name}{suffix}"] = v
        deps_list, data_file_nodes, data_callers = extract_dependencies_from_file(full, mod_name) 
        graph[mod_name] = structure
        master_sources.update(fixed_sources)
        deps[mod_name] = deps_list
        master_data_file_nodes.update(data_file_nodes)
        master_data_callers.update(data_callers)
    return graph, deps, master_sources, master_data_file_nodes, master_data_callers
def extract_dependencies_from_file(path: str, module_name: str):
    deps = []
    data_file_nodes = set() 
    data_callers = {} 
    with open(path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=path)
        except Exception:
            return deps, data_file_nodes, data_callers
    class DependencyVisitor(ast.NodeVisitor):
        def __init__(self, current_module):
            self.current_symbol = None
            self.current_module = current_module
            self.assignment_map = {} 
        def visit_FunctionDef(self, node):
            old = self.current_symbol
            old_map = self.assignment_map 
            self.current_symbol = f"{self.current_module}.{node.name}"
            self.assignment_map = {} 
            self.generic_visit(node)
            self.current_symbol = old
            self.assignment_map = old_map 
        def visit_ClassDef(self, node):
            for base in node.bases:
                if isinstance(base, ast.Name):
                    deps.append((f"{self.current_module}.{node.name}", f"{self.current_module}.{base.id}", "inherit"))
            old = self.current_symbol
            old_map = self.assignment_map 
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    self.current_symbol = f"{self.current_module}.{node.name}.{sub.name}"
                    self.assignment_map = {} 
                    self.generic_visit(sub)
            self.current_symbol = old
            self.assignment_map = old_map 
        def visit_Assign(self, node):
            if len(node.targets) == 1 and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    self.assignment_map[target.id] = node.value.value
            self.generic_visit(node)
        def visit_With(self, node):
            temp_symbol = self.current_symbol if self.current_symbol else self.current_module
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    call_node = item.context_expr
                    if isinstance(call_node.func, ast.Name) and call_node.func.id == 'open':
                        path_arg = call_node.args[0]
                        filename = None
                        if isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str):
                            filename = path_arg.value
                        elif isinstance(path_arg, ast.Name) and path_arg.id in self.assignment_map:
                            filename = self.assignment_map[path_arg.id]
                        if filename:
                            filename = filename.strip()
                            is_file = any(ext in filename.lower() for ext in FILE_EXTENSIONS)
                            if is_file and len(filename) > 0:
                                file_id = f"FILE__{filename}"
                                deps.append((temp_symbol, file_id, "data"))
                                data_file_nodes.add(file_id)
            self.generic_visit(node)
        def visit_Call(self, node):
            temp_symbol = self.current_symbol if self.current_symbol else self.current_module
            if isinstance(node.func, ast.Name) and node.func.id == 'open':
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    filename = node.args[0].value.strip()
                    is_file = any(ext in filename.lower() for ext in FILE_EXTENSIONS)
                    if is_file and len(filename) > 0:
                        file_id = f"FILE__{filename}"
                        deps.append((temp_symbol, file_id, "data"))
                        data_file_nodes.add(file_id)
            elif isinstance(node.func, ast.Attribute):
                method_name = node.func.attr.lower()
                if any(k in method_name for k in LOAD_KEYWORDS):
                    description = "DYNAMIC_ARGUMENT"
                    if node.args:
                        description = get_file_path_description(node.args[0])
                    has_extension = any(ext in description.lower() for ext in FILE_EXTENSIONS)
                    if not has_extension and 'json' in method_name:
                        description += " (JSON)"
                    elif not has_extension and 'config' in method_name:
                        description += " (CONFIG)"
                    generic_id = f"DYNAMIC_DATA__DESC_{make_safe_id(description)}"
                    deps.append((temp_symbol, generic_id, "data"))
                    data_file_nodes.add(generic_id)
                    data_callers[generic_id] = temp_symbol 
            if isinstance(node.func, ast.Name):
                deps.append((temp_symbol, f"{self.current_module}.{node.func.id}", "call"))
            if isinstance(node.func, ast.Attribute):
                deps.append((temp_symbol, f"{self.current_module}.{node.func.attr}", "call"))
            self.generic_visit(node)
    DependencyVisitor(module_name).visit(tree)
    return deps, data_file_nodes, data_callers 
def get_layout_data(structure_graph: dict, deps: dict, data_file_nodes: set, visibility_flags: dict): 
    graph = pydot.Dot(graph_type="digraph", rankdir="LR", splines="ortho", concentrate="true", arrowhead="normal")
    inferred_types = {} 
    safe_id_map = {}
    for module, items in structure_graph.items():
        safe_module = make_safe_id(module)
        safe_id_map[safe_module] = module
        style = COLOR_PALETTE["module"]
        graph.add_node(pydot.Node(safe_module, label=module, shape="component", style="filled", fillcolor=style["fill"], color=style["border"]))
        inferred_types[module] = "module"
        top_funcs = [child for p, child, k in items if p == "module" and k == "function"]
        classes = [child for p, child, k in items if p == "module" and k == "class"]
        methods = [(p, c, k) for p, c, k in items if p != "module"]
        if top_funcs and visibility_flags["function"]: 
            group_id = f"{module}.__FUNCS__"
            safe_group = make_safe_id(group_id)
            safe_id_map[safe_group] = group_id
            style = COLOR_PALETTE["group"]
            graph.add_node(pydot.Node(safe_group, label="Functions", shape="tab", style="filled", fillcolor=style["fill"], color=style["border"]))
            graph.add_edge(pydot.Edge(safe_module, safe_group))
            inferred_types[group_id] = "group"
            for func in top_funcs:
                node_id = f"{module}.{func}"
                safe_node = make_safe_id(node_id)
                safe_id_map[safe_node] = node_id
                style = COLOR_PALETTE["function"]
                graph.add_node(pydot.Node(safe_node, label=func, shape="rect", style="filled", fillcolor=style["fill"], color=style["border"]))
                graph.add_edge(pydot.Edge(safe_group, safe_node))
                inferred_types[node_id] = "function"
        for cls in classes:
            cls_id = f"{module}.{cls}"
            safe_cls = make_safe_id(cls_id)
            safe_id_map[safe_cls] = cls_id
            style = COLOR_PALETTE["class"]
            graph.add_node(pydot.Node(safe_cls, label=cls, shape="rect", style="filled", fillcolor=style["fill"], color=style["border"]))
            graph.add_edge(pydot.Edge(safe_module, safe_cls))
            inferred_types[cls_id] = "class"
        for parent_cls, method, kind in methods:
            if not visibility_flags["method"]: continue 
            cls_id = f"{module}.{parent_cls}"
            method_id = f"{module}.{parent_cls}.{method}"
            safe_cls = make_safe_id(cls_id)
            safe_method = make_safe_id(method_id)
            safe_id_map[safe_cls] = cls_id
            safe_id_map[safe_method] = method_id
            if cls_id not in inferred_types:
                style = COLOR_PALETTE["class"]
                graph.add_node(pydot.Node(safe_cls, label=parent_cls, shape="rect", style="filled", fillcolor=style["fill"], color=style["border"]))
                inferred_types[cls_id] = "class"
            style = COLOR_PALETTE["method"]
            graph.add_node(pydot.Node(safe_method, label=method, shape="rect", style="filled", fillcolor=style["fill"], color=style["border"]))
            graph.add_edge(pydot.Edge(safe_cls, safe_method))
            inferred_types[method_id] = "method"
    for file_id in data_file_nodes:
        if file_id.startswith("FILE__"):
            label = file_id[6:]
            ntype = "data"
            shape = "folder"
        elif file_id.startswith("DYNAMIC_DATA__DESC_"):
            label = file_id[20:].replace('__', ' ').replace('_', '').replace(' ', '')
            display_label = label.replace("MAPFILE", "<MAP_FILE>").replace("DYNAMICARGUMENT", "<DYNAMIC_ARGUMENT>")
            display_label = display_label.replace("DYNAMICPART", "<DYNAMIC_PART>").replace("CALLRESULT", "<CALL_RESULT>")
            ntype = "dynamic_data"
            shape = "note"
        else:
            continue
        if ntype == "data" and not visibility_flags["data"]: continue
        if ntype == "dynamic_data" and not visibility_flags["dynamic_data"]: continue
        safe_id = make_safe_id(file_id)
        safe_id_map[safe_id] = file_id
        style = COLOR_PALETTE[ntype]
        graph.add_node(pydot.Node(safe_id, label=label if ntype == 'data' else display_label, shape=shape, style="filled", fillcolor=style["fill"], color=style["border"]))
        inferred_types[file_id] = ntype
    for module, edge_list in deps.items():
        for src, dst, kind in edge_list:
            safe_src = make_safe_id(src)
            safe_dst = make_safe_id(dst)
            if safe_src not in safe_id_map or safe_dst not in safe_id_map: continue 
            if kind == "data":
                if inferred_types.get(dst) == "dynamic_data":
                    color = COLOR_PALETTE["dynamic_data"]["border"]
                else:
                    color = COLOR_PALETTE["data"]["border"]
                style = "dashed"
                arrowhead = "dot" 
            elif kind == "call":
                color = "#888888"
                style = "solid"
                arrowhead = "vee"
            elif kind == "inherit":
                color = "#aa33aa"
                style = "dashed"
                arrowhead = "vee"
            else:
                color = "#000000"
                style = "solid"
                arrowhead = "vee"
            graph.add_edge(pydot.Edge(safe_src, safe_dst, color=color, style=style, arrowhead=arrowhead))
    try:
        plain_data = graph.create(format="plain").decode("utf-8")
    except Exception:
        return None, None, inferred_types, safe_id_map
    nodes, edges = parse_plain_data(plain_data)
    return nodes, edges, inferred_types, safe_id_map


def parse_plain_data(plain_text):
    lines = plain_text.splitlines()
    if not lines: return [], []
    graph_info = lines[0].split()
    h = float(graph_info[3])
    dpi = 72
    height_px = h * dpi
    nodes = []
    edges = []
    for line in lines:
        parts = line.split()
        if not parts: continue
        kind = parts[0]
        if kind == "node":
            name = parts[1]
            x, y = float(parts[2]) * dpi, float(parts[3]) * dpi
            y = height_px - y 
            w, h = float(parts[4]) * dpi, float(parts[5]) * dpi
            label = parts[6].strip('"')
            nodes.append({"id": name, "x": x, "y": y, "w": w, "h": h, "label": label})
        elif kind == "edge":
            n_points = int(parts[3])
            points = []
            idx = 4
            for i in range(n_points):
                px, py = float(parts[idx]) * dpi, float(parts[idx+1]) * dpi
                py = height_px - py 
                points.append((px, py))
                idx += 2
            edges.append({"tail": parts[1], "head": parts[2], "points": points})
    return nodes, edges
class NativeGraphViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Fast Native Python Visualizer 🚀")
        self.geometry("1600x800")
        
        # --- NEW LAYOUT SYSTEM: PanedWindow ---
        self.main_split = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=6, bg="#3e3e3e")
        self.main_split.pack(fill="both", expand=True)

        # 1. SETUP CANVAS (Left Pane)
        self.canvas = tk.Canvas(self.main_split, bg="white")
        
        # 2. SETUP SIDEBAR (Middle Pane)
        self.sidebar = tk.Frame(self.main_split, width=200, bg="#f0f0f0")

        # 3. SETUP CONSOLE (Right Pane)
        self.console_frame = tk.Frame(self.main_split, bg="#1e1e1e", width=300)

        # --- ADD PANES IN ORDER (Left -> Right) ---
        # 1. Canvas: Set minsize to 1000. It takes up 1000px minimum and all extra space (stretch="always").
        self.main_split.add(self.canvas, minsize=10, stretch="always")
        
        # 2. Sidebar: minsize 200, fixed width (stretch="never")
        self.main_split.add(self.sidebar, minsize=200, stretch="never")
        
        # 3. Console: minsize 700, fixed width (stretch="never")
        self.main_split.add(self.console_frame, minsize=700, stretch="never")

        # In your __init__ method, within the sidebar setup (self.sidebar):
        tk.Button(self.sidebar, text="🚀 Run Code", command=self._run_code, bg="#3285a8", fg="white").pack(fill="x", padx=10, pady=(10, 5))


        # --- SETUP SEARCH BAR ---
        self.search_frame = tk.Frame(self.console_frame, bg="#3e3e3e", padx=5, pady=5)
        self.search_frame.pack(fill="x")
        
        tk.Label(self.search_frame, text="Search:", fg="white", bg="#3e3e3e").pack(side="left")
        
        self.search_entry = tk.Entry(self.search_frame, bg="#2e2e2e", fg="white", insertbackground="white")
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(5, 10))
        self.search_entry.bind('<Return>', self._search_console) # Pressing Enter finds next match
        self.search_entry.bind('<Escape>', lambda e: self._clear_search_highlight()) # Pressing Esc clears search
        
        tk.Button(self.search_frame, text="Next", command=self._search_console).pack(side="left")
        
        # Initialize search state variables
        self.search_start_index = "1.0" # Where to start the next search
        self.current_search_term = ""

        # --- SETUP CONSOLE INTERNALS ---
        from tkinter import scrolledtext
        self.console = scrolledtext.ScrolledText(
            self.console_frame,
            bg="#1e1e1e",
            fg="#d4d4d4",
            font=("Consolas", 10),
            insertbackground="#c3c3c3",
            borderwidth=0
        )
        self.console.pack(fill="both", expand=True)

        # Console coloring tags
        self.console.tag_config("key", foreground="#9cdcfe")
        self.console.tag_config("string", foreground="#ce9178")
        self.console.tag_config("number", foreground="#b5cea8")
        self.console.tag_config("bool", foreground="#569cd6")
        self.console.tag_config("null", foreground="#569cd6")
        self.console.tag_config("bracket", foreground="#d4d4d4")
        self.console.tag_config("header_tag", foreground="#4ec9b0", font=("Consolas", 11, "bold")) # Added header style

        # --- SETUP SIDEBAR CONTROLS ---
        tk.Label(self.sidebar, text="Controls", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=10)
        tk.Button(self.sidebar, text="Open File/Folder", command=self.load_path, bg="white").pack(fill="x", padx=10, pady=5)

        tk.Button(self.sidebar, text="Reset View", command=self.reset_view).pack(side="bottom", fill="x", padx=10, pady=20)
        
        tk.Label(self.sidebar, text="Class Bookmarks", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=5)
        self.class_listbox = tk.Listbox(self.sidebar, height=23)
        self.class_listbox.pack(fill="both", padx=10, pady=5)
        self.class_listbox.bind("<<ListboxSelect>>", self.jump_to_class)

        self.show_funcs_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Functions", variable=self.show_funcs_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)

        self.show_methods_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Methods", variable=self.show_methods_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)

        self.show_files_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Files (Yellow)", variable=self.show_files_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)

        self.show_dynamic_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Dynamic (Blue)", variable=self.show_dynamic_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)
        


        tk.Label(self.sidebar, text="Unused Nodes", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=5)
        self.unused_listbox = tk.Listbox(self.sidebar, height=5)
        self.unused_listbox.pack(fill="both", padx=10, pady=5)
        self.unused_listbox.bind("<<ListboxSelect>>", self.restore_unused_node)

        # --- INITIALIZE STATE VARIABLES ---
        self.tooltip = tk.Label(self.canvas, text="", bg="#2e2e2e", fg="#d4d4d4",
                                font=("Courier New", 9), bd=1, relief="solid", justify="left")
        self.tooltip.place_forget()
        self.hidden_nodes = {}
        self.unused_map = {}
        self.scale = 1.0
        self.structure_graph = {}
        self.dependencies = {}
        self.data_file_nodes = set()
        self.node_type_map = {}
        self.layout_nodes = []
        self.layout_edges = []
        self.safe_id_map = {}
        self.source_map = {}
        self.data_callers = {}
        self.project_name = ""
        self.class_bookmarks = {} # Added missing init

        # --- BINDINGS ---
        self.canvas.bind("<ButtonPress-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.do_pan)
        self.canvas.bind("<MouseWheel>", self.do_zoom)
        self.canvas.bind("<Button-4>", self.do_zoom) # Linux scroll up
        self.canvas.bind("<Button-5>", self.do_zoom) # Linux scroll down
        self.bind_all("<Control-f>", self._activate_search) # Global Ctrl+F binding

        self.console.pack(fill="both", expand=True)

        # Console coloring tags (Existing JSON tags)
        self.console.tag_config("key", foreground="#9cdcfe")
        self.console.tag_config("string", foreground="#ce9178")
        self.console.tag_config("number", foreground="#b5cea8")
        self.console.tag_config("bool", foreground="#569cd6")
        self.console.tag_config("null", foreground="#569cd6")
        self.console.tag_config("bracket", foreground="#d4d4d4")
        self.console.tag_config("header_tag", foreground="#4ec9b0", font=("Consolas", 11, "bold")) 
        
        # --- NEW PYTHON SYNTAX TAGS ---
        # Note: I've updated the font to Consolas for consistency with the rest of your console.
        self.console.tag_config("keyword", foreground="#569cd6")     # VS Code blue for Python keywords
        self.console.tag_config("comment", foreground="#6A9955", font=("Consolas", 10, "italic")) # Green/Gray for comments
        self.console.tag_config("python_string", foreground="#CE9178") # Orange-brown for strings
        self.console.tag_config("definition", foreground="#4EC9B0")  # Teal/Light Blue for def/class names
        self.console.tag_config("literal", foreground="#B5CEA8")     # Light green for boolean/numbers

    def _run_code(self):
        """Saves the current console content and runs it in a separate process."""
        
        # 1. Get the code content safely (using 'end-1c' for a cleaner string)
        code_content = self.console.get("1.0", "end-1c")
        
        # NOTE: Do NOT clear the console here yet, as the console contains the code
        # We need to run, and the output will be logged below.
        
        if not code_content.strip():
            self._log("Nothing to run.", tag="error")
            return

        lines = code_content.splitlines()
        
        # Filter out lines that look like internal headers/metadata
        # This prevents headers like '=== Source Code:...' from being compiled.
        filtered_lines = []
        for line in lines:
            if not line.startswith('=== Source Code:') and \
               not line.startswith('--- Running Temporary File:') and \
               not line.startswith('--- ERRORS ---') and \
               not line.startswith('--- OUTPUT ---') and \
               line.strip(): # Also filter out entirely empty lines
                filtered_lines.append(line)

        final_code_to_run = '\n'.join(filtered_lines)

        if not final_code_to_run.strip():
            self._log("Only header/metadata found. Nothing to run.", tag="error")
            return

        # 2. Create a temporary file and write the FILTERED code to it
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tmp:
            tmp.write(final_code_to_run) # <--- THIS IS THE CRUCIAL FIX
            tmp_filename = tmp.name
            
        self._log(f"\n--- Running Temporary File: {os.path.basename(tmp_filename)} ---", tag="header_tag")

        try:
            # 3. Execute the code using the Python interpreter in a subprocess
            result = subprocess.run(
                ['python', tmp_filename],
                capture_output=True,
                text=True,
                check=False,
                #timeout=30
            )

            # 4. Display the results
            if result.stdout:
                self._log("\n--- OUTPUT ---", tag="header_tag")
                self._log(result.stdout)
                
            if result.stderr:
                self._log("\n--- ERRORS ---", tag="error")
                self._log(result.stderr, tag="error")
                
            if not result.stdout and not result.stderr:
                self._log("\n--- Execution finished with no output. ---", tag="comment")
                
        except subprocess.TimeoutExpired:
            self._log("\n[ERROR] Execution timed out after 5 seconds.", tag="error")
        except FileNotFoundError:
            self._log("\n[FATAL ERROR] Python interpreter not found. Ensure 'python' is in your system's PATH.", tag="error")
        finally:
            # 5. Clean up the temporary file
            os.unlink(tmp_filename)

    # You may need to create a helper method to log cleanly to your console:
    def _log(self, text, tag=None):
        """Inserts text into the console and applies a tag."""
        self.console.config(state="normal")
        self.console.insert(tk.END, "\n" + text, tag)
        self.console.see(tk.END)
        self.console.config(state="disabled")

    def _activate_search(self, event=None):
        """Focuses the search entry and selects its text when Ctrl+F is pressed."""
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)
        return "break" # Prevents default Tkinter behavior

    def _clear_search_highlight(self):
        """Clears all search highlighting and resets the search state."""
        self.console.tag_remove("search_highlight", "1.0", tk.END)
        self.search_start_index = "1.0"
        self.current_search_term = ""
        self.search_entry.delete(0, tk.END) # Clear the entry box
        self.search_entry.focus_set()

    def _search_console(self, event=None):
        """Searches for the term in the console text, highlighting the next match."""
        query = self.search_entry.get()
        
        if not query:
            self._clear_search_highlight()
            return
            
        # If the search term has changed, clear highlights and restart from the beginning
        if query != self.current_search_term:
            self.current_search_term = query
            self.search_start_index = "1.0"
            self.console.tag_remove("search_highlight", "1.0", tk.END)
        
        # Define the highlight tag if it doesn't exist
        self.console.tag_config("search_highlight", background="#4d4d00", foreground="white") # Dark yellow background

        # Search from the last found position
        idx = self.console.search(query, self.search_start_index, stopindex=tk.END, nocase=1) # nocase=1 makes it case-insensitive

        if idx:
            # Match found
            self.console.tag_remove("search_highlight", "1.0", tk.END) # Clear old highlight
            
            end_idx = f"{idx} + {len(query)}c"
            
            # Apply highlight to the new match
            self.console.tag_add("search_highlight", idx, end_idx)
            
            # Scroll to make the match visible and center it
            self.console.see(idx)
            
            # Update the starting point for the next search
            self.search_start_index = end_idx
            
            # Check if we reached the end and wrap around
            if self.search_start_index == self.console.index(tk.END):
                self.search_start_index = "1.0"
                
        elif self.search_start_index != "1.0":
            # No match found from the current position to the end, wrap around and search from the start
            self.search_start_index = "1.0"
            self._search_console() # Recursive call to search from the beginning
            
        else:
            # If search is already at "1.0" and no match is found, signal failure (e.g., beep or message)
            print(f"Search term '{query}' not found.")
            self.search_start_index = "1.0" # Keep it at the start for next attempt

    def jump_to_class(self, event):
        if not self.class_listbox.curselection():
            return

        name = self.class_listbox.get(self.class_listbox.curselection()[0])
        
        # Check if the name exists and has all values
        if name not in self.class_bookmarks or len(self.class_bookmarks[name]) < 3:
            return

        # Unpack: x, y for graph canvas, text_line for code console
        x, y, text_line = self.class_bookmarks[name] 

        # --- 1. Canvas Scroll (Center the node) ---
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        # Calculate scroll fraction to center the point
        # (Coordinate - half_screen) / scroll_region_size
        bbox = self.canvas.bbox("all")
        if bbox:
            scroll_w = max(bbox[2] - bbox[0], 1)
            scroll_h = max(bbox[3] - bbox[1], 1)
            # Center X
            self.canvas.xview_moveto((x - (canvas_w/2) - bbox[0]) / scroll_w)
            # Center Y
            self.canvas.yview_moveto((y - (canvas_h/2) - bbox[1]) / scroll_h)

        # Flash highlight on Canvas
        self.canvas.create_oval(x-40, y-40, x+40, y+40,
                                outline="red", width=3,
                                tags="flash")
        self.after(600, lambda: self.canvas.delete("flash"))

        # --- 2. Console Scroll (Text Search Result) ---
        self.console.update_idletasks() 
        
        # Remove previous highlights
        self.console.tag_remove("jump_highlight", "1.0", "end") 
        
        # Force the console to show the line at the top
        self.console.see(text_line)
        try:
            # This creates a more precise scroll to put the line at the top
            line_int = int(float(text_line))
            self.console.yview(line_int - 2) # Scroll to 2 lines above target for context
        except:
            pass

        # Highlight the specific line found
        self.console.tag_add("jump_highlight", text_line, f"{text_line} lineend")
        self.console.tag_config("jump_highlight", background="#4a4a00", foreground="white")
        
        # Fade out highlight
        self.after(1500, lambda: self.console.tag_remove("jump_highlight", "1.0", "end"))        
    def print_json(self, data, prefix=""):
        """Pretty-print JSON into the console with syntax highlighting."""
        self.console.config(state="normal")
        self.console.insert("end", prefix + "\n", "bracket")

        pretty = json.dumps(data, indent=4)

        i = 0
        while i < len(pretty):
            ch = pretty[i]

            if ch in "{}[]:,":
                self.console.insert("end", ch, "bracket")
                i += 1
                continue

            if ch == '"':  # string (either key or value)
                j = i + 1
                while j < len(pretty) and pretty[j] != '"':
                    j += 1
                j += 1

                text = pretty[i:j]

                if ":" in pretty[j:j+3]:  # heuristic → key
                    tag = "key"
                else:
                    tag = "string"

                self.console.insert("end", text, tag)
                i = j
                continue

            if ch.isdigit() or (ch == "-" and pretty[i+1].isdigit()):
                j = i + 1
                while j < len(pretty) and (pretty[j].isdigit() or pretty[j] == "."):
                    j += 1
                self.console.insert("end", pretty[i:j], "number")
                i = j
                continue

            if pretty.startswith("true", i) or pretty.startswith("false", i):
                val = "true" if pretty.startswith("true", i) else "false"
                self.console.insert("end", val, "bool")
                i += len(val)
                continue

            if pretty.startswith("null", i):
                self.console.insert("end", "null", "null")
                i += 4
                continue

            self.console.insert("end", ch)
            i += 1

        self.console.insert("end", "\n\n")
        self.console.config(state="disabled")
        self.console.see("end")

    def clean_node_name(self, full_name):
        if full_name.startswith("FILE__"):
            return full_name[6:]
        if full_name.startswith("DYNAMIC_DATA__DESC_"):
            label = full_name[20:].replace('__', ' ').replace('_', '').replace(' ', '')
            display_label = label.replace("MAPFILE", "<MAP_FILE>").replace("DYNAMICARGUMENT", "<DYNAMIC_ARGUMENT>")
            display_label = display_label.replace("DYNAMICPART", "<DYNAMIC_PART>").replace("CALLRESULT", "<CALL_RESULT>")
            return display_label
        if self.project_name and full_name.startswith(self.project_name + "."):
            return full_name[len(self.project_name)+1:]
        return full_name

    def _colorize_python_content(self, content, start_index="1.0"):
        """Applies syntax highlighting to the Python code content."""
        
        # Python keywords and builtins list (Keep these at the start)
        KEYWORDS = ['for', 'in', 'if', 'else', 'elif', 'while', 'break', 'continue', 'return', 
                    'def', 'class', 'import', 'from', 'as', 'try', 'except', 'finally', 
                    'with', 'del', 'pass', 'yield', 'global', 'nonlocal', 'lambda', 'and', 'or', 'not',
                    'is', 'None', 'True', 'False']
        BUILTINS = ['print', 'len', 'range', 'list', 'dict', 'set', 'tuple', 'open', 'int', 'str', 'float']
        
        # Insert the text
        self.console.insert(start_index, content)
        end_of_content = tk.END 
        
        # Clear old content tags only from the area we are colorizing
        self.console.tag_remove('comment', start_index, end_of_content)
        self.console.tag_remove('python_string', start_index, end_of_content)
        self.console.tag_remove('keyword', start_index, end_of_content) # Clear keyword tags
        self.console.tag_remove('builtin', start_index, end_of_content) # Clear builtin tags
        self.console.tag_remove('definition', start_index, end_of_content) # Clear definition tags
        self.console.tag_remove('number', start_index, end_of_content) # Clear number tags
        
        # --- 1. COMMENTS (HIGHEST PRIORITY - Must run first) ---
        start = start_index 
        while True:
            # Find the start of a comment
            comment_start = self.console.search(r'#', start, stopindex=end_of_content, regexp=True, nocase=True)
            if comment_start:
                # Find end of the line
                line_end = self.console.search(r'\n', comment_start, stopindex=end_of_content, regexp=True)
                if not line_end:
                    line_end = end_of_content
                
                self.console.tag_add('comment', comment_start, line_end)
                start = line_end # Continue search from the next line
                continue
            break
            
        # --- 2. STRINGS (Manual check to respect comments) ---
        
        # Single-quote strings
        start = start_index 
        while True:
            string_start = self.console.search(r'\'', start, stopindex=end_of_content, regexp=True)
            
            if string_start:
                # Manual Check: If the quote is already tagged as a 'comment', skip it.
                if 'comment' in self.console.tag_names(string_start):
                    start = f'{string_start}+1c' # Move past the quote and continue search
                    continue
                
                # If we reach here, it's a valid string start. Find the closing quote.
                string_end = self.console.search(r'\'', f'{string_start}+1c', stopindex=end_of_content, regexp=True)
                
                if string_end:
                    self.console.tag_add('python_string', string_start, f'{string_end}+1c')
                    start = f'{string_end}+1c'
                    continue
                else:
                    # Handle unclosed string at the end of content
                    start = f'{string_start}+1c' 
            break

        # Double-quote strings
        start = start_index
        while True:
            string_start = self.console.search(r'"', start, stopindex=end_of_content, regexp=True)
            
            if string_start:
                # Manual Check: If the quote is already tagged as a 'comment', skip it.
                if 'comment' in self.console.tag_names(string_start):
                    start = f'{string_start}+1c'
                    continue

                # Find the closing double-quote.
                string_end = self.console.search(r'"', f'{string_start}+1c', stopindex=end_of_content, regexp=True)
                if string_end:
                    self.console.tag_add('python_string', string_start, f'{string_end}+1c')
                    start = f'{string_end}+1c'
                    continue
                else:
                    # Handle unclosed string at the end of content
                    start = f'{string_start}+1c'
            break
            
        # 3. KEYWORDS and BUILTINS (Using word boundaries)
        tags_to_check = ['comment', 'python_string'] # Tags that keywords/builtins cannot overlap

        for keyword in KEYWORDS:
            tag_start = start_index
            while True:
                # Search for the keyword
                tag_start = self.console.search(r'\y' + keyword + r'\y', tag_start, stopindex=end_of_content, regexp=True, nocase=True)
                
                if tag_start:
                    # Manual Check: Check if the keyword is inside a comment or string
                    current_tags = self.console.tag_names(tag_start)
                    if any(t in current_tags for t in tags_to_check):
                        tag_start = f'{tag_start}+1c' # Move past the first character and search again
                        continue
                        
                    keyword_length = len(keyword)
                    tag_end = f"{tag_start} + {keyword_length}c"
                    self.console.tag_add('keyword', tag_start, tag_end)
                    tag_start = tag_end # Continue search from after the match
                else:
                    break
        
        for builtin in BUILTINS:
            tag_start = start_index
            while True:
                tag_start = self.console.search(r'\y' + builtin + r'\y', tag_start, stopindex=end_of_content, regexp=True, nocase=True)
                
                if tag_start:
                    # Manual Check: Check if the builtin is inside a comment or string
                    current_tags = self.console.tag_names(tag_start)
                    if any(t in current_tags for t in tags_to_check):
                        tag_start = f'{tag_start}+1c'
                        continue
                        
                    tag_end = f"{tag_start} + {len(builtin)}c"
                    self.console.tag_add('builtin', tag_start, tag_end)
                    tag_start = tag_end
                else:
                    break

        # 4. CLASS/DEF NAMES (Look for name following 'class ' or 'def ')
        def _highlight_name(key_word, tag):
            search_start = start_index
            while True:
                key_start = self.console.search(r'\y' + key_word + r'\y', search_start, stopindex=end_of_content, regexp=True)
                if not key_start: break
                
                # Manual Check: Check if the keyword is inside a comment or string
                current_tags = self.console.tag_names(key_start)
                if any(t in current_tags for t in tags_to_check):
                    search_start = f'{key_start}+1c'
                    continue

                # Start searching for the name immediately after the keyword + space
                name_start = f'{key_start} + {len(key_word) + 1}c'
                
                # The name ends at the first non-word character or parenthesis/colon
                name_end_index = self.console.search(r'[\s(:]', name_start, stopindex=end_of_content, regexp=True)
                if name_end_index:
                    self.console.tag_add(tag, name_start, name_end_index)
                    search_start = name_end_index # Continue search from after the name
                else:
                    search_start = f'{key_start} + 1c' # Move past the keyword if name not found

        _highlight_name('class', 'definition')
        _highlight_name('def', 'definition')

        # 5. NUMBERS (Simple number highlighting)
        start = start_index
        while True:
            # Look for number pattern: optional hyphen, then digits, optional decimal point and digits
            match_start = self.console.search(r'[-]?\b\d+(\.\d*)?\b', start, stopindex=end_of_content, regexp=True)
            if not match_start:
                break
            
            # Manual Check: Check if the number is inside a comment or string
            current_tags = self.console.tag_names(match_start)
            if any(t in current_tags for t in tags_to_check):
                start = f'{match_start}+1c'
                continue

            # Calculate end of match (This is still a bit complex, but let's stick to your method for now)
            end_match = self.console.search(r'[^\d.]', match_start, stopindex=end_of_content, regexp=True)
            
            if end_match:
                # Get the actual matched string to find its length
                matched_string = self.console.get(match_start, end_match).strip()
                match_end = f'{match_start} + {len(matched_string)}c'
            else:
                match_end = tk.END
            
            self.console.tag_add('number', match_start, match_end)
            start = match_end

    def _display_raw_file_content(self, path):
        """Reads the content of the file, colorizes it, and displays it in self.console."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.console.config(state="normal")
            self.console.delete("1.0", tk.END) # Clear any previous content
            
            header = f"=== Source Code: {os.path.basename(path)} ===\n\n"
            self.console.insert(tk.END, header, "header_tag")
            
            # Insert the content and immediately colorize it
            self._colorize_python_content(content) 
            
            self.console.config(state="disabled")
            self.console.see("1.0") # Scroll to the top
            
        except Exception as e:
            self.console.config(state="normal")
            self.console.delete("1.0", tk.END)
            self.console.insert(tk.END, f"[ERROR] Could not read file {path}: {e}")
            self.console.config(state="disabled")

            
    def load_path(self):
        # 1. Open the file dialog, restricted to Python files first
        path = filedialog.askopenfilename(filetypes=[("Python files", "*.py"), ("All files", "*.*")])
        
        # 2. If the user cancels the file dialog, try the directory dialog
        if not path: 
            path = filedialog.askdirectory()
            
        if not path: 
            return
        
        self.title(f"Visualizer - {os.path.basename(path)}")

        # --- CONSOLE MANAGEMENT: Clear everything ---
        # The _display_raw_file_content function will handle the clearing if it runs.
        # If it doesn't run, we must still clear any previous content.
        self.console.config(state="normal")
        self.console.delete("1.0", tk.END)
        self.console.config(state="disabled")

        # --- RAW CODE DISPLAY ---
        if os.path.isfile(path) and path.endswith(".py"):
            self._display_raw_file_content(path)
        
        # --- GRAPH ANALYSIS LOGIC ---
        results = scan_path_for_structure(path)
        
        if len(results) == 5:
            # Structure analysis was successful
            self.structure_graph, self.dependencies, self.source_map, self.data_file_nodes, self.data_callers = results
            
            if self.structure_graph:
                self.project_name = list(self.structure_graph.keys())[0].split('.')[0]
            else:
                self.project_name = ""
                
            self.draw_graph()

            # -----------------------------------------------------------------
            # !!! REMOVE THESE LINES TO STOP PRINTING JSON TO THE MAIN EDITOR !!!
            # -----------------------------------------------------------------
            # self.print_json(self.structure_graph, prefix="\n\n=== Structure Graph ===")
            # self.print_json(self.dependencies, prefix="=== Dependencies ===")
            # self.print_json(list(self.data_file_nodes), prefix="=== Data Files ===")
            
            # OPTIONAL: Keep the JSON printing but redirect it to a dedicated log/debug file or separate widget
            # For now, just remove them to solve the core problem.
        
    def draw_graph(self):
        self.canvas.delete("all")
        visibility_flags = {
            "function": self.show_funcs_var.get(),
            "method": self.show_methods_var.get(),
            "data": self.show_files_var.get(), # 'data' corresponds to files (blue)
            "dynamic_data": self.show_dynamic_var.get(), # 'dynamic_data' corresponds to dynamic args (yellow)
        }

        self.class_listbox.delete(0, tk.END)
        self.class_bookmarks = {}

        results = get_layout_data(self.structure_graph, self.dependencies, self.data_file_nodes, visibility_flags)

        if not results: return
        self.layout_nodes, self.layout_edges, self.node_type_map, self.safe_id_map = results
        for e in self.layout_edges:
            edge_tag = f"edge__{e['tail']}__{e['head']}"
            line_points = [coord for pt in e["points"][:-1] for coord in pt]
            real_tail = self.safe_id_map.get(e["tail"], e["tail"])
            real_head = self.safe_id_map.get(e["head"], e["head"])
            head_ntype = self.node_type_map.get(real_head, "unknown")
            type_tag = "edge_unknown"
            if head_ntype == "data": type_tag = "edge_to_file"          
            elif head_ntype == "dynamic_data": type_tag = "edge_to_dynamic" 
            elif head_ntype == "function": type_tag = "edge_to_func"
            elif head_ntype == "method": type_tag = "edge_to_method"
            edge_kind = "unknown"
            for module_deps in self.dependencies.values():
                for src, dst, kind in module_deps:
                    if src == real_tail and dst == real_head:
                        edge_kind = kind
                        break
                if edge_kind != "unknown": break
            if edge_kind == "data":
                edge_color = COLOR_PALETTE["dynamic_data"]["border"] if head_ntype == "dynamic_data" else COLOR_PALETTE["data"]["border"]
                width = 2
            elif edge_kind == "inherit":
                edge_color = "#aa33aa"
                width = 1
            else: 
                edge_color = COLOR_PALETTE["edge"]["fill"]
                width = 1
            self.canvas.create_line(line_points, fill=edge_color, width=width, smooth=True, 
                                    tags=(edge_tag, "edge", type_tag)) 
            if len(e["points"]) >= 2:
                p2x, p2y = e["points"][-1]
                p1x, p1y = e["points"][-2]
                angle = math.atan2(p2y - p1y, p2x - p1x)
                tip_x, tip_y = p2x, p2y
                if edge_kind == "data":
                    r = 3
                    self.canvas.create_oval(tip_x-r, tip_y-r, tip_x+r, tip_y+r, 
                                            fill=edge_color, outline=edge_color, 
                                            tags=(edge_tag, "edge", type_tag)) 
                else:
                    arrow_length = 8
                    base1_x = tip_x - arrow_length * math.cos(angle - 0.5)
                    base1_y = tip_y - arrow_length * math.sin(angle - 0.5)
                    base2_x = tip_x - arrow_length * math.cos(angle + 0.5)
                    base2_y = tip_y - arrow_length * math.sin(angle + 0.5)
                    self.canvas.create_polygon(tip_x, tip_y, base1_x, base1_y, base2_x, base2_y, 
                                               fill=edge_color, outline=edge_color, 
                                               tags=(edge_tag, "edge", type_tag)) 
            src_name = self.clean_node_name(real_tail) 
            dst_name = self.clean_node_name(real_head) 
            edge_text = f"Source: {src_name}\nTarget: {dst_name}\nType: {edge_kind.upper()}"
            self.canvas.tag_bind(edge_tag, "<Enter>", lambda event, t=edge_tag, txt=edge_text, c=edge_color: self.show_edge_tooltip(event, t, txt, c))

            self.canvas.tag_bind(edge_tag, "<Leave>", lambda event, t=edge_tag, c=edge_color: self.hide_edge_tooltip(t, c))

        for n in self.layout_nodes:
            real_id = self.safe_id_map.get(n["id"], n["id"])
            ntype = self.node_type_map.get(real_id, "unknown")
            
            # --- CLASS BOOKMARK CAPTURE ---
            if ntype == "class":
                clean = self.clean_node_name(real_id)
                self.class_listbox.insert(tk.END, clean)
                
                # *** IMPORTANT ASSUMPTION/PLACEHOLDER ***
                # We need the starting line number of the class definition.
                # In a real scenario, this information would be generated by your
                # 'scan_path_for_structure' function and stored in 'self.source_map'
                # or a separate map. I'll use 1.0 as a placeholder line number.
                # Line numbers in Text widgets are 'line.char', so we use '1.0' for line 1, col 0.
                text_line_start = self.get_class_line_number(real_id) # Call a new helper method
                
                # Store (canvas_x, canvas_y, text_line_start)
                self.class_bookmarks[clean] = (n["x"], n["y"], text_line_start)
            # --------------------------------

            
            color_scheme = COLOR_PALETTE.get(ntype, {"fill": "#ffffff", "border": "#000000"})
            x, y, w, h = n["x"], n["y"], n["w"], n["h"]
            x0, y0 = x - w/2, y - h/2
            x1, y1 = x + w/2, y + h/2
            dash = (3, 3) if ntype == "group" else None
            width = 2 if ntype in ["module", "data", "dynamic_data"] else 1 
            font = ("Arial", 10, "bold") if ntype in ["module", "group", "data", "dynamic_data"] else ("Arial", 8)
            group_tag = f"node__{real_id}"
            rect_tag = f"rect__{real_id}" 
            self.canvas.create_rectangle(x0, y0, x1, y1,
                                         fill=color_scheme["fill"],
                                         outline=color_scheme["border"],
                                         width=width, dash=dash, 
                                         tags=(group_tag, rect_tag, ntype)) 
            self.canvas.create_text(x, y, text=n["label"], font=font, tags=(group_tag, ntype))
            self.canvas.tag_bind(group_tag, "<Button-1>", lambda e, nid=real_id: self.toggle_node(nid))
            if ntype in ["data", "dynamic_data"]:
                self.canvas.tag_bind(group_tag, "<Enter>", lambda e, nid=real_id, rt=rect_tag: self.show_data_node_info(e, nid, rt))
                self.canvas.tag_bind(group_tag, "<Leave>", lambda e, rt=rect_tag, w=width: self.hide_data_node_info(rt, w))
            else:
                self.canvas.tag_bind(group_tag, "<Enter>", lambda e, nid=real_id, rt=rect_tag: self.show_node_code(e, nid, rt))
                self.canvas.tag_bind(group_tag, "<Leave>", lambda e, rt=rect_tag, c=color_scheme["fill"], w=width: self.hide_node_code(rt, c, w))
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self.reset_view()

    def get_class_line_number(self, node_id):
        """
        Searches the console text for the definition of the class/function.
        Returns the text index (e.g., '45.0') if found, otherwise '1.0'.
        """
        # 1. Extract the simple name (e.g., 'module.Simulation' -> 'Simulation')
        short_name = node_id.split(".")[-1]

        # 2. Define patterns to look for. 
        # We assume standard Python syntax: "class Name" or "def Name"
        search_patterns = [
            f"class {short_name}", 
            f"def {short_name}"
        ]

        # 3. Search the actual text widget content
        start_pos = "1.0"
        for pattern in search_patterns:
            # .search returns an index string (row.col) or empty string if not found
            found_pos = self.console.search(pattern, start_pos, stopindex=tk.END)
            if found_pos:
                return found_pos
        
        # If not found, look for just the name (less accurate, but a backup)
        found_pos = self.console.search(short_name, start_pos, stopindex=tk.END)
        if found_pos:
            return found_pos

        return "1.0"
    
    def show_data_node_info(self, event, node_id, rect_tag):
        self.canvas.itemconfig(rect_tag, width=3)
        if node_id.startswith("DYNAMIC_DATA__DESC_"):
            caller_id = self.data_callers.get(node_id)
            if caller_id:
                code = self.source_map.get(caller_id)
                header = f"Code block relying on data: {self.clean_node_name(caller_id)}\n{'-'*50}\n"
            else:
                code = "Code definition not found."
                header = f"DYNAMIC DATA: {self.clean_node_name(node_id)}\n{'-'*50}\n"
        elif node_id.startswith("FILE__"):
            path = node_id[6:]
            code = f"File Path: {path}"
            header = f"STATIC FILE DEPENDENCY\n{'-'*50}\n"
        else:
            return
        lines = (header + code).splitlines()
        if len(lines) > 20: lines = lines[:20] + ["... (truncated)"]
        clean_code = "\n".join(lines)
        self.tooltip.config(text=clean_code)
        self.tooltip.place(x=event.x_root + 1000, y=event.y_root + 12)
        self.tooltip.lift()
    def safe_place_tooltip(self, x, y):
        self.tooltip.update_idletasks()
        tip_w = self.tooltip.winfo_width()
        tip_h = self.tooltip.winfo_height()
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if x + tip_w > canvas_w:
            x = x - tip_w + 1000
        if y + tip_h > canvas_h:
            y = y - tip_h - 20
        self.tooltip.place(x=x, y=y)
    def hide_data_node_info(self, rect_tag, original_width):
        self.canvas.itemconfig(rect_tag, width=original_width)
        self.tooltip.place_forget()
    def show_node_code(self, event, node_id, rect_tag):
        self.canvas.itemconfig(rect_tag, fill="#ffff99", width=2)
        code = self.source_map.get(node_id)
        if not code: code = f"(No source code found for {node_id})"
        lines = code.splitlines()
        if len(lines) > 20: lines = lines[:20] + ["... (truncated)"]
        clean_code = "\n".join(lines)
        self.tooltip.config(text=clean_code)
        self.tooltip.place(x=event.x_root - 300, y=event.y_root + 10)
        self.tooltip.lift()
    def hide_node_code(self, rect_tag, original_color, original_width):
        self.canvas.itemconfig(rect_tag, fill=original_color, width=original_width)
        self.tooltip.place_forget()
    def show_edge_tooltip(self, event, tag, text, original_color):
        self.canvas.itemconfig(tag, fill="yellow", width=3)
        self.tooltip.config(text=text)
        self.tooltip.place(x=event.x_root - 300, y=event.y_root + 10)
        self.tooltip.lift()
    def hide_edge_tooltip(self, tag, original_color):
        self.canvas.itemconfig(tag, fill=original_color, width=1)
        self.tooltip.place_forget()
        
    def toggle_node(self, node_id):
        tag = f"node__{node_id}"
        ntype = self.node_type_map.get(node_id, "unknown")
        connected_edges = []
        for e in self.layout_edges:
            real_tail = self.safe_id_map.get(e["tail"], e["tail"])
            real_head = self.safe_id_map.get(e["head"], e["head"])
            if real_tail == node_id or real_head == node_id:
                connected_edges.append(e)
        if node_id in self.hidden_nodes:
            self.canvas.itemconfigure(tag, state="normal")
            if ntype == "class":
                for nid, t in self.node_type_map.items():
                    if t == "method" and nid.startswith(node_id + "."):
                        self.canvas.itemconfigure(f"node__{nid}", state="normal")
            for e in connected_edges:
                edge_tag = f"edge__{e['tail']}__{e['head']}"
                self.canvas.itemconfigure(edge_tag, state="normal")
            del self.hidden_nodes[node_id]
            to_delete = [i for i, real in self.unused_map.items() if real == node_id]
            for i in sorted(to_delete, reverse=True):
                try: self.unused_listbox.delete(i)
                except: pass
                del self.unused_map[i]
            new_map = {}
            for new_i, old_i in enumerate(sorted(self.unused_map.keys())):
                new_map[new_i] = self.unused_map[old_i]
            self.unused_map = new_map
        else:
            self.canvas.itemconfigure(tag, state="hidden")
            if ntype == "class":
                for nid, t in self.node_type_map.items():
                    if t == "method" and nid.startswith(node_id + "."):
                        self.canvas.itemconfigure(f"node__{nid}", state="hidden")
            for e in connected_edges:
                edge_tag = f"edge__{e['tail']}__{e['head']}"
                self.canvas.itemconfigure(edge_tag, state="hidden")
            self.hidden_nodes[node_id] = {"type": ntype}
            pretty = self.clean_node_name(node_id) 
            idx = self.unused_listbox.size()
            self.unused_listbox.insert(tk.END, pretty)
            self.unused_map[idx] = node_id
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def restore_unused_node(self, event):
        selection = self.unused_listbox.curselection()
        if not selection: return
        idx = selection[0]
        real_id = self.unused_map.get(idx)
        if not real_id: return
        if real_id.count(".") >= 2 and not real_id.startswith("FILE__") and not real_id.startswith("DYNAMIC_DATA__"):
            module, cls, method = real_id.split(".", 2)
            class_id = f"{module}.{cls}"
            if class_id in self.hidden_nodes: self.toggle_node(class_id)
            if real_id in self.hidden_nodes: self.toggle_node(real_id)
        else:
            self.toggle_node(real_id)
    def toggle_visibility(self):
        func_state = "normal" if self.show_funcs_var.get() else "hidden"
        self.canvas.itemconfigure("function", state=func_state)      
        self.canvas.itemconfigure("edge_to_func", state=func_state)  
        meth_state = "normal" if self.show_methods_var.get() else "hidden"
        self.canvas.itemconfigure("method", state=meth_state)        
        self.canvas.itemconfigure("edge_to_method", state=meth_state)
        file_state = "normal" if self.show_files_var.get() else "hidden"
        self.canvas.itemconfigure("data", state=file_state)          
        self.canvas.itemconfigure("edge_to_file", state=file_state)  
        dyn_state = "normal" if self.show_dynamic_var.get() else "hidden"
        self.canvas.itemconfigure("dynamic_data", state=dyn_state)      
        self.canvas.itemconfigure("edge_to_dynamic", state=dyn_state)   
    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)
    def do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1) 
    def do_zoom(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        scale = 1.0
        if (getattr(event, 'num', 0) == 5) or (getattr(event, 'delta', 0) < 0): 
            scale = 1/1.05 
        elif (getattr(event, 'num', 0) == 4) or (getattr(event, 'delta', 0) > 0): 
            scale = 1.05 
        self.canvas.scale("all", x, y, scale, scale)
        self.scale *= scale
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    def reset_view(self):
        self.canvas.update_idletasks()
        bbox = self.canvas.bbox("all")
        if not bbox: return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        gw, gh = bbox[2]-bbox[0], bbox[3]-bbox[1]
        if gw == 0 or gh == 0: return
        scale = min(cw/gw, ch/gh) * 0.9
        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        self.canvas.scale("all", cx, cy, 1/self.scale, 1/self.scale) 
        self.scale = 1.0 
        self.canvas.scale("all", cx, cy, scale, scale)
        self.scale = scale
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
if __name__ == "__main__":
    app = NativeGraphViewer()
    app.mainloop()
