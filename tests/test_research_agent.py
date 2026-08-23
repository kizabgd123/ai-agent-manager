"""
Test suite for the Research Agent with MongoDB integration.
"""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest


class MockLLMClient:
    """Mock LLM client for testing."""
    
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.call_history = []
    
    def generate(self, prompt: str) -> str:
        self.call_history.append(prompt)
        # Return mock responses based on prompt content
        if "analyze" in prompt.lower() or "concepts" in prompt.lower():
            return '{"concepts": ["AI", "ML"], "subtopics": ["deep learning"], "search_queries": ["AI research"]}'
        elif "summarize" in prompt.lower():
            return "This paper presents a novel approach to machine learning."
        elif "synthesis" in prompt.lower() or "themes" in prompt.lower():
            return "Common themes include neural networks and optimization techniques."
        elif "gaps" in prompt.lower() or "limitations" in prompt.lower():
            return "Key gaps include lack of real-world validation and scalability concerns."
        else:
            return "Mock response from LLM."
    
    def generate_with_tools(self, prompt: str, tools: list) -> dict:
        self.call_history.append({"prompt": prompt, "tools": tools})
        return {
            "content": "Mock tool-based response",
            "tool_calls": [],
            "raw_response": {}
        }


class TestMongoDBTool:
    """Tests for MongoDB integration tool."""
    
    def test_mongodb_tool_initialization(self):
        """Test MongoDB tool can be initialized."""
        from agent import MongoDBTool
        
        mongo_tool = MongoDBTool(
            atlas_uri="mongodb://localhost:27017",
            database="test_db",
            collection="test_collection"
        )
        
        assert mongo_tool.database == "test_db"
        assert mongo_tool.collection == "test_collection"
    
    def test_mongodb_tool_insert_paper(self):
        """Test inserting a paper into MongoDB."""
        from agent import MongoDBTool, Paper
        
        mongo_tool = MongoDBTool(
            atlas_uri="mongodb://localhost:27017",
            database="test_db",
            collection="papers"
        )
        
        paper = Paper(
            title="Test Paper",
            authors=["Author 1"],
            abstract="Test abstract",
            url="https://example.com",
            year=2024
        )
        
        result = mongo_tool.insert_paper(paper)
        assert result["status"] == "success"
    
    def test_mongodb_tool_search_returns_list(self):
        """Test that search returns a list."""
        from agent import MongoDBTool
        
        mongo_tool = MongoDBTool(
            atlas_uri="mongodb://localhost:27017",
            database="test_db",
            collection="papers"
        )
        
        results = mongo_tool.search_papers("test query", limit=5)
        assert isinstance(results, list)


class TestPaperSearchTool:
    """Tests for paper search functionality."""

    @staticmethod
    def _response(payload):
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.read.return_value = json.dumps(payload).encode()
        return response

    def test_search_constructs_semantic_scholar_request(self):
        """Build a URL-encoded request with requested fields and API key."""
        from agent import PaperSearchTool

        response = self._response({"data": []})
        with patch("agent.research_agent.urllib.request.urlopen", return_value=response) as urlopen:
            PaperSearchTool(api_key="secret").search("graph neural networks", limit=3)

        request = urlopen.call_args.args[0]
        assert request.full_url.startswith(PaperSearchTool.API_URL)
        assert "query=graph+neural+networks" in request.full_url
        assert "limit=3" in request.full_url
        assert "fields=title%2Cauthors%2Cabstract%2Curl%2Cyear%2Cvenue%2CfieldsOfStudy" in request.full_url
        assert request.get_header("X-api-key") == "secret"
        assert urlopen.call_args.kwargs["timeout"] == 10

    def test_search_filters_years_and_enforces_limit(self):
        """Apply an inclusive local year filter before returning the limit."""
        from agent import PaperSearchTool

        payload = {
            "data": [
                {"title": "Old", "year": 2019, "authors": []},
                {"title": "Included one", "year": 2021, "authors": []},
                {"title": "Included two", "year": 2022, "authors": []},
                {"title": "Included three", "year": 2023, "authors": []},
            ]
        }
        with patch("agent.research_agent.urllib.request.urlopen", return_value=self._response(payload)):
            papers = PaperSearchTool().search("AI", year_range=(2021, 2023), limit=2)

        assert [paper.title for paper in papers] == ["Included one", "Included two"]

    def test_search_maps_provider_results_and_skips_malformed_records(self):
        """Map supported Semantic Scholar fields without inventing paper data."""
        from agent import PaperSearchTool, Paper

        payload = {
            "data": [
                {
                    "title": "  Mapped paper  ",
                    "authors": [{"name": " Ada Lovelace "}, {"name": ""}, "invalid"],
                    "abstract": " A useful abstract. ",
                    "url": " https://example.org/paper ",
                    "year": 2024,
                    "venue": " TestConf ",
                    "fieldsOfStudy": [" Computer Science ", 42],
                },
                {"title": "Missing year", "authors": []},
                "not a record",
            ]
        }
        with patch("agent.research_agent.urllib.request.urlopen", return_value=self._response(payload)):
            papers = PaperSearchTool().search("AI")

        assert len(papers) == 1
        assert isinstance(papers[0], Paper)
        assert papers[0] == Paper(
            title="Mapped paper",
            authors=["Ada Lovelace"],
            abstract="A useful abstract.",
            url="https://example.org/paper",
            year=2024,
            venue="TestConf",
            keywords=["Computer Science"],
        )

    def test_search_returns_empty_list_for_empty_provider_results(self):
        """Do not substitute fabricated papers when the provider finds none."""
        from agent import PaperSearchTool

        with patch("agent.research_agent.urllib.request.urlopen", return_value=self._response({"data": []})):
            assert PaperSearchTool().search("obscure topic") == []

    @pytest.mark.parametrize("error", [urllib.error.HTTPError("url", 500, "error", {}, None), urllib.error.URLError("offline")])
    def test_search_returns_empty_list_for_provider_failures(self, error):
        """Provider failures are handled without emitting placeholder records."""
        from agent import PaperSearchTool

        with patch("agent.research_agent.urllib.request.urlopen", side_effect=error):
            assert PaperSearchTool().search("AI") == []


