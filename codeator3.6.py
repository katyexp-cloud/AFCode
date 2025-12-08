#drag canvas
#zoom ok maybe slow
#hide unhide
#optimized tkinter
#method hiding

import ast
import os
import pydot
import tkinter as tk
from tkinter import filedialog
import math
import re

# ----------------- 0. GLOBAL COLOR PALETTE -----------------
COLOR_PALETTE = {
    "module":   {"fill": "#dae8fc", "border": "#6c8ebf"},  # Light Blue
    "group":    {"fill": "#f5f5f5", "border": "#333333"},  # Light Gray
    "class":    {"fill": "#ffe6cc", "border": "#d79b00"},  # Light Orange
    "method":   {"fill": "#d5e8d4", "border": "#82b366"},  # Light Green
    "function": {"fill": "#f8cecc", "border": "#b85450"},  # Light Red
    "edge":     {"fill": "#999999"}                        # Gray
}

# ----------------- 1. UTILITY: SAFE NODE ID -----------------
def make_safe_id(s: str):
    """Convert any string to a safe Graphviz node ID"""
    return re.sub(r'[^A-Za-z0-9_]', '_', s)

# ----------------- 2. STRUCTURE PARSING -----------------
def extract_structure_from_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=path)
        except Exception:
            return []
    items = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            items.append(("module", node.name, "function"))
        elif isinstance(node, ast.ClassDef):
            items.append(("module", node.name, "class"))
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    items.append((node.name, sub.name, "method"))
    return items

def scan_path_for_structure(path: str):
    graph = {}
    if os.path.isfile(path) and path.endswith(".py"):
        module = os.path.basename(path).replace(".py", "")
        graph[module] = extract_structure_from_file(path)
        return graph
    for dirpath, _, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                full = os.path.join(dirpath, file)
                mod_name = os.path.relpath(full, path).replace(os.sep, ".")[:-3]
                graph[mod_name] = extract_structure_from_file(full)
    return graph

