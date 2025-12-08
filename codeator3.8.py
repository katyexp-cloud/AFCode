#drag canvas
#zoom ok maybe slow
#hide unhide
#optimized tkinter
#method hiding
#connect everything
#hover everything

import ast
import os
import pydot
import tkinter as tk
from tkinter import filedialog
import math
import re

# ----------------- 0. GLOBAL COLOR PALETTE -----------------
COLOR_PALETTE = {
    "module":   {"fill": "#dae8fc", "border": "#6c8ebf"},
    "group":    {"fill": "#f5f5f5", "border": "#333333"},
    "class":    {"fill": "#ffe6cc", "border": "#d79b00"},
    "method":   {"fill": "#d5e8d4", "border": "#82b366"},
    "function": {"fill": "#f8cecc", "border": "#b85450"},
    "edge":     {"fill": "#999999"}
}

# ----------------- 1. UTILITY: SAFE NODE ID -----------------
def make_safe_id(s: str):
    return re.sub(r'[^A-Za-z0-9_]', '_', s)

# ----------------- 2. STRUCTURE PARSING -----------------
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

    if os.path.isfile(path) and path.endswith(".py"):
        module = os.path.basename(path).replace(".py", "")
        structure, sources = extract_structure_from_file(path)
        graph[module] = structure
        master_sources.update(sources)
        deps[module] = extract_dependencies_from_file(path, module)
        return graph, deps, master_sources

    for dirpath, _, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                full = os.path.join(dirpath, file)
                mod_name = os.path.relpath(full, path).replace(os.sep, ".")[:-3]
                structure, sources = extract_structure_from_file(full)
                
                base_mod = os.path.basename(full).replace(".py", "")
                fixed_sources = {}
                for k, v in sources.items():
                    suffix = k[len(base_mod):]
                    fixed_sources[f"{mod_name}{suffix}"] = v

                graph[mod_name] = structure
                master_sources.update(fixed_sources)
                deps[mod_name] = extract_dependencies_from_file(full, mod_name)

    return graph, deps, master_sources

def extract_dependencies_from_file(path: str, module_name: str):
    deps = []
    with open(path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=path)
        except Exception:
            return deps

    class DependencyVisitor(ast.NodeVisitor):
        def __init__(self):
            self.current_symbol = None
        def visit_FunctionDef(self, node):
            old = self.current_symbol
            self.current_symbol = f"{module_name}.{node.name}"
            self.generic_visit(node)
            self.current_symbol = old
        def visit_ClassDef(self, node):
            for base in node.bases:
                if isinstance(base, ast.Name):
                    deps.append((f"{module_name}.{node.name}", f"{module_name}.{base.id}", "inherit"))
            old = self.current_symbol
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    self.current_symbol = f"{module_name}.{node.name}.{sub.name}"
                    self.generic_visit(sub)
            self.current_symbol = old
        def visit_Call(self, node):
            if not self.current_symbol: return
            if isinstance(node.func, ast.Name):
                deps.append((self.current_symbol, f"{module_name}.{node.func.id}", "call"))
            if isinstance(node.func, ast.Attribute):
                deps.append((self.current_symbol, f"{module_name}.{node.func.attr}", "call"))
            self.generic_visit(node)

    DependencyVisitor().visit(tree)
    return deps

# ----------------- 3. GRAPHVIZ LAYOUT -----------------
def get_layout_data(structure_graph: dict, deps: dict):
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

        if top_funcs:
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

    for module, edge_list in deps.items():
        for src, dst, kind in edge_list:
            safe_src = make_safe_id(src)
            safe_dst = make_safe_id(dst)
            if safe_src not in safe_id_map or safe_dst not in safe_id_map: continue
            color = "#888888" if kind == "call" else "#aa33aa"
            style = "solid" if kind == "call" else "dashed"
            graph.add_edge(pydot.Edge(safe_src, safe_dst, color=color, style=style, arrowhead="vee"))

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

