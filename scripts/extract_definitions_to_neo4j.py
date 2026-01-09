#!/usr/bin/env python3
"""
📖 Extract Definitions to Neo4j
Parses legal documents and extracts definitions into Neo4j graph
"""

import asyncio
import logging
import os
import re
from typing import List, Dict, Any, Optional
from neo4j import AsyncGraphDatabase
import chromadb

from core.logging_config import configure_logging

# Configure logging once for script execution
configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


class DefinitionExtractor:
    """Extracts definitions from legal documents"""

    # Patterns for finding definitions in Russian legal text (РАСШИРЕНО)
    DEFINITION_PATTERNS = [
        # "термин (далее - определение)" - extended to capture longer terms
        r'([а-яА-ЯёЁ\s]{3,100})\s*\(далее\s*[-–—]\s*([а-яА-ЯёЁ\s]{3,100})\)',

        # "термин понимается как..."
        r'([а-яА-ЯёЁ\s]{3,100})\s+понимается\s+(?:как|следующее)',

        # "термин означает..."
        r'([а-яА-ЯёЁ\s]{3,100})\s+означает',

        # "термин - это..."
        r'([а-яА-ЯёЁ\s]{3,100})\s*[-–—]\s*это',

        # «термин» — это ... (кавычки-ёлочки)
        r'«([^»]{2,100})»\s*[-–—]\s*это',

        # "термин" — это ... (двойные кавычки)
        r'"([^"]{2,100})"\s*[-–—]\s*это',

        # "под термином понимается..."
        r'[пП]од\s+([а-яА-ЯёЁ\s]{3,100})\s+понимается',
        
        # NEW: "термин является..."
        r'([а-яА-ЯёЁ\s]{3,100})\s+является',
        
        # NEW: "термин представляет собой..."
        r'([а-яА-ЯёЁ\s]{3,100})\s+представляет\s+собой',
        
        # NEW: "для целей настоящего закона под термином понимается..."
        r'для\s+целей\s+[а-яА-ЯёЁ\s]+закона\s+под\s+([а-яА-ЯёЁ\s]{3,100})\s+понимается',
        
        # NEW: "в настоящем законе используются следующие понятия: термин -"
        r'используются\s+следующие\s+(?:понятия|термины|определения)[:\s]+([а-яА-ЯёЁ\s]{3,100})\s*[-–—]',
        
        # NEW: "термин признается..."
        r'([а-яА-ЯёЁ\s]{3,100})\s+признается',
        
        # NEW: "к термину относится..."
        r'[кК]\s+([а-яА-ЯёЁ\s]{3,100})\s+относится',

        # NEW: мн. ч. "термины понимаются как/следующие"
        r'([а-яА-ЯёЁ\s]{3,100})\s+понимаются\s+(?:как|следующие)',

        # NEW: "термин следует понимать как"
        r'([а-яА-ЯёЁ\s]{3,100})\s+следует\s+понимать\s+как',

        # NEW: "термин считается"
        r'([а-яА-ЯёЁ\s]{3,100})\s+считается',

        # NEW: "термин включает (в себя)"
        r'([а-яА-ЯёЁ\s]{3,100})\s+включает(?:\s+в\s+себя)?',

        # NEW: "в настоящем (Федеральном) законе под термином понимается ..."
        r'в\s+настоящем\s+(?:Федеральном\s+законе|законе)\s+под\s+([а-яА-ЯёЁ\s]{3,100})\s+понимается',

        # NEW: "термин обозначает"
        r'([а-яА-ЯёЁ\s]{3,100})\s+обозначает',
    ]

    def extract_from_text(self, text: str, metadata: Dict) -> List[Dict[str, Any]]:
        """Extract definitions from chunk text"""
        definitions = []

        for pattern in self.DEFINITION_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                # For "X (далее - Y)" pattern, use group(2) as term (the short form)
                # For other patterns, use group(1)
                if len(match.groups()) >= 2:
                    # Pattern: "full term (далее - short term)"
                    term = match.group(2).strip()  # Use the short form
                    full_term = match.group(1).strip()
                else:
                    # Pattern: "term понимается/означает/это..."
                    term = match.group(1).strip()
                    full_term = term

                # Get the full context (300 chars after the term)
                start_pos = match.start()
                end_pos = min(start_pos + 400, len(text))
                context = text[start_pos:end_pos].strip()

                definition = {
                    "term": term.lower(),
                    "term_original": term,
                    "full_term": full_term,
                    "definition_text": context,
                    "law": metadata.get("law", "unknown"),
                    "article": metadata.get("article", ""),
                    "chunk_id": metadata.get("id", ""),
                    "pattern_type": "regex"
                }
                definitions.append(definition)

        return definitions


