import tkinter as tk
from tkinter import filedialog, messagebox
import ast
import os

def analyze_code(code: str):
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

    # extract comments manually (since AST ignores them)
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            analysis["comments"].append(stripped)

    # detect simple UI hints
    if "pygame.display" in code or "pygame.init" in code:
        analysis["ui_elements"].append("pygame UI")
    if "tkinter" in code:
        analysis["ui_elements"].append("tkinter UI")

    # build readable output
    output = ["=== 🧩 CODEATOR ANALYSIS ===\n"]
    output.append("📦 Imports:")
    for i in analysis["imports"]:
        output.append(f"  - {i}")
    output.append("\n🌍 Globals:")
    for g in analysis["globals"]:
        output.append(f"  - {g}")
    output.append("\n🔧 Functions:")
    for f in analysis["functions"]:
        output.append(f"  - {f}")
    output.append("\n🏗️ Classes & Methods:")
    for cls, methods in analysis["classes"].items():
        output.append(f"  - {cls}:")
        for m in methods:
            output.append(f"      * {m}")
    output.append("\n💬 Comments:")
    for c in analysis["comments"]:
        output.append(f"  {c}")
    output.append("\n🖥️ UI Elements:")
    for ui in analysis["ui_elements"]:
        output.append(f"  - {ui}")
    output.append("\n✅ Done.")

    return "\n".join(output)


def analyze_button_click():
    code = code_input.get("1.0", tk.END)
    result = analyze_code(code)
    output_box.delete("1.0", tk.END)
    output_box.insert(tk.END, result)


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
root.title("🧠 Codeator - Python Code Analyzer")
root.geometry("900x800")
root.configure(bg="#f9f9f9")

title_label = tk.Label(root, text="Codeator", font=("Arial", 20, "bold"), bg="#f9f9f9", fg="#222")
title_label.pack(pady=10)

open_btn = tk.Button(root, text="📂 Open .py File", command=open_file, font=("Arial", 12))
open_btn.pack(pady=5)

code_label = tk.Label(root, text="Enter or paste Python code:", font=("Arial", 12), bg="#f9f9f9")
code_label.pack(pady=5)

code_input = tk.Text(root, height=15, width=100, font=("Courier", 10))
code_input.pack(pady=5)

analyze_btn = tk.Button(root, text="🔍 Analyze Code", command=analyze_button_click, font=("Arial", 12, "bold"), bg="#0078D7", fg="white")
analyze_btn.pack(pady=10)

output_label = tk.Label(root, text="Analysis Result:", font=("Arial", 12), bg="#f9f9f9")
output_label.pack(pady=5)

output_box = tk.Text(root, height=20, width=100, font=("Courier", 10), bg="#f0f0f0")
output_box.pack(pady=5)

root.mainloop()
