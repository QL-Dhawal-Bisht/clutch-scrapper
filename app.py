import streamlit as st
import pandas as pd
import time
import random
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from pathlib import Path
import zipfile
import io
from google.cloud import storage

# def save_to_gcs(df, filename):
#     client = storage.Client()
#     bucket = client.get_bucket("your-bucket-name")
#     blob = bucket.blob(f"clutch_data/{filename}")
#     blob.upload_from_string(df.to_csv(index=False), content_type="text/csv")
#     return f"gs://your-bucket-name/clutch_data/{filename}"

# Configuration
DEFAULT_DELAY_RANGE = (1, 3)
DEFAULT_MAX_WORKERS = 3

# Set up default download directory
# DOWNLOADS_DIR = Path.home() / "Downloads"
# CLUTCH_DATA_DIR = DOWNLOADS_DIR / "clutch_data"
# CLUTCH_DATA_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOADS_DIR = Path("/tmp")
CLUTCH_DATA_DIR = DOWNLOADS_DIR / "clutch_data"
CLUTCH_DATA_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"
]

def setup_driver():
    """Configure optimized Chrome WebDriver"""
    options = Options()
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("window-size=1200,800")
    options.add_argument("--headless=new")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(20)
    return driver

def process_row(row, driver):
    """Process a single row with an existing driver"""
    name = str(row['Reviewer Name']).strip()
    if name.lower() == "anonymous":
        return "Anonymous"
    
    company = str(row['Reviewer Company']).split(",")[-1].strip() if "," in str(row['Reviewer Company']) else str(row['Reviewer Company']).strip()
    
    try:
        query = f"{name} {company} site:linkedin.com/in"
        
        driver.get("https://duckduckgo.com/")
        search_box = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.NAME, "q")))
        search_box.clear()
        search_box.send_keys(query + Keys.RETURN)

        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'linkedin.com/in/')]"))
        )
        
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'linkedin.com/in/')]")
        href = links[0].get_attribute("href") if links else None
        
        if href:
            return href
        else:
            return "Not Found"
            
    except Exception as e:
        return "Error"

def process_batch(df_batch, delay_range, progress_callback=None, batch_id=0):
    """Process a batch of rows with a shared driver"""
    driver = setup_driver()
    results = []
    try:
        for i, (_, row) in enumerate(df_batch.iterrows()):
            results.append(process_row(row, driver))
            if progress_callback:
                progress_callback(batch_id, i + 1, len(df_batch))
            time.sleep(random.uniform(*delay_range))
    finally:
        driver.quit()
    return results

