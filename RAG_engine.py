"""
Kerala Panchayat RAG API - Production Ready Function
Simple API for Kerala Panchayat document queries
"""

import os
import time
import pickle
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# External dependencies
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from groq import Groq

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class QueryResponse:
    """Response data structure"""
    answer: str
    sources: List[str]
    confidence: float
    response_time: float
    num_sources: int
    success: bool
    error_message: Optional[str] = None

class KeralaPanchayatRAG:
    """Production-ready Kerala Panchayat RAG System"""
    
    def __init__(self, 
                 model_name: str = 'all-MiniLM-L6-v2',
                 groq_api_key: Optional[str] = None,
                 index_path: str = "kerala_panchayat_index.bin",
                 chunks_path: str = "kerala_chunks.pkl"):
        """
        Initialize the RAG system
        
        Args:
            model_name: Sentence transformer model name
            groq_api_key: Groq API key (if None, will read from env)
            index_path: Path to FAISS index file
            chunks_path: Path to chunks pickle file
        """
        # API setup
        self.groq_api_key = groq_api_key or os.getenv('GROQ_API_KEY')
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY not found. Set it as environment variable or pass as parameter.")
        
        self.groq_client = Groq(api_key=self.groq_api_key)
        
        # File paths
        self.index_path = index_path
        self.chunks_path = chunks_path
        
        # Initialize components
        self.embedding_model = None
        self.index = None
        self.chunks = []
        
        # Load the system
        self._load_embedding_model(model_name)
        self._load_system()
        
        logger.info("Kerala Panchayat RAG system initialized successfully")
    
    def _detect_device(self) -> str:
        """Detect if CUDA is available"""
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.current_device()
                return 'cuda'
            else:
                return 'cpu'
        except ImportError:
            return 'cpu'
    
    def _load_embedding_model(self, model_name: str):
        """Load the sentence transformer model"""
        try:
            device = self._detect_device()
            self.embedding_model = SentenceTransformer(model_name, device=device)
            logger.info(f"Embedding model loaded on {device}")
        except Exception as e:
            logger.warning(f"Failed to load model on detected device, falling back to CPU: {e}")
            self.embedding_model = SentenceTransformer(model_name, device='cpu')
    
    def _load_system(self):
        """Load the preprocessed FAISS index and chunks"""
        try:
            # Load FAISS index
            if not os.path.exists(self.index_path):
                raise FileNotFoundError(f"FAISS index not found at {self.index_path}")
            
            self.index = faiss.read_index(self.index_path)
            
            # Load chunks
            if not os.path.exists(self.chunks_path):
                raise FileNotFoundError(f"Chunks file not found at {self.chunks_path}")
            
            with open(self.chunks_path, 'rb') as f:
                self.chunks = pickle.load(f)
            
            logger.info(f"System loaded with {len(self.chunks)} document sections")
            
        except Exception as e:
            logger.error(f"Failed to load system: {e}")
            raise
    
    def _search_relevant_sections(self, query: str, k: int = 3) -> List[Tuple[str, float]]:
        """Search for relevant document sections"""
        if self.index is None or not self.chunks:
            raise ValueError("System not properly loaded")
        
        # Create query embedding
        query_embedding = self.embedding_model.encode([query])
        faiss.normalize_L2(query_embedding)
        
        # Search FAISS index
        scores, indices = self.index.search(query_embedding.astype('float32'), k)
        
        # Extract results
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1 and idx < len(self.chunks):
                results.append((self.chunks[idx], float(score)))
        
        return results
    
    def _generate_answer(self, query: str, context: str) -> str:
        """Generate answer using Groq API"""
        system_prompt = """You are a helpful assistant that explains Kerala Panchayat rules and procedures in simple, easy-to-understand language.

Your guidelines:
- Use simple, clear language that anyone can understand
- Avoid legal jargon and complex terms
- Break down complex procedures into simple steps
- Give practical examples when helpful
- Use bullet points for lists and procedures
- Be encouraging and helpful in tone
- If something is technical, explain it in simple terms first

Remember: Your users may not have legal or administrative background, so make everything easy to understand."""

        user_prompt = f"""Based on this information from Kerala Panchayat documents, please answer the user's question in simple, clear language:

REFERENCE INFORMATION:
{context}

USER'S QUESTION: {query}

Please provide a helpful answer that:
1. Explains things in simple terms
2. Uses easy-to-understand language
3. Gives step-by-step guidance if needed
4. Is encouraging and supportive

ANSWER:"""

        try:
            chat_completion = self.groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="llama3-70b-8192",
                temperature=0.3,
                max_tokens=800,
            )
            
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            raise
    
    def query(self, question: str, num_sources: int = 3) -> QueryResponse:
        """
        Main function to query the RAG system
        
        Args:
            question: User's question
            num_sources: Number of relevant sources to retrieve
            
        Returns:
            QueryResponse object with answer and metadata
        """
        start_time = time.time()
        
        try:
            # Validate input
            if not question or not question.strip():
                return QueryResponse(
                    answer="Please provide a valid question.",
                    sources=[],
                    confidence=0.0,
                    response_time=time.time() - start_time,
                    num_sources=0,
                    success=False,
                    error_message="Empty question provided"
                )
            
            # Search for relevant sections
            relevant_sections = self._search_relevant_sections(question, k=num_sources)
            
            if not relevant_sections:
                return QueryResponse(
                    answer="I couldn't find information about this topic in the Kerala Panchayat documents. Could you try asking in a different way?",
                    sources=[],
                    confidence=0.0,
                    response_time=time.time() - start_time,
                    num_sources=0,
                    success=True
                )
            
            # Prepare context
            context = "\n\n".join([section for section, _ in relevant_sections])
            
            # Generate answer
            answer = self._generate_answer(question, context)
            
            # Calculate metrics
            confidence = sum(score for _, score in relevant_sections) / len(relevant_sections)
            sources = [section[:200] + "..." if len(section) > 200 else section 
                      for section, _ in relevant_sections]
            
            return QueryResponse(
                answer=answer,
                sources=sources,
                confidence=confidence,
                response_time=time.time() - start_time,
                num_sources=len(relevant_sections),
                success=True
            )
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return QueryResponse(
                answer="Sorry, I encountered an error while processing your question. Please try again.",
                sources=[],
                confidence=0.0,
                response_time=time.time() - start_time,
                num_sources=0,
                success=False,
                error_message=str(e)
            )

