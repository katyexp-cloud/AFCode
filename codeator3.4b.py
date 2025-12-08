import ast
import os
import pydot
import tempfile
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk

# ---------------------------
# Helpers: parse python files
# ---------------------------
def extract_structure_from_file(path: str):
    """Extract classes, methods, and functions from a Python file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
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
    """Scan a single file or directory for classes and functions."""
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
    """Build a graphviz/pydot graph (left->right layout)."""
    graph = pydot.Dot(graph_type="digraph", rankdir="LR", splines="ortho", concentrate="true")
    node_style = {
        "module":   {"shape": "component", "style": "filled", "fillcolor": "#dae8fc", "fontname": "Arial-Bold"},
        "class":    {"shape": "record",    "style": "filled", "fillcolor": "#ffe6cc", "fontname": "Arial"},
        "method":   {"shape": "oval",      "style": "filled", "fillcolor": "#d5e8d4", "fontname": "Arial", "fontsize": "10"},
        "function": {"shape": "note",      "style": "filled", "fillcolor": "#f8cecc", "fontname": "Arial", "fontsize": "10"}
    }

    modules = sorted(list(structure_graph.keys()))
    ITEMS_PER_COLUMN = 5
    columns = [modules[i:i + ITEMS_PER_COLUMN] for i in range(0, len(modules), ITEMS_PER_COLUMN)]

    for col_idx, column_modules in enumerate(columns):
        sub = pydot.Subgraph(rank="same")
        prev = None
        for m in column_modules:
            graph.add_node(pydot.Node(m, **node_style["module"]))
            sub.add_node(pydot.Node(m))
            if prev:
                graph.add_edge(pydot.Edge(prev, m, style="invis", weight=5))
            prev = m
        graph.add_subgraph(sub)
        if col_idx > 0:
            top_prev = columns[col_idx - 1][0]
            top_curr = column_modules[0]
            graph.add_edge(pydot.Edge(top_prev, top_curr, style="invis", weight=10))

    for module, items in structure_graph.items():
        for parent, child, kind in items:
            child_id = f"{module}.{child}"
            style = node_style.get(kind, {})
            graph.add_node(pydot.Node(child_id, label=child, **style))
            if parent == "module":
                graph.add_edge(pydot.Edge(module, child_id))
            else:
                parent_id = f"{module}.{parent}"
                graph.add_edge(pydot.Edge(parent_id, child_id))

    return graph

def render_graph(graph):
    """Write graph to a temp png and return path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    graph.write_png(tmp.name)
    return tmp.name