class TestResearchAgent:
    """Tests for the Research Agent workflow."""
    
    def test_agent_initialization(self):
        """Test that agent can be initialized with required components."""
        from agent import ResearchAgent, MongoDBTool, PaperSearchTool
        
        llm_client = MockLLMClient()
        mongo_tool = MongoDBTool("", "test_db", "papers")
        search_tool = MagicMock()
        search_tool.search.return_value = []
        
        agent = ResearchAgent(llm_client, mongo_tool, search_tool)
        
        assert agent.llm is not None
        assert agent.mongo is not None
        assert agent.search is not None
        assert hasattr(agent, 'tools')
    
    def test_agent_has_tools_defined(self):
        """Test that agent defines its available tools."""
        from agent import ResearchAgent, MongoDBTool, PaperSearchTool
        
        llm_client = MockLLMClient()
        mongo_tool = MongoDBTool("", "test_db", "papers")
        search_tool = MagicMock()
        search_tool.search.return_value = []
        
        agent = ResearchAgent(llm_client, mongo_tool, search_tool)
        
        assert len(agent.tools) > 0
        assert any(tool["name"] == "search_papers" for tool in agent.tools)
        assert any(tool["name"] == "store_paper" for tool in agent.tools)
    
    def test_execute_research_workflow(self):
        """Test the full research workflow execution."""
        from agent import ResearchAgent, MongoDBTool
        
        llm_client = MockLLMClient()
        mongo_tool = MongoDBTool("", "test_db", "papers")
        search_tool = MagicMock()
        search_tool.search.return_value = []
        
        agent = ResearchAgent(llm_client, mongo_tool, search_tool)
        
        result = agent.execute_research_workflow(
            "What are recent advances in machine learning?",
            max_papers=3
        )
        
        assert "research_question" in result
        assert "papers_found" in result
        assert "papers_stored" in result
        assert "synthesis" in result
        assert "research_gaps" in result
        assert "workflow_log" in result
    
    def test_workflow_logs_steps(self):
        """Test that workflow logs each step."""
        from agent import ResearchAgent, MongoDBTool
        
        llm_client = MockLLMClient()
        mongo_tool = MongoDBTool("", "test_db", "papers")
        search_tool = MagicMock()
        search_tool.search.return_value = []
        
        agent = ResearchAgent(llm_client, mongo_tool, search_tool)
        result = agent.execute_research_workflow("Test question", max_papers=1)
        
        workflow_log = result["workflow_log"]
        assert len(workflow_log) >= 4  # At least 4 steps logged
        
        # Check that steps are sequential
        for i, log_entry in enumerate(workflow_log):
            assert "step" in log_entry
            assert "action" in log_entry or "result" in log_entry


class TestPaperDataClass:
    """Tests for the Paper data class."""
    
    def test_paper_creation(self):
        """Test creating a paper instance."""
        from agent import Paper
        
        paper = Paper(
            title="Test Paper",
            authors=["Author 1", "Author 2"],
            abstract="This is a test abstract",
            url="https://example.com/paper",
            year=2024,
            venue="Test Conference",
            keywords=["test", "example"]
        )
        
        assert paper.title == "Test Paper"
        assert len(paper.authors) == 2
        assert paper.year == 2024
    
    def test_paper_to_dict(self):
        """Test converting paper to dictionary."""
        from agent import Paper
        
        paper = Paper(
            title="Test Paper",
            authors=["Author 1"],
            abstract="Abstract text",
            url="https://example.com",
            year=2024
        )
        
        paper_dict = paper.to_dict()
        
        assert isinstance(paper_dict, dict)
        assert paper_dict["title"] == "Test Paper"
        assert "created_at" in paper_dict


class TestCreateResearchAgent:
    """Tests for the factory function."""
    
    def test_create_research_agent(self):
        """Test creating an agent via factory function."""
        from agent import create_research_agent
        from agent import ResearchAgent
        
        llm_client = MockLLMClient()
        agent = create_research_agent(llm_client, mongo_uri="mongodb://localhost")
        
        assert isinstance(agent, ResearchAgent)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
