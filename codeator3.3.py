import ast
import os
import pydot
import tempfile
import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
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
        col_sub = pydot.Subgraph(rank="same")
        previous_mod = None
        for mod in column_modules:
            graph.add_node(pydot.Node(mod, **node_style["module"]))
            col_sub.add_node(pydot.Node(mod))
            if previous_mod:
                graph.add_edge(pydot.Edge(previous_mod, mod, style="invis", weight=5))
            previous_mod = mod
        graph.add_subgraph(col_sub)
        if col_idx > 0:
            top_of_prev_col = columns[col_idx-1][0]
            top_of_curr_col = column_modules[0]
            graph.add_edge(pydot.Edge(top_of_prev_col, top_of_curr_col, style="invis", weight=10))
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
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    graph.write_png(tmp.name)
    return tmp.name
class DependencyViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Dependency Visualizer")
        self.geometry("1200x800")
        self.v_scroll = tk.Scrollbar(self, orient="vertical")
        self.h_scroll = tk.Scrollbar(self, orient="horizontal")
        self._last_image_size = (1, 1)
        self.canvas = tk.Canvas(self, bg="#f0f0f0", 
                                yscrollcommand=self.v_scroll.set, 
                                xscrollcommand=self.h_scroll.set)
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.image_cache = {}  
        menu = tk.Menu(self)
        filemenu = tk.Menu(menu, tearoff=0)
        filemenu.add_command(label="Open File / Folder", command=self.load_path)
        menu.add_cascade(label="File", menu=filemenu)
        self.config(menu=menu)
        self.tkimg = None
        self.original_image = None
        self.current_image = None
        self.zoom_factor = 1.0
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Shift-MouseWheel>", self.on_shift_wheel)
        self.canvas.bind("<Control-MouseWheel>", self.on_ctrl_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)
        self.rect = None
        self.start_x = None
        self.start_y = None
        self.canvas.bind("<ButtonPress-1>", self.on_click_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_select)
        self.canvas.bind("<ButtonRelease-1>", self.on_click_release)

        self.pending_wheel_steps = 0
        self._zoom_job_scheduled = False


    def build_zoom_cache(self):
        base = self.original_image
        zoom_levels = [
            0.1, 0.2, 0.3, 0.5,
            0.75, 1.0,
            1.5, 2.0, 3.0, 4.0,
            6.0, 8.0, 12.0
        ]
        self.image_cache = {}
        for z in zoom_levels:
            w = int(base.width * z)
            h = int(base.height * z)
            self.image_cache[z] = base.resize((w, h), Image.LANCZOS)
            
    def get_cached_zoom(self, z):
        if not self.image_cache:
            return self.original_image
        nearest = min(self.image_cache.keys(), key=lambda k: abs(k - z))
        return self.image_cache[nearest]
    
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
        self.original_image = Image.open(path).convert("RGBA")
        self.zoom_factor = 1.0
        self.image_cache = {}
        self.current_image = self.original_image
        self._last_image_size = (self.original_image.width, self.original_image.height)
        self.build_zoom_cache_quick()
        self.update_canvas_image()
        self.after(100, lambda: self.build_zoom_cache_full())
        
    def build_zoom_cache_quick(self):
        base = self.original_image
        quick_levels = [0.5, 1.0, 2.0]
        self.image_cache = {}
        try:
            for z in quick_levels:
                w = max(1, int(base.width * z))
                h = max(1, int(base.height * z))
                self.image_cache[z] = base.resize((w, h), Image.LANCZOS)
        except Exception:
            self.image_cache = {1.0: base}
            
    def build_zoom_cache_full(self):
        base = self.original_image
        full_levels = [
            0.1, 0.2, 0.3, 0.4, 0.6, 0.75,
            1.5, 3.0, 4.0, 6.0, 8.0, 12.0
        ]
        remaining = [z for z in full_levels if z not in self.image_cache]
        
        def build_chunk(idx=0, chunk_size=2):
            if idx >= len(remaining):
                return
            end = min(idx + chunk_size, len(remaining))
            for j in range(idx, end):
                z = remaining[j]
                try:
                    w = max(1, int(base.width * z))
                    h = max(1, int(base.height * z))
                    self.image_cache[z] = base.resize((w, h), Image.LANCZOS)
                except Exception:
                    pass
            self.after(20, lambda: build_chunk(end, chunk_size))
        build_chunk(0, chunk_size=2)
        
    def get_cached_zoom(self, z):
        if not self.image_cache:
            return self.original_image
        nearest = min(self.image_cache.keys(), key=lambda k: abs(k - z))
        return self.image_cache[nearest]
    
    def update_canvas_image(self, center_on_rect=None):
        if not self.original_image:
            return
        self.current_image = self.get_cached_zoom(self.zoom_factor)
        w, h = self.current_image.size
        self._last_image_size = (w, h)
        self.tkimg = ImageTk.PhotoImage(self.current_image)
        self.canvas.delete("img") 
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=(0, 0, w, h))
        if center_on_rect:
            cx, cy = center_on_rect
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            target_x = w * cx - (cw / 2)
            target_y = h * cy - (ch / 2)
            self.canvas.xview_moveto(target_x / w)
            self.canvas.yview_moveto(target_y / h)
            
    def on_shift_wheel(self, event):
        if event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        else:
            self.canvas.yview_scroll(1, "units")
        return "break"
    
    def on_ctrl_wheel(self, event):
        if event.delta > 0:
            self.canvas.xview_scroll(-1, "units")
        else:
            self.canvas.xview_scroll(1, "units")
        return "break"
    
    def on_mouse_wheel(self, event):
        if not self.original_image:
            return "break"

        # Normalize wheel direction cross-platform
        is_up = False
        if hasattr(event, "delta") and event.delta:
            is_up = event.delta > 0
        elif hasattr(event, "num"):
            is_up = (event.num == 4)

        self.pending_wheel_steps += 1 if is_up else -1

        self._last_wheel_event_xy = (event.x, event.y)

        if not self._zoom_job_scheduled:
            self._zoom_job_scheduled = True
            self.after(16, self._process_pending_wheel_steps)  # limit to 60fps


        return "break"
    
    def _process_pending_wheel_steps(self):
        self._zoom_job_scheduled = False

        steps = self.pending_wheel_steps
        if steps == 0:
            return

        # capture and reset queue
        self.pending_wheel_steps = 0

        # Use the last cursor position we saved
        last_pos = getattr(self, "_last_wheel_event_xy", (self.canvas.winfo_width() // 2,
                                                          self.canvas.winfo_height() // 2))
        ex, ey = last_pos

        # Perform each step sequentially (this ensures each tick is applied)
        # but we keep the per-step work minimal by relying on cached images.
        if steps > 0:
            for _ in range(steps):
                self._apply_one_zoom_step(1.1, ex, ey)
        else:
            for _ in range(-steps):
                self._apply_one_zoom_step(0.9, ex, ey)

    def _apply_one_zoom_step(self, factor, event_x, event_y):
        # compute old/new zoom
        old_zoom = self.zoom_factor
        new_zoom = max(0.05, min(50.0, old_zoom * factor))
        if new_zoom == old_zoom:
            return

        # anchor in image coordinates BEFORE zoom
        img_x_before = self.canvas.canvasx(event_x)
        img_y_before = self.canvas.canvasy(event_y)

        rel_x = img_x_before / max(1, self._last_image_size[0])
        rel_y = img_y_before / max(1, self._last_image_size[1])

        # update state & pick cached image
        self.zoom_factor = new_zoom
        self.current_image = self.get_cached_zoom(new_zoom)
        new_w, new_h = self.current_image.size
        self._last_image_size = (new_w, new_h)

        # create tk image once per step (cached images are small/fast)
        self.tkimg = ImageTk.PhotoImage(self.current_image)

        # redraw (we always overwrite previous "img" — cheap)
        self.canvas.delete("img")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))

        # center-if-smaller behavior (keeps unzoom-to-corner fixed)
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

        # compute where the image pixel lands after zoom
        img_x_after = rel_x * new_w
        img_y_after = rel_y * new_h

        # compute view top-left so that the pixel stays under cursor
        new_view_x0 = (img_x_after - event_x) / new_w
        new_view_y0 = (img_y_after - event_y) / new_h

        max_x = 1 - canvas_w / new_w
        max_y = 1 - canvas_h / new_h

        new_view_x0 = min(max(new_view_x0, 0), max_x)
        new_view_y0 = min(max(new_view_y0, 0), max_y)

        self.canvas.xview_moveto(new_view_x0)
        self.canvas.yview_moveto(new_view_y0)

        
    def on_click_start(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, 
            outline="red", width=2, dash=(4, 4)
        )
    def on_drag_select(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
    def on_click_release(self, event):
        if not self.rect:
            return
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        self.canvas.delete(self.rect)
        self.rect = None
        box_width = abs(end_x - self.start_x)
        box_height = abs(end_y - self.start_y)
        if box_width < 10 or box_height < 10:
            return
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        scale_x = canvas_w / box_width
        scale_y = canvas_h / box_height
        zoom_multiplier = min(scale_x, scale_y)
        self.zoom_factor *= zoom_multiplier
        current_img_w = self.current_image.width
        current_img_h = self.current_image.height
        center_x_px = (self.start_x + end_x) / 2
        center_y_px = (self.start_y + end_y) / 2
        ratio_x = center_x_px / current_img_w
        ratio_y = center_y_px / current_img_h
        self.update_canvas_image(center_on_rect=(ratio_x, ratio_y))
if __name__ == "__main__":
    app = DependencyViewer()
    app.mainloop()
