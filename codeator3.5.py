#drag canvas
#zoom ok maybe slow
#hide unhide, svg

import ast
import os
import pydot
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk
import xml.etree.ElementTree as ET

# ---------- Helpers to extract structure ----------
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

# ---------- Graph builder (respects collapsed_classes) ----------
def build_graphviz_graph(structure_graph: dict, collapsed_classes=None):
    if collapsed_classes is None:
        collapsed_classes = set()

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

    # Module layout in columns
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
                graph.add_edge(pydot.Edge(previous_mod, mod, style="invis", weight=5))
            previous_mod = mod
        graph.add_subgraph(col_sub)
        if col_idx > 0:
            prev_top = columns[col_idx-1][0]
            curr_top = column_modules[0]
            graph.add_edge(pydot.Edge(prev_top, curr_top, style="invis", weight=10))

    # Build nodes and candidate edges
    all_nodes = set()
    candidate_edges = []  # (src, dst, kind)
    for module, items in structure_graph.items():
        all_nodes.add(module)
        top_funcs = [child for parent, child, kind in items if parent == "module" and kind == "function"]
        fake_root_id = None
        if top_funcs:
            fake_root_id = f"{module}.__FUNCS__"
            all_nodes.add(fake_root_id)
        for parent, child, kind in items:
            child_id = f"{module}.{child}"
            all_nodes.add(child_id)
            if parent == "module":
                if kind == "function" and fake_root_id:
                    src = fake_root_id
                else:
                    src = module
            else:
                src = f"{module}.{parent}"
            dst = child_id
            candidate_edges.append((src, dst, kind))

    # Filter edges to remove any that are incident to collapsed_classes
    visible_edges = []
    for src, dst, kind in candidate_edges:
        if src in collapsed_classes or dst in collapsed_classes:
            continue
        visible_edges.append((src, dst, kind))

    # compute node degrees from visible edges
    node_degrees = {n: 0 for n in all_nodes}
    for src, dst, _ in visible_edges:
        node_degrees[src] = node_degrees.get(src, 0) + 1
        node_degrees[dst] = node_degrees.get(dst, 0) + 1

    # nodes with degree 0 (but not modules) -> move into __UNUSED__ per module
    unused_nodes_per_module = {}
    for node in list(all_nodes):
        if node in modules:
            continue
        if node_degrees.get(node, 0) == 0:
            if "." in node:
                mod = node.split(".", 1)[0]
            else:
                continue
            unused_nodes_per_module.setdefault(mod, []).append(node)

    # Add Functions / Unused nodes and module -> group edges
    for module in modules:
        func_id = f"{module}.__FUNCS__"
        if func_id in all_nodes:
            graph.add_node(pydot.Node(func_id, label="Functions", **node_style["class"]))
            graph.add_edge(pydot.Edge(module, func_id))
        if module in unused_nodes_per_module:
            unused_id = f"{module}.__UNUSED__"
            graph.add_node(pydot.Node(unused_id, label="Unused", **node_style["class"]))
            graph.add_edge(pydot.Edge(module, unused_id))

    # Add regular nodes
    for module, items in structure_graph.items():
        for parent, child, kind in items:
            child_id = f"{module}.{child}"
            style = node_style.get(kind, {})
            graph.add_node(pydot.Node(child_id, label=child, **style))

    # Add visible edges
    for src, dst, _ in visible_edges:
        graph.add_edge(pydot.Edge(src, dst))

    # Add unused -> node edges
    for module, nodes in unused_nodes_per_module.items():
        unused_id = f"{module}.__UNUSED__"
        for node in nodes:
            if node in all_nodes:
                graph.add_edge(pydot.Edge(unused_id, node))

    return graph

# ---------- Render helpers ----------
def render_graph_to_files(graph):
    """
    Return (png_path, svg_text)
    Writes PNG to temporary file and returns SVG text (string).
    """
    try:
        png_bytes = graph.create(format="png")
        svg_bytes = graph.create(format="svg")
    except Exception as e:
        raise RuntimeError("Graphviz rendering failed: " + str(e))

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(png_bytes)
    tmp.flush()
    tmp.close()

    try:
        svg_text = svg_bytes.decode("utf-8")
    except Exception:
        svg_text = None

    return tmp.name, svg_text

