"""
Test suite for doc_to_scenarios pipeline.
Tests case formatting, JSON validation, and caching functionality.
"""

import pytest
import json
import os
from doc_to_scenarios import format_case, check_json, TestScenario
from unittest.mock import patch, MagicMock


# Test data - the example case provided by user
TEST_CASE_RAW = """Case 1) A 4 year old patient with one day of cough and fever.
Malaria test negative. He's eating well and not vomiting.
Questions:
- What is the child's respiratory rate? (Answer: 65)
- Does the child have chest indrawing or stridor? (Answer: No)
Answer: Treat as pneumonia (non-severe) based on fast breathing
Diagnosis: Pneumonia"""

TEST_CASE_FORMATTED_JSON = {
    "case_number": 1,
    "name": "4yo with cough and fever",
    "description": "NURSE: A 4 year old patient with one day of cough and fever. Malaria test negative. He's eating well and not vomiting. AGENT_QUESTIONS: - What is the child's respiratory rate? (NURSE_RESPONSE: 65) - Does the child have chest indrawing or stridor? (NURSE_RESPONSE: No) AGENT_ANSWER: Treat as pneumonia (non-severe) based on fast breathing. DIAGNOSIS: Pneumonia",
    "original_text": TEST_CASE_RAW,
    "expected_diagnosis": "Pneumonia"
}


class TestCheckJson:
    """Test the JSON validation function"""
    
    def test_valid_json(self):
        """Test that valid JSON is parsed correctly"""
        valid_json_str = json.dumps(TEST_CASE_FORMATTED_JSON)
        result = check_json(valid_json_str, 1)
        
        assert result is not None
        assert result["case_number"] == 1
        assert result["name"] == "4yo with cough and fever"
        assert "original_text" in result
    
    def test_invalid_json(self, capsys):
        """Test that invalid JSON returns None and prints warning"""
        invalid_json = "{ this is not valid json }"
        result = check_json(invalid_json, 1)
        
        assert result is None
        captured = capsys.readouterr()
        assert "Warning" in captured.out
        assert "case 1" in captured.out
    
    def test_empty_string(self):
        """Test that empty string returns None"""
        result = check_json("", 0)
        assert result is None
    
    def test_partial_json(self):
        """Test that partial JSON returns None"""
        partial = '{"case_number": 1, "name":'
        result = check_json(partial, 2)
        assert result is None


class TestFormatCase:
    """Test the case formatting function"""
    
    @patch('doc_to_scenarios.litellm.completion')
    def test_format_case_returns_string(self, mock_completion):
        """Test that format_case returns a string"""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(TEST_CASE_FORMATTED_JSON)
        mock_completion.return_value = mock_response
        
        result = format_case(TEST_CASE_RAW)
        
        assert isinstance(result, str)
        assert mock_completion.called
    
    @patch('doc_to_scenarios.litellm.completion')
    def test_format_case_uses_system_prompt(self, mock_completion):
        """Test that format_case uses the system prompt"""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "{}"
        mock_completion.return_value = mock_response
        
        format_case(TEST_CASE_RAW)
        
        # Check that the system prompt was used
        call_args = mock_completion.call_args
        messages = call_args[1]['messages']
        assert len(messages) == 2
        assert messages[0]['role'] == 'system'
        assert 'test scenario' in messages[0]['content'].lower()
        assert messages[1]['role'] == 'user'
        assert messages[1]['content'] == TEST_CASE_RAW


class TestCachingSystem:
    """Test the JSONL caching system"""
    
    @pytest.fixture
    def temp_cache_file(self, tmp_path):
        """Create a temporary cache file for testing"""
        cache_file = tmp_path / "test_cache.jsonl"
        return str(cache_file)
    
    def test_cache_write_and_read(self, temp_cache_file):
        """Test that scenarios can be written to and read from cache"""
        # Write test scenarios to cache
        test_scenarios = [
            TEST_CASE_FORMATTED_JSON,
            {**TEST_CASE_FORMATTED_JSON, "case_number": 2, "original_text": "Different case"}
        ]
        
        with open(temp_cache_file, 'w') as f:
            for scenario in test_scenarios:
                f.write(json.dumps(scenario) + '\n')
        
        # Read back from cache
        cached_cases = {}
        with open(temp_cache_file, 'r') as f:
            for line in f:
                if line.strip():
                    scenario = json.loads(line)
                    if 'original_text' in scenario:
                        cached_cases[scenario['original_text']] = scenario
        
        # Verify
        assert len(cached_cases) == 2
        assert TEST_CASE_RAW in cached_cases
        assert cached_cases[TEST_CASE_RAW]['case_number'] == 1
    
    def test_cache_handles_empty_lines(self, temp_cache_file):
        """Test that cache reading handles empty lines gracefully"""
        with open(temp_cache_file, 'w') as f:
            f.write(json.dumps(TEST_CASE_FORMATTED_JSON) + '\n')
            f.write('\n')  # Empty line
            f.write('\n')  # Another empty line
            f.write(json.dumps({**TEST_CASE_FORMATTED_JSON, "case_number": 2, "original_text": "Case 2"}) + '\n')
        
        # Read and verify no crashes
        cached_cases = {}
        with open(temp_cache_file, 'r') as f:
            for line in f:
                if line.strip():
                    scenario = json.loads(line)
                    if 'original_text' in scenario:
                        cached_cases[scenario['original_text']] = scenario
        
        assert len(cached_cases) == 2
    
    def test_cache_deduplication(self, temp_cache_file):
        """Test that cache deduplicates by original_text"""
        # Write same case twice with different data
        case1 = TEST_CASE_FORMATTED_JSON
        case2 = {**TEST_CASE_FORMATTED_JSON, "name": "Updated name"}
        
        with open(temp_cache_file, 'w') as f:
            f.write(json.dumps(case1) + '\n')
            f.write(json.dumps(case2) + '\n')
        
        # Read back - should only have one entry (last one wins)
        cached_cases = {}
        with open(temp_cache_file, 'r') as f:
            for line in f:
                if line.strip():
                    scenario = json.loads(line)
                    if 'original_text' in scenario:
                        cached_cases[scenario['original_text']] = scenario
        
        assert len(cached_cases) == 1
        assert cached_cases[TEST_CASE_RAW]['name'] == "Updated name"


class TestIntegration:
    """Integration tests for the full pipeline"""
    
    @patch('doc_to_scenarios.extract_case_separated_docs')
    @patch('doc_to_scenarios.format_case')
    def test_pipeline_with_mock_llm(self, mock_format, mock_extract, tmp_path):
        """Test the full pipeline with mocked LLM calls"""
        from doc_to_scenarios import doc_to_scenarios
        
        # Setup mocks
        mock_extract.return_value = [TEST_CASE_RAW]
        mock_format.return_value = json.dumps(TEST_CASE_FORMATTED_JSON)
        
        # Change to temp directory for cache file
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            # First run - should process case
            scenarios = doc_to_scenarios(retries=1)
            
            assert len(scenarios) == 1
            assert scenarios[0]['case_number'] == 1
            assert scenarios[0]['name'] == "4yo with cough and fever"
            
            # Verify cache file was created
            assert os.path.exists('case_scenarios_cache.jsonl')
            
            # Second run - should load from cache
            mock_format.reset_mock()
            scenarios2 = doc_to_scenarios(retries=1)
            
            assert len(scenarios2) == 1
            # Format should not be called again (loaded from cache)
            assert not mock_format.called
            
        finally:
            os.chdir(original_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

