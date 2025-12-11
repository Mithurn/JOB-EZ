"""
📄 RESUME MANAGER
Handles all resume-related operations:
- Discovers PDFs in data/resumes/
- Extracts clean text from PDFs
- Caches results to avoid re-parsing
- Provides resume metadata for LLM matching
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional
import PyPDF2


class ResumeManager:
    def __init__(self, resumes_dir: str = "data/resumes"):
        """
        Initialize the resume manager.
        
        Args:
            resumes_dir: Path to folder containing resume PDFs
        """
        self.resumes_dir = Path(resumes_dir)
        self.cache_file = self.resumes_dir / ".resume_cache.json"
        self.resumes: Dict[str, Dict] = {}
        
        # Create directory if it doesn't exist
        self.resumes_dir.mkdir(parents=True, exist_ok=True)
        
        # Load cached data or scan fresh
        self._load_resumes()
    
    
    def _load_resumes(self):
        """
        Load resumes from cache or parse PDFs if cache is stale.
        """
        # Try to load from cache first
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                
                # Verify cache is still valid (files haven't changed)
                if self._is_cache_valid(cached_data):
                    self.resumes = cached_data
                    print(f"✅ Loaded {len(self.resumes)} resumes from cache")
                    return
            except Exception as e:
                print(f"⚠️ Cache corrupted, rebuilding: {e}")
        
        # Cache miss or invalid - scan and parse all PDFs
        print("🔍 Scanning for resume PDFs...")
        self._scan_and_parse_pdfs()
        self._save_cache()
    
    
    def _is_cache_valid(self, cached_data: Dict) -> bool:
        """
        Check if cached data matches current PDF files.
        """
        pdf_files = set(f.name for f in self.resumes_dir.glob("*.pdf"))
        cached_files = set(cached_data.keys())
        
        # Cache is valid if file lists match
        return pdf_files == cached_files
    
    
    def _scan_and_parse_pdfs(self):
        """
        Find all PDFs and extract their text content.
        """
        pdf_files = list(self.resumes_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"❌ No PDFs found in {self.resumes_dir}")
            print(f"   Please add resume PDFs like: frontend.pdf, backend.pdf, fullstack.pdf")
            return
        
        for pdf_path in pdf_files:
            try:
                print(f"📄 Parsing {pdf_path.name}...")
                text = self._extract_text_from_pdf(pdf_path)
                
                # Store resume data
                self.resumes[pdf_path.name] = {
                    'filename': pdf_path.name,
                    'path': str(pdf_path.absolute()),
                    'text': text,
                    'word_count': len(text.split()),
                    'size_kb': pdf_path.stat().st_size / 1024
                }
                
                print(f"   ✓ Extracted {len(text.split())} words")
                
            except Exception as e:
                print(f"   ❌ Failed to parse {pdf_path.name}: {e}")
        
        print(f"\n✅ Successfully loaded {len(self.resumes)} resumes")
    
    
    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content (cleaned)
        """
        text_content = []
        
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)
                except Exception as e:
                    print(f"      ⚠️ Warning: Failed to read page {page_num + 1}: {e}")
        
        # Join all pages and clean up
        full_text = "\n\n".join(text_content)
        cleaned_text = self._clean_text(full_text)
        
        return cleaned_text
    
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text (remove extra whitespace, fix encoding issues).
        """
        # Replace multiple newlines with double newline
        text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
        
        # Remove excessive spaces
        import re
        text = re.sub(r' +', ' ', text)
        
        # Fix common encoding issues
        text = text.replace('\u2019', "'")  # Smart apostrophe
        text = text.replace('\u2013', "-")  # En dash
        text = text.replace('\u2014', "--") # Em dash
        text = text.replace('\u201c', '"')  # Smart quote left
        text = text.replace('\u201d', '"')  # Smart quote right
        
        return text.strip()
    
    
    def _save_cache(self):
        """
        Save parsed resumes to cache file.
        """
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.resumes, f, indent=2, ensure_ascii=False)
            print(f"💾 Cache saved to {self.cache_file}")
        except Exception as e:
            print(f"⚠️ Could not save cache: {e}")
    
    
    def get_resume_text(self, filename: str) -> Optional[str]:
        """
        Get the text content of a specific resume.
        
        Args:
            filename: Name of the resume file (e.g., "frontend.pdf")
            
        Returns:
            Resume text or None if not found
        """
        resume = self.resumes.get(filename)
        return resume['text'] if resume else None
    
    
    def get_all_resumes(self) -> Dict[str, Dict]:
        """
        Get all loaded resumes with their metadata.
        
        Returns:
            Dictionary of {filename: resume_data}
        """
        return self.resumes
    
    
    def get_resume_summary(self, filename: str) -> Optional[Dict]:
        """
        Get metadata about a specific resume (without full text).
        
        Args:
            filename: Name of the resume file
            
        Returns:
            Dictionary with filename, word_count, size_kb
        """
        resume = self.resumes.get(filename)
        if not resume:
            return None
        
        return {
            'filename': resume['filename'],
            'word_count': resume['word_count'],
            'size_kb': round(resume['size_kb'], 2)
        }
    
    
    def list_available_resumes(self) -> List[str]:
        """
        Get a list of all available resume filenames.
        
        Returns:
            List of resume filenames
        """
        return list(self.resumes.keys())
    
    
    def reload_resumes(self):
        """
        Force re-scan and re-parse all PDFs (ignores cache).
        Use this if you've added/modified resume PDFs.
        """
        print("🔄 Force reloading all resumes...")
        self._scan_and_parse_pdfs()
        self._save_cache()
    
    
    def get_resume_path(self, filename: str) -> Optional[str]:
        """
        Get the absolute file path of a resume.
        Useful for uploading the PDF to job forms.
        
        Args:
            filename: Name of the resume file
            
        Returns:
            Absolute path or None if not found
        """
        resume = self.resumes.get(filename)
        return resume['path'] if resume else None


# ============================================================
# 🧪 TESTING / STANDALONE USAGE
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTING RESUME MANAGER")
    print("=" * 60 + "\n")
    
    # Initialize manager
    manager = ResumeManager()
    
    # List all resumes
    print("\n📋 Available Resumes:")
    print("-" * 60)
    for filename in manager.list_available_resumes():
        summary = manager.get_resume_summary(filename)
        print(f"  • {summary['filename']}")
        print(f"    Words: {summary['word_count']} | Size: {summary['size_kb']} KB")
    
    # Show sample text from first resume
    if manager.list_available_resumes():
        first_resume = manager.list_available_resumes()[0]
        print(f"\n📄 Sample text from {first_resume}:")
        print("-" * 60)
        text = manager.get_resume_text(first_resume)
        print(text[:500] + "..." if len(text) > 500 else text)
    else:
        print("\n⚠️ No resumes found! Add PDFs to data/resumes/")
    
    print("\n" + "=" * 60)
    print("✅ Testing complete!")
    print("=" * 60)