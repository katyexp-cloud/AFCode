#drag canvas
#zoom ok maybe slow
#hide unhide
#optimized tkinter
#method hiding
#connect everything
#hover everything
#json and periphery

import ast
import os
import pydot
import tkinter as tk
from tkinter import filedialog
import math
import re
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
    
    # 1. ADD MODULES (always shown)
    for module, items in structure_graph.items():
        safe_module = make_safe_id(module)
        safe_id_map[safe_module] = module
        style = COLOR_PALETTE["module"]
        graph.add_node(pydot.Node(safe_module, label=module, shape="component", style="filled", fillcolor=style["fill"], color=style["border"]))
        inferred_types[module] = "module"
        
        top_funcs = [child for p, child, k in items if p == "module" and k == "function"]
        classes = [child for p, child, k in items if p == "module" and k == "class"]
        methods = [(p, c, k) for p, c, k in items if p != "module"]
        
        # 2. ADD TOP-LEVEL FUNCTIONS (Filtered by visibility_flags["function"])
        if top_funcs and visibility_flags["function"]: # <--- NEW CHECK
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
                
        # 3. ADD CLASSES (always shown if present)
        for cls in classes:
            cls_id = f"{module}.{cls}"
            safe_cls = make_safe_id(cls_id)
            safe_id_map[safe_cls] = cls_id
            style = COLOR_PALETTE["class"]
            graph.add_node(pydot.Node(safe_cls, label=cls, shape="rect", style="filled", fillcolor=style["fill"], color=style["border"]))
            graph.add_edge(pydot.Edge(safe_module, safe_cls))
            inferred_types[cls_id] = "class"

        # 4. ADD METHODS (Filtered by visibility_flags["method"])
        for parent_cls, method, kind in methods:
            if not visibility_flags["method"]: continue # <--- NEW CHECK
                
            cls_id = f"{module}.{parent_cls}"
            method_id = f"{module}.{parent_cls}.{method}"
            safe_cls = make_safe_id(cls_id)
            safe_method = make_safe_id(method_id)
            safe_id_map[safe_cls] = cls_id
            safe_id_map[safe_method] = method_id
            
            # (Class node generation logic - unchanged, ensures methods have a class parent)
            if cls_id not in inferred_types:
                style = COLOR_PALETTE["class"]
                graph.add_node(pydot.Node(safe_cls, label=parent_cls, shape="rect", style="filled", fillcolor=style["fill"], color=style["border"]))
                inferred_types[cls_id] = "class"
                
            style = COLOR_PALETTE["method"]
            graph.add_node(pydot.Node(safe_method, label=method, shape="rect", style="filled", fillcolor=style["fill"], color=style["border"]))
            graph.add_edge(pydot.Edge(safe_cls, safe_method))
            inferred_types[method_id] = "method"
            
    # 5. ADD DATA/DYNAMIC DATA NODES (Filtered by visibility_flags["data"] or ["dynamic_data"])
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
            
        # --- NEW CHECKS ---
        if ntype == "data" and not visibility_flags["data"]: continue
        if ntype == "dynamic_data" and not visibility_flags["dynamic_data"]: continue
        # --- END NEW CHECKS ---
            
        safe_id = make_safe_id(file_id)
        safe_id_map[safe_id] = file_id
        style = COLOR_PALETTE[ntype]
        graph.add_node(pydot.Node(safe_id, label=label if ntype == 'data' else display_label, shape=shape, style="filled", fillcolor=style["fill"], color=style["border"]))
        inferred_types[file_id] = ntype

    # 6. ADD EDGES (This is implicitly filtered because edges to non-existent nodes are ignored)
    for module, edge_list in deps.items():
        for src, dst, kind in edge_list:
            safe_src = make_safe_id(src)
            safe_dst = make_safe_id(dst)
            
            # Since we skipped node generation above, the IDs won't be in safe_id_map
            # This check ensures we only try to draw edges to nodes that actually exist in the graph
            if safe_src not in safe_id_map or safe_dst not in safe_id_map: continue 
            
            # ... (Rest of edge styling logic is unchanged)
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
        self.geometry("1200x800")

        self.sidebar = tk.Frame(self, width=200, bg="#f0f0f0")
        self.sidebar.pack(side="right", fill="y")

        self.canvas = tk.Canvas(self, bg="white")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.tooltip = tk.Label(self.canvas, text="", bg="#2e2e2e", fg="#d4d4d4", 
                                font=("Courier New", 9), bd=1, relief="solid", justify="left")
        self.tooltip.place_forget() 

        # --- CONTROLS SECTION ---
        tk.Label(self.sidebar, text="Controls", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=10)
        
        tk.Button(self.sidebar, text="Open File/Folder", command=self.load_path, bg="white").pack(fill="x", padx=10, pady=5)

        # 1. Functions Checkbox
        self.show_funcs_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Functions", variable=self.show_funcs_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)

        # 2. Methods Checkbox
        self.show_methods_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Methods", variable=self.show_methods_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)

        # 3. Files Checkbox (Blue Boxes)
        self.show_files_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Files (Yellow)", variable=self.show_files_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)

        # 4. Dynamic Data Checkbox (Yellow Boxes)
        self.show_dynamic_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Dynamic (Blue)", variable=self.show_dynamic_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)

        tk.Button(self.sidebar, text="Reset View", command=self.reset_view).pack(side="bottom", fill="x", padx=10, pady=20)

        # --- UNUSED NODES SECTION ---
        tk.Label(self.sidebar, text="Unused Nodes", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=5)
        self.unused_listbox = tk.Listbox(self.sidebar, height=10)
        self.unused_listbox.pack(fill="both", padx=10, pady=5)
        self.unused_listbox.bind("<<ListboxSelect>>", self.restore_unused_node)

        # Initialize Data Structures
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

        # Bindings
        self.canvas.bind("<ButtonPress-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.do_pan)
        self.canvas.bind("<MouseWheel>", self.do_zoom) 
        self.canvas.bind("<Button-4>", self.do_zoom) 
        self.canvas.bind("<Button-5>", self.do_zoom)
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
    def load_path(self):
        path = filedialog.askopenfilename(filetypes=[("Python files", "*.py"), ("All files", "*.*")])
        if not path: path = filedialog.askdirectory()
        if not path: return
        self.title(f"Visualizer - {os.path.basename(path)}")
        results = scan_path_for_structure(path)
        if len(results) == 5:
            self.structure_graph, self.dependencies, self.source_map, self.data_file_nodes, self.data_callers = results
        else:
            return
        if self.structure_graph:
            self.project_name = list(self.structure_graph.keys())[0].split('.')[0]
        else:
            self.project_name = ""
        self.draw_graph()
    def draw_graph(self):
        self.canvas.delete("all")

        # 1. Collect visibility states from checkboxes
        visibility_flags = {
            "function": self.show_funcs_var.get(),
            "method": self.show_methods_var.get(),
            "data": self.show_files_var.get(), # 'data' corresponds to files (blue)
            "dynamic_data": self.show_dynamic_var.get(), # 'dynamic_data' corresponds to dynamic args (yellow)
        }
        
        # Note: self.hidden_nodes logic for manual hiding is now skipped here
        # since we are relying on global visibility filtering first.

        # 2. Generate the layout ONLY for visible components
        results = get_layout_data(self.structure_graph, self.dependencies, self.data_file_nodes, visibility_flags)
        
        if not results: return
        self.layout_nodes, self.layout_edges, self.node_type_map, self.safe_id_map = results
        
        
        # --- DRAW EDGES ---
        for e in self.layout_edges:
            edge_tag = f"edge__{e['tail']}__{e['head']}"
            line_points = [coord for pt in e["points"][:-1] for coord in pt]
            
            real_tail = self.safe_id_map.get(e["tail"], e["tail"])
            real_head = self.safe_id_map.get(e["head"], e["head"])
            
            # --- NEW: DETERMINE TARGET TYPE FOR HIDING ---
            head_ntype = self.node_type_map.get(real_head, "unknown")
            
            # Create a specific tag for the edge based on what it connects TO
            type_tag = "edge_unknown"
            if head_ntype == "data": type_tag = "edge_to_file"          # For Blue boxes
            elif head_ntype == "dynamic_data": type_tag = "edge_to_dynamic" # For Yellow boxes
            elif head_ntype == "function": type_tag = "edge_to_func"
            elif head_ntype == "method": type_tag = "edge_to_method"
            
            # ... (Rest of edge color logic) ...
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

            # --- DRAW LINE (Added type_tag) ---
            self.canvas.create_line(line_points, fill=edge_color, width=width, smooth=True, 
                                    tags=(edge_tag, "edge", type_tag)) # <--- Added type_tag here

            # --- DRAW ARROWHEAD/DOT (Added type_tag) ---
            if len(e["points"]) >= 2:
                p2x, p2y = e["points"][-1]
                p1x, p1y = e["points"][-2]
                angle = math.atan2(p2y - p1y, p2x - p1x)
                tip_x, tip_y = p2x, p2y
                
                if edge_kind == "data":
                    r = 3
                    self.canvas.create_oval(tip_x-r, tip_y-r, tip_x+r, tip_y+r, 
                                            fill=edge_color, outline=edge_color, 
                                            tags=(edge_tag, "edge", type_tag)) # <--- Added type_tag here
                else:
                    arrow_length = 8
                    base1_x = tip_x - arrow_length * math.cos(angle - 0.5)
                    base1_y = tip_y - arrow_length * math.sin(angle - 0.5)
                    base2_x = tip_x - arrow_length * math.cos(angle + 0.5)
                    base2_y = tip_y - arrow_length * math.sin(angle + 0.5)
                    self.canvas.create_polygon(tip_x, tip_y, base1_x, base1_y, base2_x, base2_y, 
                                               fill=edge_color, outline=edge_color, 
                                               tags=(edge_tag, "edge", type_tag)) # <--- Added type_tag here

            src_name = self.clean_node_name(real_tail) 
            dst_name = self.clean_node_name(real_head) 
            edge_text = f"Source: {src_name}\nTarget: {dst_name}\nType: {edge_kind.upper()}"
            self.canvas.tag_bind(edge_tag, "<Enter>", lambda event, t=edge_tag, txt=edge_text, c=edge_color: self.show_edge_tooltip(event, t, txt, c))
            self.canvas.tag_bind(edge_tag, "<Leave>", lambda event, t=edge_tag, c=edge_color: self.hide_edge_tooltip(t, c))

        # --- DRAW NODES (Unchanged, just kept for context) ---
        for n in self.layout_nodes:
            real_id = self.safe_id_map.get(n["id"], n["id"])
            ntype = self.node_type_map.get(real_id, "unknown")
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


        #self.tooltip.place(x=self.canvas.canvasx(event.x) + 15, y=self.canvas.canvasy(event.y) + 15)
        self.tooltip.place(x=event.x_root + 1000, y=event.y_root + 12)

        self.tooltip.lift()
            
    def safe_place_tooltip(self, x, y):
        self.tooltip.update_idletasks()
        tip_w = self.tooltip.winfo_width()
        tip_h = self.tooltip.winfo_height()

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        # If tooltip goes too far right, move left
        if x + tip_w > canvas_w:
            x = x - tip_w + 1000

        # If tooltip goes too low, move up
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
        # 1. Functions
        func_state = "normal" if self.show_funcs_var.get() else "hidden"
        self.canvas.itemconfigure("function", state=func_state)      # Hide Nodes
        self.canvas.itemconfigure("edge_to_func", state=func_state)  # Hide Lines

        # 2. Methods
        meth_state = "normal" if self.show_methods_var.get() else "hidden"
        self.canvas.itemconfigure("method", state=meth_state)        # Hide Nodes
        self.canvas.itemconfigure("edge_to_method", state=meth_state)# Hide Lines

        # 3. Files (Blue)
        file_state = "normal" if self.show_files_var.get() else "hidden"
        self.canvas.itemconfigure("data", state=file_state)          # Hide Nodes
        self.canvas.itemconfigure("edge_to_file", state=file_state)  # Hide Lines

        # 4. Dynamic Data (Yellow)
        dyn_state = "normal" if self.show_dynamic_var.get() else "hidden"
        self.canvas.itemconfigure("dynamic_data", state=dyn_state)      # Hide Nodes
        self.canvas.itemconfigure("edge_to_dynamic", state=dyn_state)   # Hide Lines
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
