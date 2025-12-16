# AFCode


Custom Python OOP compiler built on AST, Pydot and Graphviz modules.

Layout (expanded):
<img width="1600" height="950" alt="image" src="https://github.com/user-attachments/assets/62547b7e-929e-46cd-8459-8d7b7e9d89d6" />


---
## What it can do

* **OOP Structure Visualization:** Automatically generates a graph of the .py file/code.
    * **Colored boxes** represent classes, functions, and files.
    * **Arrows** (lines) illustrate **dependencies** and **call relationships**.
    * zoom/unzoom, reset zoom, drag, quick find via bookmarked classes/defs, hover tooltips (arrows: where are they connecting to; boxes: content of def/class)
* **Compile:** Execute code directly from the console pane.
* **Build .exe:** via pyinstaller; preset commands + manual.
* **Canvas:** Filter and toggle visibility of different node types:
    * **Panning & Zooming** Using mouse drag and scroll wheel. Shift/Ctrl for increaed/turbo speed zoom/unzoom.
    * **Project** (blue), **Functions** (red), **Classes** (yellow) and **Methods** (green)
    * **Files** (yellow)
    * **Dynamic Data/Variables** (blue)
* **Console:**
    * **Search & Highlight** Yellow background after search (Next) /bookmarks
    * **Autocomplete** AST based autocomplete
    * **Font coloring** IDLE/IDE style + mellow black background. Whole file or by lines.
    * **Line wrapping** Toggle line wrapping.
    * **Undo/Redo:** Endless instances of undo/redo.
    * Tab/Shift+tab whole lines.
* **Navigation:**
    * **Boosted Scrollbar:** Hold shift for increased scrolling speed. Or ctrl for turbo boost.
    * **Class/def Bookmarks:** Jump instantly from the sidebar list to the corresponding class node on the canvas and its definition in the console.
    * **Obliterate:** Dissipates the whole screen into oblivion.
* **GUI:**
    * Resize via hotkeys or dragging. Console/Canvas/Both view.   
    * Manually adjustable height of listbox bookmarks.
    * Autosave of all entries and layout to .json when closed.
    * Start always with the last project open.
    * layout: drag all nested windows and main window; minsize menu = 200px; minsize console = 700px; minsize canvas = 1px

---


## Usage Instructions
  
### Run Code

* compile and run with debug console
* shift-Run Code for Run Code & Save

### Render

* Renders OOP graph into canvas
* Fills Bookmarks - classes and defs
* shift-Render for Render & Save

### Build .exe

* Starts WIndows cmd and builds .exe via pyinstall command
* choose (or write) additionall "--" commands in the middle pane
* shift-Build .exe for Build .exe & Save

### Open

* opens filedialog -> choose .py file; if not selected -> choose folder
* shift-open to Open recent history popup

### Save

* Save - overwrite; if nothing to overwrite, then Save As

### Class/function bookmarks

* fetch class and def content of imported .py file (must be in OOP mode or render manually)
* checkboxes:
   * Show Functions/Methods: Hide/unhide functions (def in root) and methods (def in class)
   * Show Functions/Methods: Hide/unhide functions (def in root) and methods (def in class)
   * OOP mode: automatically draws graph in real time while editing code

### Delete comments / Remove spaces

* removes #, ''' and """ comments from the code straight in edit mode (don't need to render)
  
 ### Unused nodes

* Hidden nodes in canvas (left-clicked)

 ### Reset view

* Zoom/unzoom canvas via undo/redo.

 ### Class / Def / Unused nodes lists H:

* Manually set the size of listboxes (in lines)

 ### --CMD settings

 * Choose commands for pyinstall .exe

 ### Visualiser settings
 
* Resolution: quality of the picture; heavy on CPU
* Speed
* Damping: low = turns into noise soon
* Strength
* Interference
* Scatter: True/False
* Target FPS
* CLip every N Frames

---

### Hotkeys / Controls

* f1: resize to the left
* f2: resize to the right
* f3: toggle canvas lock
* f4: visualiser
* f5: run code
* f6: save & run code
* f7: build code
* f8: save & build code

* ctrl+n: new instance
* ctrl+g / shift-Open: open recent files popup
* ctrl+z: undo
* ctrl+shift+z: redo
* ctrl+q: recolor (refresh) text
* ctrl+s: save file (overwrite without asking)
* ctrl+shift+s: save file as (opens filedialog)
* ctrl+f: toggle search in console
* mousewheel: in canvas: zoom/unzoom; in text: scroll; in middle pane: scroll; in listboxes: scroll
* shift+mousewheel: 2x speed scrolling/zooming
* ctrl+mousewheel: 5x speed scrolling/zooming
* left-click on box in canvas: hide
* left-click on class/def in Bookmards: show (in text and in canvas)

---

## Prerequisites

Python 3.x and following modules:

* import ast
* import math
* import threading
* import subprocess
* import re
* import tempfile
* import json
* import queue
* import time
* import sys
* import os

* import tkinter as tk
* from tkinter import ttk, filedialog, messagebox, scrolledtext

* import pydot

* import numpy as np
* from PIL import ImageGrab, ImageTk, Image
* from numpy.fft import fft2, fftshift

---

TO-DO:
What would be great if it had
* debug console jumps to bug line via click

Known issues
* find nodes in canvas sometimes off due to zoom
* scrollbars glitching when resizing windows
* obliteration is heavy on CPU
* obliteration click out+in glitchy
* find via syntax + bookmarks unfinished

