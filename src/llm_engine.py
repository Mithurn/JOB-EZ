"""
🧠 LLM ENGINE
Uses Google Gemini to intelligently match job descriptions to resumes.
This is the "brain" of the bot that decides which resume to use.
"""

import os
import json
from typing import Dict, Optional, List
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LLMEngine:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the LLM engine with Gemini.
        
        Args:
            api_key: Google AI API key (or uses GEMINI_API_KEY from .env)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "❌ GEMINI_API_KEY not found!\n"
                "   1. Get your free API key: from google ai studio"
                "   2. Add to .env file: GEMINI_API_KEY=your_key_here"
            )
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        
        # Use Gemini 1.5 Flash (fast and cheap, perfect for this task)
        self.model = genai.GenerativeModel('gemini-flash-latest')
        
        print("LLM Engine initialized (Gemini 2.0 Flash)")
    
    
    def select_best_resume(
        self, 
        job_description: str, 
        resumes: Dict[str, Dict],
        job_title: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Analyze job description and select the most suitable resume.
        
        Args:
            job_description: The full job posting text
            resumes: Dictionary of resume data from ResumeManager
            job_title: Optional job title for better context
            
        Returns:
            {
                'selected_resume': 'frontend.pdf',
                'confidence': 0.92,
                'reasoning': 'This resume highlights React and TypeScript...',
                'match_score': 85
            }
        """
        if not resumes:
            raise ValueError("❌ No resumes available for matching!")
        
        # Build the prompt
        prompt = self._build_matching_prompt(job_description, resumes, job_title)
        
        try:
            print("Analyzing job description with Gemini...")
            
            # Call Gemini API
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Parse the JSON response
            result = self._parse_llm_response(result_text, resumes)
            
            print(f" Selected: {result['selected_resume']} "
                  f"(Confidence: {result['confidence']:.0%})")
            
            return result
            
        except Exception as e:
            print(f"⚠️ LLM error: {e}")
            # Fallback: return first resume
            return self._fallback_selection(resumes)
    
    
    def _build_matching_prompt(
        self, 
        job_description: str, 
        resumes: Dict[str, Dict],
        job_title: Optional[str]
    ) -> str:
        """
        Construct the prompt for Gemini to analyze and match.
        """
        # Prepare resume summaries (first 800 words of each)
        resume_summaries = {}
        for filename, data in resumes.items():
            text = data['text']
            words = text.split()[:800]  # Limit context size
            resume_summaries[filename] = ' '.join(words)
        
        job_context = f"Job Title: {job_title}\n\n" if job_title else ""
        
        prompt = f"""You are an expert resume matcher for job applications. Your task is to analyze a job description and select the BEST resume from the available options.

{job_context}Job Description:
---
{job_description[:3000]}  
---

Available Resumes:
"""
        
        for filename, text in resume_summaries.items():
            prompt += f"\n\n=== {filename} ===\n{text}\n"
        
        prompt += """

TASK:
Analyze the job requirements and select the resume that is the BEST match. Consider:
1. Technical skills alignment (frameworks, languages, tools)
2. Experience level match (junior/mid/senior)
3. Domain expertise (frontend/backend/fullstack/devops/etc.)
4. Relevant projects or achievements

RESPOND ONLY IN THIS EXACT JSON FORMAT (no markdown, no explanation outside JSON):
{
  "selected_resume": "exact_filename.pdf",
  "confidence": 0.85,
  "reasoning": "Brief 1-2 sentence explanation of why this resume is best",
  "match_score": 85,
  "key_matches": ["React", "TypeScript", "5+ years experience"]
}

Rules:
- selected_resume MUST be one of the exact filenames provided
- confidence: 0.0 to 1.0 (decimal)
- match_score: 0 to 100 (integer)
- Be decisive - always pick ONE resume, even if none are perfect
- If multiple resumes are equally good, pick the most specialized one
"""
        
        return prompt
    
    
    def _parse_llm_response(self, response_text: str, resumes: Dict) -> Dict:
        """
        Parse and validate the LLM's JSON response.
        """
        try:
            # Remove markdown code blocks if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            # Parse JSON
            result = json.loads(response_text.strip())
            
            # Validate required fields
            required_fields = ['selected_resume', 'confidence', 'reasoning', 'match_score']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate selected resume exists
            if result['selected_resume'] not in resumes:
                # Try to find closest match (case-insensitive)
                selected_lower = result['selected_resume'].lower()
                for filename in resumes.keys():
                    if filename.lower() == selected_lower:
                        result['selected_resume'] = filename
                        break
                else:
                    raise ValueError(f"Invalid resume: {result['selected_resume']}")
            
            # Normalize confidence to 0-1 range
            confidence = float(result['confidence'])
            if confidence > 1.0:
                confidence = confidence / 100.0
            result['confidence'] = max(0.0, min(1.0, confidence))
            
            # Validate match_score
            result['match_score'] = max(0, min(100, int(result['match_score'])))
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse LLM JSON response: {e}")
            print(f"   Raw response: {response_text[:200]}...")
            return self._fallback_selection(resumes)
        except Exception as e:
            print(f"⚠️ Error validating LLM response: {e}")
            return self._fallback_selection(resumes)
    
    
    def _fallback_selection(self, resumes: Dict) -> Dict:
        """
        Fallback: return first resume if LLM fails.
        """
        first_resume = list(resumes.keys())[0]
        print(f"⚠️ Using fallback: {first_resume}")
        
        return {
            'selected_resume': first_resume,
            'confidence': 0.5,
            'reasoning': 'Fallback selection due to LLM error',
            'match_score': 50,
            'key_matches': []
        }
    
    
    def should_apply(
        self, 
        job_description: str,
        match_result: Dict,
        min_confidence: float = 0.6,
        min_match_score: int = 60
    ) -> bool:
        """
        Decide whether to apply based on match quality.
        
        Args:
            job_description: The job posting text
            match_result: Result from select_best_resume()
            min_confidence: Minimum confidence threshold (0.0-1.0)
            min_match_score: Minimum match score (0-100)
            
        Returns:
            True if the job is worth applying to
        """
        confidence = match_result.get('confidence', 0)
        score = match_result.get('match_score', 0)
        
        # Check thresholds
        if confidence < min_confidence:
            print(f"⏭️ Skipping: Low confidence ({confidence:.0%} < {min_confidence:.0%})")
            return False
        
        if score < min_match_score:
            print(f"⏭️ Skipping: Low match score ({score} < {min_match_score})")
            return False
        
        # Optional: Check for red flags in job description
        red_flags = ['commission only', 'pay to apply']
        job_lower = job_description.lower()
        
        for flag in red_flags:
            if flag in job_lower:
                print(f"🚩 Red flag detected: '{flag}' - Skipping")
                return False
        
        print(f"✅ Good match! Proceeding with application")
        return True
    
    
    def extract_job_info(self, job_description: str) -> Dict[str, str]:
        """
        Extract structured information from job description (optional utility).
        
        Returns:
            {
                'company': 'Google',
                'location': 'Remote',
                'experience_level': 'Mid-level',
                'key_skills': ['Python', 'AWS', 'Docker']
            }
        """
        prompt = f"""Extract key information from this job description in JSON format:

{job_description[:2000]}

Respond ONLY with JSON (no markdown):
{{
  "company": "company name or 'Unknown'",
  "location": "location or 'Remote/Not specified'",
  "experience_level": "Entry/Mid/Senior/Not specified",
  "key_skills": ["skill1", "skill2", "skill3"]
}}
"""
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Clean markdown if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0]
            
            return json.loads(result_text.strip())
            
        except Exception as e:
            print(f"⚠️ Could not extract job info: {e}")
            return {
                'company': 'Unknown',
                'location': 'Not specified',
                'experience_level': 'Not specified',
                'key_skills': []
            }


# ============================================================
# 🧪 TESTING / STANDALONE USAGE
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TESTING LLM ENGINE")
    print("=" * 60 + "\n")
    
    # Check for API key
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY not found in .env file")
        print("\n📝 Create a .env file with:")
        print("   GEMINI_API_KEY=your_api_key_here")
        print("\n🔑 Get your key at: https://makersuite.google.com/app/apikey")
        exit(1)
    
    # Initialize engine
    engine = LLMEngine()
    
    # Mock resume data
    mock_resumes = {
        'frontend.pdf': {
            'text': 'Frontend Developer with 5 years experience in React, TypeScript, Next.js. Built scalable web applications for 100k+ users. Expert in Redux, TailwindCSS, responsive design.',
            'filename': 'frontend.pdf'
        },
        'backend.pdf': {
            'text': 'Backend Engineer specializing in Node.js, Python, PostgreSQL. Designed microservices architecture handling 1M+ requests/day. Experience with Docker, Kubernetes, AWS.',
            'filename': 'backend.pdf'
        }
    }
    
    # Mock job description
    mock_job = """
    Senior Frontend Engineer - Remote
    
    We're looking for an experienced React developer to join our team.
    
    Requirements:
    - 5+ years with React and TypeScript
    - Experience with Next.js and server-side rendering
    - Strong CSS skills (TailwindCSS preferred)
    - Experience building customer-facing products
    
    Nice to have:
    - Redux or Zustand state management
    - Performance optimization experience
    """
    
    # Test resume matching
    print("\n🎯 Testing resume selection:")
    print("-" * 60)
    result = engine.select_best_resume(mock_job, mock_resumes, "Senior Frontend Engineer")
    
    print(f"\n📊 Result:")
    print(f"   Selected: {result['selected_resume']}")
    print(f"   Confidence: {result['confidence']:.0%}")
    print(f"   Match Score: {result['match_score']}/100")
    print(f"   Reasoning: {result['reasoning']}")
    
    # Test should_apply logic
    print("\n🤔 Should we apply?")
    print("-" * 60)
    should_apply = engine.should_apply(mock_job, result, min_confidence=0.7, min_match_score=70)
    print(f"   Decision: {'✅ YES' if should_apply else '❌ NO'}")
    
    print("\n" + "=" * 60)
    print("✅ Testing complete!")
    print("=" * 60)