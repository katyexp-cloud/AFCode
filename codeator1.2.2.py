import tkinter as tk
from tkinter import filedialog, messagebox, Toplevel
import ast
import os
import re

selected_to_remove = set()
current_code = ""
delete_comments_var = None  # checkbox control


def analyze_code(code: str):
    global current_code
    current_code = code

    try:
        tree = ast.parse(code)
    except Exception as e:
        return f"⚠️ Could not parse code:\n{e}"

    analysis = {
        "imports": [],
        "globals": [],
        "functions": [],
        "classes": {},
        "comments": [],
        "ui_elements": []
    }

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                analysis["imports"].append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module if node.module else ""
            for alias in node.names:
                analysis["imports"].append(f"{mod}.{alias.name}")
        elif isinstance(node, ast.FunctionDef):
            analysis["functions"].append(node.name)
        elif isinstance(node, ast.ClassDef):
            methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
            analysis["classes"][node.name] = methods
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    analysis["globals"].append(target.id)

    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            analysis["comments"].append(stripped)

    if "pygame.display" in code or "pygame.init" in code:
        analysis["ui_elements"].append("pygame UI")
    if "tkinter" in code:
        analysis["ui_elements"].append("tkinter UI")

    return analysis


def build_analysis_display(analysis):
    output_box.config(state="normal")
    output_box.delete("1.0", tk.END)

    # header
    output_box.insert(tk.END, "=== 🧩 CODEATOR ANALYSIS ===\n\n", "header")

    # imports
    output_box.insert(tk.END, "📦 Imports:\n", "section")
    for i in analysis["imports"]:
        output_box.insert(tk.END, f"  - {i}\n", "imports")

    # globals
    output_box.insert(tk.END, "\n🌍 Globals:\n", "section")
    for g in analysis["globals"]:
        output_box.insert(tk.END, f"  - {g}\n", "globals")

    # functions (clickable)
    output_box.insert(tk.END, "\n🔧 Functions:\n", "section")
    for f in analysis["functions"]:
        tag = f"func_{f}"
        output_box.insert(tk.END, f"  - {f}\n", (tag,))
        output_box.tag_bind(tag, "<Button-1>", lambda e, name=f: toggle_selection(name))
        # default style for function tags
        output_box.tag_config(tag, foreground="#1E90FF", underline=True)  # dodger blue

    # classes & methods (clickable)
    output_box.insert(tk.END, "\n🏗️ Classes & Methods:\n", "section")
    for cls, methods in analysis["classes"].items():
        tag = f"class_{cls}"
        output_box.insert(tk.END, f"  - {cls}\n", (tag,))
        output_box.tag_bind(tag, "<Button-1>", lambda e, name=cls: toggle_selection(name))
        output_box.tag_config(tag, foreground="#8A2BE2", underline=True)  # blueviolet
        for m in methods:
            output_box.insert(tk.END, f"      * {m}\n", "method")

    # comments
    output_box.insert(tk.END, "\n💬 Comments:\n", "section")
    for c in analysis["comments"]:
        output_box.insert(tk.END, f"  {c}\n", "comments")

    # ui elements
    output_box.insert(tk.END, "\n🖥️ UI Elements:\n", "section")
    for ui in analysis["ui_elements"]:
        output_box.insert(tk.END, f"  - {ui}\n", "ui")

    output_box.insert(tk.END, "\n✅ Done.\n", "footer")

    # tag styles for non-clickables
    output_box.tag_config("imports", foreground="#2E8B57")   # sea green
    output_box.tag_config("globals", foreground="#D2691E")   # chocolate / orange-brown
    output_box.tag_config("comments", foreground="#6C6C6C", font=("Courier", 9, "italic"))  # gray
    output_box.tag_config("ui", foreground="#8B4513")        # saddle brown
    output_box.tag_config("method", foreground="#333333")
    output_box.tag_config("section", foreground="#444444", font=("Arial", 10, "bold"))
    output_box.tag_config("header", foreground="#222222", font=("Arial", 12, "bold"))
    output_box.tag_config("footer", foreground="#222222", font=("Arial", 10, "bold"))

    output_box.config(state="disabled")