# ------------------------------------------------
# Main app: dependency viewer with Q/W zoom keys
# ------------------------------------------------
class DependencyViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Dependency Visualizer (Q/W zoom)")
        self.geometry("1200x800")

        # canvas + scrollbars
        self.v_scroll = tk.Scrollbar(self, orient="vertical")
        self.h_scroll = tk.Scrollbar(self, orient="horizontal")
        self.canvas = tk.Canvas(self, bg="#f0f0f0", 
                                yscrollcommand=self.v_scroll.set,
                                xscrollcommand=self.h_scroll.set)
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # menu
        menu = tk.Menu(self)
        filemenu = tk.Menu(menu, tearoff=0)
        filemenu.add_command(label="Open File / Folder", command=self.load_path)
        menu.add_cascade(label="File", menu=filemenu)
        self.config(menu=menu)

        # image state
        self.original_image = None          # PIL original
        self.current_image = None           # PIL currently displayed (from cache)
        self.tkimg = None                   # PhotoImage reference
        self.zoom_factor = 1.0
        self._last_image_size = (1, 1)      # current displayed image pixel size (w, h)

        # image cache (small set for responsiveness)
        self.image_cache = {}

        # bindings
        # remove mouse-wheel zoom entirely (no wheel bindings)
        # keep panning via shift/ctrl + wheel default behavior (left as-is)
        # bind Q/W keys to zoom
        self.bind_all("<Key>", self._on_key)
        # allow clicking/dragging marquee
        self.rect = None
        self.start_x = None
        self.start_y = None
        self.canvas.bind("<ButtonPress-1>", self.on_click_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_select)
        self.canvas.bind("<ButtonRelease-1>", self.on_click_release)

    # ----------------------------
    # Caching helpers
    # ----------------------------
    def build_quick_cache(self):
        """Build a small helpful cache to keep navigation snappy."""
        if not self.original_image:
            return
        base = self.original_image
        quick_levels = [0.5, 1.0, 2.0]
        self.image_cache = {}
        for z in quick_levels:
            try:
                w = max(1, int(base.width * z))
                h = max(1, int(base.height * z))
                self.image_cache[z] = base.resize((w, h), Image.LANCZOS)
            except Exception:
                pass
        # always keep original size available
        if 1.0 not in self.image_cache:
            self.image_cache[1.0] = base

    def build_full_cache(self):
        """Build more zoom levels in background (not blocking)."""
        if not self.original_image:
            return
        base = self.original_image
        all_levels = [0.1, 0.2, 0.3, 0.4, 0.6, 0.75, 1.5, 3.0, 4.0, 6.0, 8.0, 12.0]
        remaining = [z for z in all_levels if z not in self.image_cache]
        def chunk(i=0, chunk_size=2):
            if i >= len(remaining):
                return
            for j in range(i, min(i+chunk_size, len(remaining))):
                z = remaining[j]
                try:
                    w = max(1, int(base.width * z))
                    h = max(1, int(base.height * z))
                    self.image_cache[z] = base.resize((w, h), Image.LANCZOS)
                except Exception:
                    pass
            self.after(30, lambda: chunk(i+chunk_size, chunk_size))
        chunk()

    def get_cached_zoom(self, z):
        """Return nearest cached PIL image for requested zoom z."""
        if not self.image_cache:
            return self.original_image
        nearest = min(self.image_cache.keys(), key=lambda k: abs(k - z))
        return self.image_cache[nearest]

    # ----------------------------
    # Loading and drawing
    # ----------------------------
    def load_path(self):
        path = filedialog.askopenfilename(filetypes=[("Python files", "*.py"), ("All files", "*.*")])
        if not path:
            path = filedialog.askdirectory()
        if not path:
            return

        dep_graph = scan_path_for_structure(path)
        g = build_graphviz_graph(dep_graph)
        img_path = render_graph(g)
        self.display_image(img_path)

    def display_image(self, path):
        """Load an image, reset state and show quickly."""
        self.original_image = Image.open(path).convert("RGBA")
        self.zoom_factor = 1.0
        self.image_cache = {}
        self.current_image = self.original_image
        self._last_image_size = (self.original_image.width, self.original_image.height)

        self.build_quick_cache()
        self.update_canvas_image()
        # schedule full cache build in the background
        self.after(150, self.build_full_cache)

    def update_canvas_image(self, center_on_rect=None):
        """Draw current_image on canvas and update scrollregion. Optionally center on ratio coords."""
        if not self.original_image:
            return

        self.current_image = self.get_cached_zoom(self.zoom_factor)
        w, h = self.current_image.size
        self._last_image_size = (w, h)

        self.tkimg = ImageTk.PhotoImage(self.current_image)
        # clear and draw
        self.canvas.delete("img")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=(0, 0, w, h))

        # If image smaller than canvas, center it
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if w <= canvas_w or h <= canvas_h:
            # draw centered with offset
            offset_x = max(0, (canvas_w - w) // 2)
            offset_y = max(0, (canvas_h - h) // 2)
            self.canvas.delete("img")
            self.canvas.create_image(offset_x, offset_y, anchor="nw", image=self.tkimg, tags="img")
            # scrollbars not meaningful when image smaller; reset to origin
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
            return

        # If a center_on_rect is provided (ratios 0..1), place that center in the canvas center
        if center_on_rect:
            cx, cy = center_on_rect
            target_x = w * cx - (canvas_w / 2)
            target_y = h * cy - (canvas_h / 2)
            nx = max(0.0, min(1.0, target_x / max(1, w)))
            ny = max(0.0, min(1.0, target_y / max(1, h)))
            self.canvas.xview_moveto(nx)
            self.canvas.yview_moveto(ny)

    # ----------------------------
    # Keybindings: Q/W zoom
    # ----------------------------
    def _on_key(self, event):
        # Accept q/Q as zoom out, w/W as zoom in
        key = event.keysym.lower()
        if key == "w":
            self._zoom_by_key(1.1)
        elif key == "q":
            self._zoom_by_key(0.9)
        # allow +/- too
        elif key in ("plus", "equal"):
            self._zoom_by_key(1.1)
        elif key in ("minus", "underscore"):
            self._zoom_by_key(0.9)

    def _zoom_by_key(self, factor):
        """Apply one zoom step anchored at current mouse pointer within canvas if possible."""
        if not self.original_image:
            return

        old_zoom = self.zoom_factor
        new_zoom = max(0.05, min(50.0, old_zoom * factor))
        if new_zoom == old_zoom:
            return

        # Determine anchor point:
        # Try to get current pointer position and convert to canvas coordinates.
        # If pointer not over canvas, anchor to canvas center.
        try:
            px_root = self.winfo_pointerx()
            py_root = self.winfo_pointery()
            canvas_root_x = self.canvas.winfo_rootx()
            canvas_root_y = self.canvas.winfo_rooty()
            widget_x = px_root - canvas_root_x
            widget_y = py_root - canvas_root_y
            # If pointer is outside canvas bounds, fallback to center
            if widget_x < 0 or widget_y < 0 or widget_x > self.canvas.winfo_width() or widget_y > self.canvas.winfo_height():
                widget_x = self.canvas.winfo_width() // 2
                widget_y = self.canvas.winfo_height() // 2
        except Exception:
            widget_x = self.canvas.winfo_width() // 2
            widget_y = self.canvas.winfo_height() // 2

        # image coordinates under that widget point BEFORE zoom
        img_x_before = self.canvas.canvasx(widget_x)
        img_y_before = self.canvas.canvasy(widget_y)

        # relative position in current image
        rel_x = img_x_before / max(1, self._last_image_size[0])
        rel_y = img_y_before / max(1, self._last_image_size[1])

        # update zoom and pick nearest cached image
        self.zoom_factor = new_zoom
        self.current_image = self.get_cached_zoom(new_zoom)
        new_w, new_h = self.current_image.size
        self._last_image_size = (new_w, new_h)

        # redraw
        self.tkimg = ImageTk.PhotoImage(self.current_image)
        self.canvas.delete("img")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))

        # If image smaller than canvas, center and done
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if new_w <= canvas_w or new_h <= canvas_h:
            offset_x = max(0, (canvas_w - new_w) // 2)
            offset_y = max(0, (canvas_h - new_h) // 2)
            self.canvas.delete("img")
            self.canvas.create_image(offset_x, offset_y, anchor="nw", image=self.tkimg, tags="img")
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)
            return

        # compute where the anchored pixel lands after zoom
        img_x_after = rel_x * new_w
        img_y_after = rel_y * new_h

        # compute view top-left so pixel stays at same widget coordinate
        new_view_x0 = (img_x_after - widget_x) / new_w
        new_view_y0 = (img_y_after - widget_y) / new_h

        # clamp to valid scroll range
        max_x = 1 - (canvas_w / new_w)
        max_y = 1 - (canvas_h / new_h)
        new_view_x0 = min(max(new_view_x0, 0.0), max_x)
        new_view_y0 = min(max(new_view_y0, 0.0), max_y)

        self.canvas.xview_moveto(new_view_x0)
        self.canvas.yview_moveto(new_view_y0)

    # ----------------------------
    # Marquee zoom (click-drag)
    # ----------------------------
    def on_click_start(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y,
                                                 outline="red", width=2, dash=(4,4))

    def on_drag_select(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_click_release(self, event):
        if not self.rect:
            return
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        self.canvas.delete(self.rect)
        self.rect = None

        box_w = abs(end_x - self.start_x)
        box_h = abs(end_y - self.start_y)
        if box_w < 8 or box_h < 8:
            return

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        scale_x = canvas_w / box_w
        scale_y = canvas_h / box_h
        zoom_multiplier = min(scale_x, scale_y)

        # apply zoom and center on box center
        center_x_px = (self.start_x + end_x) / 2
        center_y_px = (self.start_y + end_y) / 2

        # update factor and update
        self.zoom_factor *= zoom_multiplier
        # ratio relative to current image
        ratio_x = center_x_px / max(1, self._last_image_size[0])
        ratio_y = center_y_px / max(1, self._last_image_size[1])
        self.update_canvas_image(center_on_rect=(ratio_x, ratio_y))

# ----------------------
# Run app
# ----------------------
if __name__ == "__main__":
    app = DependencyViewer()
    app.mainloop()
