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
    """
    Builds a Left-to-Right graph. 
    Modules are stacked in vertical columns (groups of 5), 
    and their classes/functions flow horizontally to the right.
    """
    # rankdir="LR": Flows Left to Right
    # splines="ortho": Uses right-angled lines (cleaner for large diagrams)
    graph = pydot.Dot(graph_type="digraph", rankdir="LR", splines="ortho", concentrate="true")

    # --- Sophisticated Styling ---
    node_style = {
        "module":   {"shape": "component", "style": "filled", "fillcolor": "#dae8fc", "fontname": "Arial-Bold"},
        "class":    {"shape": "record",    "style": "filled", "fillcolor": "#ffe6cc", "fontname": "Arial"},
        "method":   {"shape": "oval",      "style": "filled", "fillcolor": "#d5e8d4", "fontname": "Arial", "fontsize": "10"},
        "function": {"shape": "note",      "style": "filled", "fillcolor": "#f8cecc", "fontname": "Arial", "fontsize": "10"}
    }

    modules = sorted(list(structure_graph.keys()))

    # =================================================================
    # 1. THE GRID LAYOUT (Vertical Columns of 5)
    # =================================================================
    ITEMS_PER_COLUMN = 5 
    
    # Create chunks
    columns = [modules[i:i + ITEMS_PER_COLUMN] for i in range(0, len(modules), ITEMS_PER_COLUMN)]

    for col_idx, column_modules in enumerate(columns):
        
        # In 'LR' mode, rank='same' aligns nodes VERTICALLY into a column
        col_sub = pydot.Subgraph(rank="same")
        
        previous_mod = None

        for mod in column_modules:
            # Add Module Node
            graph.add_node(pydot.Node(mod, **node_style["module"]))
            col_sub.add_node(pydot.Node(mod))

            # INTERNAL COLUMN BACKBONE: 
            # Invisible edge from Mod1 -> Mod2 to ensure they stack in order
            if previous_mod:
                graph.add_edge(pydot.Edge(previous_mod, mod, style="invis", weight=5))
            previous_mod = mod
        
        graph.add_subgraph(col_sub)

        # CROSS-COLUMN BACKBONE:
        # Connect the top of Column 1 to the top of Column 2 to keep columns ordered left-to-right
        if col_idx > 0:
            top_of_prev_col = columns[col_idx-1][0]
            top_of_curr_col = column_modules[0]
            # This pushes the new column to the right
            graph.add_edge(pydot.Edge(top_of_prev_col, top_of_curr_col, style="invis", weight=10))

    # =================================================================
    # 2. CONNECT CHILDREN (Expanding Horizontally)
    # =================================================================
    for module, items in structure_graph.items():
        for parent, child, kind in items:
            
            child_id = f"{module}.{child}"
            style = node_style.get(kind, {})
            
            # Add Child Node
            graph.add_node(pydot.Node(child_id, label=child, **style))

            # Add Edge (Parent -> Child)
            if parent == "module":
                graph.add_edge(pydot.Edge(module, child_id))
            else:
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
        # Determine zoom direction
        if event.num == 5 or event.delta < 0:
            factor = 0.9
        else:
            factor = 1.1

        # Clamp zoom
        new_zoom = self.zoom_factor * factor
        new_zoom = max(0.05, min(50, new_zoom))
        factor = new_zoom / self.zoom_factor
        self.zoom_factor = new_zoom

        # --- IMPORTANT PART: Keep mouse position stable ---

        # Mouse position in canvas coordinates
        mouse_x = self.canvas.canvasx(event.x)
        mouse_y = self.canvas.canvasy(event.y)

        # Compute where the mouse is in the original image coordinate system
        img_x = mouse_x / (self.zoom_factor / factor)
        img_y = mouse_y / (self.zoom_factor / factor)

        # Resize image
        w = int(self.original_image.width * self.zoom_factor)
        h = int(self.original_image.height * self.zoom_factor)
        self.current_image = self.original_image.resize((w, h), Image.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(self.current_image)

        # Redraw image
        self.canvas.delete("img")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=(0, 0, w, h))

        # --- SCROLL so that img_x, img_y stays under cursor ---
        self.canvas.xview_moveto((img_x * self.zoom_factor - event.x) / w)
        self.canvas.yview_moveto((img_y * self.zoom_factor - event.y) / h)




# =====================================================================
#  Main entry point
# =====================================================================
if __name__ == "__main__":
    app = DependencyViewer()
    app.mainloop()
