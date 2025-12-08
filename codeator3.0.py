import ast
import os
import pydot
import tempfile
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk


# =====================================================================
#  Public API – these can be imported by other Python programs
# =====================================================================
def extract_imports_from_file(path: str):
    """Return a list of imported module names inside a Python file."""
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
    """Extract classes, methods, and functions from a Python file."""
    with open(path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=path)
        except Exception:
            return []

    items = []  # (parent, child, type)

    for node in tree.body:
        # -------------------------
        # Top-level functions
        # -------------------------
        if isinstance(node, ast.FunctionDef):
            items.append(("module", node.name, "function"))

        # -------------------------
        # Classes + their methods
        # -------------------------
        elif isinstance(node, ast.ClassDef):
            items.append(("module", node.name, "class"))

            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    items.append((node.name, sub.name, "method"))

    return items

def scan_path_for_structure(path: str):
    """Scan a single file or directory for classes and functions."""
    graph = {}

    # Single file
    if os.path.isfile(path) and path.endswith(".py"):
        module = os.path.basename(path).replace(".py", "")
        graph[module] = extract_structure_from_file(path)
        return graph

    # Directory
    for dirpath, _, files in os.walk(path):
        for file in files:
            if file.endswith(".py"):
                full = os.path.join(dirpath, file)
                mod_name = os.path.relpath(full, path).replace(os.sep, ".")[:-3]
                graph[mod_name] = extract_structure_from_file(full)

    return graph


def build_graphviz_graph(structure_graph: dict):
    """Build UML-like graph without horizontal noodle expansion."""
    graph = pydot.Dot(graph_type="digraph", rankdir="LR")  # left→right, not top→bottom

    modules = list(structure_graph.keys())

    # ---- chunk modules into vertical columns of 5 ----
    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    # rows become columns when rankdir=LR
    for idx, column in enumerate(chunks(modules, 5)):
        col_sub = pydot.Subgraph(
            graph_name=f"cluster_col_{idx}",
            rank="same"   # same vertical level
        )

        for module in column:
            col_sub.add_node(pydot.Node(
                module,
                shape="box",
                style="filled",
                fillcolor="lightblue"
            ))

        graph.add_subgraph(col_sub)

    # ---- add items under each module, vertically ----
    for module, items in structure_graph.items():

        for parent, child, kind in items:
            color = {
                "class": "orange",
                "function": "lightgreen",
                "method": "yellow",
            }.get(kind, "white")

            child_name = f"{module}.{child}"

            graph.add_node(pydot.Node(
                child_name,
                shape="box",
                style="filled",
                fillcolor=color
            ))

            # force vertical stacking inside each module
            graph.add_edge(pydot.Edge(
                f"{module}" if parent == "module" else f"{module}.{parent}",
                child_name,
                constraint="true"
            ))

    return graph



def render_graph(graph):
    """Save graphviz graph to a temporary PNG file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    graph.write_png(tmp.name)
    return tmp.name


# =====================================================================
#  Tkinter GUI class (can also be imported, but runs only if main)
# =====================================================================
class DependencyViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Dependency Visualizer")

        self.canvas = tk.Canvas(self, bg="white")
        self.canvas.pack(fill="both", expand=True)
        
        self.zoom_factor = 1.0
        self.canvas_scale = 1.0

        # Mouse wheel bindings
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)   # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_zoom)   # Linux scroll down

        menu = tk.Menu(self)
        filemenu = tk.Menu(menu, tearoff=0)
        filemenu.add_command(label="Open File / Folder", command=self.load_path)
        menu.add_cascade(label="File", menu=filemenu)
        self.config(menu=menu)

        self.tkimg = None


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
        # keep the original full-resolution image
        self.original_image = Image.open(path)
        self.current_image = self.original_image.copy()
        self.tkimg = ImageTk.PhotoImage(self.current_image)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def on_zoom(self, event):
        if event.num == 5 or event.delta < 0:
            factor = 0.9
        else:
            factor = 1.1

        self.zoom_factor *= factor

        # limit zoom so it never goes to zero or infinity
        self.zoom_factor = max(0.05, min(50, self.zoom_factor))

        # compute new size
        w = int(self.original_image.width * self.zoom_factor)
        h = int(self.original_image.height * self.zoom_factor)

        # resize the image
        self.current_image = self.original_image.resize((w, h), Image.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(self.current_image)

        # redraw
        self.canvas.delete("img")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=(0, 0, w, h))



# =====================================================================
#  Main entry point
# =====================================================================
if __name__ == "__main__":
    app = DependencyViewer()
    app.mainloop()