class Neo4jDefinitionLoader:
    """Loads definitions into Neo4j graph"""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "change_me_in_env")
        self.driver = None

    async def connect(self):
        """Connect to Neo4j"""
        self.driver = AsyncGraphDatabase.driver(
            self.uri, auth=(self.user, self.password)
        )
        logger.info(f"Connected to Neo4j at {self.uri}")

    async def close(self):
        """Close connection"""
        if self.driver:
            await self.driver.close()

    async def create_constraints(self):
        """Create constraints and indexes"""
        async with self.driver.session() as session:
            # Clear existing Definition nodes first
            await session.run("MATCH (d:Definition) DETACH DELETE d")
            logger.info("Cleared existing Definition nodes")

            # Create index on Definition term (not constraint, since regex may create duplicates)
            await session.run(
                "CREATE INDEX definition_term_idx IF NOT EXISTS "
                "FOR (d:Definition) ON (d.term)"
            )
            logger.info("Created Definition index")

    async def add_definition(self, definition: Dict[str, Any]):
        """Add a definition node to Neo4j"""
        async with self.driver.session() as session:
            query = """
            MERGE (d:Definition {term: $term})
            SET d.term_original = $term_original,
                d.full_term = $full_term,
                d.definition_text = $definition_text,
                d.law = $law,
                d.article = $article,
                d.chunk_id = $chunk_id,
                d.pattern_type = $pattern_type

            // Link to Article node if exists
            WITH d
            OPTIONAL MATCH (a:Article {law: $law, article_number: $article})
            FOREACH (_ IN CASE WHEN a IS NOT NULL THEN [1] ELSE [] END |
                MERGE (d)-[:DEFINED_IN]->(a)
            )

            RETURN d.term as term
            """

            result = await session.run(query, **definition)
            record = await result.single()
            if record:
                logger.info(f"Added definition: {record['term']}")

    async def get_definition_count(self) -> int:
        """Get count of Definition nodes"""
        async with self.driver.session() as session:
            result = await session.run("MATCH (d:Definition) RETURN count(d) as count")
            record = await result.single()
            return record["count"] if record else 0


async def main():
    """Main extraction pipeline"""
    logger.info("="*80)
    logger.info("DEFINITION EXTRACTION TO NEO4J")
    logger.info("="*80)

    # 1. Connect to ChromaDB
    logger.info("\n[1/5] Connecting to ChromaDB...")
    chroma_client = chromadb.HttpClient(
        host=os.getenv("CHROMADB_HOST", "localhost"),
        port=int(os.getenv("CHROMADB_PORT", 8000))
    )
    collection = chroma_client.get_collection("documents")
    doc_count = collection.count()
    logger.info(f"ChromaDB collection: {doc_count} documents")

    # 2. Get all documents
    logger.info("\n[2/5] Fetching all documents...")
    all_docs = collection.get(
        include=["documents", "metadatas"]
    )
    logger.info(f"Retrieved {len(all_docs['documents'])} documents")

    # 3. Extract definitions
    logger.info("\n[3/5] Extracting definitions...")
    extractor = DefinitionExtractor()
    all_definitions = []

    for i, (text, metadata) in enumerate(zip(all_docs['documents'], all_docs['metadatas'])):
        definitions = extractor.extract_from_text(text, metadata)
        all_definitions.extend(definitions)

        if (i + 1) % 100 == 0:
            logger.info(f"  Processed {i+1}/{len(all_docs['documents'])} documents...")

    logger.info(f"Extracted {len(all_definitions)} definitions")

    # Show sample definitions
    logger.info("\nSample definitions found:")
    for i, defn in enumerate(all_definitions[:10], 1):
        logger.info(f"  {i}. '{defn['term']}' (from: {defn.get('full_term', defn['term'])})")
        logger.info(f"     Law: {defn['law']}, Article: {defn['article']}")
        logger.info(f"     Text: {defn['definition_text'][:120]}...")

    # 4. Connect to Neo4j
    logger.info("\n[4/5] Connecting to Neo4j...")
    neo4j_loader = Neo4jDefinitionLoader()
    await neo4j_loader.connect()
    await neo4j_loader.create_constraints()

    # 5. Load definitions
    logger.info("\n[5/5] Loading definitions to Neo4j...")
    loaded_count = 0
    for i, defn in enumerate(all_definitions):
        try:
            await neo4j_loader.add_definition(defn)
            loaded_count += 1
        except Exception as e:
            logger.warning(f"Failed to load definition '{defn['term']}': {e}")

        if (i + 1) % 10 == 0:
            logger.info(f"  Loaded {loaded_count}/{len(all_definitions)} definitions...")

    # Final count
    final_count = await neo4j_loader.get_definition_count()
    logger.info(f"\nFinal Neo4j Definition count: {final_count}")

    await neo4j_loader.close()

    logger.info("\n" + "="*80)
    logger.info("EXTRACTION COMPLETE")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