# ---------- SVG parsing to extract node boxes ----------
def parse_svg_node_boxes(svg_text, png_path):
    if not svg_text:
        return {}

    try:
        root = ET.fromstring(svg_text)
    except Exception:
        return {}

    svg_w = None
    svg_h = None
    width_attr = root.get("width")
    height_attr = root.get("height")
    viewBox = root.get("viewBox")
    if width_attr and height_attr:
        def parse_wh(v):
            try:
                if v.endswith("pt"):
                    return float(v[:-2])
                if v.endswith("px"):
                    return float(v[:-2])
                return float(v)
            except Exception:
                return None
        svg_w = parse_wh(width_attr)
        svg_h = parse_wh(height_attr)
    if (svg_w is None or svg_h is None) and viewBox:
        try:
            parts = viewBox.split()
            svg_w = float(parts[2])
            svg_h = float(parts[3])
        except Exception:
            pass

    try:
        img = Image.open(png_path)
        png_w, png_h = img.size
    except Exception:
        return {}

    if svg_w and svg_h and svg_w > 0 and svg_h > 0:
        sx = png_w / svg_w
        sy = png_h / svg_h
    else:
        sx = sy = 1.0

    node_boxes = {}
    # find all g elements with a title child
    for g in root.findall(".//{http://www.w3.org/2000/svg}g") + root.findall(".//g"):
        title_elem = g.find("{http://www.w3.org/2000/svg}title") or g.find("title")
        if title_elem is None:
            continue
        node_name = title_elem.text.strip() if title_elem.text else None
        if not node_name:
            continue

        bbox = None
        poly = g.find("{http://www.w3.org/2000/svg}polygon") or g.find("polygon")
        if poly is not None and 'points' in poly.attrib:
            pts = poly.attrib.get('points').strip().split()
            coords = []
            for p in pts:
                if ',' in p:
                    a, b = p.split(',')
                else:
                    parts = p.split(',')
                    if len(parts) >= 2:
                        a, b = parts[0], parts[1]
                    else:
                        continue
                try:
                    coords.append((float(a), float(b)))
                except Exception:
                    pass
            if coords:
                xs = [c[0] for c in coords]
                ys = [c[1] for c in coords]
                minx, maxx = min(xs), max(xs)
                miny, maxy = min(ys), max(ys)
                bbox = (minx, miny, maxx, maxy)
        if bbox is None:
            ell = g.find("{http://www.w3.org/2000/svg}ellipse") or g.find("ellipse")
            if ell is not None:
                try:
                    cx = float(ell.attrib.get("cx", "0"))
                    cy = float(ell.attrib.get("cy", "0"))
                    rx = float(ell.attrib.get("rx", "0"))
                    ry = float(ell.attrib.get("ry", "0"))
                    bbox = (cx - rx, cy - ry, cx + rx, cy + ry)
                except Exception:
                    bbox = None
        if bbox is None:
            rect = g.find("{http://www.w3.org/2000/svg}rect") or g.find("rect")
            if rect is not None:
                try:
                    x = float(rect.attrib.get("x", "0"))
                    y = float(rect.attrib.get("y", "0"))
                    w = float(rect.attrib.get("width", "0"))
                    h = float(rect.attrib.get("height", "0"))
                    bbox = (x, y, x + w, y + h)
                except Exception:
                    bbox = None
        if bbox is None:
            text = g.find("{http://www.w3.org/2000/svg}text") or g.find("text")
            if text is not None:
                try:
                    x = float(text.attrib.get("x", "0"))
                    y = float(text.attrib.get("y", "0"))
                    bbox = (x-10, y-6, x+10, y+6)
                except Exception:
                    bbox = None
        if bbox is None:
            continue

        x1_svg, y1_svg, x2_svg, y2_svg = bbox
        x1_px = int(x1_svg * sx)
        y1_px = int(y1_svg * sy)
        x2_px = int(x2_svg * sx)
        y2_px = int(y2_svg * sy)
        node_boxes[node_name] = (x1_px, y1_px, x2_px, y2_px)

    return node_boxes