# Global instance for production use
_rag_instance = None

def get_rag_instance() -> KeralaPanchayatRAG:
    """Get or create RAG instance (singleton pattern)"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = KeralaPanchayatRAG()
    return _rag_instance

def ask_kerala_panchayat(question: str, num_sources: int = 3) -> Dict:
    """
    Simple function to ask questions about Kerala Panchayat
    
    Args:
        question: User's question
        num_sources: Number of relevant sources to retrieve (default: 3)
        
    Returns:
        Dictionary containing:
        - answer: The generated answer
        - sources: List of relevant source texts
        - confidence: Confidence score (0-1)
        - response_time: Time taken to process
        - num_sources: Number of sources found
        - success: Whether the query was successful
        - error_message: Error message if any
    """
    try:
        rag_system = get_rag_instance()
        response = rag_system.query(question, num_sources)
        
        return {
            'answer': response.answer,
            'sources': response.sources,
            'confidence': response.confidence,
            'response_time': response.response_time,
            'num_sources': response.num_sources,
            'success': response.success,
            'error_message': response.error_message
        }
        
    except Exception as e:
        logger.error(f"Error in ask_kerala_panchayat: {e}")
        return {
            'answer': "System error occurred. Please try again later.",
            'sources': [],
            'confidence': 0.0,
            'response_time': 0.0,
            'num_sources': 0,
            'success': False,
            'error_message': str(e)
        }

# Example usage
if __name__ == "__main__":
    # Test the function
    test_question = "How do I apply for a birth certificate from Panchayat?"
    
    print("Testing Kerala Panchayat RAG System...")
    print(f"Question: {test_question}")
    print("-" * 50)
    
    result = ask_kerala_panchayat(test_question)
    
    print(f"Success: {result['success']}")
    print(f"Answer: {result['answer']}")
    print(f"Sources found: {result['num_sources']}")
    print(f"Response time: {result['response_time']:.2f}s")
    print(f"Confidence: {result['confidence']:.3f}")
    
    if result['error_message']:
        print(f"Error: {result['error_message']}")