# AFCode


Custom Python compiler to help me orient myself in 10k lines of .py file. Currently designing game Anarchy Forever with that - thus the name AFCoder a.k.a Absolutely Fucking Compiler.

<img width="1598" height="980" alt="image" src="https://github.com/user-attachments/assets/6998bc06-394b-41c4-b56e-e4698c8f6eb6" />





---
## What it can do

* **OOP Structure Visualization:** Automatically generates a navigable, dependency graph of your Python project.
    * **Colored boxes** represent classes, functions, and files.
    * **Arrows** (lines) illustrate **dependencies** and **call relationships**.
    * zoom/unzoom, reset zoom, drag, quick find via bookmarked classes/defs, hover tooltips (arrows: where are they connecting to; boxes: content of def/class)
* **Code Runner:** Execute code directly from the console pane.
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
* **Navigation:**
    * **Boosted Scrollbar:** Hold shift for increased scrolling speed. Or ctrl for turbo boost 3:->
    * **Class/def Bookmarks:** Jump instantly from the sidebar list to the corresponding class node on the canvas and its definition in the console.
    * **Obliterate:** Dissipates the whole screen into oblivion.

---
## What it can't do

* compile/export straight to .exe via pyinstaller + settings
* nicely find canvas nodes via bookmarks (it can do that, but it's sketchy thanks to zooming)

---

## Prerequisites

Python 3.x and following modules:

* **`tkinter`** (Standard Library)
* **`subprocess`** (Standard Library)
* **`tempfile`** (Standard Library)
* **`os`** (Standard Library)
* **`json`** (Standard Library)
* **`scrolledtext`** (From `tkinter` module)

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
* 
 ### Unused nodes

* Hidden nodes in canvas (left-clicked)

 ### Reset view

* Zoom/unzoom canvas via undo/redo.


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
* checkboxes:
   * Show Functions/Methods: Hide/unhide functions (def in root) and methods (def in class)
   * Show Functions/Methods: Hide/unhide functions (def in root) and methods (def in class)
   * OOP mode: automatically draws graph in real time while editing code
* layout: drag all nested windows and main window; minsize menu = 200px; minsize console = 700px; minsize canvas = 1px