# ----------------- 3. GRAPHVIZ LAYOUT -----------------
def get_layout_data(structure_graph: dict):
    graph = pydot.Dot(graph_type="digraph", rankdir="LR", splines="ortho", concentrate="true", arrowhead="normal")
    inferred_types = {} 
    safe_id_map = {}

    for module, items in structure_graph.items():
        safe_module = make_safe_id(module)
        safe_id_map[safe_module] = module
        # Module node
        style = COLOR_PALETTE["module"]
        graph.add_node(pydot.Node(safe_module, label=module, shape="component", style="filled",
                                  fillcolor=style["fill"], color=style["border"]))
        inferred_types[module] = "module"

        # Top-level functions
        top_funcs = [child for p, child, k in items if p == "module" and k == "function"]
        classes = [child for p, child, k in items if p == "module" and k == "class"]
        methods = [(p, c, k) for p, c, k in items if p != "module"]

        # Functions group
        if top_funcs:
            group_id = f"{module}.__FUNCS__"
            safe_group = make_safe_id(group_id)
            safe_id_map[safe_group] = group_id
            style = COLOR_PALETTE["group"]
            graph.add_node(pydot.Node(safe_group, label="Functions", shape="tab", style="filled",
                                      fillcolor=style["fill"], color=style["border"]))
            graph.add_edge(pydot.Edge(safe_module, safe_group))
            inferred_types[group_id] = "group"

            for func in top_funcs:
                node_id = f"{module}.{func}"
                safe_node = make_safe_id(node_id)
                safe_id_map[safe_node] = node_id
                style = COLOR_PALETTE["function"]
                graph.add_node(pydot.Node(safe_node, label=func, shape="rect", style="filled",
                                          fillcolor=style["fill"], color=style["border"]))
                graph.add_edge(pydot.Edge(safe_group, safe_node))
                inferred_types[node_id] = "function"

        # Classes
        for cls in classes:
            cls_id = f"{module}.{cls}"
            safe_cls = make_safe_id(cls_id)
            safe_id_map[safe_cls] = cls_id
            style = COLOR_PALETTE["class"]
            graph.add_node(pydot.Node(safe_cls, label=cls, shape="rect", style="filled",
                                      fillcolor=style["fill"], color=style["border"]))
            graph.add_edge(pydot.Edge(safe_module, safe_cls))
            inferred_types[cls_id] = "class"

        # Methods
        for parent_cls, method, kind in methods:
            cls_id = f"{module}.{parent_cls}"
            method_id = f"{module}.{parent_cls}.{method}"
            safe_cls = make_safe_id(cls_id)
            safe_method = make_safe_id(method_id)
            safe_id_map[safe_cls] = cls_id
            safe_id_map[safe_method] = method_id

            if cls_id not in inferred_types:
                style = COLOR_PALETTE["class"]
                graph.add_node(pydot.Node(safe_cls, label=parent_cls, shape="rect", style="filled",
                                          fillcolor=style["fill"], color=style["border"]))
                inferred_types[cls_id] = "class"

            style = COLOR_PALETTE["method"]
            graph.add_node(pydot.Node(safe_method, label=method, shape="rect", style="filled",
                                      fillcolor=style["fill"], color=style["border"]))
            graph.add_edge(pydot.Edge(safe_cls, safe_method))
            inferred_types[method_id] = "method"

    try:
        plain_data = graph.create(format="plain").decode("utf-8")
    except Exception as e:
        print(f"Graphviz rendering failed: {e}")
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
            x = float(parts[2]) * dpi
            y = float(parts[3]) * dpi
            y = height_px - y
            w = float(parts[4]) * dpi
            h = float(parts[5]) * dpi
            label = parts[6].strip('"')
            nodes.append({"id": name, "x": x, "y": y, "w": w, "h": h, "label": label})
        elif kind == "edge":
            n_points = int(parts[3])
            points = []
            idx = 4
            for i in range(n_points):
                px = float(parts[idx]) * dpi
                py = float(parts[idx+1]) * dpi
                py = height_px - py
                points.append((px, py))
                idx += 2
            arrow_tip = points[-1] if points else None
            arrow_base = points[-2] if len(points) >= 2 else None
            edges.append({"tail": parts[1], "head": parts[2], "points": points, "arrow_tip": arrow_tip, "arrow_base": arrow_base})
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

        tk.Label(self.sidebar, text="Controls", font=("Arial", 12, "bold"), bg="#f0f0f0").pack(pady=10)
        tk.Button(self.sidebar, text="Open File/Folder", command=self.load_path, bg="white").pack(fill="x", padx=10, pady=5)

        self.show_funcs_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Functions", variable=self.show_funcs_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)
        self.show_methods_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.sidebar, text="Show Methods", variable=self.show_methods_var,
                       command=self.toggle_visibility, bg="#f0f0f0").pack(anchor="w", padx=10)

        tk.Button(self.sidebar, text="Reset View", command=self.reset_view).pack(side="bottom", fill="x", padx=10, pady=20)

        # Inside the __init__ method, after checkboxes:
        tk.Label(self.sidebar, text="Unused Nodes", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(pady=5)
        self.unused_listbox = tk.Listbox(self.sidebar, height=10)
        self.unused_listbox.pack(fill="both", padx=10, pady=5)
        self.unused_listbox.bind("<<ListboxSelect>>", self.restore_unused_node)

        # Track hidden nodes
        self.hidden_nodes = {}  # {node_id: {"type": ntype, "tags": (...) } }


        self.scale = 1.0
        self.structure_graph = {}
        self.node_type_map = {}
        self.layout_nodes = []
        self.layout_edges = []
        self.safe_id_map = {}

        # Bindings
        self.canvas.bind("<ButtonPress-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.do_pan)
        self.canvas.bind("<MouseWheel>", self.do_zoom)
        self.canvas.bind("<Button-4>", self.do_zoom)
        self.canvas.bind("<Button-5>", self.do_zoom)

    def load_path(self):
        path = filedialog.askopenfilename(filetypes=[("Python files", "*.py"), ("All files", "*.*")])
        if not path:
            path = filedialog.askdirectory()
        if not path: return

        self.title(f"Visualizer - {os.path.basename(path)}")
        self.structure_graph = scan_path_for_structure(path)
        self.draw_graph()

    def draw_graph(self):
        self.canvas.delete("all")
        visible_structure = {mod: [item for item in items if self.safe_id_map.get(make_safe_id(f"{mod}.{item[1]}"), f"{mod}.{item[1]}") not in self.hidden_nodes] 
                             for mod, items in self.structure_graph.items()}
        results = get_layout_data(visible_structure)
        if not results: return
        self.layout_nodes, self.layout_edges, self.node_type_map, self.safe_id_map = results

        # Draw edges
        for e in self.layout_edges:
            real_head = self.safe_id_map.get(e["head"], e["head"])
            edge_color = COLOR_PALETTE["edge"]["fill"]
            line_points = [coord for pt in e["points"][:-1] for coord in pt]
            edge_tag = f"edge__{e['tail']}__{e['head']}"
            self.canvas.create_line(line_points, fill=edge_color, width=1, smooth=True, tags=(edge_tag,))

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
                self.canvas.create_polygon(
                    tip_x, tip_y, base1_x, base1_y, base2_x, base2_y,
                    fill=edge_color, outline=edge_color, tags=(edge_tag,)
                )

        # Draw nodes
        for n in self.layout_nodes:
            real_id = self.safe_id_map.get(n["id"], n["id"])
            ntype = self.node_type_map.get(real_id, "unknown")
            color_scheme = COLOR_PALETTE.get(ntype, {"fill": "#ffffff", "border": "#000000"})
            
            x, y, w, h = n["x"], n["y"], n["w"], n["h"]
            x0, y0 = x - w/2, y - h/2
            x1, y1 = x + w/2, y + h/2
            tags = ("node", ntype, real_id)
            dash = (3, 3) if ntype == "group" else None
            width = 2 if ntype == "module" else 1
            font = ("Arial", 10, "bold") if ntype in ["module", "group"] else ("Arial", 8)

            # Replace tuple tags
            tag = f"node__{real_id}"

            rect_id = self.canvas.create_rectangle(x0, y0, x1, y1,
                                                   fill=color_scheme["fill"],
                                                   outline=color_scheme["border"],
                                                   width=width, dash=dash, tags=(tag,))
            text_id = self.canvas.create_text(x, y, text=n["label"], font=font, tags=(tag,))

            # Bind click
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, nid=real_id: self.toggle_node(nid))

            edge_tag = f"edge__{e['tail']}__{e['head']}"
            self.canvas.create_line(line_points, fill=edge_color, width=1, smooth=True, tags=(edge_tag,))


        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self.reset_view()


        
    def toggle_node(self, node_id):
        tag = f"node__{node_id}"
        ntype = self.node_type_map.get(node_id, "unknown")

        # Collect all edges connected to this node
        connected_edges = []
        for e in self.layout_edges:
            if (self.safe_id_map.get(e['tail'], e['tail']) == node_id or
                self.safe_id_map.get(e['head'], e['head']) == node_id):
                connected_edges.append(e)

        if node_id in self.hidden_nodes:
            # Restore nodes
            self.canvas.itemconfigure(tag, state="normal")
            # Restore methods
            if ntype == "class":
                for nid, t in self.node_type_map.items():
                    if t == "method" and nid.startswith(node_id + "."):
                        self.canvas.itemconfigure(f"node__{nid}", state="normal")
            # Restore connected edges
            for e in connected_edges:
                edge_tag = f"edge__{e['tail']}__{e['head']}"
                self.canvas.itemconfigure(edge_tag, state="normal")
            del self.hidden_nodes[node_id]
            # Remove from listbox
            idxs = [i for i, v in enumerate(self.unused_listbox.get(0, tk.END)) if v == node_id]
            for i in idxs[::-1]:
                self.unused_listbox.delete(i)
        else:
            # Hide nodes
            self.canvas.itemconfigure(tag, state="hidden")
            if ntype == "class":
                for nid, t in self.node_type_map.items():
                    if t == "method" and nid.startswith(node_id + "."):
                        self.canvas.itemconfigure(f"node__{nid}", state="hidden")
            # Hide connected edges
            for e in connected_edges:
                edge_tag = f"edge__{e['tail']}__{e['head']}"
                self.canvas.itemconfigure(edge_tag, state="hidden")
            self.hidden_nodes[node_id] = {"type": ntype}
            self.unused_listbox.insert(tk.END, node_id)

        # Shrink & recenter graph after hiding/restoring
        self.reset_view()



    def restore_unused_node(self, event):
        """Triggered when clicking on an item in the unused listbox"""
        selection = self.unused_listbox.curselection()
        if not selection: return
        node_id = self.unused_listbox.get(selection[0])
        self.toggle_node(node_id)

    def toggle_visibility(self):
        func_state = "normal" if self.show_funcs_var.get() else "hidden"
        self.canvas.itemconfigure("function", state=func_state)
        self.canvas.itemconfigure("to_function", state=func_state)

        meth_state = "normal" if self.show_methods_var.get() else "hidden"
        self.canvas.itemconfigure("method", state=meth_state)
        self.canvas.itemconfigure("to_method", state=meth_state)

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)
    def do_pan(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)
    def do_zoom(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        scale = 1.0
        if (getattr(event, 'num', 0) == 5) or (getattr(event, 'delta', 0) < 0):
            scale = 0.9
        elif (getattr(event, 'num', 0) == 4) or (getattr(event, 'delta', 0) > 0):
            scale = 1.1
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
