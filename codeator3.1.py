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
    """Build a UML-like graph with a Grid Layout to prevent ultra-wide images."""
    
    # compound='true' allows edges between clusters, concentrate='true' merges duplicate edges
    graph = pydot.Dot(graph_type="digraph", rankdir="TB", compound="true", concentrate="true")

    # A nicer styling for the nodes
    node_style = {
        "module": {"shape": "component", "style": "filled", "fillcolor": "#dae8fc", "fontname": "Arial-Bold"},
        "class":  {"shape": "record",    "style": "filled", "fillcolor": "#ffe6cc", "fontname": "Arial"},
        "method": {"shape": "oval",      "style": "filled", "fillcolor": "#d5e8d4", "fontname": "Arial", "fontsize": "10"},
        "function": {"shape": "note",    "style": "filled", "fillcolor": "#f8cecc", "fontname": "Arial", "fontsize": "10"}
    }

    modules = sorted(list(structure_graph.keys()))

    # =================================================================
    # 1. THE GRID LAYOUT LOGIC
    # =================================================================
    ITEMS_PER_ROW = 5  # <--- Change this to control width
    
    # Chunk modules into rows
    rows = [modules[i:i + ITEMS_PER_ROW] for i in range(0, len(modules), ITEMS_PER_ROW)]

    for row_idx, row_modules in enumerate(rows):
        
        # A. Create a Subgraph for this row to force alignment
        # rank='same' forces all modules in this list to be on the same horizontal level
        row_sub = pydot.Subgraph(rank="same")
        
        for mod in row_modules:
            # Create the Module node immediately so we can align it
            # We use the module name as the ID
            graph.add_node(pydot.Node(mod, **node_style["module"]))
            row_sub.add_node(pydot.Node(mod))
        
        graph.add_subgraph(row_sub)

        # B. Create Invisible "Backbone" Edges to stack rows vertically
        # Connect the first item of the current row to the first item of the next row.
        if row_idx < len(rows) - 1:
            first_in_current = row_modules[0]
            first_in_next = rows[row_idx + 1][0]
            
            # style="invis" creates a layout force without drawing a visible line
            graph.add_edge(pydot.Edge(first_in_current, first_in_next, style="invis", weight=10))

    # =================================================================
    # 2. CONNECT CHILDREN (Classes, Methods)
    # =================================================================
    for module, items in structure_graph.items():
        for parent, child, kind in items:
            
            # Create unique ID for the child node (e.g., "module_name.ClassName")
            child_id = f"{module}.{child}"
            
            # Add the Child Node
            style = node_style.get(kind, {})
            graph.add_node(pydot.Node(child_id, label=child, **style))

            # Create Edge from Parent -> Child
            if parent == "module":
                # Connect Module -> Class/Function
                graph.add_edge(pydot.Edge(module, child_id))
            else:
                # Connect Class -> Method
                parent_id = f"{module}.{parent}"
                graph.add_edge(pydot.Edge(parent_id, child_id))

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
