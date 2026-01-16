import re
from typing import Dict, List

class CheatDetector:
    def __init__(self):
        self.suspicion_threshold = 5
        
    def analyze_response(
        self, 
        question: str, 
        answer: str, 
        response_time: float,
        question_difficulty: int = 3
    ) -> Dict:
        """
        Analyze student response for potential cheating indicators
        
        Args:
            question: The question asked
            answer: Student's answer
            response_time: Time taken to respond (seconds)
            question_difficulty: Scale 1-5
            
        Returns:
            Dict with suspicion_score and flags
        """
        suspicion_score = 0
        flags = []
        
        # Check 1: Response time analysis
        expected_time = len(answer.split()) * 0.5  # ~2 words per second
        if response_time < expected_time * 0.3 and len(answer) > 50:
            suspicion_score += 3
            flags.append("Suspiciously fast response for answer length")
        
        # Check 2: Overly perfect grammar/formatting
        if self._is_overly_polished(answer):
            suspicion_score += 2
            flags.append("Answer appears professionally formatted (possible copy-paste)")
        
        # Check 3: Complexity mismatch
        if question_difficulty >= 4 and self._is_generic_answer(answer):
            suspicion_score += 2
            flags.append("Generic answer to complex question")
        
        # Check 4: Unusual patterns
        if self._has_suspicious_patterns(answer):
            suspicion_score += 1
            flags.append("Unusual text patterns detected")
        
        # Determine risk level
        if suspicion_score >= 6:
            risk_level = "HIGH"
        elif suspicion_score >= 3:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            "suspicion_score": suspicion_score,
            "flags": flags,
            "risk_level": risk_level
        }
    
    def _is_overly_polished(self, text: str) -> bool:
        """Check if text is suspiciously well-formatted"""
        # Check for markdown formatting, bullet points, etc.
        markdown_patterns = [r'\*\*.*?\*\*', r'^\s*[-*+]\s', r'^\s*\d+\.\s']
        for pattern in markdown_patterns:
            if re.search(pattern, text, re.MULTILINE):
                return True
        
        # Check for perfect grammar indicators
        sentences = text.split('.')
        if len(sentences) > 3:
            # Check if all sentences start with capital and end with period
            perfect_count = sum(1 for s in sentences if s.strip() and s.strip()[0].isupper())
            if perfect_count == len([s for s in sentences if s.strip()]):
                return True
        
        return False
    
    def _is_generic_answer(self, text: str) -> bool:
        """Check if answer is too generic"""
        generic_phrases = [
            "it depends", "in general", "typically", "usually",
            "it is important", "it is essential", "one should"
        ]
        generic_count = sum(1 for phrase in generic_phrases if phrase in text.lower())
        return generic_count >= 2
    
    def _has_suspicious_patterns(self, text: str) -> bool:
        """Check for copy-paste indicators"""
        # Check for repeated exact phrases (copy-paste error)
        words = text.split()
        if len(words) != len(set(words)):
            # Has duplicate words - check if it's unusual
            word_freq = {}
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1
            
            # If any word appears more than 3 times (excluding common words)
            common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at'}
            for word, freq in word_freq.items():
                if word.lower() not in common_words and freq > 3:
                    return True
        
        return False