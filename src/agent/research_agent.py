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
import urllib.error
import urllib.parse
import urllib.request
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
    """Tool for interacting with MongoDB Atlas via HTTP API."""
    
    def __init__(self, atlas_uri: str, database: str, collection: str):
        self.atlas_uri = atlas_uri
        self.database = database
        self.collection = collection
        self.base_url = f"{atlas_uri}/api/rest/v2" if atlas_uri else ""
    
    def insert_paper(self, paper: Paper) -> dict:
        """Insert a paper into MongoDB."""
        # In production, use proper MongoDB Atlas Data API
        return {"status": "success", "paper_id": paper.title}
    
    def search_papers(self, query: str, limit: int = 5) -> list[dict]:
        """Search for papers in MongoDB using vector search."""
        # Simulated search - in production use Atlas Vector Search
        return []
    
    def get_all_papers(self) -> list[dict]:
        """Retrieve all stored papers."""
        return []


class PaperSearchTool:
    """Search papers through the Semantic Scholar Graph API.

    Semantic Scholar documents its paper-search endpoint at
    ``https://api.semanticscholar.org/api-docs/graph#tag/Paper-Data/operation/
    get_graph_paper_search``.  The API key is optional for low-volume requests,
    but is sent when one has been configured.
    """

    API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    DEFAULT_LIMIT = 10
    MAX_LIMIT = 100
    FIELDS = "title,authors,abstract,url,year,venue,fieldsOfStudy"
    
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        # Could integrate with: Semantic Scholar, arXiv, PubMed, etc.
    
    def search(
        self,
        query: str,
        year_range: tuple[int, int] | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[Paper]:
        """Return up to ``limit`` valid papers matching ``query``.

        Invalid provider records and request/response failures produce no paper
        rather than placeholder data.  ``year_range`` is applied locally as an
        inclusive filter because the API may return records outside its search
        constraints.
        """
        if not isinstance(query, str) or not query.strip():
            return []

        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            return []
        limit = min(limit, self.MAX_LIMIT)

        normalized_year_range = self._normalize_year_range(year_range)
        if year_range is not None and normalized_year_range is None:
            return []

        params = {"query": query.strip(), "limit": limit, "fields": self.FIELDS}
        url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.load(response)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return []

        records = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(records, list):
            return []

        papers = []
        for record in records:
            paper = self._map_record(record)
            if paper is None:
                continue
            if normalized_year_range and not (
                normalized_year_range[0] <= paper.year <= normalized_year_range[1]
            ):
                continue
            papers.append(paper)
            if len(papers) == limit:
                break
        return papers

    @staticmethod
    def _normalize_year_range(year_range: tuple[int, int] | None) -> tuple[int, int] | None:
        """Validate and normalize an inclusive publication-year range."""
        if year_range is None:
            return None
        if (
            not isinstance(year_range, tuple)
            or len(year_range) != 2
            or any(not isinstance(year, int) or isinstance(year, bool) for year in year_range)
        ):
            return None
        start, end = year_range
        return (start, end) if start <= end else None

    @staticmethod
    def _map_record(record: Any) -> Paper | None:
        """Convert a valid Semantic Scholar record to a ``Paper`` instance."""
        if not isinstance(record, dict):
            return None

        title = record.get("title")
        year = record.get("year")
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(year, int)
            or isinstance(year, bool)
        ):
            return None

        authors_data = record.get("authors", [])
        if not isinstance(authors_data, list):
            return None
        authors = [
            author["name"].strip()
            for author in authors_data
            if isinstance(author, dict)
            and isinstance(author.get("name"), str)
            and author["name"].strip()
        ]

        abstract = record.get("abstract")
        url = record.get("url")
        venue = record.get("venue")
        fields = record.get("fieldsOfStudy", [])
        return Paper(
            title=title.strip(),
            authors=authors,
            abstract=abstract.strip() if isinstance(abstract, str) else "",
            url=url.strip() if isinstance(url, str) else "",
            year=year,
            venue=venue.strip() if isinstance(venue, str) else "",
            keywords=[field.strip() for field in fields if isinstance(field, str) and field.strip()]
            if isinstance(fields, list)
            else [],
        )


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


def create_research_agent(llm_client, mongo_uri: str = None) -> ResearchAgent:
    """Factory function to create a configured ResearchAgent."""
    mongo_uri = mongo_uri or os.getenv("MONGODB_ATLAS_URI", "")
    mongo_tool = MongoDBTool(
        atlas_uri=mongo_uri,
        database="research_assistant",
        collection="papers"
    )
    search_tool = PaperSearchTool(api_key=os.getenv("PAPER_SEARCH_API_KEY", ""))
    
    return ResearchAgent(llm_client, mongo_tool, search_tool)