def toggle_selection(name):
    # determine tag for this name
    tag_func = f"func_{name}"
    tag_class = f"class_{name}"
    if tag_func in output_box.tag_names():
        tag = tag_func
    else:
        tag = tag_class

    if name in selected_to_remove:
        selected_to_remove.remove(name)
        # restore original color depending on tag type
        if tag.startswith("func_"):
            output_box.tag_config(tag, foreground="#1E90FF", background="white")
        else:
            output_box.tag_config(tag, foreground="#8A2BE2", background="white")
    else:
        selected_to_remove.add(name)
        output_box.tag_config(tag, foreground="white", background="#d9534f")  # white on bootstrap-danger


# --- Codeator 1.2.2: Shift + drag to quick-mark defs/classes ---
def shift_hover_mark(event):
    # 1 = Shift modifier bitmask (common on many platforms)
    if event.state & 0x0001:
        # find tags under the mouse pointer
        tags = output_box.tag_names(f"@{event.x},{event.y}")
        for tag in tags:
            if tag.startswith(("func_", "class_")):
                name = tag.split("_", 1)[1]
                if name not in selected_to_remove:
                    selected_to_remove.add(name)
                    output_box.tag_config(tag, foreground="white", background="#d9534f")


def remove_selected_items(code, items_to_remove):
    lines = code.splitlines()
    new_lines = []
    skip_block = False
    indent_level = None
    name_pattern = re.compile(r'^\s*(def|class)\s+(\w+)')

    for i, line in enumerate(lines):
        match = name_pattern.match(line)
        if match:
            kind, name = match.groups()
            if name in items_to_remove:
                skip_block = True
                indent_level = len(line) - len(line.lstrip())
                continue  # skip the line

        if skip_block:
            current_indent = len(line) - len(line.lstrip())
            if line.strip() == "":
                continue
            if current_indent <= indent_level:
                skip_block = False
                indent_level = None
            else:
                continue

        if not skip_block:
            new_lines.append(line)

    cleaned = "\n".join(new_lines)
    cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
    return cleaned


def remove_comments(code):
    cleaned = re.sub(r'(?m)^\s*#.*$', '', code)
    # try to remove inline comments but avoid removing # inside strings (best-effort)
    cleaned = re.sub(r'(?m)([^\'"\n]*)(#.*$)', lambda m: m.group(1) if ('"' not in m.group(0) and "'" not in m.group(0)) else m.group(0), cleaned)
    cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned)
    return cleaned


