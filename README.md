# AFCoder

Readme created 99% by GPT, there's no time!

A powerful and fast desktop application built with **Tkinter** for visualizing the structure and dependencies of Python code, especially useful for complex **Object-Oriented Programming (OOP)** projects. It provides a dynamic graph of classes, functions, and files, alongside an integrated console for code execution and analysis.

A.K.A. my compiler to help me orient myself in 10k lines of .py file. Currently designing game Anarchy Forever with that - thus the name AFCoder a.k.a Absolutely Fucking Compiler.

Layout:
<img width="1598" height="980" alt="image" src="https://github.com/user-attachments/assets/98f9b556-3ac6-47a8-bf47-02ad588278d5" />




Picture: Just me compiling my app in my compiler from IDLE compiler.
![compilerz](https://github.com/user-attachments/assets/63fdd16c-3239-4075-823c-d1eb62c80fc3)

---
## Key Features

* **OOP Structure Visualization:** Automatically generates a navigable, dependency graph of your Python project.
    * **Nodes** represent classes, functions, and files.
    * **Edges** (lines) illustrate **dependencies** and **call relationships**.
* **Integrated Code Runner:** Execute code snippets directly from the console pane without leaving the application. Perfect for testing modules or debugging logic.
* **Dynamic View Controls:** Filter and toggle visibility of different node types:
    * **Functions** and **Methods**
    * **Files** (typically marked in **Yellow**)
    * **Dynamic Data/Variables** (typically marked in **Blue**)
* **Interactive Navigation:**
    * **Canvas Panning & Zooming** (using mouse drag and scroll wheel).
    * **Class Bookmarks:** Jump instantly from the sidebar list to the corresponding class node on the canvas and its definition in the console.
* **Advanced Console:**
    * **Search & Highlight** (`Ctrl+F` binding).
    * **Syntax Highlighting** (for JSON and Python output/code).
    * Clean separation of executed code's **Standard Output** and **Error** logs.

---

## Prerequisites

This application requires Python 3.x and the standard Tkinter library (which is usually included with Python). You will also need the following modules:

* **`tkinter`** (Standard Library)
* **`subprocess`** (Standard Library)
* **`tempfile`** (Standard Library)
* **`os`** (Standard Library)
* **`json`** (Standard Library)
* **`scrolledtext`** (From `tkinter` module)

## How to Run

1.  **Clone the Repository (or save the file):**
    ```bash
    git clone [YOUR_REPO_URL]
    cd [your-project-directory]
    ```

2.  **Execute the Application:**
    ```bash
    python your_main_file_name.py
    ```

## Usage Instructions

### 1. Load a Project

1.  Click the **"Open File/Folder"** button in the left **Sidebar**.
2.  Select the Python file or project directory you wish to visualize.

### 2. Visualize the Structure

* The **Canvas** (Left Pane) will automatically populate with a diagram showing the relationships between your code components.
* **Zoom** in/out using the **Mouse Scroll Wheel**.
* **Pan** by holding the **Left Mouse Button** and dragging.
* Use the **Class Bookmarks** list to quickly navigate to key definitions.

### 3. Run Code

1.  Click a node in the graph or select a file to display its source code in the **Console** (Right Pane).
2.  **Edit** the code directly in the console text area.
3.  Click the **"Run Code"** button in the **Sidebar**.
4.  The application creates a temporary, runnable file, executes it in a separate process, and displays the **output/errors** in a separate popup window or appended to the console. **(Note: Any header lines like **`=== Source Code: ...`** are automatically removed before compilation to prevent errors.)**
