"""
AI Research Assistant Agent
A multi-step reasoning agent that helps researchers discover, organize, and synthesize academic papers.

Partner Track: MongoDB
Problem Solved: Researchers spend hours manually searching, reading, and organizing academic papers.
This agent automates literature review by:
1. Searching for relevant papers based on research questions
2. Extracting key findings and methodologies
3. Storing and organizing papers in MongoDB
4. Generating synthesis reports and identifying research gaps
"""

from __future__ import annotations

import json
import os
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Paper:
    """Represents an academic paper."""
    title: str
    authors: list[str]
    abstract: str
    url: str
    year: int
    venue: str = ""
    keywords: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "url": self.url,
            "year": self.year,
            "venue": self.venue,
            "keywords": self.keywords,
            "created_at": datetime.now(timezone.utc).isoformat()
        }


class MongoDBTool:
    """Persist and retrieve papers with the MongoDB Python driver.

    ``atlas_uri`` is a standard MongoDB connection URI, such as the URI copied
    from Atlas.  The target collection must have a MongoDB text index covering
    the fields that should be searchable (for example ``title``, ``abstract``,
    and ``keywords``).  Supplying ``client`` is useful for tests and lets an
    application manage the driver's lifecycle itself.
    """

    def __init__(
        self,
        atlas_uri: str,
        database: str,
        collection: str,
        *,
        username: str | None = None,
        password: str | None = None,
        auth_source: str | None = None,
        client: Any | None = None,
    ):
        self.atlas_uri = atlas_uri
        self.database = database
        self.collection = collection
        self.username = username
        self.password = password
        self.auth_source = auth_source
        self._client = client

    def _get_collection(self) -> Any:
        """Return the configured collection, creating the driver client lazily."""
        if self._client is None:
            if not self.atlas_uri:
                raise ValueError(
                    "MongoDB is not configured. Set MONGODB_URI (or "
                    "MONGODB_ATLAS_URI) before using MongoDBTool."
                )

            from pymongo import MongoClient

            connection_options: dict[str, Any] = {
                "serverSelectionTimeoutMS": 5_000,
            }
            if self.username:
                connection_options["username"] = self.username
            if self.password:
                connection_options["password"] = self.password
            if self.auth_source:
                connection_options["authSource"] = self.auth_source
            self._client = MongoClient(self.atlas_uri, **connection_options)

        return self._client[self.database][self.collection]

    @staticmethod
    def _record(document: dict[str, Any]) -> dict[str, Any]:
        """Return a document that is safe to pass to an LLM or JSON encoder."""
        record = dict(document)
        if "_id" in record:
            record["_id"] = str(record["_id"])
        return record

    def insert_paper(self, paper: Paper) -> dict[str, str]:
        """Insert the exact dictionary representation of ``paper``."""
        result = self._get_collection().insert_one(paper.to_dict())
        return {"status": "success", "paper_id": str(result.inserted_id)}

    def search_papers(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search papers through MongoDB's indexed ``$text`` search.

        MongoDB ranks text-search matches using its text index.  This avoids a
        collection scan and does not require creating embeddings at write time.
        """
        if not query.strip():
            return []
        if limit < 1:
            return []

        cursor = self._get_collection().find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}},
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        return [self._record(document) for document in cursor]

    def get_all_papers(self) -> list[dict[str, Any]]:
        """Retrieve every paper stored in the configured collection."""
        return [self._record(document) for document in self._get_collection().find({})]


class PaperSearchTool:
    """Tool for searching academic papers via external APIs."""
    
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        # Could integrate with: Semantic Scholar, arXiv, PubMed, etc.
    
    def search(self, query: str, year_range: tuple[int, int] = None) -> list[Paper]:
        """Search for papers matching the query."""
        # Simulated results - in production call actual API
        papers = [
            Paper(
                title=f"Research Paper on {query}",
                authors=["Author A", "Author B"],
                abstract=f"This paper explores {query} in depth...",
                url="https://example.com/paper1",
                year=2024,
                venue="Example Conference",
                keywords=[query, "research"]
            )
        ]
        return papers


class ResearchAgent:
    """
    Multi-step AI agent for automated literature review.
    
    Workflow:
    1. Parse research question and extract key concepts
    2. Search for relevant papers using multiple sources
    3. Extract and summarize key information from each paper
    4. Store organized data in MongoDB
    5. Generate synthesis report with insights and gaps
    """
    
    def __init__(self, llm_client, mongo_tool: MongoDBTool, search_tool: PaperSearchTool):
        self.llm = llm_client
        self.mongo = mongo_tool
        self.search = search_tool
        self.tools = self._define_tools()
    
    def _define_tools(self) -> list[dict[str, Any]]:
        """Define available tools for the agent."""
        return [
            {
                "name": "search_papers",
                "description": "Search for academic papers based on a research query",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {
                            "type": "STRING",
                            "description": "The research topic or question to search for"
                        },
                        "year_start": {
                            "type": "INTEGER",
                            "description": "Starting year for paper search"
                        },
                        "year_end": {
                            "type": "INTEGER",
                            "description": "Ending year for paper search"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "store_paper",
                "description": "Store a paper's details in the MongoDB database",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING", "description": "Paper title"},
                        "authors": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of authors"},
                        "abstract": {"type": "STRING", "description": "Paper abstract"},
                        "url": {"type": "STRING", "description": "URL to the paper"},
                        "year": {"type": "INTEGER", "description": "Publication year"},
                        "keywords": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Keywords"}
                    },
                    "required": ["title", "authors", "abstract", "url", "year"]
                }
            },
            {
                "name": "summarize_paper",
                "description": "Generate a concise summary of a paper's key contributions",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "abstract": {"type": "STRING", "description": "The paper's abstract"},
                        "focus": {"type": "STRING", "description": "Specific aspect to focus on (e.g., methodology, results)"}
                    },
                    "required": ["abstract"]
                }
            },
            {
                "name": "compare_papers",
                "description": "Compare multiple papers and identify similarities/differences",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "paper_abstracts": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of abstracts to compare"},
                        "comparison_aspect": {"type": "STRING", "description": "What to compare (methods, findings, etc.)"}
                    },
                    "required": ["paper_abstracts"]
                }
            }
        ]
    
    def execute_research_workflow(self, research_question: str, max_papers: int = 10) -> dict:
        """
        Execute the full literature review workflow.
        
        Steps:
        1. Analyze the research question
        2. Generate search queries
        3. Search and retrieve papers
        4. Process and store each paper
        5. Synthesize findings
        6. Identify research gaps
        """
        workflow_log = []
        
        # Step 1: Analyze research question
        workflow_log.append({"step": 1, "action": "Analyzing research question"})
        analysis_prompt = f"""
        Analyze this research question and extract:
        1. Key concepts and terminology
        2. Related sub-topics to explore
        3. Suggested search queries
        
        Research Question: {research_question}
        
        Return as JSON with keys: concepts, subtopics, search_queries
        """
        
        analysis_response = self.llm.generate(analysis_prompt)
        workflow_log.append({"step": 1, "result": "Analysis complete"})
        
        # Step 2: Search for papers
        workflow_log.append({"step": 2, "action": "Searching for relevant papers"})
        search_queries = [research_question]  # Could extract from analysis
        found_papers = []
        
        for query in search_queries[:3]:  # Limit searches
            papers = self.search.search(query)
            found_papers.extend(papers)
            if len(found_papers) >= max_papers:
                break
        
        workflow_log.append({"step": 2, "result": f"Found {len(found_papers)} papers"})
        
        # Step 3: Process and store papers
        workflow_log.append({"step": 3, "action": "Processing and storing papers"})
        stored_papers = []
        
        for paper in found_papers[:max_papers]:
            # Summarize the paper
            summary_prompt = f"""
            Summarize this paper's key contributions in 2-3 sentences:
            Title: {paper.title}
            Abstract: {paper.abstract}
            """
            summary = self.llm.generate(summary_prompt)
            
            # Store in MongoDB
            self.mongo.insert_paper(paper)
            stored_papers.append({
                "paper": paper.to_dict(),
                "summary": summary
            })
        
        workflow_log.append({"step": 3, "result": f"Stored {len(stored_papers)} papers"})
        
        # Step 4: Synthesize findings
        workflow_log.append({"step": 4, "action": "Synthesizing research findings"})
        
        if stored_papers:
            abstracts = [p["paper"]["abstract"] for p in stored_papers]
            synthesis_prompt = f"""
            Based on these research paper abstracts, provide:
            1. Common themes and patterns
            2. Key methodologies used
            3. Main findings across papers
            4. Areas of agreement or disagreement
            
            Abstracts:
            {json.dumps(abstracts[:5], indent=2)}
            
            Research Question: {research_question}
            """
            synthesis = self.llm.generate(synthesis_prompt)
        else:
            synthesis = "No papers found to synthesize."
        
        workflow_log.append({"step": 4, "result": "Synthesis complete"})
        
        # Step 5: Identify research gaps
        workflow_log.append({"step": 5, "action": "Identifying research gaps"})
        gaps_prompt = f"""
        Based on the synthesized research, identify:
        1. Unanswered questions
        2. Methodological limitations
        3. Opportunities for future research
        4. Underexplored areas
        
        Synthesis: {synthesis[:2000]}
        """
        gaps = self.llm.generate(gaps_prompt)
        workflow_log.append({"step": 5, "result": "Gap analysis complete"})
        
        return {
            "research_question": research_question,
            "papers_found": len(found_papers),
            "papers_stored": len(stored_papers),
            "stored_papers": stored_papers,
            "synthesis": synthesis,
            "research_gaps": gaps,
            "workflow_log": workflow_log,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def chat_with_papers(self, user_query: str, context_papers: list[dict] = None) -> str:
        """
        Enable Q&A over stored papers using RAG (Retrieval Augmented Generation).
        """
        if not context_papers:
            context_papers = self.mongo.get_all_papers()
        
        # Build context from papers
        context = "\n\n".join([
            f"Paper: {p.get('title', 'Unknown')}\nAbstract: {p.get('abstract', 'N/A')}"
            for p in context_papers[:5]
        ])
        
        prompt = f"""
        You are a research assistant answering questions based on academic papers.
        
        Available Papers:
        {context}
        
        User Question: {user_query}
        
        Answer the question using only information from the papers above.
        If the answer isn't in the papers, say so clearly.
        Include citations (paper titles) when referencing specific information.
        """
        
        return self.llm.generate(prompt)


def create_research_agent(
    llm_client,
    mongo_uri: str | None = None,
) -> ResearchAgent:
    """Create an agent configured from MongoDB driver environment variables.

    Required at runtime: ``MONGODB_URI`` (or the legacy ``MONGODB_ATLAS_URI``).
    Optional credential variables are ``MONGODB_USERNAME``,
    ``MONGODB_PASSWORD``, and ``MONGODB_AUTH_SOURCE``.  The database and
    collection can be selected with ``MONGODB_DATABASE`` and
    ``MONGODB_COLLECTION`` respectively.
    """
    mongo_uri = mongo_uri or os.getenv("MONGODB_URI") or os.getenv("MONGODB_ATLAS_URI", "")
    mongo_tool = MongoDBTool(
        atlas_uri=mongo_uri,
        database=os.getenv("MONGODB_DATABASE", "research_assistant"),
        collection=os.getenv("MONGODB_COLLECTION", "papers"),
        username=os.getenv("MONGODB_USERNAME") or None,
        password=os.getenv("MONGODB_PASSWORD") or None,
        auth_source=os.getenv("MONGODB_AUTH_SOURCE") or None,
    )
    search_tool = PaperSearchTool(api_key=os.getenv("PAPER_SEARCH_API_KEY", ""))
    
    return ResearchAgent(llm_client, mongo_tool, search_tool)
