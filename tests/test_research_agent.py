"""
Test suite for the Research Agent with MongoDB integration.
"""

import pytest


class InMemoryCursor(list):
    """Small MongoDB cursor double used for integration-style agent tests."""

    def sort(self, _specification):
        return self

    def limit(self, count):
        return InMemoryCursor(self[:count])


class InMemoryCollection:
    def __init__(self):
        self.documents = []

    def insert_one(self, document):
        stored = dict(document)
        stored["_id"] = len(self.documents) + 1
        self.documents.append(stored)
        return type("InsertOneResult", (), {"inserted_id": stored["_id"]})()

    def find(self, filter_document, _projection=None):
        if "$text" not in filter_document:
            return InMemoryCursor(dict(document) for document in self.documents)

        terms = filter_document["$text"]["$search"].lower().split()
        matches = [
            dict(document)
            for document in self.documents
            if any(
                term in " ".join(
                    [
                        document["title"],
                        document["abstract"],
                        *document.get("keywords", []),
                    ]
                ).lower()
                for term in terms
            )
        ]
        return InMemoryCursor(matches)


class InMemoryMongoClient:
    def __init__(self):
        self.collection = InMemoryCollection()

    def __getitem__(self, _database):
        return {"papers": self.collection, "test_collection": self.collection}


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
            collection="test_collection",
            client=InMemoryMongoClient(),
        )
        
        assert mongo_tool.database == "test_db"
        assert mongo_tool.collection == "test_collection"
    
    def test_mongodb_tool_insert_paper(self):
        """Test inserting a paper into MongoDB."""
        from agent import MongoDBTool, Paper
        
        client = InMemoryMongoClient()
        mongo_tool = MongoDBTool(
            atlas_uri="mongodb://localhost:27017",
            database="test_db",
            collection="papers",
            client=client,
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
        assert client.collection.documents[0]["title"] == paper.title
    
    def test_mongodb_tool_search_returns_list(self):
        """Test that search returns a list."""
        from agent import MongoDBTool
        
        mongo_tool = MongoDBTool(
            atlas_uri="mongodb://localhost:27017",
            database="test_db",
            collection="papers",
            client=InMemoryMongoClient(),
        )
        
        results = mongo_tool.search_papers("test query", limit=5)
        assert isinstance(results, list)


class TestPaperSearchTool:
    """Tests for paper search functionality."""
    
    def test_search_returns_papers(self):
        """Test that search returns a list of papers."""
        from agent import PaperSearchTool, Paper
        
        search_tool = PaperSearchTool(api_key="test_key")
        results = search_tool.search("machine learning")
        
        assert len(results) > 0
        assert all(isinstance(p, Paper) for p in results)
    
    def test_paper_has_required_fields(self):
        """Test that returned papers have required fields."""
        from agent import PaperSearchTool
        
        search_tool = PaperSearchTool()
        results = search_tool.search("AI")
        
        if results:
            paper = results[0]
            assert hasattr(paper, 'title')
            assert hasattr(paper, 'authors')
            assert hasattr(paper, 'abstract')
            assert hasattr(paper, 'url')
            assert hasattr(paper, 'year')


class TestResearchAgent:
    """Tests for the Research Agent workflow."""
    
    def test_agent_initialization(self):
        """Test that agent can be initialized with required components."""
        from agent import ResearchAgent, MongoDBTool, PaperSearchTool
        
        llm_client = MockLLMClient()
        mongo_tool = MongoDBTool("", "test_db", "papers", client=InMemoryMongoClient())
        search_tool = PaperSearchTool()
        
        agent = ResearchAgent(llm_client, mongo_tool, search_tool)
        
        assert agent.llm is not None
        assert agent.mongo is not None
        assert agent.search is not None
        assert hasattr(agent, 'tools')
    
    def test_agent_has_tools_defined(self):
        """Test that agent defines its available tools."""
        from agent import ResearchAgent, MongoDBTool, PaperSearchTool
        
        llm_client = MockLLMClient()
        mongo_tool = MongoDBTool("", "test_db", "papers", client=InMemoryMongoClient())
        search_tool = PaperSearchTool()
        
        agent = ResearchAgent(llm_client, mongo_tool, search_tool)
        
        assert len(agent.tools) > 0
        assert any(tool["name"] == "search_papers" for tool in agent.tools)
        assert any(tool["name"] == "store_paper" for tool in agent.tools)
    
    def test_execute_research_workflow(self):
        """Test the full research workflow execution."""
        from agent import ResearchAgent, MongoDBTool, PaperSearchTool
        
        llm_client = MockLLMClient()
        mongo_tool = MongoDBTool("", "test_db", "papers", client=InMemoryMongoClient())
        search_tool = PaperSearchTool()
        
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
        from agent import ResearchAgent, MongoDBTool, PaperSearchTool
        
        llm_client = MockLLMClient()
        mongo_tool = MongoDBTool("", "test_db", "papers", client=InMemoryMongoClient())
        search_tool = PaperSearchTool()
        
        agent = ResearchAgent(llm_client, mongo_tool, search_tool)
        result = agent.execute_research_workflow("Test question", max_papers=1)
        
        workflow_log = result["workflow_log"]
        assert len(workflow_log) >= 4  # At least 4 steps logged
        
        # Check that steps are sequential
        for i, log_entry in enumerate(workflow_log):
            assert "step" in log_entry
            assert "action" in log_entry or "result" in log_entry

    def test_inserted_paper_is_retrieved_and_used_for_chat(self):
        """Exercise persistence, retrieval, and RAG context as one flow."""
        from agent import MongoDBTool, Paper, PaperSearchTool, ResearchAgent

        client = InMemoryMongoClient()
        mongo_tool = MongoDBTool("mongodb://test", "test_db", "papers", client=client)
        paper = Paper(
            title="Reliable Retrieval for Research Assistants",
            authors=["Ada Lovelace"],
            abstract="Indexed retrieval makes research answers grounded in papers.",
            url="https://example.com/retrieval",
            year=2025,
            keywords=["retrieval", "RAG"],
        )
        mongo_tool.insert_paper(paper)

        stored_papers = mongo_tool.get_all_papers()
        assert stored_papers[0]["title"] == paper.title
        assert mongo_tool.search_papers("grounded retrieval", limit=1)[0]["title"] == paper.title

        llm_client = MockLLMClient()
        agent = ResearchAgent(llm_client, mongo_tool, PaperSearchTool())
        agent.chat_with_papers("What makes answers grounded?")

        assert paper.title in llm_client.call_history[-1]
        assert paper.abstract in llm_client.call_history[-1]


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
    
    def test_create_research_agent(self, monkeypatch):
        """Test creating an agent via factory function."""
        from agent import create_research_agent
        from agent import ResearchAgent
        
        llm_client = MockLLMClient()
        monkeypatch.setenv("MONGODB_DATABASE", "configured_db")
        monkeypatch.setenv("MONGODB_COLLECTION", "configured_papers")
        monkeypatch.setenv("MONGODB_USERNAME", "configured_user")
        monkeypatch.setenv("MONGODB_PASSWORD", "configured_password")
        agent = create_research_agent(llm_client, mongo_uri="mongodb://localhost")
        
        assert isinstance(agent, ResearchAgent)
        assert agent.mongo.database == "configured_db"
        assert agent.mongo.collection == "configured_papers"
        assert agent.mongo.username == "configured_user"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
