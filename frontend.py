# frontend.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import ImageTk, Image
import pyperclip
import os
import sys

# Import the backend
from backend import Backend, ProjectData, APP_NAME

class App(ttk.Window):
    """
    Main application window for Vinted Seller Studio.
    
    Provides a GUI for managing clothing listings, processing images,
    generating descriptions, and preparing content for the Vinted marketplace.
    """
    def __init__(self, themename="solar"):
        """Initialize the application with the specified theme."""
        super().__init__(themename=themename)
        self._suppress_events = False
        
        try:
            if sys.platform.startswith('win'):
                # Determine base path (works for both script and executable)
                base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
                icon_path = os.path.join(base_path, "icon.ico")
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Icon error: {e}")

        try:
            self.backend = Backend()
            # Handle critical initialization errors if any
            if hasattr(self.backend, 'initialization_error') and self.backend.initialization_error:
                messagebox.showerror(
                    self.backend.lang.get("critical_error_title", "Critical Error"),
                    self.backend.initialization_error
                )
                self.destroy()
                sys.exit(1)

            self.lang = self.backend.lang
            if hasattr(self.backend, 'initialization_warning') and self.backend.initialization_warning:
                messagebox.showwarning(
                    self.lang.get("warning", "Warning"),
                    self.backend.initialization_warning
                )
        except Exception as e:
            messagebox.showerror("Startup Error", f"Failed to initialize application:\n{e}")
            self.destroy()
            sys.exit(1)

        self.title(self.lang.get("app_title", APP_NAME))
        if sys.platform.startswith('win'):
            self.state('zoomed')  # Maximize on Windows
        else:
            self.attributes('-zoomed', True)  # Maximize on Linux/others

        # Initialize state variables
        self.proc_image_widgets = []
        self.selected_processed_index = None
        self.tag_vars = {}
        self.tag_checkbuttons = {}
        self.color_vars = {}
        self.color_checkbuttons = {}
        self.measurement_entries = {}
        self.editor_window = None
        self.type_listbox = None
        self.tag_editor_listbox = None
        self.color_editor_listbox = None
        self.bg_combobox_map = {}
        self.editor_type_tag_vars = {}
        self.editor_type_tag_checkbuttons = {}

        # Create the GUI
        self._create_main_gui()
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

        # Initialize the first project if none exists
        if self.backend.get_project_count() == 0:
            new_index = self.backend.add_new_project(self.lang.get("new_project", "New Project"))
            self.backend.set_current_project_index(new_index)

        self._update_project_label()
        self.refresh_all_displays()

    # ====================== WINDOW LIFECYCLE ======================
    def _on_app_close(self):
        """Handle application closing: cleanup and destroy."""
        self.backend.cleanup_temp_dir()
        self.destroy()

    # ====================== MAIN GUI STRUCTURE ======================
    def _create_main_gui(self):
        """Create the main application GUI structure."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Top toolbar with buttons
        self._create_top_toolbar()
        
        # Main area with left panel and right notebook
        main_frame = ttk.Frame(self, padding="5 0 5 5")
        main_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=0, minsize=350)
        main_frame.grid_columnconfigure(1, weight=1)
        
        # Left container for controls
        self._create_left_panel(main_frame)
        
        # Right container with notebook
        self._create_right_panel(main_frame)

    def _create_top_toolbar(self):
        """Create the top toolbar with action buttons."""
        top_frame = ttk.Frame(self, padding="5 5 5 5")
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        
        # Configure columns for top_frame
        top_frame.columnconfigure(0, weight=0)  # Project navigation
        top_frame.columnconfigure(1, weight=1)  # Spacer
        top_frame.columnconfigure(2, weight=1)  # File operations
        top_frame.columnconfigure(3, weight=1)  # Processing
        top_frame.columnconfigure(4, weight=0)  # Settings
        
        # Project Navigation (Left)
        nav_frame = ttk.Frame(top_frame)
        nav_frame.grid(row=0, column=0, sticky="w")
        
        # Add new project and remove project buttons
        ttk.Button(
            nav_frame,
            text=self.lang.get("new_project_button", "➕ Project"),
            command=self.ui_add_new_project
        ).grid(row=0, column=0, padx=1)
        
        self.btn_prev_project = ttk.Button(nav_frame, text="<", command=self.prev_project, width=3)
        self.btn_prev_project.grid(row=0, column=1, padx=1)
        
        self.project_label_var = tk.StringVar()
        ttk.Label(nav_frame, textvariable=self.project_label_var, anchor="center", width=15).grid(row=0, column=2, padx=1)
        
        self.btn_next_project = ttk.Button(nav_frame, text=">", command=self.next_project, width=3)
        self.btn_next_project.grid(row=0, column=3, padx=1)
        
        ttk.Button(
            nav_frame,
            text=self.lang.get("remove_project_button", "🗑️ Project"),
            command=self.ui_remove_current_project
        ).grid(row=0, column=4, padx=1)
        
        # File Operations (Middle-Left)
        file_ops_frame = ttk.Frame(top_frame)
        file_ops_frame.grid(row=0, column=2, sticky="w")
        
        ttk.Button(
            file_ops_frame,
            text=self.lang.get("add_images_button", "➕ Images"),
            command=self.ui_load_single_project_images
        ).grid(row=0, column=0, padx=1)
        
        ttk.Button(
            file_ops_frame,
            text=self.lang.get("load_zip_button", "📦 Zip"),
            command=self.ui_load_projects_zip
        ).grid(row=0, column=1, padx=1)
        
        # Processing/Generate/Save (Middle-Right)
        process_frame = ttk.Frame(top_frame)
        process_frame.grid(row=0, column=3, sticky="we")
        
        # Add solid background color checkbox
        self.global_use_solid_bg_var = tk.BooleanVar(value=self.backend.use_solid_bg)
        ttk.Checkbutton(
            process_frame,
            text=self.lang.get("use_solid_bg", "Use solid background color"),
            variable=self.global_use_solid_bg_var,
            command=self._on_global_use_solid_bg_change
        ).grid(row=0, column=0, padx=(0, 10))
        
        ttk.Button(
            process_frame, 
            text=self.lang.get("process_images_button", "✨ Process"), 
            command=self.ui_process_current_project_images
        ).grid(row=0, column=1, padx=1)
        
        ttk.Button(
            process_frame, 
            text=self.lang.get("generate_desc_button", "📝 Generate"), 
            command=self.ui_generate_current_description
        ).grid(row=0, column=2, padx=1)
        
        ttk.Button(
            process_frame, 
            text=self.lang.get("save_output_button", "💾 Save"), 
            command=self.ui_save_current_project_output, 
            bootstyle="primary-outline"
        ).grid(row=0, column=3, padx=1)
        
        # Settings (Far Right)
        ttk.Button(
            top_frame, 
            text=self.lang.get("open_editor_button", "⚙️ Settings"), 
            command=self.open_editor_window
        ).grid(row=0, column=4, sticky="e", padx=(10, 0))

    def _create_left_panel(self, parent):
        """Create the left control panel with form fields."""
        left_container = ttk.Frame(parent)
        left_container.grid(row=0, column=0, sticky="ns", padx=(0, 5))
        left_container.grid_rowconfigure(0, weight=1)
        left_container.grid_rowconfigure(1, weight=0)
        left_container.grid_columnconfigure(0, weight=1)
        
        # Create a scrollable canvas for the controls
        self.left_control_canvas = tk.Canvas(left_container, borderwidth=0, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=self.left_control_canvas.yview)
        self.left_control_canvas.configure(yscrollcommand=left_scrollbar.set)
        self.left_control_canvas.grid(row=0, column=0, sticky="nsew")
        left_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Create a frame inside the canvas for the controls
        self.control_frame = ttk.Frame(self.left_control_canvas, padding="5")
        self.control_frame_id = self.left_control_canvas.create_window((0, 0), window=self.control_frame, anchor="nw")
        
        # Bind events for scrolling and resizing
        self.control_frame.bind("<Configure>", lambda e: self._on_frame_configure(self.left_control_canvas))
        self.left_control_canvas.bind("<Configure>", lambda e: self._on_canvas_configure(self.left_control_canvas, self.control_frame_id))
        self.left_control_canvas.bind("<Enter>", lambda e: self._bind_mousewheel(self.left_control_canvas))
        self.left_control_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        # Create the actual form controls
        self._create_left_controls(self.control_frame)
        
        # Add hint text at the bottom
        self.hint_label = ttk.Label(
            left_container, 
            text=self.lang.get("no_values_mandatory_hint", "*All fields are optional"), 
            font=("TkDefaultFont", 8, "italic"), 
            anchor="w"
        )
        self.hint_label.grid(row=1, column=0, sticky="ew", padx=5, pady=(5, 0))

    def _create_right_panel(self, parent):
        """Create the right panel with notebook tabs."""
        right_container = ttk.Frame(parent)
        right_container.grid(row=0, column=1, sticky="nsew")
        right_container.grid_rowconfigure(0, weight=1)
        right_container.grid_columnconfigure(0, weight=1)
        
        # Create notebook with tabs
        self.notebook = ttk.Notebook(right_container)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        
        # Create frames for each tab
        self.images_tab_frame = ttk.Frame(self.notebook, padding="5")
        self.description_tab_frame = ttk.Frame(self.notebook, padding="5")
        
        # Add frames to notebook
        self.notebook.add(
            self.images_tab_frame, 
            text=self.lang.get("images_tab", "🖼️ Images & Adjustments")
        )
        self.notebook.add(
            self.description_tab_frame, 
            text=self.lang.get("description_tab", "📝 Description")
        )
        
        # Create content for each tab
        self._create_images_tab(self.images_tab_frame)
        self._create_description_tab(self.description_tab_frame)

    # ====================== CANVAS HELPERS ======================
    def _on_frame_configure(self, canvas):
        """Update canvas scrollregion when the frame changes size."""
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        
        # Show/hide scrollbar based on content height
        content_height = canvas.winfo_height()
        canvas_height = canvas.winfo_height()
        scrollbar = canvas.master.children.get('!scrollbar')
        if scrollbar:
            if content_height <= canvas_height:
                scrollbar.grid_remove()
            else:
                scrollbar.grid()

    def _on_canvas_configure(self, canvas, frame_id):
        """Update the canvas item width when the canvas is resized."""
        if canvas and frame_id:
            canvas.itemconfig(frame_id, width=canvas.winfo_width())
            self._on_frame_configure(canvas)

    def _bind_mousewheel(self, widget):
        """Bind mousewheel events to the widget."""
        widget.bind_all("<MouseWheel>", lambda e, w=widget: self._on_mousewheel(e, w), add="+")

    def _unbind_mousewheel(self):
        """Unbind mousewheel events."""
        self.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event, widget):
        """Handle mousewheel scrolling for a widget."""
        if widget is None or not widget.winfo_exists():
            return
            
        scroll_delta = int(-1 * (event.delta / 120))
        
        if isinstance(widget, tk.Canvas):
            yview = widget.yview()
            if (scroll_delta < 0 and yview[0] > 0) or (scroll_delta > 0 and yview[1] < 1.0):
                widget.yview_scroll(scroll_delta, "units")
        elif isinstance(widget, (tk.Text, tk.Listbox)):
            widget.yview_scroll(scroll_delta, "units")

    # ====================== LEFT PANEL CONTROLS ======================
    def _create_left_controls(self, parent):
        """Create the form controls for the left panel."""
        parent.grid_columnconfigure(0, weight=1)
        row_index = 0
        
        # Clothing Type
        type_frame = ttk.LabelFrame(parent, text=self.lang.get("clothing_type", "Clothing Type:"), padding="5")
        type_frame.grid(row=row_index, column=0, sticky="ew", pady=(0, 5))
        type_frame.grid_columnconfigure(0, weight=1)
        
        self.clothing_type_var = tk.StringVar()
        self.clothing_type_combo = ttk.Combobox(type_frame, textvariable=self.clothing_type_var, state="readonly")
        self.clothing_type_combo.grid(row=0, column=0, sticky="ew")
        self.clothing_type_combo.bind("<<ComboboxSelected>>", self._on_clothing_type_changed)
        self._update_clothing_type_options()
        row_index += 1
        
        # Condition/State
        state_frame = ttk.LabelFrame(parent, text=self.lang.get("state", "Condition:"), padding="5")
        state_frame.grid(row=row_index, column=0, sticky="ew", pady=(0, 4))
        state_frame.grid_columnconfigure(0, weight=1)
        
        self.state_entry = ttk.Entry(state_frame)
        self.state_entry.grid(row=0, column=0, sticky="ew")
        self.state_entry.bind("<KeyRelease>", lambda e: self._save_current_form_to_backend())
        row_index += 1
        
        # Measurements
        self.measurement_lframe = ttk.LabelFrame(parent, text=self.lang.get("measurements", "Measurements:"), padding="5")
        self.measurement_lframe.grid(row=row_index, column=0, sticky="ew", pady=(0, 5))
        self.measurement_lframe.grid_columnconfigure(1, weight=1)
        row_index += 1
        
        # Custom Hashtags
        custom_frame = ttk.LabelFrame(parent, text=self.lang.get("custom_hashtags", "Custom Hashtags (#tag1, #tag2)"), padding="5")
        custom_frame.grid(row=row_index, column=0, sticky="ew", pady=(0, 5))
        custom_frame.grid_columnconfigure(0, weight=1)
        
        self.custom_hashtags_entry = ttk.Entry(custom_frame)
        self.custom_hashtags_entry.grid(row=0, column=0, sticky="ew")
        self.custom_hashtags_entry.bind("<KeyRelease>", lambda e: self._save_current_form_to_backend())
        row_index += 1
        
        # Tags
        self._create_tags_section(parent, row_index)
        row_index += 1
        
        # Colors section
        self._create_colors_section(parent, row_index)
        row_index += 1
        
        # Storage Info
        storage_frame = ttk.LabelFrame(parent, text=self.lang.get("storage_info", "Storage Info"), padding="5")
        storage_frame.grid(row=row_index, column=0, sticky="ew", pady=(0, 5))
        storage_frame.grid_columnconfigure(1, weight=0)
        
        ttk.Label(storage_frame, text=self.lang.get("owner_letter", "Owner Initial:")).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.owner_entry = ttk.Entry(storage_frame, width=10)
        self.owner_entry.grid(row=0, column=1, sticky="w", pady=2)
        self.owner_entry.bind("<KeyRelease>", lambda e: self._save_current_form_to_backend())
        
        ttk.Label(storage_frame, text=self.lang.get("storage_letter", "Storage Code:")).grid(row=1, column=0, sticky="w", padx=(0, 5))
        self.storage_entry = ttk.Entry(storage_frame, width=10)
        self.storage_entry.grid(row=1, column=1, sticky="w", pady=2)
        self.storage_entry.bind("<KeyRelease>", lambda e: self._save_current_form_to_backend())

    def _create_tags_section(self, parent, row_index):
        """Create the tags section with checkboxes."""
        tags_lframe = ttk.LabelFrame(parent, text=self.lang.get("tags", "Tags:"), padding="5")
        tags_lframe.grid(row=row_index, column=0, sticky="ew", pady=(0, 5))
        tags_lframe.grid_columnconfigure(0, weight=1)
        
        # Add search field
        self.tag_search_var = tk.StringVar()
        self.tag_search_entry = ttk.Entry(tags_lframe, textvariable=self.tag_search_var, width=30)
        self.tag_search_entry.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.tag_search_entry.bind("<KeyRelease>", self._filter_tags_display)
        self.tag_search_entry.bind("<FocusIn>", 
                                lambda e: self._on_entry_focus_in(
                                    self.tag_search_entry, 
                                    self.lang.get("search_placeholder", "🔍 Search...")
                                ))
        self._add_placeholder(self.tag_search_entry, self.lang.get("search_placeholder", "🔍 Search..."))
        
        # Create scrollable container for checkboxes
        tags_canvas_frame = ttk.Frame(tags_lframe)
        tags_canvas_frame.grid(row=1, column=0, sticky="nsew")
        tags_canvas_frame.grid_rowconfigure(0, weight=1)
        tags_canvas_frame.grid_columnconfigure(0, weight=1)
        
        self.tags_canvas = tk.Canvas(tags_canvas_frame, borderwidth=0, highlightthickness=0, height=200)
        tags_scrollbar = ttk.Scrollbar(tags_canvas_frame, orient='vertical', command=self.tags_canvas.yview)
        self.tags_canvas.configure(yscrollcommand=tags_scrollbar.set)
        self.tags_canvas.grid(row=0, column=0, sticky="nsew")
        tags_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Create frame for checkboxes
        self.tags_check_container = ttk.Frame(self.tags_canvas, padding=(5, 0))
        self.tags_check_container_id = self.tags_canvas.create_window((0, 0), window=self.tags_check_container, anchor='nw')
        
        # Bind events
        self.tags_check_container.bind("<Configure>", lambda e: self._update_canvas_scrollregion(self.tags_canvas))
        self.tags_canvas.bind("<Configure>", lambda e: self._update_canvas_itemwidth(self.tags_canvas, self.tags_check_container_id, e.width))
        self.tags_canvas.bind("<Enter>", lambda e: self._bind_mousewheel(self.tags_canvas))
        self.tags_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        # Create tag checkboxes
        self._create_tag_checkboxes()

    def _create_colors_section(self, parent, row_index):
        """Create the colors section with checkboxes."""
        colors_lframe = ttk.LabelFrame(parent, text=self.lang.get("colors_tab", "🎨 Colors"), padding="5")
        colors_lframe.grid(row=row_index, column=0, sticky="ew", pady=(0, 5))
        colors_lframe.grid_columnconfigure(0, weight=1)

        # Add search field
        self.color_search_var = tk.StringVar()
        self.color_search_entry = ttk.Entry(colors_lframe, textvariable=self.color_search_var, width=30)
        self.color_search_entry.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.color_search_entry.bind("<KeyRelease>", self._filter_colors_display)
        self.color_search_entry.bind("<FocusIn>", 
                                  lambda e: self._on_entry_focus_in(
                                      self.color_search_entry, 
                                      self.lang.get("search_placeholder", "🔍 Search...")
                                  ))
        self._add_placeholder(self.color_search_entry, self.lang.get("search_placeholder", "🔍 Search..."))

        # Create scrollable container for checkboxes
        colors_canvas_frame = ttk.Frame(colors_lframe)
        colors_canvas_frame.grid(row=1, column=0, sticky="nsew")
        colors_canvas_frame.grid_rowconfigure(0, weight=1)
        colors_canvas_frame.grid_columnconfigure(0, weight=1)

        self.colors_canvas = tk.Canvas(colors_canvas_frame, borderwidth=0, highlightthickness=0, height=150)
        colors_scrollbar = ttk.Scrollbar(colors_canvas_frame, orient='vertical', command=self.colors_canvas.yview)
        self.colors_canvas.configure(yscrollcommand=colors_scrollbar.set)
        self.colors_canvas.grid(row=0, column=0, sticky="nsew")
        colors_scrollbar.grid(row=0, column=1, sticky="ns")

        # Create frame for checkboxes
        self.colors_check_container = ttk.Frame(self.colors_canvas, padding=(5, 0))
        self.colors_check_container_id = self.colors_canvas.create_window((0, 0), window=self.colors_check_container, anchor='nw')
        
        # Bind events
        self.colors_check_container.bind("<Configure>", lambda e: self._update_canvas_scrollregion(self.colors_canvas))
        self.colors_canvas.bind("<Configure>", lambda e: self._update_canvas_itemwidth(self.colors_canvas, self.colors_check_container_id, e.width))
        self.colors_canvas.bind("<Enter>", lambda e: self._bind_mousewheel(self.colors_canvas))
        self.colors_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())

        # Create color checkboxes
        self._create_color_checkboxes()

    # ====================== IMAGES TAB ======================
    def _create_images_tab(self, parent):
        """Create the images tab content."""
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        # Create scrollable canvas for image display
        self.img_canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        img_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.img_canvas.yview)
        self.img_canvas.configure(yscrollcommand=img_scrollbar.set)
        self.img_canvas.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        img_scrollbar.grid(row=0, column=1, sticky="ns", pady=(0, 5))
        
        # Create frame for image display
        self.img_display_frame = ttk.Frame(self.img_canvas, padding="5")
        self.img_display_frame_id = self.img_canvas.create_window((0, 0), window=self.img_display_frame, anchor="nw")
        
        # Bind events
        self.img_display_frame.bind("<Configure>", lambda e: self._on_frame_configure(self.img_canvas))
        self.img_canvas.bind("<Configure>", lambda e: self._on_canvas_configure(self.img_canvas, self.img_display_frame_id))
        self.img_canvas.bind("<Enter>", lambda e: self._bind_mousewheel(self.img_canvas))
        self.img_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        # Create adjustment controls
        self._create_adjustment_controls(parent)

    def _create_adjustment_controls(self, parent):
        """Create the image adjustment controls."""
        adj_frame = ttk.LabelFrame(
            parent, 
            text=self.lang.get("adjustments_label", "Adjust Selected Image"), 
            padding="10"
        )
        adj_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        adj_frame.grid_columnconfigure(1, weight=1)
        row = 0
        
        # Background selection
        ttk.Label(adj_frame, text=self.lang.get("background_select_label", "Background Image:")).grid(
            row=row, column=0, sticky="w", pady=2
        )
        self.bg_select_var = tk.StringVar()
        self.bg_select_combo = ttk.Combobox(
            adj_frame, textvariable=self.bg_select_var, state="readonly", width=30
        )
        self.bg_select_combo.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
        self.bg_select_combo.bind("<<ComboboxSelected>>", self._on_bg_selection_change)
        self._update_bg_selector_options()
        row += 1
        
        # Background ratio checkbox
        self.bg_ratio_var = tk.BooleanVar()
        bg_ratio_check = ttk.Checkbutton(
            adj_frame,
            text=self.lang.get("background_ratio_label", "Use Horizontal (4:3) Ratio"),
            variable=self.bg_ratio_var,
            command=self._on_checkbox_change
        )
        bg_ratio_check.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        # Preserve object checkbox
        self.skip_bg_removal_var = tk.BooleanVar(value=False)
        skip_bg_check = ttk.Checkbutton(
            adj_frame,
            text=self.lang.get("preserve_object", "Preserve object (skip background removal)"),
            variable=self.skip_bg_removal_var,
            command=self._on_checkbox_change
        )
        skip_bg_check.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        # Solid background checkbox
        self.item_use_solid_bg_var = tk.BooleanVar(value=False)
        solid_bg_check = ttk.Checkbutton(
            adj_frame,
            text=self.lang.get("use_solid_bg", "Use solid background color"),
            variable=self.item_use_solid_bg_var,
            command=self._on_checkbox_change
        )
        solid_bg_check.grid(row=row, column=1, sticky="w", padx=5, pady=2)
        row += 1
        
        # Vertical position slider
        ttk.Label(adj_frame, text=self.lang.get("vertical_offset_factor", "Vertical Position:")).grid(
            row=row, column=0, sticky="w", pady=1
        )
        self.slider_vof = ttk.Scale(
            adj_frame, 
            from_=-1.0, 
            to=1.0, 
            orient="horizontal",
            length=200,
            value=0.0,
            command=self._on_slider_change
        )
        self.slider_vof.grid(row=row, column=1, sticky="ew", padx=5, pady=1)
        self.label_vof = ttk.Label(adj_frame, text="+0.00")
        self.label_vof.grid(row=row, column=2, sticky="w", padx=5, pady=1)
        row += 1

        # Horizontal position slider
        ttk.Label(adj_frame, text=self.lang.get("horizontal_offset_factor", "Horizontal Position:")).grid(
            row=row, column=0, sticky="w", pady=1
        )
        self.slider_hof = ttk.Scale(
            adj_frame, 
            from_=-1.0, 
            to=1.0, 
            orient="horizontal",
            length=200,
            value=0.0,
            command=self._on_slider_change
        )
        self.slider_hof.grid(row=row, column=1, sticky="ew", padx=5, pady=1)
        self.label_hof = ttk.Label(adj_frame, text="+0.00")
        self.label_hof.grid(row=row, column=2, sticky="w", padx=5, pady=1)
        row += 1

        # Size slider
        ttk.Label(adj_frame, text=self.lang.get("size_scale_factor", "Size:")).grid(
            row=row, column=0, sticky="w", pady=1
        )
        self.slider_scale = ttk.Scale(
            adj_frame, 
            from_=0.5, 
            to=2.0, 
            orient="horizontal",
            length=200,
            value=1.0,
            command=self._on_slider_change
        )
        self.slider_scale.grid(row=row, column=1, sticky="ew", padx=5, pady=1)
        self.label_scale = ttk.Label(adj_frame, text="1.0×")
        self.label_scale.grid(row=row, column=2, sticky="w", padx=5, pady=1)

    # ====================== DESCRIPTION TAB ======================
    def _create_description_tab(self, parent):
        """Create the description tab content."""
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        
        # Text area for description
        self.desc_text = tk.Text(parent, height=15, width=60, wrap="word", relief="solid", borderwidth=1)
        desc_scroll = ttk.Scrollbar(parent, orient="vertical", command=self.desc_text.yview)
        self.desc_text.configure(yscrollcommand=desc_scroll.set)
        self.desc_text.grid(row=0, column=0, sticky="nsew", pady=(0, 5))
        desc_scroll.grid(row=0, column=1, sticky="ns", pady=(0, 5))
        self.desc_text.bind("<KeyRelease>", lambda e: self._save_current_form_to_backend())
        self.desc_text.bind("<Enter>", lambda e: self._bind_mousewheel(self.desc_text))
        self.desc_text.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        # Copy button
        copy_btn = ttk.Button(
            parent, 
            text=self.lang.get("copy_desc_button", "✂️ Copy Description"), 
            command=self.ui_copy_description
        )
        copy_btn.grid(row=1, column=0, columnspan=2, pady=(5, 0))

    # ====================== HELPER METHODS ======================
    def _update_canvas_scrollregion(self, canvas):
        """Update the scrollregion of a canvas to match its contents."""
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _update_canvas_itemwidth(self, canvas, item_id, width):
        """Update the width of a canvas item."""
        canvas.itemconfig(item_id, width=width)

    def _add_placeholder(self, entry, placeholder):
        """Add placeholder text to an entry widget."""
        entry.insert(0, placeholder)
        entry.config(foreground="grey")
        entry.bind("<FocusIn>", lambda args: self._on_entry_focus_in(entry, placeholder), add='+')
        entry.bind("<FocusOut>", lambda args: self._on_entry_focus_out(entry, placeholder), add='+')

    def _on_entry_focus_in(self, entry, placeholder):
        """Handle entry focus in - clear placeholder text."""
        current_text = entry.get()
        if current_text == placeholder:
            entry.delete(0, tk.END)
            entry.config(foreground=self.style.lookup('TEntry', 'foreground'))

    def _on_entry_focus_out(self, entry, placeholder):
        """Handle entry focus out - restore placeholder if empty."""
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(foreground="grey")

    def _get_color_from_name(self, color_name):
        """Get a hex color value from a color name."""
        color_name = color_name.lower()
        color_map = {
            "red": "#ff0000", "green": "#00ff00", "blue": "#0000ff",
            "yellow": "#ffff00", "orange": "#ffa500", "purple": "#800080",
            "pink": "#ffc0cb", "brown": "#a52a2a", "black": "#000000",
            "white": "#ffffff", "grey": "#808080", "gray": "#808080",
            "turquoise": "#40e0d0"
        }
        
        for key, value in color_map.items():
            if key in color_name:
                return value
        return "#cccccc"

    def _refresh_listbox_with_search(self, listbox, search_var, items, new_button_text, preserve_selection=True):
        """
        Refresh a listbox with filtered items based on search text.
        
        Args:
            listbox: The listbox to refresh
            search_var: StringVar containing search text
            items: List of all possible items
            new_button_text: Text for the "New" item at the end
            preserve_selection: Whether to preserve the current selection
            
        Returns:
            list: The items that were added to the listbox
        """
        if not listbox:
            return []
            
        # Remember current selection if needed
        current_selection = None
        if preserve_selection:
            sel = listbox.curselection()
            if sel:
                current_selection = listbox.get(sel[0])
                
        # Clear the listbox
        listbox.delete(0, tk.END)
        
        # Get search term, ignore if it's the placeholder
        search_term = search_var.get().strip().lower()
        placeholder = self.lang.get("search_placeholder", "🔍 Search...").lower()
        if search_term == placeholder or not search_term:
            search_term = ""
            
        # Add filtered items
        added_items = []
        for item in sorted(items):
            if search_term == "" or search_term in item.lower():
                listbox.insert(tk.END, item)
                added_items.append(item)
                
        # Add the "New" button at the end
        listbox.insert(tk.END, new_button_text)
        added_items.append(new_button_text)
        
        # Restore selection or select first item
        selection_index = 0
        if current_selection and current_selection in added_items:
            selection_index = added_items.index(current_selection)
            
        if listbox.size() > 0:
            listbox.selection_set(selection_index)
            listbox.see(selection_index)
            listbox.activate(selection_index)
            
        listbox.update_idletasks()
        return added_items

    # ====================== TAG & COLOR METHODS ======================
    def _create_tag_checkboxes(self):
        """Create checkboxes for each known tag."""
        for widget in self.tags_check_container.winfo_children():
            widget.destroy()
            
        self.tag_vars.clear()
        self.tag_checkbuttons.clear()
        
        # Filter out color tags (those ending with " color")
        sorted_tags = sorted([tag for tag in self.backend.hashtag_mapping.keys() 
                            if not tag.endswith(" color")])
        
        self.tags_check_container.grid_columnconfigure(0, weight=1)
        row_num = 0
        
        for tag in sorted_tags:
            var = tk.BooleanVar(value=False)
            self.tag_vars[tag] = var
            
            c = ttk.Checkbutton(
                self.tags_check_container, 
                text=tag, 
                variable=var, 
                command=self._on_tag_checkbox_changed
            )
            c.grid(row=row_num, column=0, sticky="w", pady=1)
            self.tag_checkbuttons[tag] = c
            row_num += 1
            
        self.tags_check_container.update_idletasks()
        self._update_canvas_scrollregion(self.tags_canvas)
        self.tags_canvas.yview_moveto(0)
        
        # Show all tags by default
        self._filter_tags_display()

    def _filter_tags_display(self, event=None):
        """Filter tag checkboxes based on search text."""
        if not hasattr(self, 'tag_search_entry'):
            return
            
        search_term = self.tag_search_var.get().lower().strip()
        placeholder = self.lang.get("search_placeholder", "🔍 Search...").lower()
        
        # Check if text is placeholder or empty
        is_placeholder = search_term == placeholder.lower() and self.tag_search_entry.cget('foreground') == "grey"
        show_all = not search_term or is_placeholder
        row_num = 0
        
        # Always show all tags on initial load
        if event is None:
            show_all = True
            
        for tag, cb in self.tag_checkbuttons.items():
            if show_all or search_term in tag.lower():
                cb.grid(row=row_num, column=0, sticky="w", pady=1)
                row_num += 1
            else:
                cb.grid_forget()
                
        self.tags_check_container.update_idletasks()
        self._update_canvas_scrollregion(self.tags_canvas)
        self.tags_canvas.yview_moveto(0)

    def _on_tag_checkbox_changed(self):
        """Handle tag checkbox state change."""
        self._save_current_form_to_backend()

    def _create_color_checkboxes(self):
        """Create checkboxes for each color with a color swatch."""
        for widget in self.colors_check_container.winfo_children():
            widget.destroy()
            
        self.color_vars.clear()
        self.color_checkbuttons.clear()
        
        # Get only color tags
        color_tags = [tag for tag in self.backend.hashtag_mapping.keys() if tag.endswith(" color")]
        sorted_colors = sorted(color_tags)
        
        self.colors_check_container.grid_columnconfigure(0, weight=1)
        
        row_num = 0
        for color in sorted_colors:
            var = tk.BooleanVar(value=False)
            self.color_vars[color] = var
            
            display_name = color.replace(" color", "")
            
            color_frame = ttk.Frame(self.colors_check_container)
            color_frame.grid(row=row_num, column=0, sticky="ew", pady=1)
            color_frame.grid_columnconfigure(0, weight=1)
            
            c = ttk.Checkbutton(
                color_frame, 
                text=display_name, 
                variable=var, 
                command=self._on_color_checkbox_changed
            )
            c.grid(row=0, column=0, sticky="w")
            self.color_checkbuttons[color] = c
            
            # Add color swatch
            preview_color = self._get_color_from_name(display_name)
            color_swatch = tk.Canvas(color_frame, width=15, height=15, bd=1, relief="solid")
            color_swatch.configure(bg=preview_color)
            color_swatch.grid(row=0, column=1, padx=(3, 0), pady=0, sticky="e")
            
            row_num += 1
            
        # Initially show all colors
        self._filter_colors_display()

    def _filter_colors_display(self, event=None):
        """Filter color checkboxes based on search text."""
        if not hasattr(self, 'color_search_entry'):
            return
            
        search_term = self.color_search_var.get().lower().strip()
        placeholder = self.lang.get("search_placeholder", "🔍 Search...").lower()
        
        # Check if text is placeholder or empty
        is_placeholder = search_term == placeholder.lower() and self.color_search_entry.cget('foreground') == "grey"
        show_all = not search_term or is_placeholder
        row_num = 0
        
        # Always show all colors on initial load
        if event is None:
            show_all = True
            
        for color, cb in self.color_checkbuttons.items():
            display_name = color.replace(" color", "").lower()
            if show_all or search_term in display_name:
                # Show parent frame containing checkbox and swatch
                parent_frame = cb.master
                parent_frame.grid(row=row_num, column=0, sticky="ew", pady=1)
                row_num += 1
            else:
                # Hide parent frame
                cb.master.grid_forget()
                
        self.colors_check_container.update_idletasks()
        self._update_canvas_scrollregion(self.colors_canvas)
        self.colors_canvas.yview_moveto(0)

    def _on_color_checkbox_changed(self):
        """Handle color checkbox state change."""
        self._save_current_form_to_backend()

    # ====================== FORM HANDLING ======================
    def _update_clothing_type_options(self):
        """Update the clothing type dropdown options."""
        options = [""] + sorted(list(self.backend.templates.keys()))
        current_val = self.clothing_type_var.get()
        self.clothing_type_combo['values'] = options
        
        # If current value isn't in the new options, clear it
        if current_val not in options:
            self.clothing_type_var.set(options[0] if options else "")
            
        self.clothing_type_combo.set(self.clothing_type_var.get())

    def _on_clothing_type_changed(self, event=None):
        """Handle clothing type selection change."""
        new_type = self.clothing_type_var.get()
        proj = self.backend.get_current_project()
        
        if not proj or proj.clothing_type == new_type:
            return
            
        self._save_current_form_to_backend()
        self._update_measurement_fields_display(new_type)
        
        # Set default tags based on the selected type
        default_tags = self.backend.templates.get(new_type, {}).get("default_tags", [])
        changed_tags = False
        
        for dt in default_tags:
            if dt in self.tag_vars and not self.tag_vars[dt].get():
                self.tag_vars[dt].set(True)
                changed_tags = True
                
        if changed_tags:
            self._save_current_form_to_backend(update_type=new_type)
        else:
            self.backend.update_project_data(self.backend.get_current_project_index(), {'clothing_type': new_type})
            
        self.refresh_left_controls_display()

    def _update_measurement_fields_display(self, clothing_type):
        """Update the measurement fields based on clothing type."""
        # Clear the measurement frame
        for widget in self.measurement_lframe.winfo_children():
            if isinstance(widget, (ttk.Entry, ttk.Label)):
                widget.destroy()
                
        self.measurement_entries = {}
        
        # If no clothing type, just return (frame will be hidden)
        if not clothing_type:
            return
            
        fields = self.backend.templates.get(clothing_type, {}).get("fields", [])
        proj = self.backend.get_current_project()
        row_num = 0
        
        for field in fields:
            ttk.Label(self.measurement_lframe, text=field + ":").grid(
                row=row_num, column=0, sticky="w", padx=(0, 5), pady=2
            )
            entry = ttk.Entry(self.measurement_lframe)
            entry.grid(row=row_num, column=1, sticky="ew", pady=2)
            
            if proj:
                entry.insert(tk.END, proj.measurements.get(field, ""))
                
            entry.bind("<KeyRelease>", lambda e, f=field: self._save_current_form_to_backend())
            entry.bind("<Return>", self._focus_next_widget)
            self.measurement_entries[field] = entry
            row_num += 1

    def _focus_next_widget(self, event):
        """Move focus to the next widget on Enter key."""
        event.widget.tk_focusNext().focus()
        return "break"  # Prevent default behavior

    def _save_current_form_to_backend(self, update_type=None):
        """Save the current form data to the backend."""
        idx = self.backend.get_current_project_index()
        if idx < 0:
            return
            
        # Get selected tags and colors
        selected_tags = [tag for tag, var in self.tag_vars.items() if var.get()]
        selected_colors = [color for color, var in self.color_vars.items() if var.get()]
        
        # Combine for backend storage
        all_selected_tags = selected_tags + selected_colors
        
        proj_data = {
            "clothing_type": update_type if update_type is not None else self.clothing_type_var.get(),
            "state": self.state_entry.get(),
            "measurements": {field: entry.get() for field, entry in self.measurement_entries.items()},
            "selected_tags": all_selected_tags,
            "custom_hashtags": self.custom_hashtags_entry.get(),
            "generated_description": self.desc_text.get(1.0, tk.END).strip(),
            "owner_letter": self.owner_entry.get(),
            "storage_letter": self.storage_entry.get()
        }
            
        self.backend.update_project_data(idx, proj_data)

    # ====================== UI DISPLAY UPDATES ======================
    def refresh_all_displays(self):
        """Refresh all UI elements with current data."""
        self.refresh_left_controls_display()
        self.refresh_right_display()
        self._update_project_label()

    def refresh_left_controls_display(self):
        """Refresh the left panel controls with current project data."""
        proj = self.backend.get_current_project()
        has_proj = proj is not None
        has_clothing_type = has_proj and proj.clothing_type
        
        # Update hint label
        self.hint_label.config(
            text=self.lang.get("no_values_mandatory_hint", "*All fields are optional") if has_proj else ""
        )
        
        # Update clothing type selector
        self._update_clothing_type_options()
        self.clothing_type_var.set(proj.clothing_type if has_proj else "")
        
        # Update state field
        state_val = proj.state if has_proj else ""
        if self.state_entry.get() != state_val:
            self.state_entry.delete(0, tk.END)
            self.state_entry.insert(tk.END, state_val)
        
        # Show/hide measurement frame based on clothing type
        if has_clothing_type:
            self.measurement_lframe.grid(row=2, column=0, sticky="ew", pady=(0, 5))
            self._update_measurement_fields_display(proj.clothing_type)
        else:
            self.measurement_lframe.grid_remove()  # Hide the frame
            
        # Update tag checkboxes
        if not hasattr(self, 'tag_vars') or not self.tag_vars:
            self._create_tag_checkboxes()
        else:
            for tag, var in self.tag_vars.items():
                var.set(has_proj and tag in proj.selected_tags)
            self._filter_tags_display()
        
        # Update color checkboxes
        if hasattr(self, 'color_vars'):
            for color, var in self.color_vars.items():
                var.set(has_proj and color in proj.selected_tags)
            self._filter_colors_display()
            
        # Update custom hashtags field
        custom_val = proj.custom_hashtags if has_proj else ""
        if self.custom_hashtags_entry.get() != custom_val:
            self.custom_hashtags_entry.delete(0, tk.END)
            self.custom_hashtags_entry.insert(tk.END, custom_val)
            
        # Update owner and storage fields
        owner_val = proj.owner_letter if has_proj else ""
        if self.owner_entry.get() != owner_val:
            self.owner_entry.delete(0, tk.END)
            self.owner_entry.insert(tk.END, owner_val)
            
        storage_val = proj.storage_letter if has_proj else ""
        if self.storage_entry.get() != storage_val:
            self.storage_entry.delete(0, tk.END)
            self.storage_entry.insert(tk.END, storage_val)

    def refresh_right_display(self):
        """Refresh the right panel display with current project data."""
        proj = self.backend.get_current_project()
        
        # Clear current image display
        for widget in self.img_display_frame.winfo_children():
            widget.destroy()
            
        self.proc_image_widgets = []
        display_placeholder = True
        previous_selection = self.selected_processed_index
        
        if proj and proj.clothing_images:
            display_placeholder = False
            max_cols = 3
            col_num = 0
            row_num = 0
            
            # Configure grid columns
            for c in range(max_cols):
                self.img_display_frame.grid_columnconfigure(c, weight=1, uniform="imgCol")
                
            # Create widgets for each image
            for i, img_data in enumerate(proj.clothing_images):
                item_frame = ttk.Frame(self.img_display_frame, relief="groove", borderwidth=1, padding=5)
                item_frame.grid(row=row_num, column=col_num, padx=5, pady=5, sticky="nsew")
                item_frame.grid_columnconfigure(0, weight=1)
                
                # Add image controls
                img_control_frame = ttk.Frame(item_frame)
                img_control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
                img_control_frame.grid_columnconfigure(0, weight=1)
                
                # Add remove button
                ttk.Button(
                    img_control_frame, 
                    text=self.lang.get("remove_image_button", "🗑️"), 
                    width=3,
                    command=lambda idx=i: self.ui_remove_image(idx)
                ).grid(row=0, column=1, sticky="e")
                
                # Display original image thumbnail
                try:
                    orig_thumb = img_data["image"].copy()
                    orig_thumb.thumbnail((150, 150))
                    orig_photo = ImageTk.PhotoImage(orig_thumb)
                    orig_lbl = ttk.Label(item_frame, image=orig_photo)
                    orig_lbl.image = orig_photo
                    orig_lbl.grid(row=0, column=0, pady=(0, 5))
                except Exception as e:
                    print(f"Thumbnail Error (Original) {i}: {e}")
                    ttk.Label(item_frame, text="Error loading image").grid(row=0, column=0, pady=(0, 5))
                    
                # Display processed image if available
                if i < len(proj.processed_images):
                    proc_item = proj.processed_images[i]
                    try:
                        processed_img = proc_item["processed"]
                        thumb_w, thumb_h = (200, 150) if proc_item.get("is_horizontal", False) else (150, 200)
                        proc_thumb = processed_img.copy()
                        proc_thumb.thumbnail((thumb_w, thumb_h))
                        proc_photo = ImageTk.PhotoImage(proc_thumb)
                        proc_lbl = ttk.Label(
                            item_frame, 
                            image=proc_photo, 
                            cursor="hand2", 
                            relief="solid", 
                            borderwidth=1
                        )
                        proc_lbl.image = proc_photo
                        proc_lbl.grid(row=1, column=0)
                        proc_lbl.bind("<Button-1>", lambda e, idx=i: self._on_processed_image_click(idx))
                        self.proc_image_widgets.append({"label": proc_lbl, "photo": proc_photo, "index": i})
                    except Exception as e:
                        print(f"Thumbnail Error (Processed) {i}: {e}")
                        ttk.Label(item_frame, text="Error loading processed image").grid(row=1, column=0)
                else:
                    ttk.Label(
                        item_frame, 
                        text=self.lang.get("not_processed", "(Not Processed)")
                    ).grid(row=1, column=0)
                    
                # Move to next column or row
                col_num = (col_num + 1) % max_cols
                if col_num == 0:
                    row_num += 1
                    
        # Show placeholder if no images
        if display_placeholder or not proj:
            msg = (self.lang.get("no_project", "No project loaded or selected.") if not proj else 
                   self.lang.get("no_images_in_project", "No clothing images loaded for this project."))
            ttk.Label(self.img_display_frame, text=msg).grid()
            self.selected_processed_index = None
        elif self.selected_processed_index is not None and self.selected_processed_index >= len(proj.processed_images):
            self.selected_processed_index = None
        
        # Force layout update
        if self.proc_image_widgets:
            self.update_idletasks()
        
        # Highlight the selected image if any
        need_highlight = (self.selected_processed_index is not None and self.proc_image_widgets)
        if need_highlight:
            self._highlight_selected_processed()
            
        # Update adjustment fields
        self._populate_adjustment_fields()
        
        # Update the canvas scrollregion
        self.img_display_frame.update_idletasks()
        self._update_canvas_scrollregion(self.img_canvas)
        
        # Update description text
        current_desc_text = self.desc_text.get(1.0, tk.END).strip()
        backend_desc = proj.generated_description if proj else ""
        
        if current_desc_text != backend_desc:
            self.desc_text.delete(1.0, tk.END)
            self.desc_text.insert(tk.END, backend_desc)

    def _update_project_label(self):
        """Update the project navigation label."""
        i = self.backend.get_current_project_index()
        total = self.backend.get_project_count()
        lbl = self.lang.get('project_label', 'Project')
        self.project_label_var.set(f"{lbl} {i+1} of {total}" if total > 0 else f"{lbl} 0 of 0")

    def _highlight_selected_processed(self):
        """Highlight the selected image with a thicker border."""
        if not self.proc_image_widgets or self.selected_processed_index is None:
            return
            
        selected_border = 4      # Thicker border for selected images
        normal_border = 1        # Thin border for unselected images
        
        for widget_info in self.proc_image_widgets:
            lbl = widget_info["label"]
            idx = widget_info["index"]
            
            if idx == self.selected_processed_index:
                lbl.configure(relief="solid", borderwidth=selected_border)
            else:
                lbl.configure(relief="solid", borderwidth=normal_border)

    def _update_bg_selector_options(self):
        """Update the background selector dropdown options."""
        self.bg_combobox_map.clear()
        auto_option = self.lang.get("auto_background_option", "Auto (Default)")
        options = [auto_option]
        self.bg_combobox_map[auto_option] = None
        
        # Add all background options
        for bg_path in self.backend.backgrounds:
            display_name = os.path.basename(bg_path)
            options.append(display_name)
            self.bg_combobox_map[display_name] = bg_path
            
        # Set values and maintain current selection if possible
        current_val = self.bg_select_var.get()
        self.bg_select_combo['values'] = options
        
        if current_val in options:
            self.bg_select_var.set(current_val)
        else:
            self.bg_select_var.set(auto_option)

    def _populate_adjustment_fields(self):
        """Update adjustment fields with values from the selected image."""
        # Set flag to suppress events while updating controls
        self._suppress_events = True
        
        proj = self.backend.get_current_project()
        if proj and self.selected_processed_index is not None and 0 <= self.selected_processed_index < len(proj.processed_images):
            item = proj.processed_images[self.selected_processed_index]
            
            # Set position adjustments to sliders
            self.slider_vof.set(item["vof"])
            self.slider_hof.set(item["hof"])
            self.slider_scale.set(item["scale"])
            
            # Update the slider labels
            vof_val = round(float(self.slider_vof.get()), 2)
            hof_val = round(float(self.slider_hof.get()), 2)
            scale_val = round(float(self.slider_scale.get()), 2)
            self.label_vof.config(text=f"{vof_val:+.2f}")
            self.label_hof.config(text=f"{hof_val:+.2f}")
            self.label_scale.config(text=f"{scale_val:.1f}×")
            
            # Set checkbox states
            skip_bg = item.get("skip_bg_removal", False)
            self.skip_bg_removal_var.set(skip_bg)
            
            use_solid_bg = item.get("use_solid_bg", False)
            self.item_use_solid_bg_var.set(use_solid_bg)
            
            # Set ratio and background selection
            self.bg_ratio_var.set(item.get("is_horizontal", False))
            
            # Update background selector
            self._update_bg_selector_options()
            
            # Set the selected background
            selected_bg_key = self.lang.get("auto_background_option", "Auto (Default)")
            user_choice = item.get("user_bg_path")
            
            if user_choice is not None:
                for display_name, full_path in self.bg_combobox_map.items():
                    if full_path == user_choice:
                        selected_bg_key = display_name
                        break
                        
            self.bg_select_var.set(selected_bg_key)
        else:
            # Clear all fields if no image selected
            self.slider_vof.set(0.0)
            self.slider_hof.set(0.0)
            self.slider_scale.set(1.0)
            self.label_vof.config(text="+0.00")
            self.label_hof.config(text="+0.00")
            self.label_scale.config(text="1.0×")
            self.skip_bg_removal_var.set(False)
            self.item_use_solid_bg_var.set(False)
            self.bg_ratio_var.set(False)
            self._update_bg_selector_options()
            self.bg_select_var.set(self.lang.get("auto_background_option", "Auto (Default)"))
        
        # Allow a brief delay to ensure all controls are updated before re-enabling events
        self.after(50, self._reenable_events)

    # ====================== EVENT HANDLERS ======================
    def _reenable_events(self):
        """Re-enable event handling after populating controls."""
        self._suppress_events = False
        
    def _on_global_use_solid_bg_change(self):
        """Handle global solid background setting change."""
        use_solid = self.global_use_solid_bg_var.get()
        current_config = self.backend.config_data.copy()
        current_config["use_solid_bg"] = use_solid
        
        # Save setting to backend
        if self.backend.save_main_config(current_config):
            # Update any UI elements that depend on this setting
            self._update_bg_selector_options()

    def _on_slider_change(self, value):
        """Handle adjustment slider change events."""
        # Skip processing if events are suppressed
        if self._suppress_events:
            return
            
        # Round values for display
        vof_val = round(float(self.slider_vof.get()), 2)
        hof_val = round(float(self.slider_hof.get()), 2)
        scale_val = round(float(self.slider_scale.get()), 2)
        
        # Update the labels
        self.label_vof.config(text=f"{vof_val:+.2f}")
        self.label_hof.config(text=f"{hof_val:+.2f}")
        self.label_scale.config(text=f"{scale_val:.1f}×")
        
        # Apply changes immediately
        self.ui_apply_adjustments()

    def _on_checkbox_change(self):
        """Handle checkbox state changes in adjustment panel."""
        if self._suppress_events:
            return
        # Allow the checkbox to visually update first
        self.after(50, lambda: self._process_with_indicator(self.ui_apply_adjustments))

    def _on_bg_selection_change(self, event=None):
        """Handle background selection change."""
        if self._suppress_events:
            return
        self._process_with_indicator(self.ui_apply_adjustments)

    def _on_processed_image_click(self, index):
        """Handle click on a processed image."""
        # Avoid unnecessary operations if same image clicked again
        if self.selected_processed_index == index:
            return
            
        proj = self.backend.get_current_project()
        if not proj or not (0 <= index < len(proj.processed_images)):
            return

        # Store previous selection to update only what changed
        prev_selection = self.selected_processed_index
        self.selected_processed_index = index
        
        # Directly update only the two images that changed state
        for widget_info in self.proc_image_widgets:
            idx = widget_info["index"]
            if idx == index:
                # Thicker solid border for selected
                widget_info["label"].configure(relief="solid", borderwidth=4)
            elif idx == prev_selection:
                # Thin border for unselected
                widget_info["label"].configure(relief="solid", borderwidth=1)
        
        # Update adjustment fields for the new selection
        self._populate_adjustment_fields()

    # ====================== UI ACTIONS ======================
    def prev_project(self):
        """Navigate to the previous project."""
        idx = self.backend.get_current_project_index()
        if idx > 0:
            self._save_current_form_to_backend()
            self.backend.set_current_project_index(idx - 1)
            self.selected_processed_index = None
            self.refresh_all_displays()

    def next_project(self):
        """Navigate to the next project."""
        idx = self.backend.get_current_project_index()
        count = self.backend.get_project_count()
        if idx < count - 1:
            self._save_current_form_to_backend()
            self.backend.set_current_project_index(idx + 1)
            self.selected_processed_index = None
            self.refresh_all_displays()

    def _process_with_indicator(self, operation_func, *args, **kwargs):
        """
        Show a processing indicator while executing a function.
        
        Args:
            operation_func: Function to execute
            *args, **kwargs: Arguments to pass to the function
        """
        # Create processing dialog
        dialog = tk.Toplevel(self)
        dialog.title(self.lang.get("processing_title", "Processing"))
        dialog.geometry("250x100")
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.focus_set()
        
        # Center dialog in parent window
        x = self.winfo_x() + (self.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Processing indicator
        ttk.Label(
            dialog, 
            text=self.lang.get("processing_warning", "Processing image..."), 
            font=("TkDefaultFont", 10, "bold")
        ).pack(pady=(15, 10))
        
        progress = ttk.Progressbar(dialog, mode="indeterminate", length=200)
        progress.pack(pady=(0, 10))
        progress.start(10)
        
        # Update to make sure dialog is drawn
        dialog.update()
        
        # Execute operation after UI update
        def execute_operation():
            try:
                result = operation_func(*args, **kwargs)
                dialog.destroy()
                return result
            except Exception as e:
                dialog.destroy()
                print(f"Operation error: {e}")
                return None
                
        # Schedule the operation
        self.after(50, execute_operation)

    def ui_load_single_project_images(self):
        """Load images into the current project."""
        idx = self.backend.get_current_project_index()
        if idx < 0:
            messagebox.showwarning(
                self.lang.get("warning", "Warning"), 
                self.lang.get("no_project", "No project loaded or selected."), 
                parent=self
            )
            return
            
        paths = filedialog.askopenfilenames(
            title=self.lang.get("load_images_button", "➕ Add Images to Current"),
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp"), ("All Files", "*.*")],
            parent=self
        )
        
        if not paths:
            return
            
        success, loaded_count, errors = self.backend.load_single_project_images(idx, paths)
        
        if errors:
            messagebox.showwarning(
                self.lang.get("warning", "Warning"),
                f"Loaded {loaded_count} image(s).\nIssues:\n- " + "\n- ".join(errors),
                parent=self
            )
        elif not success and loaded_count == 0:
            messagebox.showerror(
                self.lang.get("error", "Error"), 
                "Failed to load any images.", 
                parent=self
            )
            
        if loaded_count > 0:
            self.refresh_right_display()

    def ui_load_projects_zip(self):
        """Load projects from a zip file."""
        zip_path = filedialog.askopenfilename(
            title=self.lang.get("load_zip_button", "📦 Zip"),
            filetypes=[("Zip Files", "*.zip")],
            parent=self
        )
        
        if not zip_path:
            return

        self.config(cursor="watch")
        self.update_idletasks()

        try:
            success, message, img_count, errors = self.backend.load_projects_from_zip(zip_path)
        except Exception as e:
            success = False
            message = f"An unexpected error occurred during zip loading:\n{e}"
            errors = []
            print(f"Zip Load Exception: {e}")
        finally:
            self.config(cursor="")

        if success:
            if errors:
                messagebox.showwarning(
                    self.lang.get("warning", "Warning"),
                    "Zip Load Issues:\n- " + "\n- ".join(errors),
                    parent=self
                )
            self.selected_processed_index = None
            self.refresh_all_displays()
        else:
            messagebox.showerror(
                self.lang.get("error", "Error"),
                message,
                parent=self
            )

    def ui_add_new_project(self):
        """Add a new empty project and switch to it."""
        self._save_current_form_to_backend()
        new_index = self.backend.add_new_project(self.lang.get("new_project", "New Project"))
        self.backend.set_current_project_index(new_index)
        self.selected_processed_index = None
        self.refresh_all_displays()

    def ui_remove_current_project(self):
        """Remove the current project after confirmation."""
        idx = self.backend.get_current_project_index()
        if idx < 0:
            messagebox.showwarning(
                self.lang.get("warning", "Warning"), 
                self.lang.get("no_project", "No project loaded or selected."), 
                parent=self
            )
            return
            
        if messagebox.askyesno(
            self.lang.get("confirm_delete", "Confirm Deletion"), 
            self.lang.get("confirm_remove_project", "Remove current project?"), 
            parent=self
        ):
            result = self.backend.remove_project(idx)
            if result:
                self.selected_processed_index = None
                self.refresh_all_displays()
            else:
                messagebox.showwarning(
                    self.lang.get("warning", "Warning"), 
                    "Failed to delete project", 
                    parent=self
                )

    def ui_process_current_project_images(self):
        """Process all images in the current project."""
        idx = self.backend.get_current_project_index()
        proj = self.backend.get_project(idx)
        
        if not proj:
            messagebox.showwarning(
                self.lang.get("warning", "Warning"), 
                self.lang.get("no_project", "No project loaded or selected."), 
                parent=self
            )
            return
            
        if not proj.clothing_images:
            messagebox.showwarning(
                self.lang.get("warning", "Warning"), 
                self.lang.get("no_image_loaded", "Please upload clothing images first."), 
                parent=self
            )
            return
            
        # Only check for background images if not using solid background colors
        if not self.backend.backgrounds and not self.backend.use_solid_bg:
            messagebox.showwarning(
                self.lang.get("warning", "Warning"), 
                self.lang.get("no_background", "No background images found or solid color disabled."), 
                parent=self
            )
            return
            
        self._save_current_form_to_backend()
        
        # Create progress popup
        popup = tk.Toplevel(self)
        popup.title(self.lang.get("processing_title", "Processing"))
        popup.geometry("350x150")
        popup.transient(self)
        popup.grab_set()
        
        ttk.Label(popup, text=self.lang.get("processing_warning", "Processing images...")).pack(padx=20, pady=10)
        
        progress = ttk.Progressbar(popup, orient="horizontal", length=300, mode="determinate")
        progress.pack(padx=20, pady=5)
        
        status_var = tk.StringVar(value="Starting...")
        status_label = ttk.Label(popup, textvariable=status_var)
        status_label.pack(padx=20, pady=5)
        
        popup.update()
        
        # Process images with progress updates
        total_images = len(proj.clothing_images)
        progress["maximum"] = total_images
        
        errors = []
        processed_count = 0
        current_global_setting = self.backend.use_solid_bg
        
        for i, item in enumerate(proj.clothing_images):
            status_var.set(f"Processing image {i+1} of {total_images}...")
            progress["value"] = i
            popup.update()
            
            # Check if this image needs processing
            needs_processing = (
                i >= len(proj.processed_images) or 
                "processed" not in proj.processed_images[i] or 
                proj.processed_images[i]["processed"] is None or
                # Force reprocessing if solid_bg setting changed
                (i < len(proj.processed_images) and 
                proj.processed_images[i].get("use_solid_bg", None) != current_global_setting)
            )
            
            if needs_processing:
                success, error_msg = self.backend.process_single_image(idx, i)
                if error_msg:
                    errors.append(error_msg)
                if success:
                    processed_count += 1
            
            progress["value"] = i + 1
            popup.update()
        
        popup.destroy()
        
        self.selected_processed_index = None
        self.refresh_right_display()
        
        if errors:
            msg = "Issues during processing:\n- " + "\n- ".join(errors)
            messagebox.showwarning(self.lang.get("warning", "Warning"), msg, parent=self)
        elif processed_count == 0:
            messagebox.showinfo(
                self.lang.get("info", "Info"), 
                self.lang.get("all_images_processed", "All images already processed."), 
                parent=self
            )

    def ui_remove_image(self, image_index):
        """Remove an image from the current project."""
        idx = self.backend.get_current_project_index()
        proj = self.backend.get_project(idx)
        
        if not proj or image_index < 0 or image_index >= len(proj.clothing_images):
            return
            
        # Remove the image from clothing_images
        proj.clothing_images.pop(image_index)
        
        # Also remove any processed version if it exists
        processed_images = proj.processed_images.copy()
        if image_index < len(processed_images):
            processed_images.pop(image_index)
        proj.processed_images = processed_images
            
        # Reset selection if needed
        if self.selected_processed_index is not None:
            if self.selected_processed_index == image_index:
                self.selected_processed_index = None
            elif self.selected_processed_index > image_index:
                self.selected_processed_index -= 1
        
        # Force complete refresh of UI
        self.proc_image_widgets = []
        self.refresh_right_display()
        
        # Update system
        self.update_idletasks()

    def ui_apply_adjustments(self):
        """Apply adjustment settings to the selected image."""
        idx = self.backend.get_current_project_index()
        if idx < 0:
            return
            
        if self.selected_processed_index is None:
            # Silently return instead of showing warning
            return
            
        # Get values from sliders
        vof = float(self.slider_vof.get())
        hof = float(self.slider_hof.get())
        scale = float(self.slider_scale.get())
        
        # Get other settings
        selected_bg_display = self.bg_select_var.get()
        user_bg_path = self.bg_combobox_map.get(selected_bg_display)
        is_horizontal = self.bg_ratio_var.get()
        skip_bg_removal = self.skip_bg_removal_var.get()
        use_solid_bg = self.item_use_solid_bg_var.get()
        
        # Check if force reprocessing is needed
        proj = self.backend.get_project(idx)
        force_reprocess = False
        
        if proj and 0 <= self.selected_processed_index < len(proj.processed_images):
            item = proj.processed_images[self.selected_processed_index]
            
            # Settings that require reprocessing
            old_skip_state = item.get("skip_bg_removal", False)
            old_solid_bg_state = item.get("use_solid_bg", None)
            
            if old_skip_state != skip_bg_removal or old_solid_bg_state != use_solid_bg:
                force_reprocess = True
        
        # Apply the adjustments
        new_image = self.backend.apply_image_adjustments(
            idx, self.selected_processed_index, vof, hof, scale,
            user_bg_path=user_bg_path, 
            is_horizontal=is_horizontal,
            skip_bg_removal=skip_bg_removal,
            use_solid_bg=use_solid_bg,
            force_reprocess=force_reprocess
        )
        
        if new_image:
            # Find the widget for the selected image
            target_widget_info = next(
                (wi for wi in self.proc_image_widgets if wi["index"] == self.selected_processed_index),
                None
            )
            
            if target_widget_info:
                lbl = target_widget_info["label"]
                try:
                    # Create a new thumbnail
                    thumb_w, thumb_h = (200, 150) if is_horizontal else (150, 200)
                    thumb = new_image.copy()
                    thumb.thumbnail((thumb_w, thumb_h))
                    new_photo = ImageTk.PhotoImage(thumb)
                    lbl.configure(image=new_photo)
                    lbl.image = new_photo
                    target_widget_info["photo"] = new_photo
                    
                    # Update appearance based on state
                    if skip_bg_removal:
                        lbl.configure(relief="solid", borderwidth=3)
                    else:
                        lbl.configure(relief="raised", borderwidth=2)
                    
                    # Restore selection highlight
                    self._highlight_selected_processed()
                except Exception as e:
                    print(f"Thumbnail Update Error: {e}")
                    self.refresh_right_display()
            else:
                self.refresh_right_display()
        else:
            # Only show error if we have a valid image selected
            messagebox.showerror(
                self.lang.get("error", "Error"), 
                "Failed to apply adjustments.", 
                parent=self
            )

    def ui_generate_current_description(self):
        """Generate description for the current project."""
        idx = self.backend.get_current_project_index()
        if idx < 0:
            messagebox.showwarning(
                self.lang.get("warning", "Warning"), 
                self.lang.get("no_project", "No project loaded or selected."), 
                parent=self
            )
            return
            
        self._save_current_form_to_backend()
        
        new_description = self.backend.generate_description_for_project(idx)
        self.desc_text.delete(1.0, tk.END)
        self.desc_text.insert(tk.END, new_description)
        
        # Switch to description tab
        try:
            desc_tab_id = self.notebook.tabs()[-1]
            self.notebook.select(desc_tab_id)
        except:
            pass

    def ui_copy_description(self):
        """Copy the description to clipboard."""
        desc = self.desc_text.get(1.0, tk.END).strip()
        if not desc:
            messagebox.showwarning(
                self.lang.get("warning", "Warning"), 
                self.lang.get("copy_empty", "Description is empty."), 
                parent=self
            )
            return
            
        try:
            pyperclip.copy(desc)
            messagebox.showinfo(
                self.lang.get("success", "Success"),
                self.lang.get("copy_success", "Description copied to clipboard."),
                parent=self
            )
        except Exception as e:
            print(f"Clipboard Error: {e}")
            messagebox.showerror(
                self.lang.get("error", "Error"), 
                f"{self.lang.get('copy_fail', 'Could not copy to clipboard')}:\n{e}", 
                parent=self
            )

    def ui_save_current_project_output(self):
        """Save the current project's processed images and description."""
        idx = self.backend.get_current_project_index()
        proj = self.backend.get_project(idx)
        
        if not proj:
            messagebox.showwarning(
                self.lang.get("warning", "Warning"), 
                self.lang.get("no_project", "No project loaded or selected."), 
                parent=self
            )
            return
            
        if not proj.processed_images:
            messagebox.showwarning(
                self.lang.get("warning", "Warning"), 
                self.lang.get("no_processed_images", "No processed images exist for this project."), 
                parent=self
            )
            return
            
        base_folder = filedialog.askdirectory(
            title=self.lang.get("select_output_base_folder", "Select Folder to Save Project Output"),
            initialdir=".",
            parent=self
        )
        
        if not base_folder:
            return
            
        self.ui_generate_current_description()  # Ensure description is current
        
        self.config(cursor="watch")
        self.update_idletasks()
        
        success, output_folder, img_ok, img_err, desc_ok = self.backend.save_project_output(idx, base_folder)
        
        self.config(cursor="")
        
        if success:
            desc_status = "OK" if desc_ok else "Failed"
            summary = self.lang.get(
                "save_summary_msg", 
                "Saved to:\n{folder}\n\nImages OK: {img_ok}\nImages Failed: {img_err}\nDesc Saved: {desc_ok}"
            ).format(
                folder=output_folder,
                img_ok=img_ok,
                img_err=img_err,
                desc_ok=desc_status
            )
            messagebox.showinfo(
                self.lang.get("save_summary_title", "Output Saved"), 
                summary, 
                parent=self
            )
        else:
            messagebox.showerror(
                self.lang.get("error", "Error"), 
                output_folder, 
                parent=self
            )

    # ====================== SETTINGS EDITOR WINDOW ======================
    def open_editor_window(self):
        """Open the settings editor window."""
        if self.editor_window and self.editor_window.winfo_exists():
            self.editor_window.lift()
            self.editor_window.focus_force()
            return
            
        self.editor_window = tk.Toplevel(self)
        self.editor_window.title(self.lang.get("settings_editor_title", "Vinted Style Studio - Settings"))
        self.editor_window.geometry("850x700")
        self.editor_window.transient(self)
        
        # Create notebook with tabs
        notebook = ttk.Notebook(self.editor_window)
        notebook.bind("<<NotebookTabChanged>>", self._on_editor_notebook_tab_changed)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Helper function to create tabs
        def create_tab(tab_text_key, creation_func):
            tab_text = self.lang.get(tab_text_key, tab_text_key.replace("_tab", "").capitalize())
            container, inner_frame = self._create_scrollable_frame(notebook)
            notebook.add(container, text=tab_text)
            creation_func(inner_frame)
            
        # Create editor tabs
        create_tab("clothing_types_tab", self._create_clothing_types_editor)
        create_tab("tags_tab", self._create_tag_mapping_editor)
        create_tab("colors_tab", self._create_colors_editor)
        create_tab("backgrounds_tab", self._create_backgrounds_editor)
        create_tab("general_settings_tab", self._create_general_settings_editor)
        
        # Set cleanup handler
        self.editor_window.protocol("WM_DELETE_WINDOW", self._on_editor_close)

    def _on_editor_close(self):
        """Handle editor window closing."""
        if self.editor_window:
            self.editor_window.destroy()
        self.editor_window = None
        self.type_listbox = None
        self.tag_editor_listbox = None
        self.color_editor_listbox = None
        
    def _on_editor_notebook_tab_changed(self, event):
        """Handle notebook tab change in editor window."""
        selected_tab = event.widget.tab(event.widget.select(), "text")
        # Refresh type listbox when clothing types tab is selected
        if selected_tab in (self.lang.get("clothing_types_tab", "👕 Clothing Types"), "Clothing Types"):
            self._editor_refresh_type_listbox()

    def _create_scrollable_frame(self, parent_notebook):
        """Create a scrollable frame for editor tabs."""
        container = ttk.Frame(parent_notebook)
        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        inner_frame = ttk.Frame(canvas, padding=10)
        inner_frame_id = canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        
        inner_frame.bind("<Configure>", lambda e: self._update_canvas_scrollregion(canvas))
        canvas.bind("<Configure>", lambda e: self._update_canvas_itemwidth(canvas, inner_frame_id, e.width))
        canvas.bind("<Enter>", lambda e: self._bind_mousewheel(canvas))
        canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        return container, inner_frame

    # --- Clothing Types Editor ---
    def _create_clothing_types_editor(self, parent):
        """Create the clothing types editor UI."""
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)
        
        # Left panel - type list
        frame_left = ttk.Frame(parent)
        frame_left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        frame_left.grid_rowconfigure(2, weight=1)
        frame_left.grid_columnconfigure(0, weight=1)
        
        ttk.Label(frame_left, text=self.lang.get("existing_clothing_types", "📦 Existing Clothing Types:")).grid(row=0, column=0, sticky="w")
        
        # Search field
        self.editor_type_search_var = tk.StringVar()
        type_search_entry = ttk.Entry(frame_left, textvariable=self.editor_type_search_var, width=30)
        type_search_entry.grid(row=1, column=0, sticky="ew", pady=(2, 5))
        type_search_entry.bind("<KeyRelease>", self._editor_filter_types)
        type_search_entry.bind("<FocusIn>", lambda e: self._on_entry_focus_in(type_search_entry, self.lang.get("search_placeholder", "🔍 Search...")))
        self._add_placeholder(type_search_entry, self.lang.get("search_placeholder", "🔍 Search..."))
        
        # Type listbox
        listbox_frame = ttk.Frame(frame_left)
        listbox_frame.grid(row=2, column=0, sticky='nsew')
        listbox_frame.grid_rowconfigure(0, weight=1)
        listbox_frame.grid_columnconfigure(0, weight=1)
        
        self.type_listbox = tk.Listbox(listbox_frame, width=35, height=20, exportselection=False)
        type_list_scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.type_listbox.yview)
        self.type_listbox.configure(yscrollcommand=type_list_scrollbar.set)
        self.type_listbox.grid(row=0, column=0, sticky="nsew")
        type_list_scrollbar.grid(row=0, column=1, sticky="ns")
        self.type_listbox.bind("<<ListboxSelect>>", self._editor_on_type_select)
        self.type_listbox.bind("<Enter>", lambda e: self._bind_mousewheel(self.type_listbox))
        self.type_listbox.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        # Right panel - edit form
        frame_right = ttk.Frame(parent)
        frame_right.grid(row=0, column=1, rowspan=2, sticky="nsew")
        frame_right.grid_columnconfigure(0, weight=1)
        row_num = 0
        
        # Type name field
        ttk.Label(frame_right, text=self.lang.get("type_name", "Type Name:")).grid(row=row_num, column=0, sticky="w")
        self.editor_type_name_entry = ttk.Entry(frame_right)
        self.editor_type_name_entry.grid(row=row_num+1, column=0, sticky="ew", pady=(0, 5))
        row_num += 2
        
        # Measurement fields
        ttk.Label(frame_right, text=self.lang.get("measurement_fields", "Measurement Fields (comma-separated):")).grid(row=row_num, column=0, sticky="w")
        self.editor_fields_entry = ttk.Entry(frame_right)
        self.editor_fields_entry.grid(row=row_num+1, column=0, sticky="ew", pady=(0, 10))
        row_num += 2
        
        # Default tags section
        tags_edit_lframe = ttk.LabelFrame(frame_right, text=self.lang.get("default_tags", "Default Tags (Auto-selected)"), padding=5)
        tags_edit_lframe.grid(row=row_num, column=0, sticky="nsew", pady=(0, 10))
        row_num += 1
        tags_edit_lframe.grid_columnconfigure(0, weight=1)
        tags_edit_lframe.grid_rowconfigure(1, weight=1)
        
        # Tags search field
        self.editor_type_tag_search_var = tk.StringVar()
        type_tag_search_entry = ttk.Entry(tags_edit_lframe, textvariable=self.editor_type_tag_search_var, width=25)
        type_tag_search_entry.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        type_tag_search_entry.bind("<KeyRelease>", self._editor_filter_type_tags)
        type_tag_search_entry.bind("<FocusIn>", lambda e: self._on_entry_focus_in(type_tag_search_entry, self.lang.get("search_placeholder", "🔍 Search...")))
        self._add_placeholder(type_tag_search_entry, self.lang.get("search_placeholder", "🔍 Search..."))
        
        # Tags scrollable container
        self.editor_type_tags_canvas = tk.Canvas(tags_edit_lframe, borderwidth=0, highlightthickness=0, height=300)
        type_tags_scroll = ttk.Scrollbar(tags_edit_lframe, orient="vertical", command=self.editor_type_tags_canvas.yview)
        self.editor_type_tags_canvas.configure(yscrollcommand=type_tags_scroll.set)
        self.editor_type_tags_canvas.grid(row=1, column=0, sticky="nsew")
        type_tags_scroll.grid(row=1, column=1, sticky="ns")
        
        # Tags checkboxes container
        self.editor_default_tags_frame = ttk.Frame(self.editor_type_tags_canvas, padding=5)
        self.editor_default_tags_frame_id = self.editor_type_tags_canvas.create_window((0, 0), window=self.editor_default_tags_frame, anchor="nw")
        self.editor_default_tags_frame.bind("<Configure>", lambda e: self._update_canvas_scrollregion(self.editor_type_tags_canvas))
        self.editor_type_tags_canvas.bind("<Configure>", lambda e: self._update_canvas_itemwidth(self.editor_type_tags_canvas, self.editor_default_tags_frame_id, e.width))
        self.editor_type_tags_canvas.bind("<Enter>", lambda e: self._bind_mousewheel(self.editor_type_tags_canvas))
        self.editor_type_tags_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        self.editor_type_tag_vars = {}
        self.editor_type_tag_checkbuttons = {}
        self._editor_rebuild_type_tag_checkboxes([])
        
        # Buttons
        btn_frame = ttk.Frame(frame_right)
        btn_frame.grid(row=row_num, column=0, sticky="ew", pady=(10, 0))
        
        ttk.Button(
            btn_frame, 
            text=self.lang.get("add_update_button", "💾 Save"), 
            command=self._editor_add_update_type
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame, 
            text=self.lang.get("delete_button", "🗑️ Delete"), 
            command=self._editor_delete_type
        ).pack(side=tk.LEFT, padx=5)
        
        # Initialize listbox
        self._editor_refresh_type_listbox()

    def _editor_refresh_type_listbox(self, preserve_selection=True):
        """Refresh the clothing type listbox with filtered items."""
        items = list(self.backend.templates.keys())
        new_button = self.lang.get("new_button", "➕ New")
        self._refresh_listbox_with_search(
            self.type_listbox, 
            self.editor_type_search_var, 
            items, 
            new_button, 
            preserve_selection
        )
        if self.type_listbox and self.type_listbox.size() > 0:
            self._editor_on_type_select()

    def _editor_filter_types(self, event=None):
        """Filter clothing types in editor based on search text."""
        self._editor_refresh_type_listbox(preserve_selection=False)

    def _editor_on_type_select(self, event=None):
        """Handle clothing type selection in editor."""
        if not self.type_listbox:
            return
            
        selection = self.type_listbox.curselection()
        if not selection and self.type_listbox.size() > 0:
            self.type_listbox.selection_set(0)
            selection = self.type_listbox.curselection()
            
        if not selection:
            self.editor_type_name_entry.delete(0, tk.END)
            self.editor_fields_entry.delete(0, tk.END)
            self._editor_rebuild_type_tag_checkboxes([])
            return
            
        type_name = self.type_listbox.get(selection[0])
        if type_name == self.lang.get("new_button", "➕ New"):
            # Clear fields for new item
            self.editor_type_name_entry.delete(0, tk.END)
            self.editor_fields_entry.delete(0, tk.END)
            self._editor_rebuild_type_tag_checkboxes([])
        else:
            # Fill fields with selected type data
            self.editor_type_name_entry.delete(0, tk.END)
            self.editor_type_name_entry.insert(tk.END, type_name)
            
            type_data = self.backend.templates.get(type_name, {})
            
            # Update fields
            fields = type_data.get("fields", [])
            self.editor_fields_entry.delete(0, tk.END)
            self.editor_fields_entry.insert(tk.END, ", ".join(fields))
            
            # Update default tags
            default_tags = type_data.get("default_tags", [])
            self._editor_rebuild_type_tag_checkboxes(default_tags)
            
        if self.editor_window:
            self.editor_window.lift()

    def _editor_rebuild_type_tag_checkboxes(self, current_defaults):
        """Rebuild the tag checkboxes in the clothing type editor."""
        # Clear existing checkboxes
        for widget in self.editor_default_tags_frame.winfo_children():
            widget.destroy()
            
        self.editor_type_tag_vars.clear()
        self.editor_type_tag_checkbuttons.clear()
        
        # Get all tags (except color tags)
        all_tags = [tag for tag in self.backend.hashtag_mapping.keys() 
                   if not tag.endswith(" color")]
        sorted_tags = sorted(all_tags)
        
        # Configure the grid
        cols = 2  # Number of columns
        self.editor_default_tags_frame.grid_columnconfigure(
            list(range(cols)), weight=1
        )
        
        # Create checkboxes
        row, col = 0, 0
        for tag in sorted_tags:
            var = tk.BooleanVar(value=(tag in current_defaults))
            self.editor_type_tag_vars[tag] = var
            
            c = ttk.Checkbutton(self.editor_default_tags_frame, text=tag, variable=var)
            c.grid(row=row, column=col, sticky="w", padx=2, pady=1)
            self.editor_type_tag_checkbuttons[tag] = c
            
            col = (col + 1) % cols
            if col == 0:
                row += 1
                
        # Update canvas scrollregion
        self.editor_default_tags_frame.update_idletasks()
        self._update_canvas_scrollregion(self.editor_type_tags_canvas)
        self.editor_type_tags_canvas.yview_moveto(0)
        
        # Show all tags initially
        self._editor_filter_type_tags()

    def _editor_filter_type_tags(self, event=None):
        """Filter default tag checkboxes based on search text."""
        search_term = self.editor_type_tag_search_var.get().lower().strip()
        placeholder = self.lang.get("search_placeholder", "🔍 Search...").lower()
        
        # Simplified check for showing all tags
        # The issue was in the complex search_entry detection that wasn't reliable
        show_all = (search_term == "" or search_term == placeholder or event is None)
        
        # Arrange visible checkboxes in a grid
        row, col = 0, 0
        cols = 2
        visible_count = 0
        
        for tag, cb in self.editor_type_tag_checkbuttons.items():
            if show_all or search_term in tag.lower():
                cb.grid(row=row, column=col, sticky="w", padx=2, pady=1)
                col = (col + 1) % cols
                if col == 0:
                    row += 1
                visible_count += 1
            else:
                cb.grid_forget()
                
        # Adjust column weights
        num_cols_needed = 1 if visible_count <= row + 1 else cols
        for i in range(cols):
            self.editor_default_tags_frame.grid_columnconfigure(i, weight=(1 if i < num_cols_needed else 0))
            
        # Update canvas
        self.editor_default_tags_frame.update_idletasks()
        self._update_canvas_scrollregion(self.editor_type_tags_canvas)
        self.editor_type_tags_canvas.yview_moveto(0)

    def _editor_add_update_type(self):
        """Add or update a clothing type from editor values."""
        type_name = self.editor_type_name_entry.get().strip()
        if not type_name:
            messagebox.showwarning(
                self.lang.get("input_error", "Input Error"), 
                self.lang.get("type_name_empty", "Type name empty."), 
                parent=self.editor_window
            )
            return
            
        # Parse fields from comma-separated string
        fields = [f.strip() for f in self.editor_fields_entry.get().strip().split(",") if f.strip()]
        
        # Get selected default tags
        selected_def_tags = [tag for tag, var in self.editor_type_tag_vars.items() if var.get()]
        
        # Update templates data
        current_templates = self.backend.templates.copy()
        current_templates[type_name] = {"fields": fields, "default_tags": selected_def_tags}
        
        # Save to backend
        if self.backend.save_templates_config(current_templates):
            self._editor_refresh_type_listbox()
            self._update_clothing_type_options()
            self.refresh_left_controls_display()
            messagebox.showinfo(
                self.lang.get("success", "Success"),
                self.lang.get("type_saved_msg", "Type '{type_name}' saved.").format(type_name=type_name),
                parent=self.editor_window
            )
        else:
            messagebox.showerror(
                self.lang.get("error", "Error"), 
                self.lang.get("save_failed", "Save templates failed."), 
                parent=self.editor_window
            )
            
        if self.editor_window:
            self.editor_window.lift()

    def _editor_delete_type(self):
        """Delete the selected clothing type."""
        if not self.type_listbox:
            return
            
        selection = self.type_listbox.curselection()
        if not selection:
            return
            
        type_name = self.type_listbox.get(selection[0])
        if type_name == self.lang.get("new_button", "➕ New"):
            return
            
        # Confirm deletion
        confirm_msg = self.lang.get(
            "confirm_delete_type_msg", 
            "Delete type '{type_name}'?"
        ).format(type_name=type_name)
        
        if messagebox.askyesno(
            self.lang.get("confirm_delete", "Confirm Deletion"), 
            confirm_msg, 
            parent=self.editor_window
        ):
            # Remove from templates
            current_templates = self.backend.templates.copy()
            if type_name in current_templates:
                del current_templates[type_name]
                if self.backend.save_templates_config(current_templates):
                    # Clear form fields
                    self.editor_type_name_entry.delete(0, tk.END)
                    self.editor_fields_entry.delete(0, tk.END)
                    self._editor_rebuild_type_tag_checkboxes([])
                    
                    # Update UI
                    self._editor_refresh_type_listbox()
                    self._update_clothing_type_options()
                    self.refresh_left_controls_display()
                    
                    messagebox.showinfo(
                        self.lang.get("deleted", "Deleted"),
                        self.lang.get("type_deleted_msg", "Type '{type_name}' deleted.").format(type_name=type_name),
                        parent=self.editor_window
                    )
                else:
                    messagebox.showerror(
                        self.lang.get("error", "Error"), 
                        self.lang.get("save_failed", "Save failed."), 
                        parent=self.editor_window
                    )
            else:
                messagebox.showerror(
                    self.lang.get("error", "Error"),
                    self.lang.get("type_not_found_msg", "Type '{type_name}' not found.").format(type_name=type_name),
                    parent=self.editor_window
                )
                
        if self.editor_window:
            self.editor_window.lift()
            
    # --- Tag Mapping Editor ---
    def _create_tag_mapping_editor(self, parent):
        """Create the tag mapping editor UI."""
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)
        
        # Left panel - tag list
        frame_left = ttk.Frame(parent)
        frame_left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        frame_left.grid_rowconfigure(2, weight=1)
        frame_left.grid_columnconfigure(0, weight=1)
        
        ttk.Label(frame_left, text=self.lang.get("existing_tag_mappings", "🏷️ Existing Tag Mappings:")).grid(row=0, column=0, sticky="w")
        
        # Search field
        self.editor_tag_search_var = tk.StringVar()
        tag_search_entry = ttk.Entry(frame_left, textvariable=self.editor_tag_search_var, width=30)
        tag_search_entry.grid(row=1, column=0, sticky="ew", pady=(2, 5))
        tag_search_entry.bind("<KeyRelease>", self._editor_filter_tags)
        tag_search_entry.bind("<FocusIn>", lambda e: self._on_entry_focus_in(tag_search_entry, self.lang.get("search_placeholder", "🔍 Search...")))
        self._add_placeholder(tag_search_entry, self.lang.get("search_placeholder", "🔍 Search..."))
        
        # Tag listbox
        listbox_frame = ttk.Frame(frame_left)
        listbox_frame.grid(row=2, column=0, sticky='nsew')
        listbox_frame.grid_rowconfigure(0, weight=1)
        listbox_frame.grid_columnconfigure(0, weight=1)
        
        self.tag_editor_listbox = tk.Listbox(listbox_frame, width=35, height=20, exportselection=False)
        tag_editor_scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.tag_editor_listbox.yview)
        self.tag_editor_listbox.configure(yscrollcommand=tag_editor_scrollbar.set)
        self.tag_editor_listbox.grid(row=0, column=0, sticky="nsew")
        tag_editor_scrollbar.grid(row=0, column=1, sticky="ns")
        self.tag_editor_listbox.bind("<<ListboxSelect>>", self._editor_on_tag_select)
        self.tag_editor_listbox.bind("<Enter>", lambda e: self._bind_mousewheel(self.tag_editor_listbox))
        self.tag_editor_listbox.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        # Right panel - edit form
        frame_right = ttk.Frame(parent)
        frame_right.grid(row=0, column=1, rowspan=2, sticky="nsew")
        frame_right.grid_columnconfigure(0, weight=1)
        row_num = 0
        
        # Tag name field
        ttk.Label(frame_right, text=self.lang.get("tag", "Tag:")).grid(row=row_num, column=0, sticky="w")
        self.editor_tag_entry = ttk.Entry(frame_right)
        self.editor_tag_entry.grid(row=row_num+1, column=0, sticky="ew", pady=(0, 5))
        row_num += 2
        
        # Hashtags field
        ttk.Label(frame_right, text=self.lang.get("hashtags", "Hashtags (comma-separated):")).grid(row=row_num, column=0, sticky="w")
        self.editor_hashtags_entry = ttk.Entry(frame_right)
        self.editor_hashtags_entry.grid(row=row_num+1, column=0, sticky="ew", pady=(0, 10))
        row_num += 2
        
        # Buttons
        btn_frame = ttk.Frame(frame_right)
        btn_frame.grid(row=row_num, column=0, sticky="ew", pady=(10, 0))
        
        ttk.Button(
            btn_frame, 
            text=self.lang.get("add_update_button", "💾 Save"), 
            command=self._editor_add_update_tag
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame, 
            text=self.lang.get("delete_button", "🗑️ Delete"), 
            command=self._editor_delete_tag
        ).pack(side=tk.LEFT, padx=5)
        
        # Initialize listbox
        self._editor_refresh_tag_listbox()

    def _editor_refresh_tag_listbox(self, preserve_selection=True):
        """Refresh the tag mapping listbox with filtered items."""
        # Only include non-color tags for the tag mappings editor
        items = [tag for tag in self.backend.hashtag_mapping.keys() if not tag.endswith(" color")]
        new_button = self.lang.get("new_button", "➕ New")
        self._refresh_listbox_with_search(
            self.tag_editor_listbox, 
            self.editor_tag_search_var, 
            items, 
            new_button, 
            preserve_selection
        )

    def _editor_filter_tags(self, event=None):
        """Filter tags in editor based on search text."""
        self._editor_refresh_tag_listbox(preserve_selection=False)

    def _editor_on_tag_select(self, event=None):
        """Handle tag selection in editor."""
        if not self.tag_editor_listbox:
            return
            
        selection = self.tag_editor_listbox.curselection()
        if not selection and self.tag_editor_listbox.size() > 0:
            self.tag_editor_listbox.selection_set(0)
            selection = self.tag_editor_listbox.curselection()
            
        if not selection:
            self.editor_tag_entry.delete(0, tk.END)
            self.editor_hashtags_entry.delete(0, tk.END)
            return
            
        tag = self.tag_editor_listbox.get(selection[0])
        if tag == self.lang.get("new_button", "➕ New"):
            # Clear fields for new item
            self.editor_tag_entry.delete(0, tk.END)
            self.editor_hashtags_entry.delete(0, tk.END)
        else:
            # Fill fields with selected tag data
            self.editor_tag_entry.delete(0, tk.END)
            self.editor_tag_entry.insert(tk.END, tag)
            
            hashtags = self.backend.hashtag_mapping.get(tag, [])
            self.editor_hashtags_entry.delete(0, tk.END)
            self.editor_hashtags_entry.insert(tk.END, ", ".join(hashtags))
                
        if self.editor_window:
            self.editor_window.lift()

    def _editor_add_update_tag(self):
        """Add or update a tag mapping from editor values."""
        tag = self.editor_tag_entry.get().strip()
        if not tag:
            messagebox.showwarning(
                self.lang.get("input_error", "Input Error"), 
                self.lang.get("tag_empty", "Tag empty."), 
                parent=self.editor_window
            )
            return
            
        # Parse hashtags from comma-separated string
        hashtags = [
            h.strip().replace("#", "").replace(" ", "_") 
            for h in self.editor_hashtags_entry.get().strip().split(",") 
            if h.strip()
        ]
        
        if not hashtags:
            messagebox.showwarning(
                self.lang.get("input_error", "Input Error"), 
                self.lang.get("enter_hashtags", "Enter hashtags."), 
                parent=self.editor_window
            )
            return
            
        # Update hashtag mapping
        current_mapping = self.backend.hashtag_mapping.copy()
        current_mapping[tag] = hashtags
        
        # Save to backend
        if self.backend.save_hashtag_mapping_config(current_mapping):
            self._editor_refresh_tag_listbox()
            self._create_tag_checkboxes()  # Update main UI tag checkboxes
            self.refresh_left_controls_display()
            
            # If tags editor is open, refresh its display
            if hasattr(self, 'editor_default_tags_frame') and self.editor_default_tags_frame.winfo_exists():
                self._editor_on_type_select()
                
            messagebox.showinfo(
                self.lang.get("success", "Success"),
                self.lang.get("tag_saved_msg", "Tag '{tag}' saved.").format(tag=tag),
                parent=self.editor_window
            )
        else:
            messagebox.showerror(
                self.lang.get("error", "Error"), 
                self.lang.get("save_failed", "Save failed."), 
                parent=self.editor_window
            )
            
        if self.editor_window:
            self.editor_window.lift()

    def _editor_delete_tag(self):
        """Delete the selected tag mapping."""
        if not self.tag_editor_listbox:
            return
            
        selection = self.tag_editor_listbox.curselection()
        if not selection:
            return
            
        tag = self.tag_editor_listbox.get(selection[0])
        if tag == self.lang.get("new_button", "➕ New"):
            return
            
        # Confirm deletion
        confirm_msg = self.lang.get(
            "confirm_delete_tag_msg", 
            "Delete tag mapping '{tag}'?"
        ).format(tag=tag)
        
        if messagebox.askyesno(
            self.lang.get("confirm_delete", "Confirm Deletion"), 
            confirm_msg, 
            parent=self.editor_window
        ):
            # Remove from hashtag mapping
            current_mapping = self.backend.hashtag_mapping.copy()
            if tag in current_mapping:
                del current_mapping[tag]
                if self.backend.save_hashtag_mapping_config(current_mapping):
                    # Clear form fields
                    self.editor_tag_entry.delete(0, tk.END)
                    self.editor_hashtags_entry.delete(0, tk.END)
                    
                    # Update UI
                    self._editor_refresh_tag_listbox()
                    self._create_tag_checkboxes()
                    self.refresh_left_controls_display()
                    
                    # If clothing types editor is open, refresh it too
                    if hasattr(self, 'editor_default_tags_frame') and self.editor_default_tags_frame.winfo_exists():
                        self._editor_on_type_select()
                        
                    messagebox.showinfo(
                        self.lang.get("deleted", "Deleted"),
                        self.lang.get("tag_deleted_msg", "Tag '{tag}' deleted.").format(tag=tag),
                        parent=self.editor_window
                    )
                else:
                    messagebox.showerror(
                        self.lang.get("error", "Error"), 
                        self.lang.get("save_failed", "Save failed."), 
                        parent=self.editor_window
                    )
            else:
                messagebox.showerror(
                    self.lang.get("error", "Error"),
                    self.lang.get("tag_not_found_msg", "Tag '{tag}' not found.").format(tag=tag),
                    parent=self.editor_window
                )
                
        if self.editor_window:
            self.editor_window.lift()

    # --- Colors Editor ---
    def _create_colors_editor(self, parent):
        """Create the colors editor UI."""
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)
        
        # Left panel - color list
        frame_left = ttk.Frame(parent)
        frame_left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        frame_left.grid_rowconfigure(2, weight=1)
        frame_left.grid_columnconfigure(0, weight=1)
        
        ttk.Label(frame_left, text=self.lang.get("existing_color_mappings", "Existing Color Mappings:")).grid(row=0, column=0, sticky="w")
        
        # Search field
        self.editor_color_search_var = tk.StringVar()
        color_search_entry = ttk.Entry(frame_left, textvariable=self.editor_color_search_var, width=30)
        color_search_entry.grid(row=1, column=0, sticky="ew", pady=(2, 5))
        color_search_entry.bind("<KeyRelease>", self._editor_filter_colors)
        color_search_entry.bind("<FocusIn>", lambda e: self._on_entry_focus_in(color_search_entry, self.lang.get("search_placeholder", "🔍 Search...")))
        self._add_placeholder(color_search_entry, self.lang.get("search_placeholder", "🔍 Search..."))
        
        # Color listbox
        listbox_frame = ttk.Frame(frame_left)
        listbox_frame.grid(row=2, column=0, sticky='nsew')
        listbox_frame.grid_rowconfigure(0, weight=1)
        listbox_frame.grid_columnconfigure(0, weight=1)
        
        self.color_editor_listbox = tk.Listbox(listbox_frame, width=35, height=20, exportselection=False)
        color_editor_scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.color_editor_listbox.yview)
        self.color_editor_listbox.configure(yscrollcommand=color_editor_scrollbar.set)
        self.color_editor_listbox.grid(row=0, column=0, sticky="nsew")
        color_editor_scrollbar.grid(row=0, column=1, sticky="ns")
        self.color_editor_listbox.bind("<<ListboxSelect>>", self._editor_on_color_select)
        self.color_editor_listbox.bind("<Enter>", lambda e: self._bind_mousewheel(self.color_editor_listbox))
        self.color_editor_listbox.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        # Right panel - edit form
        frame_right = ttk.Frame(parent)
        frame_right.grid(row=0, column=1, rowspan=2, sticky="nsew")
        frame_right.grid_columnconfigure(0, weight=1)
        row_num = 0
        
        # Color name field
        ttk.Label(frame_right, text=self.lang.get("color_label", "Color:")).grid(row=row_num, column=0, sticky="w")
        self.editor_color_entry = ttk.Entry(frame_right)
        self.editor_color_entry.grid(row=row_num+1, column=0, sticky="ew", pady=(0, 5))
        row_num += 2
        
        # Color hashtags field
        ttk.Label(frame_right, text=self.lang.get("color_hashtags_label", "Color Hashtags (comma separated):")).grid(row=row_num, column=0, sticky="w")
        self.editor_color_hashtags_entry = ttk.Entry(frame_right)
        self.editor_color_hashtags_entry.grid(row=row_num+1, column=0, sticky="ew", pady=(0, 10))
        row_num += 2
        
        # Color preview swatch
        ttk.Label(frame_right, text=self.lang.get("color_preview", "Color Preview:")).grid(row=row_num, column=0, sticky="w")
        
        self.editor_color_preview = tk.Canvas(frame_right, width=100, height=30, background="#cccccc", bd=1, relief="solid")
        self.editor_color_preview.grid(row=row_num+1, column=0, sticky="w", pady=(0, 10))
        row_num += 2
        
        # Buttons
        btn_frame = ttk.Frame(frame_right)
        btn_frame.grid(row=row_num, column=0, sticky="ew", pady=(10, 0))
        
        ttk.Button(
            btn_frame, 
            text=self.lang.get("add_update_button", "💾 Save"), 
            command=self._editor_add_update_color
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame, 
            text=self.lang.get("delete_button", "🗑️ Delete"), 
            command=self._editor_delete_color
        ).pack(side=tk.LEFT, padx=5)
        
        # Initialize listbox
        self._editor_refresh_color_listbox()

    def _editor_refresh_color_listbox(self, preserve_selection=True):
        """Refresh the color listbox with filtered items."""
        # Only include color mappings (keys ending with " color")
        items = [tag for tag in self.backend.hashtag_mapping.keys() if tag.endswith(" color")]
        new_button = self.lang.get("new_button", "➕ New")
        self._refresh_listbox_with_search(
            self.color_editor_listbox, 
            self.editor_color_search_var, 
            items, 
            new_button, 
            preserve_selection
        )

    def _editor_filter_colors(self, event=None):
        """Filter colors in editor based on search text."""
        self._editor_refresh_color_listbox(preserve_selection=False)

    def _editor_on_color_select(self, event=None):
        """Handle color selection in editor."""
        if not hasattr(self, 'color_editor_listbox') or not self.color_editor_listbox:
            return
            
        selection = self.color_editor_listbox.curselection()
        if not selection and self.color_editor_listbox.size() > 0:
            self.color_editor_listbox.selection_set(0)
            selection = self.color_editor_listbox.curselection()
                
        if not selection:
            self.editor_color_entry.delete(0, tk.END)
            self.editor_color_hashtags_entry.delete(0, tk.END)
            self.editor_color_preview.config(background="#ffffff")
            return
                
        color_tag = self.color_editor_listbox.get(selection[0])
        if color_tag == self.lang.get("new_button", "➕ New"):
            # Clear fields for new item
            self.editor_color_entry.delete(0, tk.END)
            self.editor_color_hashtags_entry.delete(0, tk.END)
            self.editor_color_preview.config(background="#ffffff")
        else:
            # Fill fields with selected color data
            display_name = color_tag.replace(" color", "")
            self.editor_color_entry.delete(0, tk.END)
            self.editor_color_entry.insert(tk.END, display_name)
            
            hashtags = self.backend.hashtag_mapping.get(color_tag, [])
            self.editor_color_hashtags_entry.delete(0, tk.END)
            self.editor_color_hashtags_entry.insert(tk.END, ", ".join(hashtags))
            
            # Set preview color
            preview_color = self._get_color_from_name(display_name)
            self.editor_color_preview.config(background=preview_color)
                
        if self.editor_window:
            self.editor_window.lift()

    def _editor_add_update_color(self):
        """Add or update a color from editor values."""
        color_name = self.editor_color_entry.get().strip()
        if not color_name:
            messagebox.showwarning(
                self.lang.get("input_error", "Input Error"), 
                self.lang.get("color_name_empty", "Color name empty."), 
                parent=self.editor_window
            )
            return
            
        color_tag = color_name + " color"
        
        # Parse hashtags from comma-separated string
        hashtags = [
            h.strip().replace("#", "").replace(" ", "_") 
            for h in self.editor_color_hashtags_entry.get().strip().split(",") 
            if h.strip()
        ]
        
        if not hashtags:
            messagebox.showwarning(
                self.lang.get("input_error", "Input Error"), 
                self.lang.get("enter_hashtags", "Enter hashtags."), 
                parent=self.editor_window
            )
            return
            
        # Update hashtag mapping
        current_mapping = self.backend.hashtag_mapping.copy()
        current_mapping[color_tag] = hashtags
        
        # Save to backend
        if self.backend.save_hashtag_mapping_config(current_mapping):
            self._editor_refresh_color_listbox()
            self._create_color_checkboxes()  # Update main UI color checkboxes
            self.refresh_left_controls_display()
                
            messagebox.showinfo(
                self.lang.get("success", "Success"),
                self.lang.get("color_saved_msg", "Color '{color_name}' saved.").format(color_name=color_name),
                parent=self.editor_window
            )
        else:
            messagebox.showerror(
                self.lang.get("error", "Error"), 
                self.lang.get("save_failed", "Save failed."), 
                parent=self.editor_window
            )
                
        if self.editor_window:
            self.editor_window.lift()

    def _editor_delete_color(self):
        """Delete the selected color."""
        if not hasattr(self, 'color_editor_listbox') or not self.color_editor_listbox:
            return
                
        selection = self.color_editor_listbox.curselection()
        if not selection:
            return
                
        color_tag = self.color_editor_listbox.get(selection[0])
        if color_tag == self.lang.get("new_button", "➕ New"):
            return
                
        # Get display name for messages
        color_name = color_tag.replace(" color", "")
        
        # Confirm deletion
        confirm_msg = self.lang.get(
            "confirm_delete_color", 
            "Delete color '{color_name}'?"
        ).format(color_name=color_name)
        
        if messagebox.askyesno(
            self.lang.get("confirm_delete", "Confirm Deletion"), 
            confirm_msg, 
            parent=self.editor_window
        ):
            # Remove from hashtag mapping
            current_mapping = self.backend.hashtag_mapping.copy()
            if color_tag in current_mapping:
                del current_mapping[color_tag]
                if self.backend.save_hashtag_mapping_config(current_mapping):
                    # Clear form fields
                    self.editor_color_entry.delete(0, tk.END)
                    self.editor_color_hashtags_entry.delete(0, tk.END)
                    
                    # Update UI
                    self._editor_refresh_color_listbox()
                    self._create_color_checkboxes()  # Update main UI color checkboxes
                    self.refresh_left_controls_display()
                        
                    messagebox.showinfo(
                        self.lang.get("deleted", "Deleted"),
                        self.lang.get("color_deleted_msg", "Color '{color_name}' deleted.").format(color_name=color_name),
                        parent=self.editor_window
                    )
                else:
                    messagebox.showerror(
                        self.lang.get("error", "Error"), 
                        self.lang.get("save_failed", "Save failed."), 
                        parent=self.editor_window
                    )
            else:
                messagebox.showerror(
                    self.lang.get("error", "Error"),
                    self.lang.get("color_not_found", "Color '{color_name}' not found.").format(color_name=color_name),
                    parent=self.editor_window
                )
                    
        if self.editor_window:
            self.editor_window.lift()

    # --- Backgrounds Editor ---
    def _create_backgrounds_editor(self, parent):
        """Create the backgrounds editor UI."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(3, weight=1)
        row_num = 0
        
        # Help text
        ttk.Label(
            parent, 
            text=self.lang.get("bg_folder_info", "Backgrounds are stored in the 'bg' folder next to the application")
        ).grid(row=row_num, column=0, sticky="w", pady=(0, 10))
        row_num += 1
        
        # Add Background Files button
        add_files_frame = ttk.Frame(parent)
        add_files_frame.grid(row=row_num, column=0, sticky="ew", pady=(0, 5))
        add_files_frame.grid_columnconfigure(0, weight=1)
        
        ttk.Button(
            add_files_frame, 
            text=self.lang.get("add_bg_files", "Add Background Files..."),
            command=self._editor_add_bg_files
        ).grid(row=0, column=0, sticky="w")
        
        row_num += 1
                
        # Add backgrounds from folder section
        frame_select = ttk.Frame(parent)
        frame_select.grid(row=row_num, column=0, sticky="ew", pady=(0, 10))
        row_num += 1
        frame_select.grid_columnconfigure(1, weight=1)
        
        ttk.Label(frame_select, text=self.lang.get("select_new_bg_folder", "Import from folder:")).grid(
            row=0, column=0, sticky="w", padx=(0, 5)
        )
        self.editor_bg_folder_entry = ttk.Entry(frame_select)
        self.editor_bg_folder_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        
        ttk.Button(
            frame_select, 
            text=self.lang.get("browse_button", "Browse..."), 
            command=self._editor_browse_bg_folder, 
            width=10
        ).grid(row=0, column=2, padx=(0, 5))
        
        ttk.Button(
            frame_select, 
            text=self.lang.get("load_from_folder_button", "Load from Folder"), 
            command=self._editor_load_bg_from_folder
        ).grid(row=0, column=3)
                
        # Note about solid background
        ttk.Label(
            parent, 
            text=self.lang.get("solid_bg_note", "Note: The 'Use solid background color' option is available in the main interface.")
        ).grid(row=row_num, column=0, sticky="w", pady=(0, 10))
        row_num += 1
        
        # Background list
        ttk.Label(parent, text=self.lang.get("loaded_backgrounds", "Loaded Backgrounds:")).grid(
            row=row_num, column=0, sticky="w"
        )
        row_num += 1
        
        listbox_frame = ttk.Frame(parent)
        listbox_frame.grid(row=row_num, column=0, sticky="nsew")
        listbox_frame.grid_rowconfigure(0, weight=1)
        listbox_frame.grid_columnconfigure(0, weight=1)
        
        self.editor_bg_listbox = tk.Listbox(listbox_frame, height=20, selectmode=tk.SINGLE)
        bg_scroll = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.editor_bg_listbox.yview)
        self.editor_bg_listbox.configure(yscrollcommand=bg_scroll.set)
        self.editor_bg_listbox.grid(row=0, column=0, sticky="nsew")
        bg_scroll.grid(row=0, column=1, sticky="ns")
        self.editor_bg_listbox.bind("<Enter>", lambda e: self._bind_mousewheel(self.editor_bg_listbox))
        self.editor_bg_listbox.bind("<Leave>", lambda e: self._unbind_mousewheel())
        
        row_num += 1
        
        # Remove Selected button
        remove_frame = ttk.Frame(parent)
        remove_frame.grid(row=row_num, column=0, sticky="ew", pady=(5, 0))
        
        ttk.Button(
            remove_frame,
            text=self.lang.get("remove_selected_bg", "Remove Selected"),
            command=self._editor_remove_selected_background
        ).pack(side=tk.LEFT)
        
        # Populate the listbox
        self._editor_refresh_bg_listbox()

    def _editor_refresh_bg_listbox(self):
        """Refresh the background listbox with current backgrounds."""
        if not hasattr(self, 'editor_bg_listbox') or not self.editor_bg_listbox.winfo_exists():
            return
            
        self.editor_bg_listbox.delete(0, tk.END)
        
        # Refresh the backend backgrounds list
        self.backend.scan_backgrounds_folder()
        
        # Show basenames in the listbox for better readability
        for path in self.backend.backgrounds:
            self.editor_bg_listbox.insert(tk.END, os.path.basename(path))

    def _editor_add_bg_files(self):
        """Add background image files from file picker."""
        file_paths = filedialog.askopenfilenames(
            title=self.lang.get("add_bg_files", "Add Background Files"),
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp"), ("All Files", "*.*")],
            parent=self.editor_window
        )
        
        if not file_paths:
            return
            
        # Call backend method to add background files
        added_count, skipped = self.backend.add_background_files(file_paths)
        
        if added_count > 0:
            self._editor_refresh_bg_listbox()
            
            msg = self.lang.get("bg_added_msg", "Added {count} new background(s).").format(count=added_count)
            if skipped:
                skipped_list = "\n".join([f"{name} - {reason}" for name, reason in skipped])
                msg += f"\n\nSkipped files:\n{skipped_list}"
                
            messagebox.showinfo(
                self.lang.get("success", "Success"), 
                msg, 
                parent=self.editor_window
            )
            self._update_bg_selector_options()
        else:
            # If nothing was added but files were selected, show skipped files
            if skipped:
                skipped_list = "\n".join([f"{name} - {reason}" for name, reason in skipped])
                msg = f"No files added.\n\nSkipped files:\n{skipped_list}"
                messagebox.showinfo(
                    self.lang.get("info", "Info"), 
                    msg, 
                    parent=self.editor_window
                )
            else:
                messagebox.showinfo(
                    self.lang.get("info", "Info"), 
                    self.lang.get("bg_none_added_msg", "No new background images found."), 
                    parent=self.editor_window
                )
                
        if self.editor_window:
            self.editor_window.lift()

    def _editor_browse_bg_folder(self):
        """Browse for a background folder."""
        folder = filedialog.askdirectory(
            title=self.lang.get("select_bg_folder", "Default Backgrounds Folder:"),
            initialdir=".",
            parent=self.editor_window
        )
        
        if folder:
            self.editor_bg_folder_entry.delete(0, tk.END)
            self.editor_bg_folder_entry.insert(tk.END, folder)

    def _editor_load_bg_from_folder(self):
        """Load background images from a folder."""
        folder = self.editor_bg_folder_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning(
                self.lang.get("input_error", "Input Error"), 
                self.lang.get("bg_invalid_folder", "Please select a valid folder."), 
                parent=self.editor_window
            )
            return
            
        added_count, skipped = self.backend.add_backgrounds_from_folder(folder)
        
        if added_count > 0:
            self._editor_refresh_bg_listbox()
            
            msg = self.lang.get("bg_added_msg", "Added {count} new background(s).").format(count=added_count)
            if skipped:
                skipped_list = "\n".join([f"{name} - {reason}" for name, reason in skipped])
                msg += f"\n\nSkipped files:\n{skipped_list}"
                
            messagebox.showinfo(
                self.lang.get("success", "Success"), 
                msg, 
                parent=self.editor_window
            )
            self._update_bg_selector_options()
        else:
            # If nothing was added but folder had files, show skipped files
            if skipped:
                skipped_list = "\n".join([f"{name} - {reason}" for name, reason in skipped])
                msg = f"No files added.\n\nSkipped files:\n{skipped_list}"
                messagebox.showinfo(
                    self.lang.get("info", "Info"), 
                    msg, 
                    parent=self.editor_window
                )
            else:
                messagebox.showinfo(
                    self.lang.get("info", "Info"), 
                    self.lang.get("bg_none_added_msg", "No new background images found."), 
                    parent=self.editor_window
                )
            
        if self.editor_window:
            self.editor_window.lift()

    def _editor_remove_selected_background(self):
        """Remove the selected background file."""
        selection = self.editor_bg_listbox.curselection()
        if not selection:
            messagebox.showinfo(
                self.lang.get("info", "Info"), 
                "Please select a background to remove.", 
                parent=self.editor_window
            )
            return
            
        # Get the basename from the listbox
        basename = self.editor_bg_listbox.get(selection[0])
        
        # Find the full path in the backend.backgrounds list
        full_path = None
        for path in self.backend.backgrounds:
            if os.path.basename(path) == basename:
                full_path = path
                break
                
        if not full_path:
            messagebox.showerror(
                self.lang.get("error", "Error"), 
                "Unable to find the selected background file.", 
                parent=self.editor_window
            )
            return
            
        # Confirm deletion
        if messagebox.askyesno(
            self.lang.get("confirm_delete", "Confirm Deletion"),
            f"Remove background '{basename}'?\nThis will delete the file from disk.",
            parent=self.editor_window
        ):
            # Call backend to remove the file
            success, error_msg = self.backend.remove_bg_file(full_path)
            
            if success:
                self._editor_refresh_bg_listbox()
                self._update_bg_selector_options()
                messagebox.showinfo(
                    self.lang.get("success", "Success"), 
                    f"Background '{basename}' removed.", 
                    parent=self.editor_window
                )
            else:
                messagebox.showerror(
                    self.lang.get("error", "Error"), 
                    f"Failed to remove background: {error_msg}", 
                    parent=self.editor_window
                )
        
        if self.editor_window:
            self.editor_window.lift()

    # --- General Settings Editor ---
    def _create_general_settings_editor(self, parent):
        """Create the general settings editor UI."""
        parent.grid_columnconfigure(1, weight=1)
        row_num = 0
        
        # Language selector
        ttk.Label(parent, text=self.lang.get("language_label", "Language (Requires Restart):")).grid(
            row=row_num, column=0, sticky="w", padx=(0, 5), pady=5
        )
        
        self.editor_lang_var = tk.StringVar(value=self.backend.selected_language_code)
        lang_options = self.backend.get_available_languages()
        
        self.editor_lang_combo = ttk.Combobox(
            parent,
            textvariable=self.editor_lang_var,
            values=list(lang_options.values()),
            state="readonly",
            width=30
        )
        
        current_display_name = lang_options.get(
            self.backend.selected_language_code, 
            lang_options.get("en", "?")
        )
        self.editor_lang_combo.set(current_display_name)
        self.editor_lang_combo.grid(row=row_num, column=1, sticky="w", pady=5)
        row_num += 1
        
        # Create mapping of display names to language codes
        self.editor_lang_display_to_code = {v: k for k, v in lang_options.items()}
        
        # Units selector
        ttk.Label(parent, text=self.lang.get("units", "Units:")).grid(
            row=row_num, column=0, sticky="w", padx=(0, 5), pady=5
        )
        self.editor_units_entry = ttk.Entry(parent, width=10)
        self.editor_units_entry.grid(row=row_num, column=1, sticky="w", pady=5)
        self.editor_units_entry.insert(tk.END, self.backend.units)
        row_num += 1
        
        # Output filename prefix
        ttk.Label(parent, text=self.lang.get("output_prefix", "Output Filename Prefix:")).grid(
            row=row_num, column=0, sticky="w", padx=(0, 5), pady=5
        )
        self.editor_output_prefix_entry = ttk.Entry(parent)
        self.editor_output_prefix_entry.grid(row=row_num, column=1, sticky="ew", pady=5)
        self.editor_output_prefix_entry.insert(tk.END, self.backend.output_prefix)
        row_num += 1
        
        # Canvas dimensions section
        canvas_dimensions = ttk.LabelFrame(
            parent, 
            text=self.lang.get("canvas_dimensions", "Canvas Dimensions"), 
            padding=5
        )
        canvas_dimensions.grid(row=row_num, column=0, columnspan=2, sticky="ew", pady=10)
        canvas_dimensions.grid_columnconfigure(1, weight=1)
        canvas_dimensions.grid_columnconfigure(3, weight=1)
        row_num += 1
        
        # Vertical canvas settings
        ttk.Label(
            canvas_dimensions, 
            text=self.lang.get("vertical_canvas", "Vertical Canvas (Recommended: 600x800):")
        ).grid(row=0, column=0, sticky="w", pady=(0, 5), columnspan=4)
        
        ttk.Label(canvas_dimensions, text=self.lang.get("width", "Width:")).grid(
            row=1, column=0, sticky="w", padx=(5, 5)
        )
        self.editor_v_width_entry = ttk.Entry(canvas_dimensions, width=8)
        self.editor_v_width_entry.grid(row=1, column=1, sticky="w", padx=(0, 20))
        self.editor_v_width_entry.insert(tk.END, str(self.backend.canvas_width_v))
        
        ttk.Label(canvas_dimensions, text=self.lang.get("height", "Height:")).grid(
            row=1, column=2, sticky="w", padx=(0, 5)
        )
        self.editor_v_height_entry = ttk.Entry(canvas_dimensions, width=8)
        self.editor_v_height_entry.grid(row=1, column=3, sticky="w")
        self.editor_v_height_entry.insert(tk.END, str(self.backend.canvas_height_v))
        
        # Horizontal canvas settings
        ttk.Label(
            canvas_dimensions, 
            text=self.lang.get("horizontal_canvas", "Horizontal Canvas (Recommended: 800x600):")
        ).grid(row=2, column=0, sticky="w", pady=(10, 5), columnspan=4)
        
        ttk.Label(canvas_dimensions, text=self.lang.get("width", "Width:")).grid(
            row=3, column=0, sticky="w", padx=(5, 5)
        )
        self.editor_h_width_entry = ttk.Entry(canvas_dimensions, width=8)
        self.editor_h_width_entry.grid(row=3, column=1, sticky="w", padx=(0, 20))
        self.editor_h_width_entry.insert(tk.END, str(self.backend.canvas_width_h))
        
        ttk.Label(canvas_dimensions, text=self.lang.get("height", "Height:")).grid(
            row=3, column=2, sticky="w", padx=(0, 5)
        )
        self.editor_h_height_entry = ttk.Entry(canvas_dimensions, width=8)
        self.editor_h_height_entry.grid(row=3, column=3, sticky="w")
        self.editor_h_height_entry.insert(tk.END, str(self.backend.canvas_height_h))
        
        # Save button for all settings
        save_btn_frame = ttk.Frame(parent)
        save_btn_frame.grid(row=row_num, column=0, columnspan=2, sticky="ew", pady=20)
        save_btn_frame.grid_columnconfigure(0, weight=1)
        
        ttk.Button(
            save_btn_frame,
            text=self.lang.get("save_all_settings", "💾 Save All Settings"),
            command=self._editor_save_all_settings
        ).grid(row=0, column=1, sticky="e")

    def _editor_save_all_settings(self):
        """Save all general settings."""
        current_config = self.backend.config_data.copy()
        
        # Get language code from selected display name
        selected_display_name = self.editor_lang_var.get()
        selected_lang_code = self.editor_lang_display_to_code.get(selected_display_name, "en")
        current_config["selected_language"] = selected_lang_code
        
        # Get other settings
        current_config["units"] = self.editor_units_entry.get().strip() or "cm"
        current_config["output_prefix"] = self.editor_output_prefix_entry.get().strip() or "vinted_"
        
        # Save canvas dimensions
        try:
            current_config["canvas_width_v"] = int(self.editor_v_width_entry.get().strip())
            current_config["canvas_height_v"] = int(self.editor_v_height_entry.get().strip())
            current_config["canvas_width_h"] = int(self.editor_h_width_entry.get().strip())
            current_config["canvas_height_h"] = int(self.editor_h_height_entry.get().strip())
        except ValueError:
            messagebox.showwarning(
                self.lang.get("input_error", "Input Error"),
                self.lang.get("canvas_dimensions_error", "Canvas dimensions must be integers."),
                parent=self.editor_window
            )
            return
        
        # Save to backend
        if self.backend.save_main_config(current_config):
            messagebox.showinfo(
                self.lang.get("success", "Success"), 
                self.lang.get("settings_saved", "Settings saved. Restart application to apply language change."), 
                parent=self.editor_window
            )
        else:
            messagebox.showerror(
                self.lang.get("error", "Error"), 
                self.lang.get("save_failed", "Failed to save settings."), 
                parent=self.editor_window
            )
            
        if self.editor_window:
            self.editor_window.lift()


# ====================== APPLICATION ENTRY POINT ======================
if __name__ == "__main__":
    try:
        app = App()
        # Check if initialization was successful before running mainloop
        if hasattr(app, 'backend') and app.backend.lang:
            app.mainloop()
        # If init failed, error messages were already shown
    except Exception as e:
        # Catch-all for unexpected errors during App init itself
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Critical Startup Error", f"Application failed to initialize:\n{e}")
            root.destroy()
        except Exception as tk_e:
            print(f"CRITICAL STARTUP ERROR (TKINTER FAILED): {e}, TK Error: {tk_e}")
        sys.exit(1)