def export_cleaned():
    if not current_code.strip():
        messagebox.showwarning("No Code", "Please analyze code first.")
        return
    cleaned = remove_selected_items(current_code, selected_to_remove)
    if delete_comments_var.get():
        cleaned = remove_comments(cleaned)

    popup = Toplevel(root)
    popup.title("🧹 Cleaned Code Export - Codeator 1.2.2")
    popup.geometry("900x650")

    tk.Label(popup, text="Your cleaned code:", font=("Arial", 12, "bold")).pack(pady=5)

    text_frame = tk.Frame(popup)
    text_frame.pack(fill="both", expand=True)

    text_box = tk.Text(text_frame, wrap="none", font=("Courier", 10), bg="#1e1e1e", fg="#d4d4d4")
    text_box.pack(side="left", fill="both", expand=True)

    v_scroll = tk.Scrollbar(text_frame, command=text_box.yview)
    v_scroll.pack(side="right", fill="y")
    text_box.config(yscrollcommand=v_scroll.set)

    h_scroll = tk.Scrollbar(popup, command=text_box.xview, orient="horizontal")
    h_scroll.pack(side="bottom", fill="x")
    text_box.config(xscrollcommand=h_scroll.set)

    text_box.insert(tk.END, cleaned)

    # 🎨 Mini syntax highlighter for the export view
    def highlight_syntax():
        # Reset
        for tag in text_box.tag_names():
            text_box.tag_delete(tag)

        keywords = r"\b(import|from|def|class|if|elif|else|for|while|return|with|as|try|except|finally|lambda|True|False|None|yield|pass|break|continue)\b"
        strings = r"(\".*?\"|\'.*?\')"
        comments = r"#[^\n]*"

        def tag_regex(pattern, tag, color):
            for match in re.finditer(pattern, cleaned):
                start_idx = f"1.0+{match.start()}c"
                end_idx = f"1.0+{match.end()}c"
                text_box.tag_add(tag, start_idx, end_idx)
            text_box.tag_config(tag, foreground=color)

        tag_regex(keywords, "keyword", "#569CD6")
        tag_regex(strings, "string", "#CE9178")
        tag_regex(comments, "comment", "#6A9955")
        tag_regex(r"\bdef\b\s+\w+", "function", "#4FC1FF")
        tag_regex(r"\bclass\b\s+\w+", "class", "#C586C0")

    highlight_syntax()

    def save_to_file():
        path = filedialog.asksaveasfilename(defaultextension=".py", filetypes=[("Python Files", "*.py")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(cleaned)
            messagebox.showinfo("Exported", f"File saved to {path}")

    tk.Button(popup, text="💾 Save as .py", command=save_to_file, bg="#4CAF50", fg="white").pack(pady=5)

def analyze_button_click():
    code = code_input.get("1.0", tk.END)
    analysis = analyze_code(code)
    if isinstance(analysis, str):
        output_box.config(state="normal")
        output_box.delete("1.0", tk.END)
        output_box.insert(tk.END, analysis)
        output_box.config(state="disabled")
    else:
        build_analysis_display(analysis)


def open_file():
    path = filedialog.askopenfilename(
        title="Select a Python file",
        filetypes=[("Python Files", "*.py")]
    )
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        code_input.delete("1.0", tk.END)
        code_input.insert(tk.END, code)
        messagebox.showinfo("File Loaded", f"Loaded {os.path.basename(path)}")
    except Exception as e:
        messagebox.showerror("Error", f"Could not open file:\n{e}")


# --- UI SETUP ---
root = tk.Tk()
root.title("🧠 Codeator 1.2.2 - Interactive Python Code Analyzer")
root.geometry("980x980")
root.configure(bg="#f9f9f9")

title_label = tk.Label(root, text="🧠 Codeator 1.2.2", font=("Arial", 22, "bold"), bg="#f9f9f9", fg="#222")
title_label.pack(pady=10)

open_btn = tk.Button(root, text="📂 Open .py File", command=open_file, font=("Arial", 12))
open_btn.pack(pady=5)

code_label = tk.Label(root, text="Enter or paste Python code:", font=("Arial", 12), bg="#f9f9f9")
code_label.pack(pady=5)

# ✅ Scrollable code input
code_frame = tk.Frame(root)
code_frame.pack(pady=5, fill="both", expand=False)

code_input = tk.Text(code_frame, height=15, width=110, font=("Courier", 10), wrap="none")
code_input.pack(side="left", fill="both", expand=True)

code_v_scroll = tk.Scrollbar(code_frame, command=code_input.yview)
code_v_scroll.pack(side="right", fill="y")
code_input.config(yscrollcommand=code_v_scroll.set)

code_h_scroll = tk.Scrollbar(root, command=code_input.xview, orient="horizontal")
code_h_scroll.pack(fill="x")
code_input.config(xscrollcommand=code_h_scroll.set)

btn_frame = tk.Frame(root, bg="#f9f9f9")
btn_frame.pack(pady=10)

analyze_btn = tk.Button(btn_frame, text="🔍 Analyze Code", command=analyze_button_click,
                        font=("Arial", 12, "bold"), bg="#0078D7", fg="white")
analyze_btn.grid(row=0, column=0, padx=10)

export_btn = tk.Button(btn_frame, text="🧹 Export Cleaned", command=export_cleaned,
                       font=("Arial", 12, "bold"), bg="#FF7043", fg="white")
export_btn.grid(row=0, column=1, padx=10)

delete_comments_var = tk.BooleanVar()
delete_comments_check = tk.Checkbutton(root, text="🗑️ Delete comments on export",
                                       variable=delete_comments_var, bg="#f9f9f9", font=("Arial", 11))
delete_comments_check.pack(pady=5)

output_label = tk.Label(root, text="Analysis Result (click defs/classes to mark for deletion):",
                        font=("Arial", 12), bg="#f9f9f9")
output_label.pack(pady=5)

# ✅ Scrollable output box
output_frame = tk.Frame(root)
output_frame.pack(pady=5, fill="both", expand=True)

output_box = tk.Text(output_frame, height=25, width=110, font=("Courier", 10),
                     bg="#f0f0f0", state="disabled", wrap="none")
output_box.pack(side="left", fill="both", expand=True)

output_v_scroll = tk.Scrollbar(output_frame, command=output_box.yview)
output_v_scroll.pack(side="right", fill="y")
output_box.config(yscrollcommand=output_v_scroll.set)

output_h_scroll = tk.Scrollbar(root, command=output_box.xview, orient="horizontal")
output_h_scroll.pack(fill="x")
output_box.config(xscrollcommand=output_h_scroll.set)

# enable Shift + drag marking (Codeator 1.2.2)
output_box.bind("<B1-Motion>", shift_hover_mark)

root.mainloop()