# ----------------- 4. TKINTER VISUALIZER -----------------
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

        tk.Label(self.sidebar, text="Controls", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=10)
        tk.Button(self.sidebar, text="Open File/Folder", command=self.load_path, bg="white").pack(fill="x", padx=10, pady=5)

        self.show_funcs_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Functions", variable=self.show_funcs_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)
        self.show_methods_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Methods", variable=self.show_methods_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)

        tk.Button(self.sidebar, text="Reset View", command=self.reset_view).pack(side="bottom", fill="x", padx=10, pady=20)
        
        tk.Label(self.sidebar, text="Unused Nodes", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=5)
        self.unused_listbox = tk.Listbox(self.sidebar, height=10)
        self.unused_listbox.pack(fill="both", padx=10, pady=5)
        self.unused_listbox.bind("<<ListboxSelect>>", self.restore_unused_node)

        self.hidden_nodes = {}  
        self.unused_map = {}    
        self.scale = 1.0
        self.structure_graph = {}
        self.node_type_map = {}
        self.layout_nodes = []
        self.layout_edges = []
        self.safe_id_map = {}
        self.source_map = {}

        self.canvas.bind("<ButtonPress-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.do_pan)
        self.canvas.bind("<MouseWheel>", self.do_zoom)
        self.canvas.bind("<Button-4>", self.do_zoom)
        self.canvas.bind("<Button-5>", self.do_zoom)
        
    def load_path(self):
        path = filedialog.askopenfilename(filetypes=[("Python files", "*.py"), ("All files", "*.*")])
        if not path: path = filedialog.askdirectory()
        if not path: return
        self.title(f"Visualizer - {os.path.basename(path)}")
        self.structure_graph, self.dependencies, self.source_map = scan_path_for_structure(path)
        self.draw_graph()

    def draw_graph(self):
        self.canvas.delete("all")
        visible_structure = {mod: [item for item in items if self.safe_id_map.get(make_safe_id(f"{mod}.{item[1]}"), f"{mod}.{item[1]}") not in self.hidden_nodes] 
                             for mod, items in self.structure_graph.items()}
        results = get_layout_data(visible_structure, self.dependencies)
        if not results: return
        self.layout_nodes, self.layout_edges, self.node_type_map, self.safe_id_map = results

        # --- PREPARE NAME CLEANER ---
        if self.structure_graph:
            project_name = list(self.structure_graph.keys())[0]
        else:
            project_name = ""

        def clean_name(full_name):
            if full_name.startswith(project_name + "."):
                return full_name[len(project_name)+1:]
            return full_name

        # --- DRAW EDGES ---
        for e in self.layout_edges:
            edge_tag = f"edge__{e['tail']}__{e['head']}"
            line_points = [coord for pt in e["points"][:-1] for coord in pt]
            edge_color = COLOR_PALETTE["edge"]["fill"]
            
            # Draw line
            self.canvas.create_line(line_points, fill=edge_color, width=1, smooth=True, tags=(edge_tag,))
            
            # Draw Arrow
            if len(e["points"]) >= 2:
                p2x, p2y = e["points"][-1]
                p1x, p1y = e["points"][-2]
                angle = math.atan2(p2y - p1y, p2x - p1x)
                arrow_length = 8
                tip_x, tip_y = p2x, p2y
                base1_x = tip_x - arrow_length * math.cos(angle - 0.5)
                base1_y = tip_y - arrow_length * math.sin(angle - 0.5)
                base2_x = tip_x - arrow_length * math.cos(angle + 0.5)
                base2_y = tip_y - arrow_length * math.sin(angle + 0.5)
                self.canvas.create_polygon(tip_x, tip_y, base1_x, base1_y, base2_x, base2_y, fill=edge_color, outline=edge_color, tags=(edge_tag,))

            # --- RESTORED EDGE HOVER ---
            src_name = clean_name(self.safe_id_map.get(e["tail"], e["tail"]))
            dst_name = clean_name(self.safe_id_map.get(e["head"], e["head"]))
            edge_text = f"{src_name} → {dst_name}"

            self.canvas.tag_bind(edge_tag, "<Enter>", lambda event, t=edge_tag, txt=edge_text: self.show_edge_tooltip(event, t, txt))
            self.canvas.tag_bind(edge_tag, "<Leave>", lambda event, t=edge_tag, c=edge_color: self.hide_edge_tooltip(t, c))

        # --- DRAW NODES ---
        for n in self.layout_nodes:
            real_id = self.safe_id_map.get(n["id"], n["id"])
            ntype = self.node_type_map.get(real_id, "unknown")
            color_scheme = COLOR_PALETTE.get(ntype, {"fill": "#ffffff", "border": "#000000"})
            
            x, y, w, h = n["x"], n["y"], n["w"], n["h"]
            x0, y0 = x - w/2, y - h/2
            x1, y1 = x + w/2, y + h/2
            
            dash = (3, 3) if ntype == "group" else None
            width = 2 if ntype == "module" else 1
            font = ("Arial", 10, "bold") if ntype in ["module", "group"] else ("Arial", 8)

            group_tag = f"node__{real_id}"
            rect_tag = f"rect__{real_id}" 

            self.canvas.create_rectangle(x0, y0, x1, y1,
                                         fill=color_scheme["fill"],
                                         outline=color_scheme["border"],
                                         width=width, dash=dash, 
                                         tags=(group_tag, rect_tag))
            
            self.canvas.create_text(x, y, text=n["label"], font=font, tags=(group_tag,))

            self.canvas.tag_bind(group_tag, "<Button-1>", lambda e, nid=real_id: self.toggle_node(nid))
            self.canvas.tag_bind(group_tag, "<Enter>", lambda e, nid=real_id, rt=rect_tag: self.show_node_code(e, nid, rt))
            self.canvas.tag_bind(group_tag, "<Leave>", lambda e, rt=rect_tag, c=color_scheme["fill"]: self.hide_node_code(rt, c))

        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self.reset_view()

    # --- NODE TOOLTIP LOGIC ---
    def show_node_code(self, event, node_id, rect_tag):
        self.canvas.itemconfig(rect_tag, fill="#ffff99", width=2)
        code = self.source_map.get(node_id)
        if not code: code = f"(No source code found for {node_id})"
        lines = code.splitlines()
        if len(lines) > 20: lines = lines[:20] + ["... (truncated)"]
        clean_code = "\n".join(lines)
        self.tooltip.config(text=clean_code)
        self.tooltip.place(x=event.x + 15, y=event.y + 15)
        self.tooltip.lift()

    def hide_node_code(self, rect_tag, original_color):
        self.canvas.itemconfig(rect_tag, fill=original_color, width=1)
        self.tooltip.place_forget()

    # --- EDGE TOOLTIP LOGIC (RESTORED) ---
    def show_edge_tooltip(self, event, tag, text):
        self.canvas.itemconfig(tag, fill="yellow", width=3)
        self.tooltip.config(text=text)
        self.tooltip.place(x=event.x + 10, y=event.y + 10)
        self.tooltip.lift()

    def hide_edge_tooltip(self, tag, original_color):
        self.canvas.itemconfig(tag, fill=original_color, width=1)
        self.tooltip.place_forget()

    # --- HIDE/RESTORE LOGIC ---
    def toggle_node(self, node_id):
        tag = f"node__{node_id}"
        ntype = self.node_type_map.get(node_id, "unknown")
        
        connected_edges = []
        for e in self.layout_edges:
            if (self.safe_id_map.get(e['tail'], e['tail']) == node_id or self.safe_id_map.get(e['head'], e['head']) == node_id):
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
            pretty = node_id.split(".", 1)[1] if "." in node_id else node_id
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
        if real_id.count(".") >= 2:
            module, cls, method = real_id.split(".", 2)
            class_id = f"{module}.{cls}"
            if class_id in self.hidden_nodes: self.toggle_node(class_id)
            if real_id in self.hidden_nodes: self.toggle_node(real_id)
        else:
            self.toggle_node(real_id)

    def toggle_visibility(self):
        func_state = "normal" if self.show_funcs_var.get() else "hidden"
        self.canvas.itemconfigure("function", state=func_state)
        meth_state = "normal" if self.show_methods_var.get() else "hidden"
        self.canvas.itemconfigure("method", state=meth_state)

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)
    def do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
    def do_zoom(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        scale = 1.0
        if (getattr(event, 'num', 0) == 5) or (getattr(event, 'delta', 0) < 0): scale = 0.9
        elif (getattr(event, 'num', 0) == 4) or (getattr(event, 'delta', 0) > 0): scale = 1.1
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
        self.canvas.scale("all", 0, 0, scale, scale)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

if __name__ == "__main__":
    app = NativeGraphViewer()
    app.mainloop()
