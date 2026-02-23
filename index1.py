import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import fitz  # PyMuPDF
import threading
import os
import re
import requests
import base64
import json
from datetime import datetime
import warnings
from io import BytesIO
from PIL import Image, ImageTk

# Hide deprecation warnings
warnings.filterwarnings("ignore")

class SmartPDFAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart PDF Analyzer - COMPETITION EDITION")
        self.root.geometry("1400x900")
        
        # Data storage
        self.pdf_data = []
        self.current_pdf = None
        self.current_page = 0
        self.total_pages = 0
        self.all_text = ""
        self.images_data = []  # Store extracted images
        self.current_image_index = 0
        self.image_descriptions = {}  # Store image descriptions
        
        # API Keys
        self.groq_api_key = ""
        self.openrouter_api_key = ""
        
        # Initialize APIs
        self.groq_client = None
        self.setup_groq()
        
        # Image Models Configuration
        self.image_models = [
            "qwen/qwen-2.5-vl-72b-instruct",
             "anthropic/claude-3-haiku", # Free tier available
    "openai/gpt-4o-mini",  
            "meta-llama/llama-3.2-11b-vision-instruct"
        ]
        self.selected_image_model = tk.StringVar(value=self.image_models[0])
        
        # Colors
        self.colors = {
            'bg': '#1e1e1e',
            'fg': '#ffffff',
            'accent': '#4CAF50',
            'secondary': '#2196F3',
            'warning': '#FF9800',
            'card_bg': '#2d2d2d',
            'text_bg': '#252525',
            'highlight': '#3e3e42',
            'image_bg': '#1a1a2e',
            'scrollbar_bg': '#3e3e42',
            'scrollbar_trough': '#2d2d2d'
        }
        
        self.root.configure(bg=self.colors['bg'])
        self.create_gui()
    
    def setup_groq(self):
        """Setup Groq API"""
        try:
            if not self.groq_api_key:
                print("⚠️ Groq API key not set.")
                self.groq_status = "Not configured"
                return False
            
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_api_key)
                
                # Quick test with available model
                test_response = self.groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": "Say 'Connected'"}],
                    max_tokens=10
                )
                
                if test_response.choices[0].message.content:
                    print("✅ Groq API configured successfully!")
                    self.groq_status = "Connected"
                    return True
                    
            except ImportError:
                print("⚠️ Groq package not installed. Run: pip install groq")
                self.groq_status = "Package missing"
                return False
                
        except Exception as e:
            print(f"⚠️ Groq setup failed: {str(e)[:100]}")
            self.groq_status = f"Failed: {str(e)[:30]}"
            return False
        
        return False
    
    def create_gui(self):
        # ===== MAIN CONTAINER WITH SCROLLBAR =====
        # Create main container frame
        self.main_container = tk.Frame(self.root, bg=self.colors['bg'])
        self.main_container.pack(fill='both', expand=True)
        
        # Create canvas for scrolling
        self.canvas = tk.Canvas(self.main_container, bg=self.colors['bg'], highlightthickness=0)
        self.canvas.pack(side='left', fill='both', expand=True)
        
        # Add scrollbar to canvas - Using tk.Scrollbar instead of ttk.Scrollbar
        self.scrollbar = tk.Scrollbar(self.main_container, orient='vertical', 
                                      command=self.canvas.yview, 
                                      width=12,  # Thinner scrollbar
                                      bg=self.colors['scrollbar_bg'],
                                      troughcolor=self.colors['scrollbar_trough'],
                                      activebackground=self.colors['accent'])
        self.scrollbar.pack(side='right', fill='y')
        
        # Configure canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Create scrollable frame inside canvas
        self.scrollable_frame = tk.Frame(self.canvas, bg=self.colors['bg'])
        
        # Add scrollable frame to canvas window
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, 
                                                     anchor='nw', width=1380)  # Adjusted for scrollbar width
        
        # Configure scroll region
        def configure_scroll_region(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
        self.scrollable_frame.bind('<Configure>', configure_scroll_region)
        
        # Mouse wheel scrolling
        def on_mouse_wheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
        self.canvas.bind_all("<MouseWheel>", on_mouse_wheel)
        
        # Bind canvas resize
        def on_canvas_resize(event):
            self.canvas.itemconfig(self.canvas_frame, width=event.width)
            
        self.canvas.bind('<Configure>', on_canvas_resize)
        
        # ===== ACTUAL GUI CONTENT INSIDE SCROLLABLE FRAME =====
        # Main content container
        content_container = tk.Frame(self.scrollable_frame, bg=self.colors['bg'])
        content_container.pack(fill='both', expand=True, padx=15, pady=10)
        
        # ===== LEFT PANEL =====
        left_panel = tk.Frame(content_container, bg=self.colors['bg'], width=320)
        left_panel.pack(side='left', fill='y')
        left_panel.pack_propagate(False)
        
        # Logo/Title
        title_frame = tk.Frame(left_panel, bg=self.colors['bg'])
        title_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(title_frame, text="🚀 PDF ANALYZER PRO", 
                font=('Arial', 16, 'bold'), 
                bg=self.colors['bg'], fg=self.colors['accent']).pack()
        tk.Label(title_frame, text="Competition Edition", 
                font=('Arial', 10), 
                bg=self.colors['bg'], fg=self.colors['fg']).pack()
        
        # Page navigation info
        page_info_frame = tk.Frame(title_frame, bg=self.colors['bg'])
        page_info_frame.pack(pady=5)
        self.page_info_label = tk.Label(page_info_frame, text="Page 0 of 0",
                                       font=('Arial', 10, 'bold'),
                                       bg=self.colors['bg'], fg=self.colors['accent'])
        self.page_info_label.pack()
        
        # File selection
        file_frame = tk.LabelFrame(left_panel, text="📂 PDF SELECTION", 
                                  bg=self.colors['card_bg'], fg=self.colors['fg'],
                                  font=('Arial', 11, 'bold'))
        file_frame.pack(fill='x', pady=(0, 10))
        
        self.pdf_label = tk.Label(file_frame, text="No PDF selected", 
                                 bg=self.colors['card_bg'], fg=self.colors['warning'],
                                 font=('Arial', 9))
        self.pdf_label.pack(pady=5)
        
        tk.Button(file_frame, text="📁 Browse PDF", command=self.browse_pdf,
                 bg=self.colors['secondary'], fg='white',
                 font=('Arial', 10)).pack(pady=10)
        
        # Image Analysis Section
        image_frame = tk.LabelFrame(left_panel, text="🖼️ IMAGE ANALYSIS",
                                   bg=self.colors['card_bg'], fg=self.colors['fg'],
                                   font=('Arial', 11, 'bold'))
        image_frame.pack(fill='x', pady=(0, 10))
        
        # Image Model Selection
        tk.Label(image_frame, text="Select Model:", 
                bg=self.colors['card_bg'], fg=self.colors['fg'],
                font=('Arial', 9)).pack(anchor='w', padx=10, pady=(10, 5))
        
        self.image_model_dropdown = ttk.Combobox(image_frame, 
                                                 textvariable=self.selected_image_model,
                                                 values=self.image_models,
                                                 state="readonly",
                                                 font=('Arial', 9))
        self.image_model_dropdown.pack(fill='x', padx=10, pady=(0, 10))
        
        # Image Analysis Button
        self.analyze_images_btn = tk.Button(image_frame, 
                                           text="🔍 Analyze Images",
                                           command=self.analyze_images,
                                           bg=self.colors['accent'],
                                           fg='white',
                                           font=('Arial', 10, 'bold'),
                                           state='disabled')
        self.analyze_images_btn.pack(pady=10, padx=10, fill='x')
        
        # Image Navigation
        img_nav_frame = tk.Frame(image_frame, bg=self.colors['card_bg'])
        img_nav_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        self.prev_img_btn = tk.Button(img_nav_frame, text="◀ Prev",
                                     command=self.prev_image,
                                     state='disabled',
                                     bg=self.colors['highlight'], fg='white',
                                     font=('Arial', 9))
        self.prev_img_btn.pack(side='left')
        
        self.next_img_btn = tk.Button(img_nav_frame, text="Next ▶",
                                     command=self.next_image,
                                     state='disabled',
                                     bg=self.colors['highlight'], fg='white',
                                     font=('Arial', 9))
        self.next_img_btn.pack(side='right')
        
        # Image Status
        self.image_status_label = tk.Label(image_frame, 
                                          text="Images: Not extracted",
                                          bg=self.colors['card_bg'],
                                          fg=self.colors['warning'],
                                          font=('Arial', 8))
        self.image_status_label.pack(pady=5)
        
        # AI Mode Selection
        ai_frame = tk.LabelFrame(left_panel, text="🤖 ANSWERING MODE",
                                bg=self.colors['card_bg'], fg=self.colors['fg'],
                                font=('Arial', 11, 'bold'))
        ai_frame.pack(fill='x', pady=(0, 10))
        
        self.ai_mode = tk.StringVar(value="smart")
        
        tk.Radiobutton(ai_frame, text="🧠 Smart Mode (Groq AI)", 
                      variable=self.ai_mode, value="smart",
                      bg=self.colors['card_bg'], fg=self.colors['fg'],
                      font=('Arial', 9)).pack(anchor='w', pady=2, padx=10)
        
        tk.Radiobutton(ai_frame, text="⚡ Fast Mode (Rule-based)", 
                      variable=self.ai_mode, value="fast",
                      bg=self.colors['card_bg'], fg=self.colors['fg'],
                      font=('Arial', 9)).pack(anchor='w', pady=2, padx=10)
        
        # Status indicator
        self.groq_status_label = tk.Label(ai_frame, text=f"Groq: {self.groq_status}", 
                                         bg=self.colors['card_bg'], 
                                         fg=self.colors['accent'] if self.groq_status == "Connected" else self.colors['warning'],
                                         font=('Arial', 8))
        self.groq_status_label.pack(pady=5, padx=10)
        
        # Processing
        process_frame = tk.LabelFrame(left_panel, text="⚙️ PROCESSING",
                                     bg=self.colors['card_bg'], fg=self.colors['fg'],
                                     font=('Arial', 11, 'bold'))
        process_frame.pack(fill='x', pady=(0, 10))
        
        tk.Button(process_frame, text="▶ START ANALYSIS", command=self.start_analysis,
                 bg=self.colors['accent'], fg='white', 
                 font=('Arial', 10, 'bold')).pack(pady=15, padx=10)
        
        # Progress
        progress_frame = tk.LabelFrame(left_panel, text="📊 PROGRESS",
                                      bg=self.colors['card_bg'], fg=self.colors['fg'],
                                      font=('Arial', 11, 'bold'))
        progress_frame.pack(fill='x')
        
        self.status_label = tk.Label(progress_frame, text="Ready", 
                                    bg=self.colors['card_bg'], fg=self.colors['fg'],
                                    font=('Arial', 9))
        self.status_label.pack(pady=5, padx=10)
        
        self.progress = ttk.Progressbar(progress_frame, length=280)
        self.progress.pack(pady=10, padx=10)
        
        # ===== RIGHT PANEL =====
        right_panel = tk.Frame(content_container, bg=self.colors['bg'])
        right_panel.pack(side='right', fill='both', expand=True)
        
        # ===== TOP SECTION: PAGE NAVIGATION =====
        top_frame = tk.Frame(right_panel, bg=self.colors['bg'])
        top_frame.pack(fill='x', pady=(0, 10))
        
        # Page navigation
        nav_frame = tk.Frame(top_frame, bg=self.colors['bg'])
        nav_frame.pack(side='left', fill='x', expand=True)
        
        self.prev_btn = tk.Button(nav_frame, text="◀ PREVIOUS", command=self.prev_page,
                                 state='disabled', bg=self.colors['highlight'], fg='white',
                                 font=('Arial', 10))
        self.prev_btn.pack(side='left', padx=(0, 10))
        
        self.page_label = tk.Label(nav_frame, text="Page 0 of 0", 
                                  font=('Arial', 12, 'bold'), bg=self.colors['bg'], 
                                  fg=self.colors['accent'])
        self.page_label.pack(side='left', expand=True)
        
        self.next_btn = tk.Button(nav_frame, text="NEXT ▶", command=self.next_page,
                                 state='disabled', bg=self.colors['highlight'], fg='white',
                                 font=('Arial', 10))
        self.next_btn.pack(side='right')
        
        # Image navigation info
        img_info_frame = tk.Frame(top_frame, bg=self.colors['bg'])
        img_info_frame.pack(side='right')
        
        self.image_nav_label = tk.Label(img_info_frame, text="Image: 0/0",
                                       bg=self.colors['bg'], fg=self.colors['fg'],
                                       font=('Arial', 10))
        self.image_nav_label.pack()
        
        # ===== MIDDLE SECTION: TEXT AND IMAGE =====
        middle_frame = tk.Frame(right_panel, bg=self.colors['bg'])
        middle_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Text content (Left side)
        text_frame = tk.LabelFrame(middle_frame, text="📖 PAGE TEXT CONTENT",
                                  bg=self.colors['card_bg'], fg=self.colors['fg'],
                                  font=('Arial', 11, 'bold'))
        text_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        self.text_display = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD,
                                                     bg=self.colors['text_bg'], fg='white',
                                                     font=('Courier New', 10), height=15)
        self.text_display.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Image preview (Right side)
        image_preview_frame = tk.LabelFrame(middle_frame, text="🖼️ IMAGE PREVIEW",
                                           bg=self.colors['card_bg'], fg=self.colors['fg'],
                                           font=('Arial', 11, 'bold'))
        image_preview_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))
        
        # Canvas for image display
        self.image_canvas = tk.Canvas(image_preview_frame, 
                                     bg=self.colors['image_bg'],
                                     highlightthickness=0)
        self.image_canvas.pack(fill='both', expand=True, padx=10, pady=10)
        
        # No image label
        self.no_image_label = tk.Label(self.image_canvas, 
                                      text="📷 No image on this page\n\nClick 'Analyze Images' to process",
                                      bg=self.colors['image_bg'],
                                      fg=self.colors['fg'],
                                      font=('Arial', 12))
        self.no_image_label.place(relx=0.5, rely=0.5, anchor='center')
        
        # ===== ANALYSIS HIGHLIGHTS =====
        analysis_frame = tk.Frame(right_panel, bg=self.colors['bg'])
        analysis_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Create 3 columns
        for i in range(3):
            analysis_frame.columnconfigure(i, weight=1)
        
        # Entities
        entity_frame = tk.LabelFrame(analysis_frame, text="👤 IDENTIFIED ENTITIES",
                                    bg=self.colors['card_bg'], fg=self.colors['fg'],
                                    font=('Arial', 10, 'bold'))
        entity_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5), pady=5)
        
        self.entity_text = scrolledtext.ScrolledText(entity_frame, wrap=tk.WORD,
                                                    bg=self.colors['text_bg'], fg='white',
                                                    font=('Arial', 9), height=6)
        self.entity_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Keywords
        keyword_frame = tk.LabelFrame(analysis_frame, text="🔑 CRITICAL KEYWORDS",
                                     bg=self.colors['card_bg'], fg=self.colors['fg'],
                                     font=('Arial', 10, 'bold'))
        keyword_frame.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)
        
        self.keyword_text = scrolledtext.ScrolledText(keyword_frame, wrap=tk.WORD,
                                                     bg=self.colors['text_bg'], fg='white',
                                                     font=('Arial', 9), height=6)
        self.keyword_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Events
        event_frame = tk.LabelFrame(analysis_frame, text="⚠️ MAJOR EVENTS",
                                   bg=self.colors['card_bg'], fg=self.colors['fg'],
                                   font=('Arial', 10, 'bold'))
        event_frame.grid(row=0, column=2, sticky='nsew', padx=(5, 0), pady=5)
        
        self.event_text = scrolledtext.ScrolledText(event_frame, wrap=tk.WORD,
                                                   bg=self.colors['text_bg'], fg='white',
                                                   font=('Arial', 9), height=6)
        self.event_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # ===== SEARCH SECTION =====
        search_frame = tk.LabelFrame(right_panel, text="❓ SMART QUESTION ANSWERING (COMPETITION MODE)",
                                    bg=self.colors['card_bg'], fg=self.colors['fg'],
                                    font=('Arial', 11, 'bold'))
        search_frame.pack(fill='x', pady=(0, 10))
        
        # Search input
        input_frame = tk.Frame(search_frame, bg=self.colors['card_bg'])
        input_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(input_frame, text="🔍 Question:", bg=self.colors['card_bg'], 
                fg=self.colors['fg'], font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 10))
        
        self.search_entry = tk.Entry(input_frame, width=60, 
                                    bg=self.colors['text_bg'], fg='white',
                                    font=('Arial', 10))
        self.search_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        self.search_entry.bind('<Return>', lambda e: self.ask_question())
        
        tk.Button(input_frame, text="🚀 ASK GROQ AI", command=self.ask_question,
                 bg=self.colors['accent'], fg='white',
                 font=('Arial', 10, 'bold')).pack(side='right')
        
        # Answer Display
        answer_frame = tk.Frame(search_frame, bg=self.colors['card_bg'])
        answer_frame.pack(fill='x', padx=10, pady=(0, 10))
        
        self.answer_text = scrolledtext.ScrolledText(answer_frame, wrap=tk.WORD,
                                                    bg=self.colors['text_bg'], fg='white',
                                                    font=('Arial', 10), height=10)
        self.answer_text.pack(fill='x', pady=5)
        
        # ===== IMAGE DESCRIPTION SECTION (NEW SECTION) =====
        image_desc_frame = tk.LabelFrame(right_panel, text="📝 IMAGE ANALYSIS RESULTS",
                                        bg=self.colors['card_bg'], fg=self.colors['fg'],
                                        font=('Arial', 11, 'bold'))
        image_desc_frame.pack(fill='x')
        
        # Image Description Display
        self.image_desc_text = scrolledtext.ScrolledText(image_desc_frame, wrap=tk.WORD,
                                                        bg=self.colors['text_bg'], fg='white',
                                                        font=('Arial', 10), height=15)
        self.image_desc_text.pack(fill='x', padx=10, pady=10)
        
        # Initial message
        self.image_desc_text.insert('1.0', "No image analysis results yet.\n"
                                          "Extract images and click 'Analyze Images' to see descriptions here.")
        
        # Initial status update
        self.root.after(100, self.update_groq_status)
    
    def browse_pdf(self):
        """Browse and load PDF file"""
        filepath = filedialog.askopenfilename(
            title="Select PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        
        if filepath:
            self.current_pdf = filepath
            filename = os.path.basename(filepath)
            self.pdf_label.config(text=filename, fg=self.colors['accent'])
            
            # Enable image analysis button
            self.analyze_images_btn.config(state='normal')
            
            try:
                # Extract basic info
                doc = fitz.open(filepath)
                self.total_pages = len(doc)
                doc.close()
                self.page_label.config(text=f"Page 1 of {self.total_pages}")
                self.page_info_label.config(text=f"Page 0 of {self.total_pages}")
                
                # Extract images from PDF
                self.extract_images_from_pdf(filepath)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load PDF: {str(e)}")
    
    def extract_images_from_pdf(self, pdf_path):
        """Extract all images from PDF pages"""
        try:
            self.images_data = []
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images()
                
                if image_list:
                    for img_index, img in enumerate(image_list):
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        
                        # Convert to PIL Image
                        pil_image = Image.open(BytesIO(image_bytes))
                        
                        # Convert to RGB if necessary
                        if pil_image.mode != 'RGB':
                            pil_image = pil_image.convert('RGB')
                        
                        self.images_data.append({
                            'page': page_num + 1,
                            'index': img_index,
                            'image': pil_image,
                            'image_bytes': image_bytes,
                            'description': None  # Will be filled later
                        })
            
            doc.close()
            
            # Update status
            self.image_status_label.config(
                text=f"Images: {len(self.images_data)} found",
                fg=self.colors['accent'] if self.images_data else self.colors['warning']
            )
            
            # Update navigation label
            self.update_image_navigation_label()
            
            if self.images_data:
                self.show_current_image()
            else:
                self.show_no_image_message()
            
        except Exception as e:
            print(f"Error extracting images: {e}")
            self.image_status_label.config(
                text=f"Error extracting images",
                fg='red'
            )
    
    def analyze_images(self):
        """Analyze all extracted images using selected model"""
        if not self.images_data:
            messagebox.showinfo("No Images", "No images found in the PDF.")
            return
        
        self.status_label.config(text="Analyzing images...")
        self.progress['value'] = 0
        
        # Disable button during analysis
        self.analyze_images_btn.config(state='disabled')
        
        thread = threading.Thread(target=self.analyze_images_thread, daemon=True)
        thread.start()
    
    def analyze_images_thread(self):
        """Thread for image analysis"""
        try:
            total_images = len(self.images_data)
            
            for idx, img_data in enumerate(self.images_data):
                # Update progress
                progress_value = ((idx + 1) / total_images) * 100
                self.root.after(0, self.update_progress, progress_value, f"Image {idx+1}/{total_images}")
                
                # Analyze image
                description = self.analyze_single_image(img_data['image'])
                self.images_data[idx]['description'] = description
            
            # Analysis complete
            self.root.after(0, self.image_analysis_complete)
            
        except Exception as e:
            self.root.after(0, self.image_analysis_error, str(e))
    
    def analyze_single_image(self, pil_image):
        """Analyze single image using OpenRouter API"""
        try:
            # Convert PIL Image to base64
            buffered = BytesIO()
            pil_image.save(buffered, format="PNG")
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Prepare request
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.selected_image_model.get(),
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analyze this image in detail. Describe everything you see, including objects, text, people, colors, layout, and any important details. Be thorough and precise."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 800
            }
            
            # Send request
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                description = result['choices'][0]['message']['content']
                return description
            else:
                return f"Error: API returned status {response.status_code}"
                
        except Exception as e:
            return f"Error analyzing image: {str(e)}"
    
    def show_current_image(self):
        """Display current image on canvas"""
        if 0 <= self.current_image_index < len(self.images_data):
            img_data = self.images_data[self.current_image_index]
            
            # Hide no image label
            self.no_image_label.place_forget()
            
            # Get PIL image
            pil_image = img_data['image']
            
            # Calculate aspect ratio
            canvas_width = self.image_canvas.winfo_width()
            canvas_height = self.image_canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:
                # Resize image to fit canvas
                img_width, img_height = pil_image.size
                width_ratio = canvas_width / img_width
                height_ratio = canvas_height / img_height
                scale = min(width_ratio, height_ratio) * 0.9  # 90% of canvas
                
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                
                resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                tk_image = ImageTk.PhotoImage(resized_image)
                
                # Update canvas
                self.image_canvas.delete("all")
                self.image_canvas.create_image(canvas_width//2, canvas_height//2, 
                                              image=tk_image, anchor='center')
                self.image_canvas.image = tk_image  # Keep reference
                
                # Update navigation
                self.update_image_navigation_label()
                
                # Enable navigation buttons
                self.prev_img_btn.config(state='normal')
                self.next_img_btn.config(state='normal')
            
            # Show description if available
            self.show_image_description()
    
    def show_no_image_message(self):
        """Show message when no image is available"""
        self.no_image_label.place(relx=0.5, rely=0.5, anchor='center')
        self.image_canvas.delete("all")
        
        # Update navigation label
        self.image_nav_label.config(text="No images")
        
        # Disable navigation buttons
        self.prev_img_btn.config(state='disabled')
        self.next_img_btn.config(state='disabled')
    
    def show_image_description(self):
        """Display image description in the NEW image description section"""
        if 0 <= self.current_image_index < len(self.images_data):
            img_data = self.images_data[self.current_image_index]
            
            if img_data['description']:
                description = img_data['description']
            else:
                description = "Description not available. Click 'Analyze Images' to generate."
            
            # Format display for image description section
            formatted = f"""{"="*70}
🖼️ IMAGE ANALYSIS RESULT
{"="*70}

📊 MODEL: {self.selected_image_model.get()}
📄 PAGE: {img_data['page']}
🖼️ IMAGE: {self.current_image_index + 1}/{len(self.images_data)}

{"-"*70}
📝 DETAILED DESCRIPTION:
{"-"*70}

{description}

{"="*70}
✅ Image analysis complete
{"="*70}"""
            
            self.image_desc_text.delete('1.0', tk.END)
            self.image_desc_text.insert('1.0', formatted)
    
    def prev_image(self):
        """Show previous image"""
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.show_current_image()
    
    def next_image(self):
        """Show next image"""
        if self.current_image_index < len(self.images_data) - 1:
            self.current_image_index += 1
            self.show_current_image()
    
    def update_image_navigation_label(self):
        """Update image navigation label"""
        if self.images_data:
            self.image_nav_label.config(
                text=f"Image: {self.current_image_index + 1}/{len(self.images_data)}"
            )
        else:
            self.image_nav_label.config(text="Image: 0/0")
    
    def image_analysis_complete(self):
        """Called when image analysis is complete"""
        self.status_label.config(text="✅ Image Analysis Complete", fg=self.colors['accent'])
        self.progress['value'] = 100
        self.analyze_images_btn.config(state='normal')
        
        # Show first image description
        if self.images_data:
            self.current_image_index = 0
            self.show_current_image()
        
        messagebox.showinfo("Success", f"Image analysis complete!\nAnalyzed {len(self.images_data)} images.")
    
    def image_analysis_error(self, error):
        """Called when image analysis fails"""
        self.status_label.config(text="❌ Image Analysis Failed", fg='red')
        self.analyze_images_btn.config(state='normal')
        messagebox.showerror("Error", f"Image analysis failed: {error}")
    
    # ==================== POWERFUL GROQ SEARCH IMPLEMENTATION ====================
    
    def ask_question(self):
        """COMPETITION-LEVEL Groq search with advanced prompting"""
        question = self.search_entry.get().strip()
        if not question:
            messagebox.showwarning("Empty", "Enter a question!")
            return
        
        if not self.pdf_data:
            messagebox.showwarning("No Data", "Analyze PDF first!")
            return
        
        # Clear previous answer
        self.answer_text.delete('1.0', tk.END)
        self.answer_text.insert('1.0', "🚀 Processing with GROQ AI...\n(Master Analysis Mode)")
        self.root.update()
        
        # Get answer
        if self.ai_mode.get() == "smart" and self.groq_client:
            answer = self.powerful_groq_search(question)
        else:
            answer = self.rule_based_answer(question)
        
        # Display answer in answer section (below search box)
        self.answer_text.delete('1.0', tk.END)
        self.answer_text.insert('1.0', answer)
    
    def powerful_groq_search(self, question):
        """ULTRA-POWERFUL Groq search with competition-level prompting"""
        try:
            # Prepare enhanced context with image descriptions
            text_context = self.all_text[:8000]
            
            # Add image descriptions to context if available
            image_context = ""
            if self.images_data and any(img['description'] for img in self.images_data):
                image_context = "\n\nIMAGE DESCRIPTIONS:\n"
                for img in self.images_data[:3]:  # Limit to 3 images
                    if img['description']:
                        image_context += f"Page {img['page']}: {img['description'][:300]}...\n"
            
            full_context = text_context + image_context
            
            # COMPETITION-LEVEL PROMPT ENGINEERING
            prompt = f"""# EXPERT DOCUMENT ANALYSIS - COMPETITION MODE

## CONTEXT:
You are analyzing a comprehensive document with both text and images.

## DOCUMENT CONTENT:
{full_context}

## USER QUESTION:
{question}

## ANALYSIS FRAMEWORK:
Apply this multi-step reasoning:

### STEP 1: CONTEXTUAL UNDERSTANDING
1. Identify the document type, domain, and main topics
2. Extract key entities, relationships, and hierarchies
3. Map temporal and spatial elements if present

### STEP 2: MULTIMODAL INTEGRATION
1. Combine text evidence with image descriptions
2. Identify connections between visual and textual elements
3. Resolve any contradictions between modalities

### STEP 3: CRITICAL REASONING
1. Apply domain-specific knowledge (technical, scientific, narrative, etc.)
2. Use logical inference chains
3. Consider alternative interpretations
4. Evaluate evidence strength

### STEP 4: COMPREHENSIVE ANSWER CONSTRUCTION
1. Provide direct answer first
2. Include supporting evidence from both text and images
3. Explain reasoning process
4. Address potential ambiguities
5. Suggest related insights

## SPECIAL INSTRUCTIONS:
- BE CONFIDENT but precise
- CITE specific evidence (Page X, Image Y)
- USE bullet points for clarity when helpful
- INTEGRATE technical/narrative analysis as appropriate
- PROVIDE actionable insights if relevant
- IGNORE disclaimers like "I cannot see the image"

## FORMAT REQUIREMENTS:
- Start with clear, direct answer
- Use sections with headers if complex
- Include evidence citations
- End with key takeaways
'
## ANSWER:"""
            
            # Use available Groq models - Try different models if one fails
            groq_models = [
                "llama-3.1-8b-instant",        # Fast and reliable
                "llama-3.2-3b-preview",        # Alternative model
                "llama-3.2-1b-preview",        # Another alternative
                "mixtral-8x7b-32768",          # Mixtral model
                "gemma2-9b-it"                 # Gemma model
            ]
            
            answer_text = ""
            error_message = ""
            
            for model in groq_models:
                try:
                    response = self.groq_client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system", 
                                "content": "You are a world-class document analyst competing in an international competition. Provide master-level analysis that integrates text, images, and deep reasoning."
                            },
                            {
                                "role": "user", 
                                "content": prompt
                            }
                        ],
                        max_tokens=1500,
                        temperature=0.3,
                        top_p=0.95,
                        stream=False
                    )
                    
                    answer_text = response.choices[0].message.content.strip()
                    break  # Success, break out of loop
                    
                except Exception as model_error:
                    error_message = f"Model {model} failed: {str(model_error)[:100]}"
                    continue  # Try next model
            
            if not answer_text:
                # All models failed, fallback to rule-based
                return f"⚠️ All Groq models failed. {error_message}\n\nFallback Analysis:\n{self.rule_based_answer(question)}"
            
            # Enhanced formatting
            current_time = datetime.now().strftime("%H:%M:%S")
            formatted_answer = f"""{"="*80}
🚀 **COMPETITION ANALYSIS REPORT**
{"="*80}

📌 **QUESTION:** {question}

🔍 **ANALYSIS MODE:** GROQ AI Master Analysis
⏰ **TIME:** {current_time}
📊 **MODEL:** {model}
🖼️ **IMAGES ANALYZED:** {len([img for img in self.images_data if img['description']])}

{"-"*80}
📋 **COMPREHENSIVE ANSWER:**
{"-"*80}

{answer_text}

{"="*80}
✅ **ANALYSIS COMPLETE** | Confidence: High | Integration: Text+Images
{"="*80}"""
            
            return formatted_answer
            
        except Exception as e:
            error_msg = f"⚠️ GROQ Master Analysis Error: {str(e)[:100]}"
            fallback = self.rule_based_answer(question)
            return f"{error_msg}\n\nFallback Analysis:\n{fallback}"
    
    # ==================== EXISTING FUNCTIONS (KEEPING THEM) ====================
    
    def update_api_key(self):
        """Update Groq API key"""
        new_key = self.api_key_entry.get().strip()
        if new_key:
            self.groq_api_key = new_key
            if self.setup_groq():
                self.groq_status_label.config(text="Groq: ✅ Connected", fg=self.colors['accent'])
                messagebox.showinfo("Success", "Groq API key updated successfully!")
            else:
                self.groq_status_label.config(text="Groq: ❌ Failed", fg='red')
        else:
            messagebox.showwarning("Warning", "Please enter an API key")
    
    def update_groq_status(self):
        """Update Groq status label"""
        if hasattr(self, 'groq_status'):
            self.groq_status_label.config(
                text=f"Groq: {self.groq_status}",
                fg=self.colors['accent'] if self.groq_status == "Connected" else self.colors['warning']
            )
    
    def start_analysis(self):
        if not self.current_pdf:
            messagebox.showwarning("Warning", "Select a PDF first!")
            return
        
        self.status_label.config(text="Processing...")
        self.progress['value'] = 0
        
        thread = threading.Thread(target=self.analyze_pdf, daemon=True)
        thread.start()
    
    def analyze_pdf(self):
        """Analyze PDF text content"""
        try:
            doc = fitz.open(self.current_pdf)
            self.total_pages = len(doc)
            self.pdf_data = []
            self.all_text = ""
            
            for page_num in range(self.total_pages):
                progress = ((page_num + 1) / self.total_pages) * 100
                self.root.after(0, self.update_progress, progress, f"Page {page_num + 1}")
                
                page = doc.load_page(page_num)
                text = page.get_text()
                self.all_text += f"\n\n--- PAGE {page_num + 1} ---\n{text}"
                
                analysis = self.universal_analysis(text, page_num + 1)
                
                self.pdf_data.append({
                    'page': page_num + 1,
                    'text': text,
                    'analysis': analysis
                })
            
            doc.close()
            
            self.root.after(0, self.load_page, 0)
            self.root.after(0, self.analysis_complete)
            
        except Exception as e:
            self.root.after(0, self.analysis_error, str(e))
    
    def universal_analysis(self, text, page_num):
        """Advanced analysis using Groq API"""
        if not self.groq_client:
            return self._rule_based_analysis_fallback(text, page_num)
        
        try:
            text_chunk = text[:3500].strip()
            if len(text) > 3500:
                text_chunk += " [Text truncated for analysis]"
            
            prompt = f"""ANALYZE THIS TEXT AND EXTRACT INFORMATION:

TEXT FROM PAGE {page_num}:
"{text_chunk}"

EXTRACTION TASKS:
1. ENTITIES: Extract all important named entities (people, organizations, locations, technical terms)
2. KEYWORDS: Extract 5-10 most important keywords or key phrases
3. EVENTS: Extract key events, actions, or important occurrences

OUTPUT FORMAT - Return ONLY a valid JSON object with this exact structure:
{{
  "entities": ["Entity 1", "Entity 2", "Entity 3"],
  "keywords": ["Keyword 1", "Keyword 2", "Keyword 3"],
  "events": ["Event 1", "Event 2", "Event 3"]
}}

RETURN ONLY THE JSON OBJECT:"""
            
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert document analyst. Extract information accurately and return ONLY valid JSON."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.1,
                top_p=0.9
            )
            
            result_text = response.choices[0].message.content.strip()
            
            try:
                clean_text = result_text.replace('```json', '').replace('```', '').strip()
                analysis_data = json.loads(clean_text)
                
                analysis = {
                    'entities': list(analysis_data.get('entities', []))[:8],
                    'keywords': list(analysis_data.get('keywords', []))[:6],
                    'events': list(analysis_data.get('events', []))[:5]
                }
                
                return analysis
                
            except (json.JSONDecodeError, KeyError, ValueError):
                return self._rule_based_analysis_fallback(text, page_num)
                
        except Exception as api_error:
            return self._rule_based_analysis_fallback(text, page_num)
    
    def _rule_based_analysis_fallback(self, text, page_num):
        """Fallback rule-based analysis"""
        analysis = {
            'entities': [],
            'keywords': [],
            'events': []
        }
        
        # Entity extraction
        sentences = text.split('.')
        entity_context = {}
        
        for sentence in sentences:
            if len(sentence.strip()) > 10:
                entity_matches = self.extract_entities_with_context(sentence)
                for entity, role in entity_matches:
                    if entity not in analysis['entities']:
                        analysis['entities'].append(f"{entity} ({role})")
                        entity_context[entity] = role
        
        # Keywords extraction
        universal_categories = {
            "CHARACTERS": ['said', 'asked', 'replied', 'answered', 'whispered', 'shouted'],
            "ACTIONS": ['went', 'came', 'ran', 'walked', 'entered', 'left', 'took', 'gave'],
            "OBJECTS": ['book', 'letter', 'key', 'door', 'window', 'car', 'house', 'room'],
            "EMOTIONS": ['happy', 'sad', 'angry', 'scared', 'surprised', 'excited'],
            "TIME": ['morning', 'afternoon', 'evening', 'night', 'day', 'week', 'month', 'year'],
            "LOCATIONS": ['home', 'office', 'school', 'hospital', 'street', 'park', 'city']
        }
        
        text_lower = text.lower()
        for category, keywords in universal_categories.items():
            found_keywords = []
            for keyword in keywords:
                if keyword in text_lower:
                    found_keywords.append(keyword.upper())
            
            if found_keywords:
                analysis['keywords'].append(f"{category}: {', '.join(found_keywords[:3])}")
        
        # Events detection
        event_patterns = [
            ("DIALOGUE", ['"', 'said', 'asked', 'replied', 'answered']),
            ("ACTION", ['went to', 'came from', 'ran towards', 'walked into']),
            ("DISCOVERY", ['found', 'discovered', 'noticed', 'saw', 'observed']),
            ("CONFLICT", ['argued', 'fought', 'disagreed', 'confronted']),
            ("DECISION", ['decided', 'chose', 'selected', 'picked']),
            ("REVELATION", ['realized', 'understood', 'learned', 'found out']),
            ("TRANSITION", ['then', 'next', 'after', 'later', 'meanwhile']),
            ("DESCRIPTION", ['was', 'were', 'had', 'looked', 'seemed', 'appeared'])
        ]
        
        for sentence in sentences:
            sentence_lower = sentence.lower().strip()
            if len(sentence_lower) > 10:
                for event_name, triggers in event_patterns:
                    for trigger in triggers:
                        if trigger in sentence_lower:
                            clean_sentence = sentence.strip()
                            if len(clean_sentence) > 20:
                                analysis['events'].append(f"{event_name}: {clean_sentence[:80]}...")
                            break
        
        for key in analysis:
            analysis[key] = list(set(analysis[key]))[:10]
        
        return analysis
    
    def extract_entities_with_context(self, sentence):
        """Extract entities with their roles/context"""
        entities = []
        sentence_lower = sentence.lower()
        
        patterns = [
            (r'(Detective|Officer|Constable|Inspector|Sergeant)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', 'detective'),
            (r'(Dr\.|Doctor|Nurse|Surgeon|Physician)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', 'medical'),
            (r'(Professor|Prof\.|Lecturer|Teacher)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', 'academic'),
            (r'(Mr\.|Mrs\.|Ms\.|Miss|Master)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', 'person'),
            (r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b', 'person'),
            (r'\b([A-Z][a-z]{2,})\b(?=\s+(?:said|asked|replied|went|came|took))', 'person')
        ]
        
        for pattern, role in patterns:
            matches = re.findall(pattern, sentence)
            for match in matches:
                if isinstance(match, tuple):
                    name_parts = [m for m in match if m and len(m) > 1]
                    if name_parts:
                        entity = ' '.join(name_parts)
                        if entity.lower() not in ['the', 'and', 'but', 'for', 'from', 'this', 'that', 'with']:
                            entities.append((entity, role))
        
        return entities
    
    def update_progress(self, value, status_text):
        self.progress['value'] = value
        self.status_label.config(text=status_text)
    
    def analysis_complete(self):
        self.status_label.config(text="✅ Analysis Complete", fg=self.colors['accent'])
        self.progress['value'] = 100
        self.page_info_label.config(text=f"Page {self.current_page + 1} of {self.total_pages}")
        messagebox.showinfo("Success", f"Analysis complete!\nPages: {len(self.pdf_data)}\nImages: {len(self.images_data)}")
    
    def analysis_error(self, error):
        self.status_label.config(text="❌ Analysis Failed", fg='red')
        messagebox.showerror("Error", f"Analysis failed: {error}")
    
    def load_page(self, page_index):
        if not self.pdf_data or page_index < 0 or page_index >= len(self.pdf_data):
            return
        
        self.current_page = page_index
        page_data = self.pdf_data[page_index]
        
        self.page_label.config(text=f"Page {page_data['page']} of {len(self.pdf_data)}")
        self.page_info_label.config(text=f"Page {page_data['page']} of {self.total_pages}")
        
        self.prev_btn.config(state='normal' if page_index > 0 else 'disabled')
        self.next_btn.config(state='normal' if page_index < len(self.pdf_data) - 1 else 'disabled')
        
        self.text_display.delete('1.0', tk.END)
        self.text_display.insert('1.0', page_data['text'])
        
        analysis = page_data['analysis']
        
        self.entity_text.delete('1.0', tk.END)
        if analysis['entities']:
            self.entity_text.insert('1.0', "👤 IDENTIFIED ENTITIES:\n" + "="*30 + "\n\n")
            for entity in analysis['entities'][:8]:
                self.entity_text.insert(tk.END, f"• {entity}\n")
        else:
            self.entity_text.insert('1.0', "No entities identified.\n")
        
        self.keyword_text.delete('1.0', tk.END)
        if analysis['keywords']:
            self.keyword_text.insert('1.0', "🔑 KEY CATEGORIES:\n" + "="*30 + "\n\n")
            for keyword in analysis['keywords']:
                self.keyword_text.insert(tk.END, f"• {keyword}\n")
        else:
            self.keyword_text.insert('1.0', "No keywords identified.\n")
        
        self.event_text.delete('1.0', tk.END)
        if analysis['events']:
            self.event_text.insert('1.0', "⚠️ STORY EVENTS:\n" + "="*30 + "\n\n")
            for event in analysis['events'][:5]:
                self.event_text.insert(tk.END, f"• {event}\n\n")
        else:
            self.event_text.insert('1.0', "No events detected.\n")
    
    def prev_page(self):
        if self.current_page > 0:
            self.load_page(self.current_page - 1)
    
    def next_page(self):
        if self.current_page < len(self.pdf_data) - 1:
            self.load_page(self.current_page + 1)
    
    def rule_based_answer(self, question):
        """Rule-based answer fallback"""
        question_lower = question.lower()
        
        answers_info = {
            'direct_matches': [],
            'context_matches': [],
            'named_entities': [],
            'page_references': set()
        }
        
        question_type = self.detect_question_type(question_lower)
        
        for page_data in self.pdf_data:
            text = page_data['text']
            text_lower = text.lower()
            page_num = page_data['page']
            
            sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
            
            for sentence in sentences:
                sentence_lower = sentence.lower()
                relevance = self.calculate_relevance(sentence_lower, question_lower)
                
                if relevance > 0.7:
                    answers_info['direct_matches'].append({
                        'text': sentence,
                        'page': page_num,
                        'relevance': relevance,
                        'type': 'direct'
                    })
                    answers_info['page_references'].add(page_num)
                
                elif relevance > 0.4:
                    answers_info['context_matches'].append({
                        'text': sentence,
                        'page': page_num,
                        'relevance': relevance,
                        'type': 'context'
                    })
                    answers_info['page_references'].add(page_num)
            
            if question_type == 'who':
                self.extract_names_improved(answers_info, text, page_num, question_lower)
            elif question_type == 'when':
                self.extract_dates_times(answers_info, text, page_num)
            elif question_type == 'where':
                self.extract_locations(answers_info, text, page_num)
            elif question_type == 'number':
                self.extract_numbers(answers_info, text, page_num)
            elif question_type == 'why':
                self.extract_reasons(answers_info, text, page_num)
        
        return self.format_rule_based_answer(question, answers_info, question_type)
    
    def detect_question_type(self, question_lower):
        if 'who' in question_lower:
            return 'who'
        elif 'when' in question_lower:
            return 'when'
        elif 'where' in question_lower:
            return 'where'
        elif 'how many' in question_lower or 'how much' in question_lower:
            return 'number'
        elif 'why' in question_lower:
            return 'why'
        elif 'what' in question_lower:
            return 'what'
        elif 'how' in question_lower:
            return 'how'
        return 'general'
    
    def calculate_relevance(self, sentence, question):
        sentence_words = set(re.findall(r'\b\w+\b', sentence.lower()))
        question_words = set(re.findall(r'\b\w+\b', question.lower()))
        
        if not sentence_words or not question_words:
            return 0.0
        
        common_words = sentence_words.intersection(question_words)
        score = len(common_words) / max(len(question_words), 1)
        
        question_keywords = ['who', 'what', 'when', 'where', 'why', 'how']
        for keyword in question_keywords:
            if keyword in question and keyword in sentence:
                score += 0.2
        
        return min(score, 1.0)
    
    def extract_names_improved(self, answers_info, text, page_num, question_lower):
        for page_data in self.pdf_data:
            if page_data['page'] == page_num:
                entities = page_data['analysis'].get('entities', [])
                for entity in entities[:5]:
                    answers_info['named_entities'].append({
                        'text': entity,
                        'page': page_num,
                        'type': 'entity'
                    })
                break
        
        name_patterns = [
            r'Detective\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'Dr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'Officer\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'Professor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    name = ' '.join([m for m in match if m])
                else:
                    name = match
                
                if (len(name) > 3 and 
                    name.lower() not in ['the', 'and', 'but', 'for'] and
                    not any(month in name.lower() for month in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'])):
                    
                    is_relevant = True
                    if 'detective' in question_lower and 'detective' not in name.lower():
                        is_relevant = False
                    
                    if is_relevant:
                        answers_info['named_entities'].append({
                            'text': f"Identified: {name}",
                            'page': page_num,
                            'type': 'name'
                        })
    
    def extract_dates_times(self, answers_info, text, page_num):
        date_patterns = [
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b',
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b',
            r'\b\d{1,2}:\d{2}\s*(?:AM|PM|GMT)?\b',
            r'\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
            r'\b(?:morning|afternoon|evening|night|noon|midnight)\b'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                answers_info['named_entities'].append({
                    'text': f"Date/Time: {match}",
                    'page': page_num,
                    'type': 'datetime'
                })
    
    def extract_locations(self, answers_info, text, page_num):
        location_patterns = [
            r'\b(?:at|in|near|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b',
            r'\b(?:room|office|building|house|apartment|street|avenue|road)\s+[A-Z]?\d*\b',
            r'coordinates?\s*[:=]?\s*(\d+\.\d+°?\s*[NS],?\s*\d+\.\d+°?\s*[EW])',
            r'Server Room\s+[A-Z]'
        ]
        
        for pattern in location_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    location = ' '.join([m for m in match if m])
                else:
                    location = match
                
                if len(location) > 3:
                    answers_info['named_entities'].append({
                        'text': f"Location: {location}",
                        'page': page_num,
                        'type': 'location'
                    })
    
    def extract_numbers(self, answers_info, text, page_num):
        number_patterns = [
            r'\b\d+\s*(?:percent|%)\b',
            r'\b\d+\.?\d*\s*(?:TB|GB|MB|KB)\b',
            r'\b\d+\s*(?:dollars|USD|Rs|rupees)\b',
            r'\b\d+\s*(?:hours|minutes|seconds|days|weeks|months|years)\b',
            r'\b\d+\.?\d*\s*(?:°C|degrees|℃)\b',
            r'\b\d+\.?\d*\s*(?:GHz|MHz|Hz)\b'
        ]
        
        for pattern in number_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                answers_info['named_entities'].append({
                    'text': f"Numerical: {match}",
                    'page': page_num,
                    'type': 'number'
                })
    
    def extract_reasons(self, answers_info, text, page_num):
        reason_keywords = ['because', 'since', 'as', 'due to', 'reason', 'cause', 'therefore', 'thus']
        
        sentences = text.split('.')
        for sentence in sentences:
            sentence_lower = sentence.lower()
            for keyword in reason_keywords:
                if keyword in sentence_lower:
                    answers_info['named_entities'].append({
                        'text': sentence.strip()[:150],
                        'page': page_num,
                        'type': 'reason'
                    })
                    break
    
    def format_rule_based_answer(self, question, answers_info, question_type):
        formatted = f"""{"="*70}
🔍 QUESTION: {question}
{"="*70}

"""
        
        answers_info['direct_matches'].sort(key=lambda x: x['relevance'], reverse=True)
        answers_info['context_matches'].sort(key=lambda x: x['relevance'], reverse=True)
        
        if answers_info['direct_matches']:
            formatted += f"""✅ MOST RELEVANT MATCHES:
{"-"*30}\n"""
            
            for i, match in enumerate(answers_info['direct_matches'][:3], 1):
                page_ref = f" (Page {match['page']})" if match['page'] else ""
                formatted += f"""📌 {i}. {match['text'][:120]}...{page_ref}
   Relevance: {match['relevance']:.1%}

"""
        
        if answers_info['context_matches'] and not answers_info['direct_matches']:
            formatted += f"""📄 CONTEXTUAL INFORMATION:
{"-"*30}\n"""
            
            for i, match in enumerate(answers_info['context_matches'][:3], 1):
                page_ref = f" (Page {match['page']})" if match['page'] else ""
                formatted += f"""📌 {i}. {match['text'][:100]}...{page_ref}
   Relevance: {match['relevance']:.1%}

"""
        
        if answers_info['named_entities'] and question_type in ['who', 'what']:
            formatted += f"""👤 IDENTIFIED ENTITIES:
{"-"*30}\n"""
            
            unique_entities = []
            seen = set()
            for entity in answers_info['named_entities']:
                if entity['text'] not in seen:
                    seen.add(entity['text'])
                    unique_entities.append(entity)
            
            for i, entity in enumerate(unique_entities[:5], 1):
                page_ref = f" (Page {entity['page']})" if entity['page'] else ""
                formatted += f"   • {entity['text']}{page_ref}\n"
            formatted += "\n"
        
        if answers_info['page_references']:
            pages = sorted(answers_info['page_references'])
            formatted += f"""📄 RELEVANT PAGES: {', '.join(map(str, pages))}

"""
        
        total_matches = len(answers_info['direct_matches']) + len(answers_info['context_matches'])
        
        if total_matches > 0:
            formatted += f"""{"="*70}
📊 SUMMARY:
• Question Type: {question_type.upper()}
• Total matches found: {total_matches}
• Relevant pages: {len(answers_info['page_references'])}
• Mode: Fast Rule-based Search
• Status: ✅ Information found
{"="*70}"""
        else:
            formatted += f"""❌ NO DIRECT MATCHES FOUND

💡 SUGGESTIONS:
1. Try rephrasing your question
2. Use Smart AI mode for better understanding
3. Check analysis sections above for context
4. Search for specific keywords manually

{"="*70}
📊 SUMMARY:
• Question Type: {question_type.upper()}
• Mode: Fast Rule-based Search
• Status: ⚠️ No direct matches found
• Tip: Use more specific keywords
{"="*70}"""
        
        return formatted
    
    def format_answer(self, question, answer_text, mode_name):
        current_time = datetime.now().strftime("%H:%M:%S")
        
        formatted = f"""{"="*70}
❓ QUESTION: {question}
{"="*70}

🤖 {mode_name} ANSWER:
{"-"*30}

{answer_text}

{"="*70}
📊 MODE: {mode_name} | Time: {current_time}
{"="*70}"""
        
        return formatted

# ==================== MAIN EXECUTION ====================

if __name__ == "__main__":
    # Check required packages
    try:
        import fitz  # PyMuPDF
        import requests
        from PIL import Image, ImageTk
        
        try:
            from groq import Groq
        except ImportError:
            print("⚠️ Installing missing packages...")
            import subprocess
            subprocess.check_call(["pip", "install", "groq"])
            from groq import Groq
        
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("Please install required packages:")
        print("pip install PyMuPDF requests pillow groq")
        exit(1)
    
    root = tk.Tk()
    app = SmartPDFAnalyzer(root)
    root.mainloop()