def process_single_file(df, filename, ui_progress_callback=None):
    """Process a single dataframe with real-time progress updates"""
    if 'LinkedIn Profile' not in df.columns:
        df['LinkedIn Profile'] = ''

    # Split dataframe into batches
    batch_size = max(5, len(df) // DEFAULT_MAX_WORKERS)
    batches = [df.iloc[i:i + batch_size] for i in range(0, len(df), batch_size)]
    
    total_rows = len(df)
    processed_rows = 0
    
    # Create a shared progress tracking function
    def batch_progress_callback(batch_id, batch_processed, batch_total):
        nonlocal processed_rows
        # Calculate total processed rows across all batches
        current_total = sum(len(batches[i]) for i in range(batch_id)) + batch_processed
        if ui_progress_callback:
            ui_progress_callback(current_total, total_rows)
    
    # Process batches sequentially for better progress tracking
    all_results = []
    for i, batch in enumerate(batches):
        if ui_progress_callback:
            ui_progress_callback(processed_rows, total_rows)
        
        batch_results = process_batch(batch, DEFAULT_DELAY_RANGE, batch_progress_callback, i)
        all_results.extend(batch_results)
        processed_rows += len(batch_results)
    
    # Update dataframe with results
    df['LinkedIn Profile'] = all_results[:len(df)]
    return df

# Streamlit UI
def main():
    st.set_page_config(
        page_title="LinkedIn Profile Scraper",
        page_icon="🔍",
        layout="centered"
    )

    # Enhanced CSS to remove white blocks and improve design
    st.markdown("""
    <style>
    /* Remove default Streamlit styling and white backgrounds */
    .main .block-container {
        padding: 1rem 1rem 10rem;
        background: transparent;
    }
    
    /* Remove white background from main content area */
    .stApp > header {
        background: transparent;
    }
    
    .stApp {
        background-color: #000000      
        min-height: 100vh;
    }
    
    /* Remove white backgrounds from all containers */
    .element-container,
    .stMarkdown,
    .stContainer,
    div[data-testid="stVerticalBlock"],
    div[data-testid="stHorizontalBlock"],
    section[data-testid="stSidebar"] > div {
        background: transparent !important;
    }
    
    /* File uploader styling */
    .stFileUploader > div {
        background: rgba(255, 255, 255, 0.1) !important;
        border: 2px dashed rgba(255, 255, 255, 0.3) !important;
        border-radius: 15px !important;
        backdrop-filter: blur(10px);
    }
    
    .stFileUploader label {
        color: white !important;
        font-weight: 600 !important;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(45deg, #ff6b6b, #ffa726) !important;
        color: white !important;
        border: none !important;
        border-radius: 25px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3) !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase !important;
        letter-spacing: 1px !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(255, 107, 107, 0.4) !important;
    }
    
    /* Progress bar styling */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #ff6b6b, #ffa726) !important;
        border-radius: 10px !important;
    }
    
    .stProgress > div > div {
        background: rgba(255, 255, 255, 0.2) !important;
        border-radius: 10px !important;
    }
    
    /* Alert and message styling */
    .stAlert {
        background: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 15px !important;
        backdrop-filter: blur(10px) !important;
        color: white !important;
    }
    
    .stSuccess {
        background: rgba(76, 175, 80, 0.2) !important;
        border: 1px solid rgba(76, 175, 80, 0.4) !important;
    }
    
    .stError {
        background: rgba(244, 67, 54, 0.2) !important;
        border: 1px solid rgba(244, 67, 54, 0.4) !important;
    }
    
    .stWarning {
        background: rgba(255, 152, 0, 0.2) !important;
        border: 1px solid rgba(255, 152, 0, 0.4) !important;
    }
    
    .stInfo {
        background: rgba(33, 150, 243, 0.2) !important;
        border: 1px solid rgba(33, 150, 243, 0.4) !important;
    }
    
    /* Download button styling */
    .stDownloadButton > button {
        background: linear-gradient(45deg, #4CAF50, #45a049) !important;
        color: white !important;
        border: none !important;
        border-radius: 20px !important;
        padding: 0.5rem 1.5rem !important;
        margin: 0.25rem !important;
        font-weight: 500 !important;
        box-shadow: 0 3px 10px rgba(76, 175, 80, 0.3) !important;
    }
    
    .stDownloadButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(76, 175, 80, 0.4) !important;
    }
    
    /* Main header styling */
    .main-header {
        text-align: center;
        padding: 2rem 0;
        color: white !important;
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        background: linear-gradient(45deg, #fff, #f0f8ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    /* Glass card effect for processing cards */
    .processing-card {
        background: rgba(255, 255, 255, 0.1) !important;
        padding: 1.5rem;
        border-radius: 20px;
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        color: white;
    }
    
    .completed-file {
        background: rgba(76, 175, 80, 0.2) !important;
        border: 1px solid rgba(76, 175, 80, 0.4);
    }
    
    .processing-file {
        background: rgba(255, 193, 7, 0.2) !important;
        border: 1px solid rgba(255, 193, 7, 0.4);
    }
    
    /* Upload section styling */
    .upload-section {
        background: rgba(255, 255, 255, 0.1);
        border: 2px dashed rgba(255, 255, 255, 0.3);
        border-radius: 20px;
        padding: 2rem;
        text-align: center;
        margin: 2rem 0;
        backdrop-filter: blur(15px);
        color: white;
    }
    
    .upload-section h3 {
        color: white !important;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    /* Text styling */
    .stMarkdown p,
    .stMarkdown li,
    .stMarkdown h1,
    .stMarkdown h2,
    .stMarkdown h3,
    .stMarkdown h4,
    .stMarkdown h5,
    .stMarkdown h6 {
        color: white !important;
    }
    
    .stMarkdown strong {
        color: #fff !important;
        font-weight: 700 !important;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-completed {
        background: rgba(76, 175, 80, 0.3);
        color: #4CAF50;
        border: 1px solid rgba(76, 175, 80, 0.5);
    }
    
    .status-processing {
        background: rgba(255, 193, 7, 0.3);
        color: #FFC107;
        border: 1px solid rgba(255, 193, 7, 0.5);
    }
    
    .status-pending {
        background: rgba(158, 158, 158, 0.3);
        color: #9E9E9E;
        border: 1px solid rgba(158, 158, 158, 0.5);
    }
    
    /* Animations */
    .animate-bounce {
        animation: bounce 1s infinite;
    }
    
    @keyframes bounce {
        0%, 20%, 53%, 80%, 100% {
            transform: translate3d(0,0,0);
        }
        40%, 43% {
            transform: translate3d(0, -8px, 0);
        }
        70% {
            transform: translate3d(0, -4px, 0);
        }
        90% {
            transform: translate3d(0, -2px, 0);
        }
    }
    
    .animate-pulse {
        animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: .7; }
    }
    
    /* Remove any remaining white backgrounds */
    .css-1d391kg,
    .css-12oz5g7,
    .css-1v3fvcr,
    div[data-baseweb="popover"] {
        background: transparent !important;
    }
    
    /* Ensure text is visible */
    .stText {
        color: white !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown('<h1 class="main-header">🔍 LinkedIn Profile Scraper</h1>', unsafe_allow_html=True)
    
    # Upload section
    st.markdown("""
    <div class="upload-section">
        <h3>📁 Upload CSV Files</h3>
        <p>Upload up to 10 CSV files containing reviewer data</p>
    </div>
    """, unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader(
        "Choose CSV files",
        type=['csv'],
        accept_multiple_files=True,
        help="Each file should contain 'Reviewer Name' and 'Reviewer Company' columns",
        key="csv_uploader"
    )

    # Validate file count
    if uploaded_files and len(uploaded_files) > 10:
        st.error("❌ Maximum 10 files allowed. Please select fewer files.")
        return

    # Process files if uploaded
    if uploaded_files and st.button("🚀 Start Processing", type="primary", use_container_width=True):
        if len(uploaded_files) == 0:
            st.warning("Please upload at least one CSV file.")
            return
        
        # Initialize session state for tracking
        if 'processing_status' not in st.session_state:
            st.session_state.processing_status = {}
        
        total_files = len(uploaded_files)
        processed_files = []
        
        # Overall progress
        overall_progress = st.progress(0)
        overall_status = st.empty()
        
        # File status container
        status_container = st.container()
        
        try:
            for file_idx, uploaded_file in enumerate(uploaded_files):
                # Update overall status
                overall_status.markdown(f"**Processing file {file_idx + 1} of {total_files}: {uploaded_file.name}**")
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                try:
                    # Read the CSV
                    df = pd.read_csv(tmp_file_path)
                    
                    # Validate required columns
                    required_columns = ['Reviewer Name', 'Reviewer Company']
                    if not all(col in df.columns for col in required_columns):
                        st.error(f"❌ File '{uploaded_file.name}' missing required columns: {required_columns}")
                        continue
                    
                    # Show file processing status with immediate feedback
                    with status_container:
                        processing_placeholder = st.empty()
                        processing_placeholder.markdown(f"""
                        <div class="processing-card processing-file">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <strong>📄 {uploaded_file.name}</strong>
                                    <div style="color: rgba(255,255,255,0.8); font-size: 0.875rem;">{len(df)} rows to process</div>
                                </div>
                                <span class="status-badge status-processing animate-pulse">Starting...</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Progress tracking for current file
                    file_progress = st.progress(0)
                    file_status = st.empty()
                    
                    # Show immediate start status
                    file_status.text("🚀 Initializing processing...")
                    time.sleep(0.5)  # Brief pause to show status
                    
                    def update_progress(processed, total):
                        progress = processed / total
                        file_progress.progress(progress)
                        
                        # Update processing card status
                        processing_placeholder.markdown(f"""
                        <div class="processing-card processing-file">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <strong>📄 {uploaded_file.name}</strong>
                                    <div style="color: rgba(255,255,255,0.8); font-size: 0.875rem;">Processing {processed}/{total} rows ({progress:.1%})</div>
                                </div>
                                <span class="status-badge status-processing animate-pulse">Processing...</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        file_status.text(f"🔍 Searching LinkedIn profiles... {processed}/{total} rows ({progress:.1%})")
                    
                    # Process the file
                    processed_df = process_single_file(df, uploaded_file.name, update_progress)
                    
                    # Clean up progress indicators
                    file_progress.empty()
                    file_status.empty()
                    
                    # Update status to completed
                    processing_placeholder.markdown(f"""
                    <div class="processing-card completed-file">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <strong>📄 {uploaded_file.name}</strong>
                                <div style="color: rgba(255,255,255,0.9); font-size: 0.875rem;">✅ {len(processed_df)} rows processed</div>
                            </div>
                            <span class="status-badge status-completed">Completed</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Save processed file
                    output_filename = f"processed_{uploaded_file.name}"
                    output_path = CLUTCH_DATA_DIR / output_filename
                    
                    # Add timestamp if file exists
                    if output_path.exists():
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        output_filename = f"processed_{timestamp}_{uploaded_file.name}"
                        output_path = CLUTCH_DATA_DIR / output_filename
                    
                    processed_df.to_csv(output_path, index=False)
                    processed_files.append((output_path, processed_df))
                    
                finally:
                    # Clean up temporary file
                    os.unlink(tmp_file_path)
                
                # Update overall progress
                overall_progress.progress((file_idx + 1) / total_files)
            
            # Final status
            overall_status.markdown("✅ **All files processed successfully!**")
            
            # Download section
            if processed_files:
                st.markdown("---")
                st.markdown("### 📥 Download Processed Files")
                
                # Create download buttons for individual files
                for file_path, df in processed_files:
                    csv_data = df.to_csv(index=False)
                    st.download_button(
                        label=f"📄 Download {file_path.name}",
                        data=csv_data,
                        file_name=file_path.name,
                        mime='text/csv'
                    )
                
                # Create zip download for all files
                if len(processed_files) > 1:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for file_path, df in processed_files:
                            csv_data = df.to_csv(index=False)
                            zip_file.writestr(file_path.name, csv_data)
                    
                    st.download_button(
                        label="📦 Download All Files (ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="processed_linkedin_files.zip",
                        mime='application/zip'
                    )
                
                st.success(f"🎉 Successfully processed {len(processed_files)} files!")
                st.info(f"📁 Files also saved to: {CLUTCH_DATA_DIR}")
        
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
    
    # Instructions
    if not uploaded_files:
        st.markdown("---")
        st.markdown("### 📋 Instructions")
        st.markdown("""
        1. **Upload CSV files** (max 10) containing reviewer data
        2. Ensure each file has columns: `Reviewer Name` and `Reviewer Company`
        3. Click **Start Processing** to begin LinkedIn profile extraction
        4. Monitor progress for each file with real-time updates
        5. Download processed files when complete
        
        **Note:** The tool will search for LinkedIn profiles using DuckDuckGo and add a new `LinkedIn Profile` column to your data.
        """)

if __name__ == "__main__":
    main()