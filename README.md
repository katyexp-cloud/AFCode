# AFCode


Custom Python OOP compiler.

Normal mode:
<img width="1677" height="984" alt="image" src="https://github.com/user-attachments/assets/0d24e55e-a147-4f3f-9cf1-b2dd625fe0da" />




---
## What it can do

* **OOP Structure Visualization:** Automatically generates a graph of the .py file/code.
    * **Colored boxes** represent classes, functions, and files.
    * **Arrows** (lines) illustrate **dependencies** and **call relationships**.
    * zoom/unzoom, reset zoom, drag, quick find via bookmarked classes/defs, hover tooltips (arrows: where are they connecting to; boxes: content of def/class)
* **Code Runner:** Execute code directly from the console pane.
* **Build .exe:** via pyinstaller; preset commands + manual.
* **Canvas:** Filter and toggle visibility of different node types:
    * **Panning & Zooming** Using mouse drag and scroll wheel. Shift/Ctrl for increaed/turbo speed zoom/unzoom.
    * **Project** (blue), **Functions** (red), **Classes** (yellow) and **Methods** (green)
    * **Files** (yellow)
    * **Dynamic Data/Variables** (blue)
* **Console:**
    * **Search & Highlight** Yellow background after search (Next) /bookmarks
    * **Font coloring** IDLE/IDE style + mellow black background. Whole file or by lines.
    * Separation of executed code's **Standard Output** and **Error** logs.
    * **Undo/Redo:** Endless instances of undo/redo.
    * Tab/Shift+tab whole lines.
* **Navigation:**
    * **Boosted Scrollbar:** Hold shift for increased scrolling speed. Or ctrl for turbo boost 3:->
    * **Class/def Bookmarks:** Jump instantly from the sidebar list to the corresponding class node on the canvas and its definition in the console.
    * **Obliterate:** Dissipates the whole screen into oblivion.
* **GUI:**
    * Manually adjustable height of listbox bookmarks.
    * Autosave of all entries and layout to .json when closed.

## Known issues
* find nodes in canvas sometimes off due to zoom
* scrollbars glitching when resizing windows
* obliteration is heavy on CPU

## What would be great if it had
* debug console jumps to bug line via click

---

## Usage Instructions

### Open FIle/Folder

* opens filedialog -> choose .py file; if not selected -> choose folder
  
### Run Code

* compile and run with it's own debug console (white)

### Class/function bookmarks

* fetch class and def content of imported .py file (must be in OOP mode or render manually)

### Delete comments / Remove spaces

* removes #, ''' and """ comments from the code straight in edit mode (don't need to render)

 ### Save and render

* saves (like ctrl+s) and manually renders graph out of console without OOP mode
  
 ### Unused nodes

* Hidden nodes in canvas (left-clicked)

 ### Reset view

* Zoom/unzoom canvas via undo/redo.

## Prerequisites

Python 3.x and following modules:

import ast
import math
import threading
import subprocess
import re
import tempfile
import json
import queue
import time
import sys
import os

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import pydot

from PIL import ImageGrab, ImageTk, Image
import numpy as np
from numpy.fft import fft2, fftshift

---

### Hotkeys / Controls


* ctrl+Z / ctrl+shift+Z: Undo/Redo
* ctrl+t: obliterate/give up on your project
* ctrl+R: Recolor (refresh) text
* f5: run code
* ctrl+s: save file (overwrite without asking)
* ctrl+shift+s: save file as (opens filedialog)
* ctrl+f: search in text
* mousewheel: in canvas: zoom/unzoom; in text: scroll
* left-click on box in canvas: hide
* left-click on class/def in Bookmards: show (in text and in canvas)
* shift+mousewheel: 2x speed scrolling/zooming
* ctrl+mousewheel: 5x speed scrolling/zooming
* checkboxes:
   * Show Functions/Methods: Hide/unhide functions (def in root) and methods (def in class)
   * Show Functions/Methods: Hide/unhide functions (def in root) and methods (def in class)
   * OOP mode: automatically draws graph in real time while editing code
* layout: drag all nested windows and main window; minsize menu = 200px; minsize console = 700px; minsize canvas = 1px