# ------------------------------
# GUI viewer with vertical sidebar buttons
# ------------------------------
class DependencyViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Dependency Visualizer")

        # top-level frames: left is canvas, right is vertical sidebar
        self.main_frame = tk.Frame(self)
        self.main_frame.pack(fill="both", expand=True)

        self.canvas_frame = tk.Frame(self.main_frame)
        self.canvas_frame.pack(side=tk.LEFT, fill="both", expand=True)

        self.sidebar_frame = tk.Frame(self.main_frame, width=220)
        self.sidebar_frame.pack(side=tk.RIGHT, fill="y")

        # Canvas fixed 800x800 (inside its frame)
        self.canvas = tk.Canvas(self.canvas_frame, bg="white", width=800, height=800)
        self.canvas.pack(fill="both", expand=True)

        # Sidebar label + scrollable area for buttons
        tk.Label(self.sidebar_frame, text="Classes", font=("Arial", 12, "bold")).pack(padx=6, pady=(6, 0))
        self.buttons_container = tk.Frame(self.sidebar_frame)
        self.buttons_container.pack(fill="y", expand=True, padx=6, pady=6)

        # add a canvas to buttons_container to make it scrollable if many classes
        self.btn_scroll_canvas = tk.Canvas(self.buttons_container, borderwidth=0, highlightthickness=0)
        self.btn_scroll_canvas.pack(side="left", fill="both", expand=True)
        self.btn_scroll_inner = tk.Frame(self.btn_scroll_canvas)
        self.btn_scroll_window = self.btn_scroll_canvas.create_window((0,0), window=self.btn_scroll_inner, anchor="nw")
        # vertical scrollbar
        self.btn_vscroll = tk.Scrollbar(self.buttons_container, orient="vertical", command=self.btn_scroll_canvas.yview)
        self.btn_vscroll.pack(side="right", fill="y")
        self.btn_scroll_canvas.configure(yscrollcommand=self.btn_vscroll.set)
        self.btn_scroll_inner.bind("<Configure>", lambda e: self.btn_scroll_canvas.configure(scrollregion=self.btn_scroll_canvas.bbox("all")))

        # Fit / Reset button at bottom of sidebar
        tk.Button(self.sidebar_frame, text="Reset Zoom (Fit)", command=self.reset_zoom).pack(side="bottom", fill="x", padx=6, pady=6)

        # State
        self.structure_graph = None
        self.collapsed_classes = set()   # toggled classes whose edges are hidden (e.g. "module.Class")
        self.node_kind = {}  # node id -> kind (class/function/method)
        self.node_boxes = {}  # node id -> (x1,y1,x2,y2) in displayed coords
        self.current_png_path = None
        self.current_svg_text = None

        # zoom
        self.zoom_factor = 1.0

        # Bindings for canvas
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)
        self.canvas.bind("<Button-5>", self.on_zoom)
        self.canvas.bind("<ButtonPress-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)
        self._pan_start = None
        self._moved = False

        # Menu
        menu = tk.Menu(self)
        filemenu = tk.Menu(menu, tearoff=0)
        filemenu.add_command(label="Open File / Folder", command=self.load_path)
        filemenu.add_command(label="Rebuild (force)", command=self.rebuild_and_show)
        filemenu.add_command(label="Reset Zoom (Fit to Canvas)", command=self.reset_zoom)
        menu.add_cascade(label="File", menu=filemenu)
        self.config(menu=menu)

        self.tkimg = None

    # ---------- Load/parse helpers ----------
    def load_path(self):
        path = filedialog.askopenfilename(
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if not path:
            path = filedialog.askdirectory()
        if not path:
            return
        self.structure_graph = scan_path_for_structure(path)
        # build node_kind mapping
        self.node_kind.clear()
        for module, items in self.structure_graph.items():
            for parent, child, kind in items:
                node_id = f"{module}.{child}"
                self.node_kind[node_id] = kind
        self.collapsed_classes.clear()
        self.rebuild_and_show()

    def rebuild_and_show(self):
        if not self.structure_graph:
            return
        try:
            g = build_graphviz_graph(self.structure_graph, collapsed_classes=self.collapsed_classes)
        except Exception as e:
            messagebox.showerror("Graph build error", str(e))
            return

        try:
            png_path, svg_text = render_graph_to_files(g)
        except Exception as e:
            messagebox.showerror("Graphviz render error", str(e))
            return

        self.current_png_path = png_path
        self.current_svg_text = svg_text

        # parse node boxes from svg and map them to PNG pixels
        self.node_boxes = parse_svg_node_boxes(svg_text, png_path)

        # display PNG
        self.display_image(png_path)

        # update sidebar buttons
        self.update_sidebar_buttons()

    def display_image(self, png_path):
        self.original_image = Image.open(png_path)
        self.current_image = self.original_image.copy()
        self.tkimg = ImageTk.PhotoImage(self.current_image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=(0, 0, self.current_image.width, self.current_image.height))
        self.fit_image_to_canvas()

    def fit_image_to_canvas(self):
        canvas_w = 800
        canvas_h = 800
        img_w = self.original_image.width
        img_h = self.original_image.height
        scale = min(canvas_w / img_w, canvas_h / img_h)
        self.zoom_factor = scale
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)
        self.current_image = self.original_image.resize((new_w, new_h), Image.LANCZOS)
        self.tkimg = ImageTk.PhotoImage(self.current_image)
        self.canvas.delete("all")
        # center
        self.canvas.create_image((canvas_w-new_w)//2, (canvas_h-new_h)//2, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))
        # rescale node boxes to displayed size & offset
        self._rescale_node_boxes_after_fit(new_w, new_h)

    def _rescale_node_boxes_after_fit(self, disp_w, disp_h):
        if not self.node_boxes or not self.current_png_path:
            return
        orig = Image.open(self.current_png_path)
        orig_w, orig_h = orig.size
        sx = disp_w / orig_w
        sy = disp_h / orig_h
        offset_x = (800 - disp_w)//2
        offset_y = (800 - disp_h)//2
        new_boxes = {}
        for nid, (x1,y1,x2,y2) in self.node_boxes.items():
            nx1 = int(x1 * sx) + offset_x
            ny1 = int(y1 * sy) + offset_y
            nx2 = int(x2 * sx) + offset_x
            ny2 = int(y2 * sy) + offset_y
            new_boxes[nid] = (nx1, ny1, nx2, ny2)
        self.node_boxes = new_boxes

    def reset_zoom(self):
        if hasattr(self, "original_image"):
            self.fit_image_to_canvas()

    # ---------- Sidebar / buttons ----------
    def update_sidebar_buttons(self):
        # Clear current contents of btn_scroll_inner
        for w in self.btn_scroll_inner.winfo_children():
            w.destroy()

        if not self.structure_graph:
            return

        # Collect all class node ids sorted
        class_nodes = []
        for module, items in self.structure_graph.items():
            for parent, child, kind in items:
                if kind == "class":
                    class_nodes.append(f"{module}.{child}")
        class_nodes.sort()

        # create a button for each class
        for nid in class_nodes:
            is_collapsed = nid in self.collapsed_classes
            label = nid
            btn_text = ("👁 Show" if is_collapsed else "👁 Hide")
            btn = tk.Button(self.btn_scroll_inner, text=f"{btn_text}  {label}", anchor="w",
                            command=lambda n=nid: self.toggle_class_from_button(n))
            btn.pack(fill="x", pady=2, padx=2)

    def toggle_class_from_button(self, node_id):
        # toggle and rebuild
        if node_id in self.collapsed_classes:
            self.collapsed_classes.remove(node_id)
        else:
            self.collapsed_classes.add(node_id)
        self.rebuild_and_show()

    # ---------- Mouse: pan + click (clicks ignored for nodes; buttons control toggles) ----------
    def _on_button_press(self, event):
        self.canvas.scan_mark(event.x, event.y)
        self._pan_start = (event.x, event.y)
        self._moved = False

    def _on_mouse_drag(self, event):
        self._moved = True
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_button_release(self, event):
        # do nothing on click release (we rely on sidebar buttons)
        self._moved = False

    # ---------- Zoom handling (mouse-centric) ----------
    def on_zoom(self, event):
        is_wheel_down = (hasattr(event, "num") and event.num == 5) or getattr(event, "delta", 0) < 0
        factor = 0.9 if is_wheel_down else 1.1

        new_zoom = self.zoom_factor * factor
        new_zoom = max(0.05, min(50, new_zoom))
        factor = new_zoom / self.zoom_factor
        self.zoom_factor = new_zoom

        mouse_x = self.canvas.canvasx(event.x)
        mouse_y = self.canvas.canvasy(event.y)

        try:
            orig_w, orig_h = Image.open(self.current_png_path).size
        except Exception:
            orig_w = self.current_image.width
            orig_h = self.current_image.height

        img_x = mouse_x / (self.zoom_factor / factor) if self.zoom_factor != 0 else mouse_x
        img_y = mouse_y / (self.zoom_factor / factor) if self.zoom_factor != 0 else mouse_y

        w = int(orig_w * self.zoom_factor)
        h = int(orig_h * self.zoom_factor)
        try:
            self.current_image = Image.open(self.current_png_path).resize((w, h), Image.LANCZOS)
        except Exception:
            self.current_image = self.original_image.resize((w, h), Image.LANCZOS)

        self.tkimg = ImageTk.PhotoImage(self.current_image)
        self.canvas.delete("img")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg, tags="img")
        self.canvas.config(scrollregion=(0, 0, w, h))

        if w:
            self.canvas.xview_moveto((img_x * self.zoom_factor - event.x) / w)
        if h:
            self.canvas.yview_moveto((img_y * self.zoom_factor - event.y) / h)

        # best-effort rescale of node_boxes used for fit; actual node_boxes rederived on rebuild
        try:
            orig_w2, orig_h2 = Image.open(self.current_png_path).size
            sx = w / orig_w2
            sy = h / orig_h2
            new_boxes = {}
            for nid, (x1,y1,x2,y2) in self.node_boxes.items():
                new_boxes[nid] = (int(x1 * sx), int(y1 * sy), int(x2 * sx), int(y2 * sy))
            self.node_boxes = new_boxes
        except Exception:
            pass

if __name__ == "__main__":
    app = DependencyViewer()
    app.mainloop()
