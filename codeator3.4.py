import ast
import os
import pydot
import tempfile
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk

#drag canvas
#zoom ok maybe slow

def extract_imports_from_file(path: str):
    imports = []
    with open(path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=path)
        except Exception:
            return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports
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

def build_graphviz_graph(structure_graph: dict):
    graph = pydot.Dot(graph_type="digraph", rankdir="LR",
                      splines="ortho", concentrate="true")

    node_style = {
        "module":   {"shape": "component", "style": "filled",
                     "fillcolor": "#dae8fc", "fontname": "Arial-Bold"},
        "class":    {"shape": "record", "style": "filled",
                     "fillcolor": "#ffe6cc", "fontname": "Arial"},
        "method":   {"shape": "oval", "style": "filled",
                     "fillcolor": "#d5e8d4", "fontname": "Arial", "fontsize": "10"},
        "function": {"shape": "note", "style": "filled",
                     "fillcolor": "#f8cecc", "fontname": "Arial", "fontsize": "10"},
    }

    # ---- MODULE LAYOUT (unchanged) ----
    modules = sorted(list(structure_graph.keys()))
    ITEMS_PER_COLUMN = 5
    columns = [modules[i:i + ITEMS_PER_COLUMN]
               for i in range(0, len(modules), ITEMS_PER_COLUMN)]

    for col_idx, column_modules in enumerate(columns):
        col_sub = pydot.Subgraph(rank="same")
        previous_mod = None

        for mod in column_modules:
            graph.add_node(pydot.Node(mod, **node_style["module"]))
            col_sub.add_node(pydot.Node(mod))

            if previous_mod:
                graph.add_edge(pydot.Edge(previous_mod, mod,
                                          style="invis", weight=5))
            previous_mod = mod

        graph.add_subgraph(col_sub)

        if col_idx > 0:
            prev_top = columns[col_idx-1][0]
            curr_top = column_modules[0]
            graph.add_edge(pydot.Edge(prev_top, curr_top,
                                      style="invis", weight=10))

    # ---- CONTENT (Functions grouping FIXED) ----
    for module, items in structure_graph.items():
        # detect top-level functions
        top_funcs = [child for parent, child, kind in items
                     if parent == "module" and kind == "function"]

        fake_root_id = None

        if top_funcs:
            fake_root_id = f"{module}.__FUNCS__"
            graph.add_node(
                pydot.Node(fake_root_id, label="Functions", **node_style["class"])
            )
            graph.add_edge(pydot.Edge(module, fake_root_id))

        # now add items safely
        for parent, child, kind in items:
            child_id = f"{module}.{child}"
            style = node_style.get(kind, {})
            graph.add_node(pydot.Node(child_id, label=child, **style))

            # correct routing
            if parent == "module":
                if kind == "function" and fake_root_id:
                    graph.add_edge(pydot.Edge(fake_root_id, child_id))
                else:
                    graph.add_edge(pydot.Edge(module, child_id))
            else:
                parent_id = f"{module}.{parent}"
                graph.add_edge(pydot.Edge(parent_id, child_id))

    return graph

def render_graph(graph):
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    graph.write_png(tmp.name)
    return tmp.name

class DependencyViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Dependency Visualizer")

        # --- Canvas fixed size 800x800 ---
        self.canvas = tk.Canvas(self, bg="white", width=800, height=800)  # NEW
        self.canvas.pack()

        self.zoom_factor = 1.0

        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)   
        self.canvas.bind("<Button-5>", self.on_zoom)   

        # --- Menu ---
        menu = tk.Menu(self)
        filemenu = tk.Menu(menu, tearoff=0)
        filemenu.add_command(label="Open File / Folder", command=self.load_path)
        filemenu.add_command(label="Reset Zoom (Fit to Canvas)", command=self.reset_zoom)  # NEW
        menu.add_cascade(label="File", menu=filemenu)
        self.config(menu=menu)

        self.tkimg = None

        # --- Panning support ---
        self.canvas.bind("<ButtonPress-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.do_pan)

    def fit_image_to_canvas(self):
        canvas_w = 800
        canvas_h = 800

        img_w = self.original_image.width
        img_h = self.original_image.height

        # Fit zoom = smallest scale factor
        scale = min(canvas_w / img_w, canvas_h / img_h)

        self.zoom_factor = scale

        # Resize to fit
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)

        self.current_image = self.original_image.resize((new_w, new_h), Image.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(self.current_image)

        self.canvas.delete("all")
        self.canvas.create_image(
            (canvas_w - new_w) // 2,
            (canvas_h - new_h) // 2,
            anchor="nw",
            image=self.tkimg,
            tags="img"
        )

        self.canvas.config(scrollregion=(0, 0, new_w, new_h))

    def start_pan(self, event):
        # Remember where the mouse started
        self.canvas.scan_mark(event.x, event.y)

    def do_pan(self, event):
        # Drag canvas according to mouse movement
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def load_path(self):
        path = filedialog.askopenfilename(
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if not path:
            path = filedialog.askdirectory()
        if not path:
            return
        dep_graph = scan_path_for_structure(path)
        g = build_graphviz_graph(dep_graph)
        img_path = render_graph(g)
        self.display_image(img_path)
        
    def display_image(self, path):
        self.original_image = Image.open(path)

        # Auto-fit on load
        self.fit_image_to_canvas()
        
    def reset_zoom(self):
        if hasattr(self, "original_image"):
            self.fit_image_to_canvas()

        
    def on_zoom(self, event):
        if event.num == 5 or event.delta < 0:
            factor = 0.9
        else:
            factor = 1.1
        new_zoom = self.zoom_factor * factor
        new_zoom = max(0.05, min(50, new_zoom))
        factor = new_zoom / self.zoom_factor
        self.zoom_factor = new_zoom
        mouse_x = self.canvas.canvasx(event.x)
        mouse_y = self.canvas.canvasy(event.y)
        img_x = mouse_x / (self.zoom_factor / factor)
        img_y = mouse_y / (self.zoom_factor / factor)
        w = int(self.original_image.width * self.zoom_factor)
        h = int(self.original_image.height * self.zoom_factor)
        self.current_image = self.original_image.resize((w, h), Image.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(self.current_image)
        self.canvas.delete("img")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=(0, 0, w, h))
        self.canvas.xview_moveto((img_x * self.zoom_factor - event.x) / w)
        self.canvas.yview_moveto((img_y * self.zoom_factor - event.y) / h)
if __name__ == "__main__":
    app = DependencyViewer()
    app.mainloop()
