"""
Kerala Panchayat PDF Ingestion Script
This script processes the Kerala Panchayat Act PDF and creates searchable embeddings.
Run this script first to prepare your data before using the Streamlit app.
"""

import PyPDF2
import faiss
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pickle
import os
import sys
from pathlib import Path

class PDFIngestor:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        """
        Initialize PDF ingestion system
        
        Args:
            model_name: Sentence transformer model for embeddings
        """
        # Check device availability
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"🚀 Using device: {self.device.upper()}")
        
        # Initialize models
        print("📥 Loading embedding model...")
        self.embedding_model = SentenceTransformer(model_name, device=self.device)
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,  # Larger chunks for legal documents
            chunk_overlap=100,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        self.chunks = []
        self.index = None
        print("✅ Ingestion system initialized")
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from PDF with error handling
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text content
        """
        print(f"📄 Extracting text from: {pdf_path}")
        text = ""
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                print(f"📚 Total pages: {total_pages}")
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():  # Only add non-empty pages
                            text += f"\n--- Page {page_num} ---\n{page_text}\n"
                        
                        # Progress indicator
                        if page_num % 10 == 0:
                            print(f"   📖 Processed {page_num}/{total_pages} pages...")
                            
                    except Exception as e:
                        print(f"⚠️ Warning: Could not extract text from page {page_num}: {e}")
                        continue
                        
        except Exception as e:
            raise ValueError(f"❌ Error reading PDF file: {e}")
        
        if not text.strip():
            raise ValueError("❌ No text extracted from PDF")
        
        print(f"📝 Successfully extracted {len(text):,} characters from {total_pages} pages")
        return text
    
    def chunk_text(self, text: str) -> list:
        """
        Split text into manageable chunks
        
        Args:
            text: Full text content
            
        Returns:
            List of text chunks
        """
        print("✂️ Splitting text into chunks...")
        chunks = self.text_splitter.split_text(text)
        
        # Filter out very short chunks
        chunks = [chunk for chunk in chunks if len(chunk.strip()) > 50]
        
        print(f"📦 Created {len(chunks)} chunks")
        
        # Show sample chunk
        if chunks:
            print(f"📄 Sample chunk (first 200 chars): {chunks[0][:200]}...")
        
        return chunks
    
    def create_embeddings(self, chunks: list) -> np.ndarray:
        """
        Generate embeddings for text chunks
        
        Args:
            chunks: List of text chunks
            
        Returns:
            Numpy array of embeddings
        """
        print("🧠 Generating embeddings...")
        
        # Process in batches to avoid memory issues
        batch_size = 32
        all_embeddings = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_embeddings = self.embedding_model.encode(
                batch, 
                show_progress_bar=True,
                batch_size=batch_size
            )
            all_embeddings.append(batch_embeddings)
            
            # Progress update
            processed = min(i + batch_size, len(chunks))
            print(f"   🔄 Processed {processed}/{len(chunks)} chunks")
        
        # Combine all embeddings
        embeddings = np.vstack(all_embeddings)
        print(f"✅ Generated embeddings shape: {embeddings.shape}")
        
        return embeddings
    
    def create_faiss_index(self, embeddings: np.ndarray):
        """
        Create FAISS index for similarity search
        
        Args:
            embeddings: Numpy array of embeddings
        """
        print("🔍 Creating FAISS search index...")
        dimension = embeddings.shape[1]
        
        # Create CPU index (more compatible across systems)
        self.index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
        
        # Try GPU acceleration if available
        if self.device == 'cuda' and faiss.get_num_gpus() > 0:
            try:
                print(f"🚀 Attempting GPU acceleration - {faiss.get_num_gpus()} GPU(s) available")
                gpu_resources = faiss.StandardGpuResources()
                gpu_index = faiss.index_cpu_to_gpu(gpu_resources, 0, self.index)
                
                # Normalize and add embeddings
                faiss.normalize_L2(embeddings)
                gpu_index.add(embeddings.astype('float32'))
                self.index = gpu_index
                print("✅ GPU acceleration enabled!")
                
            except Exception as e:
                print(f"⚠️ GPU acceleration failed, using CPU: {e}")
                # Fallback to CPU
                faiss.normalize_L2(embeddings)
                self.index.add(embeddings.astype('float32'))
        else:
            # Use CPU index
            faiss.normalize_L2(embeddings)
            self.index.add(embeddings.astype('float32'))
            print("💻 Using CPU index")
        
        print(f"📊 Index created with {self.index.ntotal} vectors")
    
    def save_index_and_chunks(self, index_path: str, chunks_path: str):
        """
        Save FAISS index and chunks to disk
        
        Args:
            index_path: Path to save FAISS index
            chunks_path: Path to save text chunks
        """
        print("💾 Saving index and chunks...")
        
        try:
            # Convert GPU index to CPU before saving if necessary
            if hasattr(self.index, 'index'):  # GPU index
                cpu_index = faiss.index_gpu_to_cpu(self.index)
                faiss.write_index(cpu_index, index_path)
                print("🔄 Converted GPU index to CPU for saving")
            else:  # CPU index
                faiss.write_index(self.index, index_path)
            
            # Save chunks
            with open(chunks_path, 'wb') as f:
                pickle.dump(self.chunks, f)
            
            print(f"✅ Files saved successfully:")
            print(f"   📁 FAISS Index: {index_path}")
            print(f"   📁 Text Chunks: {chunks_path}")
            print(f"   📊 Total chunks: {len(self.chunks)}")
            
        except Exception as e:
            print(f"❌ Error saving files: {e}")
            raise
    
    def ingest_pdf(self, pdf_path: str, index_path: str = "kerala_panchayat_index.bin", 
                   chunks_path: str = "kerala_chunks.pkl"):
        """
        Complete PDF ingestion pipeline
        
        Args:
            pdf_path: Path to PDF file
            index_path: Path to save FAISS index
            chunks_path: Path to save text chunks
        """
        try:
            # Step 1: Extract text
            text = self.extract_text_from_pdf(pdf_path)
            
            # Step 2: Chunk text
            self.chunks = self.chunk_text(text)
            
            # Step 3: Generate embeddings
            embeddings = self.create_embeddings(self.chunks)
            
            # Step 4: Create FAISS index
            self.create_faiss_index(embeddings)
            
            # Step 5: Save everything
            self.save_index_and_chunks(index_path, chunks_path)
            
            # Cleanup GPU memory
            if self.device == 'cuda':
                torch.cuda.empty_cache()
                print("🧹 GPU memory cleared")
            
            print("\n🎉 PDF INGESTION COMPLETED SUCCESSFULLY!")
            print(f"📊 Summary:")
            print(f"   • Document: {os.path.basename(pdf_path)}")
            print(f"   • Total chunks: {len(self.chunks)}")
            print(f"   • Embedding dimension: {embeddings.shape[1]}")
            print(f"   • Device used: {self.device.upper()}")
            print(f"   • Index file: {index_path}")
            print(f"   • Chunks file: {chunks_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ Ingestion failed: {e}")
            return False

def find_pdf_files(directory: str = ".") -> list:
    """Find PDF files in the given directory"""
    pdf_files = []
    for file in os.listdir(directory):
        if file.lower().endswith('.pdf'):
            pdf_files.append(file)
    return pdf_files

def main():
    """Main function to run PDF ingestion"""
    print("🏛️ KERALA PANCHAYAT PDF INGESTION SYSTEM")
    print("=" * 50)
    
    # Check for PDF files
    pdf_files = find_pdf_files()
    
    if not pdf_files:
        print("❌ No PDF files found in current directory")
        pdf_path = input("Please enter the full path to your Kerala Panchayat Act PDF: ").strip()
        if not os.path.exists(pdf_path):
            print(f"❌ File not found: {pdf_path}")
            return
    else:
        print(f"📁 Found PDF files: {pdf_files}")
        if len(pdf_files) == 1:
            pdf_path = pdf_files[0]
            print(f"📄 Using: {pdf_path}")
        else:
            print("\nSelect a PDF file:")
            for i, file in enumerate(pdf_files, 1):
                print(f"{i}. {file}")
            
            try:
                choice = int(input("Enter your choice (number): ")) - 1
                pdf_path = pdf_files[choice]
            except (ValueError, IndexError):
                print("❌ Invalid choice")
                return
    
    # Check if files already exist
    index_path = "kerala_panchayat_index.bin"
    chunks_path = "kerala_chunks.pkl"
    
    if os.path.exists(index_path) and os.path.exists(chunks_path):
        overwrite = input(f"\n⚠️ Files already exist:\n- {index_path}\n- {chunks_path}\nOverwrite? (y/n): ").lower()
        if overwrite != 'y':
            print("🚫 Ingestion cancelled")
            return
    
    # Initialize and run ingestion
    print(f"\n🚀 Starting ingestion of: {pdf_path}")
    ingestor = PDFIngestor()
    
    success = ingestor.ingest_pdf(pdf_path, index_path, chunks_path)
    
    if success:
        print("\n✅ READY TO USE STREAMLIT APP!")
        print("Run the following command to start the web interface:")
        print("streamlit run streamlit_app.py")
    else:
        print("\n❌ Ingestion failed. Please check the errors above.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()