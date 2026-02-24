import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
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
from PIL import Image

# Hide deprecation warnings
warnings.filterwarnings("ignore")

# Configuration for CustomTkinter
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class SmartPDFAnalyzer(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Smart PDF Analyzer - Competition Edition")
        self.geometry("1400x900")
        
        # Data storage
        self.pdf_data = []
        self.current_pdf = None
        self.current_page = 0
        self.total_pages = 0
        self.all_text = ""
        self.images_data = []
        self.current_image_index = 0
        self.image_descriptions = {}
        self.all_entities = []
        self.all_keywords = []
        self.all_events = []
        
        # API Keys
        self.groq_api_key = ""
        self.openrouter_api_key = ""
        
        # Initialize APIs
        self.groq_client = None
        self.groq_status = "Not Initialized"
        self.setup_groq()
        
        # Image Models
        self.image_models = [
            "qwen/qwen-2.5-vl-72b-instruct",
               "anthropic/claude-3-haiku", # Free tier available
    "openai/gpt-4o-mini",   
            "meta-llama/llama-3.2-11b-vision-instruct"
        ]
        
        self.create_gui()

    def setup_groq(self):
        """Setup Groq API"""
        try:
            from groq import Groq
            self.groq_client = Groq(api_key=self.groq_api_key)
            
            # Test the connection immediately
            test_response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            self.groq_status = "Connected ✅"
            print("Groq API Connection: SUCCESS")
            return True
        except ImportError:
            self.groq_status = "Package Missing ❌"
            print("ERROR: Please run: pip install groq")
            return False
        except Exception as e:
            self.groq_status = f"Error: {str(e)[:50]} ❌"
            print(f"Groq API Connection Error: {e}")
            return False

    def create_gui(self):
        # Configure grid layout (1x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ============ SIDEBAR (LEFT) ============
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(9, weight=1)

        # Logo / Title
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="🚀 PDF ANALYZER", 
                                     font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        self.subtitle_label = ctk.CTkLabel(self.sidebar_frame, text="Competition Edition", 
                                         text_color="gray")
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 20))

        # File Selection
        self.btn_browse = ctk.CTkButton(self.sidebar_frame, text="📂 Open PDF File", 
                                      command=self.browse_pdf, height=40,
                                      fg_color="#2E7D32", hover_color="#1B5E20")
        self.btn_browse.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        self.label_filename = ctk.CTkLabel(self.sidebar_frame, text="No File Selected", 
                                         text_color="gray", wraplength=200)
        self.label_filename.grid(row=3, column=0, padx=20, pady=(0, 10))

        # Start Analysis Button
        self.btn_analyze = ctk.CTkButton(self.sidebar_frame, text="▶ Start Text Analysis", 
                                       command=self.start_analysis, state="disabled",
                                       height=40)
        self.btn_analyze.grid(row=4, column=0, padx=20, pady=10, sticky="ew")

        # Image Analysis Settings
        self.separator_1 = ctk.CTkLabel(self.sidebar_frame, text="🖼️ IMAGE ANALYSIS", 
                                      font=ctk.CTkFont(size=12, weight="bold"))
        self.separator_1.grid(row=5, column=0, padx=20, pady=(20, 5), sticky="w")
        
        self.option_model = ctk.CTkOptionMenu(self.sidebar_frame, values=self.image_models)
        self.option_model.grid(row=6, column=0, padx=20, pady=5, sticky="ew")
        
        self.btn_analyze_img = ctk.CTkButton(self.sidebar_frame, text="🔍 Analyze Images", 
                                           command=self.analyze_images, state="disabled",
                                           fg_color="#C62828", hover_color="#B71C1C")
        self.btn_analyze_img.grid(row=7, column=0, padx=20, pady=10, sticky="ew")

        # Progress Bar (Bottom of Sidebar)
        self.progress_bar = ctk.CTkProgressBar(self.sidebar_frame)
        self.progress_bar.grid(row=10, column=0, padx=20, pady=10, sticky="ew")
        self.progress_bar.set(0)
        
        # API Status Display
        self.api_status_label = ctk.CTkLabel(self.sidebar_frame, text=f"Groq: {self.groq_status}", 
                                           font=("Arial", 10))
        self.api_status_label.grid(row=11, column=0, padx=20, pady=(10, 5))
        
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Ready", font=("Arial", 10))
        self.status_label.grid(row=12, column=0, padx=20, pady=(0, 20))

        # ============ MAIN CONTENT (RIGHT) ============
        self.main_view = ctk.CTkTabview(self, corner_radius=10)
        self.main_view.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.tab_dashboard = self.main_view.add("📊 Dashboard")
        self.tab_reader = self.main_view.add("📖 Reader & Images")
        self.tab_search = self.main_view.add("❓ Smart Search")

        self.setup_reader_tab()
        self.setup_dashboard_tab()
        self.setup_search_tab()

    def setup_reader_tab(self):
        """Setup the Reader Tab (Split Text and Image)"""
        self.tab_reader.grid_columnconfigure(0, weight=1)
        self.tab_reader.grid_columnconfigure(1, weight=1)
        self.tab_reader.grid_rowconfigure(1, weight=1)

        # Navigation Bar
        nav_frame = ctk.CTkFrame(self.tab_reader, height=50, fg_color="transparent")
        nav_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        self.btn_prev_page = ctk.CTkButton(nav_frame, text="◀ Prev", width=80, 
                                         command=self.prev_page, state="disabled")
        self.btn_prev_page.pack(side="left")
        
        self.lbl_page_counter = ctk.CTkLabel(nav_frame, text="Page 0 / 0", font=("Arial", 14, "bold"))
        self.lbl_page_counter.pack(side="left", padx=20)
        
        self.btn_next_page = ctk.CTkButton(nav_frame, text="Next ▶", width=80, 
                                         command=self.next_page, state="disabled")
        self.btn_next_page.pack(side="left")

        # Text Area (Left)
        text_frame = ctk.CTkFrame(self.tab_reader)
        text_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        
        ctk.CTkLabel(text_frame, text="TEXT CONTENT", font=("Arial", 12, "bold")).pack(pady=5)
        self.textbox_content = ctk.CTkTextbox(text_frame, font=("Courier New", 13))
        self.textbox_content.pack(fill="both", expand=True, padx=5, pady=5)

        # Image Area (Right)
        image_frame = ctk.CTkFrame(self.tab_reader)
        image_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0))
        
        ctk.CTkLabel(image_frame, text="IMAGE PREVIEW", font=("Arial", 12, "bold")).pack(pady=5)
        
        # Image Display Container
        self.image_display_label = ctk.CTkLabel(image_frame, text="\n\nNo Image Selected\nor No Images on Page", 
                                              font=("Arial", 14), text_color="gray")
        self.image_display_label.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Image Nav
        img_nav = ctk.CTkFrame(image_frame, height=40, fg_color="transparent")
        img_nav.pack(fill="x", pady=5)
        
        self.btn_prev_img = ctk.CTkButton(img_nav, text="◀", width=40, command=self.prev_image, state="disabled")
        self.btn_prev_img.pack(side="left", padx=5)
        
        self.lbl_img_counter = ctk.CTkLabel(img_nav, text="Img 0/0")
        self.lbl_img_counter.pack(side="left", expand=True)
        
        self.btn_next_img = ctk.CTkButton(img_nav, text="▶", width=40, command=self.next_image, state="disabled")
        self.btn_next_img.pack(side="right", padx=5)

    def setup_dashboard_tab(self):
        """Setup Dashboard for Analysis Results"""
        self.tab_dashboard.grid_columnconfigure((0, 1, 2), weight=1)
        self.tab_dashboard.grid_rowconfigure(1, weight=1)

        # Headers
        ctk.CTkLabel(self.tab_dashboard, text="👤 ENTITIES", font=("Arial", 14, "bold"), text_color="#64B5F6").grid(row=0, column=0, pady=10)
        ctk.CTkLabel(self.tab_dashboard, text="🔑 KEYWORDS", font=("Arial", 14, "bold"), text_color="#81C784").grid(row=0, column=1, pady=10)
        ctk.CTkLabel(self.tab_dashboard, text="⚠️ EVENTS", font=("Arial", 14, "bold"), text_color="#FFB74D").grid(row=0, column=2, pady=10)

        # Text Boxes
        self.box_entities = ctk.CTkTextbox(self.tab_dashboard)
        self.box_entities.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        self.box_keywords = ctk.CTkTextbox(self.tab_dashboard)
        self.box_keywords.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        
        self.box_events = ctk.CTkTextbox(self.tab_dashboard)
        self.box_events.grid(row=1, column=2, sticky="nsew", padx=5, pady=5)
        
        # Image Analysis Result at Bottom
        ctk.CTkLabel(self.tab_dashboard, text="📝 IMAGE ANALYSIS REPORT", font=("Arial", 14, "bold")).grid(row=2, column=0, columnspan=3, pady=(20, 5))
        self.box_image_analysis = ctk.CTkTextbox(self.tab_dashboard, height=150)
        self.box_image_analysis.grid(row=3, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

    def setup_search_tab(self):
        """Setup Search/Chat Tab"""
        self.tab_search.grid_columnconfigure(0, weight=1)
        self.tab_search.grid_rowconfigure(2, weight=1)

        # Input Area
        input_frame = ctk.CTkFrame(self.tab_search, fg_color="transparent")
        input_frame.grid(row=0, column=0, sticky="ew", pady=(10, 20))
        
        self.entry_question = ctk.CTkEntry(input_frame, placeholder_text="Ask ANY question about the PDF...", height=50, font=("Arial", 14))
        self.entry_question.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_question.bind('<Return>', lambda e: self.ask_question())
        
        self.btn_ask = ctk.CTkButton(input_frame, text="🚀 ASK GROQ AI", width=150, height=50, 
                                   command=self.ask_question, font=("Arial", 14, "bold"),
                                   fg_color="#9C27B0", hover_color="#7B1FA2")
        self.btn_ask.pack(side="right")
        
        # Mode Selection
        mode_frame = ctk.CTkFrame(self.tab_search, fg_color="transparent")
        mode_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        
        self.search_mode = ctk.StringVar(value="groq")
        ctk.CTkRadioButton(mode_frame, text="🧠 GROQ AI (Intelligent)", variable=self.search_mode, value="groq").pack(side="left", padx=20)
        ctk.CTkRadioButton(mode_frame, text="⚡ Fast Search", variable=self.search_mode, value="fast").pack(side="left", padx=20)

        # Output Area
        self.box_answer = ctk.CTkTextbox(self.tab_search, font=("Arial", 14))
        self.box_answer.grid(row=2, column=0, sticky="nsew")
        self.box_answer.insert("0.0", "🤖 Ask a question about your PDF content...")

    # ==================== LOGIC SECTION ====================

    def browse_pdf(self):
        filepath = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if filepath:
            self.current_pdf = filepath
            self.label_filename.configure(text=os.path.basename(filepath))
            self.btn_analyze.configure(state="normal")
            
            try:
                doc = fitz.open(filepath)
                self.total_pages = len(doc)
                doc.close()
                self.extract_images_from_pdf(filepath)
                self.lbl_page_counter.configure(text=f"Page 0 / {self.total_pages}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")

    def extract_images_from_pdf(self, pdf_path):
        try:
            self.images_data = []
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    pil_image = Image.open(BytesIO(base_image["image"]))
                    if pil_image.mode != 'RGB':
                        pil_image = pil_image.convert('RGB')
                    
                    self.images_data.append({
                        'page': page_num + 1,
                        'image': pil_image,
                        'description': None
                    })
            
            if self.images_data:
                self.btn_analyze_img.configure(state="normal")
                self.update_image_display()
            
            self.status_label.configure(text=f"Images Found: {len(self.images_data)}")
            doc.close()
        except Exception as e:
            print(f"Img Error: {e}")

    def start_analysis(self):
        if not self.groq_client:
            messagebox.showwarning("API Error", "Groq API is not connected. Please check your API key.")
            return
            
        self.progress_bar.set(0)
        self.status_label.configure(text="Processing text with Groq AI...")
        threading.Thread(target=self.analyze_pdf, daemon=True).start()

    def analyze_pdf(self):
        try:
            doc = fitz.open(self.current_pdf)
            self.pdf_data = []
            self.all_text = ""
            self.all_entities = []
            self.all_keywords = []
            self.all_events = []
            
            for i in range(self.total_pages):
                self.after(0, lambda v=i: self.progress_bar.set((v+1)/self.total_pages))
                
                page = doc.load_page(i)
                text = page.get_text()
                self.all_text += f"\nPage {i+1}: {text}"
                
                analysis = self.intelligent_groq_analysis(text, i+1)
                self.pdf_data.append({'page': i+1, 'text': text, 'analysis': analysis})
                
                if analysis:
                    self.all_entities.extend(analysis.get('entities', []))
                    self.all_keywords.extend(analysis.get('keywords', []))
                    self.all_events.extend(analysis.get('events', []))
            
            doc.close()
            self.after(0, self.analysis_complete)
        except Exception as e:
            print(f"Analysis Error: {e}")

    def intelligent_groq_analysis(self, text, page_num):
        """Use Groq AI to intelligently extract entities, keywords, and events"""
        if not self.groq_client:
            return self.rule_based_fallback(text)
        
        try:
            prompt = f"""Extract from this text (Page {page_num}):

            Text: {text[:3000]}

            Return ONLY a JSON object with these keys:
            1. "entities": List of important entities (people, organizations, locations, concepts)
            2. "keywords": List of key terms and concepts (max 10)
            3. "events": List of critical events, actions, or important points

            Format each list as an array of strings. Be comprehensive and accurate."""
            
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are a precise text analyzer. Extract structured information from text. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            result = response.choices[0].message.content
            
            # Clean the response
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.startswith("```"):
                result = result[3:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()
            
            analysis = json.loads(result)
            return analysis
            
        except Exception as e:
            print(f"Groq Analysis Error: {e}")
            return self.rule_based_fallback(text)

    def rule_based_fallback(self, text):
        """Fallback when Groq is not available"""
        words = text.split()
        entities = []
        for word in words:
            if len(word) > 2 and word[0].isupper() and word not in entities:
                entities.append(word)
        
        common_words = {'the', 'and', 'is', 'in', 'of', 'to', 'a', 'that', 'it', 'for', 'on', 'with', 'as', 'was', 'be', 'are', 'this', 'by', 'or', 'at', 'an', 'from', 'not', 'but', 'which', 'you', 'we', 'they', 'he', 'she', 'it', 'his', 'her', 'their', 'our', 'my', 'your', 'has', 'have', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'can', 'may', 'might', 'must'}
        keywords = [word.lower() for word in words if word.lower() not in common_words and len(word) > 3][:10]
        
        sentences = re.split(r'[.!?]+', text)
        events = [s.strip() for s in sentences if any(verb in s.lower() for verb in ['created', 'developed', 'established', 'implemented', 'launched', 'started', 'began', 'occurred', 'happened', 'changed', 'increased', 'decreased'])][:5]
        
        return {
            "entities": entities[:10],
            "keywords": list(set(keywords))[:10],
            "events": events
        }

    def analysis_complete(self):
        self.status_label.configure(text="✅ Analysis Complete")
        self.btn_prev_page.configure(state="normal")
        self.btn_next_page.configure(state="normal")
        self.load_page(0)

    def load_page(self, index):
        if 0 <= index < len(self.pdf_data):
            self.current_page = index
            data = self.pdf_data[index]
            
            self.textbox_content.delete("0.0", "end")
            self.textbox_content.insert("0.0", data['text'])
            
            self.lbl_page_counter.configure(text=f"Page {data['page']} / {self.total_pages}")
            
            analysis = data.get('analysis', {})
            
            self.box_entities.delete("0.0", "end")
            if analysis.get('entities'):
                self.box_entities.insert("0.0", "\n".join(analysis['entities']))
            else:
                self.box_entities.insert("0.0", "No entities extracted")
            
            self.box_keywords.delete("0.0", "end")
            if analysis.get('keywords'):
                self.box_keywords.insert("0.0", "\n".join(analysis['keywords']))
            else:
                self.box_keywords.insert("0.0", "No keywords extracted")
            
            self.box_events.delete("0.0", "end")
            if analysis.get('events'):
                self.box_events.insert("0.0", "\n".join(analysis['events']))
            else:
                self.box_entities.insert("0.0", "No events extracted")

    def prev_page(self):
        if self.current_page > 0: 
            self.load_page(self.current_page - 1)
        
    def next_page(self):
        if self.current_page < len(self.pdf_data) - 1: 
            self.load_page(self.current_page + 1)

    # ==================== IMAGE HANDLING ====================
    def update_image_display(self):
        if not self.images_data: 
            return
        
        img_data = self.images_data[self.current_image_index]
        pil_img = img_data['image']
        
        w, h = pil_img.size
        aspect = w / h
        target_h = 300
        target_w = int(target_h * aspect)
        
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(target_w, target_h))
        
        self.image_display_label.configure(image=ctk_img, text="")
        self.lbl_img_counter.configure(text=f"Img {self.current_image_index + 1}/{len(self.images_data)}")
        
        self.btn_prev_img.configure(state="normal" if self.current_image_index > 0 else "disabled")
        self.btn_next_img.configure(state="normal" if self.current_image_index < len(self.images_data)-1 else "disabled")

        desc = img_data.get('description', "Not analyzed yet. Click 'Analyze Images' button.")
        self.box_image_analysis.delete("0.0", "end")
        self.box_image_analysis.insert("0.0", f"[Image {self.current_image_index+1} on Page {img_data['page']}]\n\n{desc}")

    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.update_image_display()

    def next_image(self):
        if self.current_image_index < len(self.images_data) - 1:
            self.current_image_index += 1
            self.update_image_display()

    def analyze_images(self):
        if not self.images_data:
            messagebox.showwarning("No Images", "No images found in PDF to analyze.")
            return
        
        self.status_label.configure(text="Analyzing images...")
        self.btn_analyze_img.configure(state="disabled")
        threading.Thread(target=self.run_image_analysis, daemon=True).start()

    def run_image_analysis(self):
        """Analyze images using OpenRouter API"""
        if not self.openrouter_api_key:
            self.after(0, lambda: messagebox.showerror("API Error", "OpenRouter API key not configured!"))
            return
        
        total_images = len(self.images_data)
        model = self.option_model.get()
        
        for i, img_data in enumerate(self.images_data):
            self.after(0, lambda v=i: self.progress_bar.set((v+1)/total_images))
            
            try:
                pil_img = img_data['image']
                
                # Convert PIL Image to base64
                buffered = BytesIO()
                pil_img.save(buffered, format="JPEG", quality=85)
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                # Prepare API request
                headers = {
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Analyze this image in detail. Describe what you see, identify any text, objects, people, or important elements."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{img_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 500
                }
                
                # Make API request
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    description = result['choices'][0]['message']['content']
                    
                    # Store description
                    img_data['description'] = description
                    self.images_data[i] = img_data
                    
                    # Update UI if this is the current image
                    if i == self.current_image_index:
                        self.after(0, self.update_image_display)
                    
                else:
                    img_data['description'] = f"API Error: {response.status_code}"
                    self.images_data[i] = img_data
                    
            except Exception as e:
                img_data['description'] = f"Analysis Error: {str(e)[:100]}"
                self.images_data[i] = img_data
            
            # Small delay to avoid rate limiting
            threading.Event().wait(0.5)
        
        self.after(0, lambda: self.status_label.configure(text="✅ Image Analysis Complete"))
        self.after(0, lambda: self.btn_analyze_img.configure(state="normal"))

    # ==================== GROQ AI POWER SEARCH (FIXED & WORKING) ====================
    def ask_question(self):
        question = self.entry_question.get().strip()
        if not question:
            messagebox.showwarning("No Question", "Please enter a question.")
            return
            
        if not self.all_text:
            messagebox.showwarning("No Data", "Please load and analyze a PDF first.")
            return
        
        # Check if Groq API is available
        if self.search_mode.get() == "groq" and not self.groq_client:
            messagebox.showerror("API Error", "Groq API is not connected. Please check:\n1. Internet connection\n2. API key\n3. pip install groq")
            return
        
        # Disable button during processing
        self.btn_ask.configure(state="disabled", text="🧠 Processing...")
        self.box_answer.delete("0.0", "end")
        
        if self.search_mode.get() == "groq":
            self.box_answer.insert("0.0", "🧠 GROQ AI is analyzing your question...\n\nPlease wait...")
        else:
            self.box_answer.insert("0.0", "⚡ Fast searching...\n\nPlease wait...")
        
        # Start processing in thread
        threading.Thread(target=self.process_question, args=(question,), daemon=True).start()

    def process_question(self, question):
        """Process question - MAIN FIXED FUNCTION"""
        try:
            # ALWAYS use Groq if selected and available
            if self.search_mode.get() == "groq" and self.groq_client:
                response_text = self.groq_ai_search(question)
            else:
                response_text = self.simple_search(question)
                
        except Exception as e:
            error_msg = f"❌ ERROR: {str(e)}\n\n"
            error_msg += "Troubleshooting:\n"
            error_msg += "1. Check internet connection\n"
            error_msg += "2. Verify Groq API key is valid\n"
            error_msg += "3. Try 'Fast Search' mode instead\n"
            error_msg += f"4. Error details: {type(e).__name__}"
            response_text = error_msg
        
        # Update UI
        self.after(0, lambda: self._update_answer(response_text))
        self.after(0, lambda: self.btn_ask.configure(state="normal", text="🚀 ASK GROQ AI"))

    def groq_ai_search(self, question):
        """DIRECT GROQ AI SEARCH - SIMPLE & WORKING"""
        try:
            # Prepare context - SIMPLE VERSION THAT WORKS
            context = f"""
            PDF CONTENT:
            {self.all_text[:6000]}
            
            QUESTION:
            {question}
            
            Please answer this question based ONLY on the PDF content above.
            Be accurate, thorough, and reference specific information from the text.
            """
            
            # Call Groq API
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a helpful assistant that answers questions based on provided PDF content. Use only the given text."
                    },
                    {"role": "user", "content": context}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content
            
            # Format the answer nicely
            formatted_answer = f"""
            🧠 GROQ AI ANSWER:
            {'='*50}
            
            {answer}
            
            {'='*50}
            📊 Based on analysis of {len(self.pdf_data)} PDF pages
            💡 Generated with Groq AI
            """
            
            return formatted_answer
            
        except Exception as e:
            print(f"Groq Search Error: {str(e)}")
            # Fallback to simple search
            return self.simple_search_with_context(question)

    def simple_search_with_context(self, question):
        """Enhanced simple search with context"""
        question_lower = question.lower()
        results = []
        
        # Search in text with more context
        for data in self.pdf_data:
            text_lower = data['text'].lower()
            if question_lower in text_lower:
                # Get the paragraph containing the match
                paragraphs = data['text'].split('\n\n')
                for para in paragraphs:
                    if question_lower in para.lower():
                        results.append(f"📄 Page {data['page']}:\n{para[:500]}...")
                        break
        
        # Search in extracted entities if no text matches
        if not results:
            for entity in set(self.all_entities):
                if question_lower in entity.lower():
                    results.append(f"👤 Entity: {entity}")
            
            for keyword in set(self.all_keywords):
                if question_lower in keyword.lower():
                    results.append(f"🔑 Keyword: {keyword}")
        
        if results:
            return f"SIMPLE SEARCH RESULTS:\n\n" + "\n\n".join(results[:5])
        else:
            # Try to answer based on overall content
            return self.answer_from_overall_context(question)

    def answer_from_overall_context(self, question):
        """Try to answer based on overall PDF content"""
        # Extract common themes from all text
        all_text_lower = self.all_text.lower()
        
        # Check for common question types
        if any(word in question.lower() for word in ['what is', 'what are', 'define', 'explain']):
            # Look for definitions or explanations
            return f"Based on the PDF content, I can tell you about:\n\n" + \
                   f"Main topics mentioned: {', '.join(set(self.all_keywords)[:10])}\n\n" + \
                   f"Main characters/entities: {', '.join(set(self.all_entities)[:10])}"
        
        elif any(word in question.lower() for word in ['who is', 'who are', 'character']):
            # Character/entity questions
            if self.all_entities:
                return f"Main entities in the PDF:\n\n" + "\n".join(set(self.all_entities)[:15])
            else:
                return "No specific entities extracted. Try analyzing with Groq AI for better results."
        
        elif any(word in question.lower() for word in ['summary', 'overview', 'main idea']):
            # Summary questions
            first_page_text = self.all_text[:1000] if len(self.all_text) > 1000 else self.all_text
            return f"PDF Summary (from first page):\n\n{first_page_text[:500]}..."
        
        else:
            return f"No direct matches found for: '{question}'\n\nTry:\n1. Using different keywords\n2. Asking specific questions\n3. Using Groq AI mode for intelligent analysis"

    def simple_search(self, question):
        """Fast rule-based search"""
        question_lower = question.lower()
        results = []
        
        # Quick search in first few pages
        for data in self.pdf_data[:10]:
            if question_lower in data['text'].lower():
                # Find the sentence
                sentences = data['text'].split('.')
                for sentence in sentences:
                    if question_lower in sentence.lower():
                        results.append(f"📄 Page {data['page']}: {sentence.strip()[:200]}")
                        break
                if len(results) >= 3:
                    break
        
        if results:
            return "FAST SEARCH RESULTS:\n\n" + "\n\n".join(results)
        else:
            return "No quick matches found. Try Groq AI mode for intelligent analysis."

    def _update_answer(self, text):
        self.box_answer.delete("0.0", "end")
        self.box_answer.insert("0.0", text)

if __name__ == "__main__":
    app = SmartPDFAnalyzer()
    app.mainloop()