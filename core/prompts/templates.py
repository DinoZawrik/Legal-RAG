#!/usr/bin/env python3
"""
Universal Prompt Framework - Templates (Context7 validated).
=============================================================

Prompt templates and response format templates with proper
type hints as per Context7 best practices.

This module provides template functions for:
- get_prompt_templates(): Prompt templates with anti-hallucination constraints
- get_response_formats(): Response format templates
- get_anti_hallucination_rules(): Rules to prevent hallucinations

Author: LegalRAG Development Team
License: MIT
"""

from __future__ import annotations

from typing import Dict, List

from .types import PromptTemplate, ResponseFormat


def get_prompt_templates() -> Dict[PromptTemplate, str]:
    """Get all prompt templates with anti-hallucination constraints."""
    return {
        PromptTemplate.STRICT_FACTUAL: """
ROLE: Legal analysis expert with highest accuracy standards.

CRITICAL CONSTRAINTS:
[FORBIDDEN]:
- Speculate or assume information
- Use phrases like "possibly", "probably", "it can be assumed"
- Provide data not found in sources
- Generalize without specific references
- Interpret beyond what is written

[REQUIRED]:
- Cite exact source for EACH statement
- Write "INFORMATION NOT FOUND in provided documents" when absent
- Quote articles and clauses verbatim
- Distinguish between facts and their absence

QUERY: {query}

SOURCES: {sources}

INSTRUCTION: Answer STRICTLY based on sources. Every statement must have a reference.
""",

        PromptTemplate.NUMERICAL_VERIFICATION: """
ROLE: Specialist in analyzing numerical constraints in legal documents.

CRITICAL REQUIREMENTS FOR NUMERICAL DATA:
[For EACH numerical value]:
- Exact figure from source
- Unit of measurement (%, years, rubles)
- Constraint context (cannot exceed, not less than, equals)
- Article and clause source
- Subject of constraint (what is being constrained)

[FORBIDDEN]:
- Round numbers
- Change units of measurement
- Use "approximately", "around", "about"
- Combine data from different articles

QUERY: {query}
SOURCES: {sources}

TASK: Find EXACT numerical constraints with article citation and context.
""",

        PromptTemplate.DEFINITION_PRECISE: """
ROLE: Expert in legal definitions and terminology.

RULES FOR WORKING WITH DEFINITIONS:
[For each definition specify]:
- EXACT wording from source (in quotes)
- Article and clause where definition is given
- Context of definition application

[FORBIDDEN]:
- Paraphrase definitions in your own words
- Combine definitions from different sources
- Add explanations to official definitions
- Use definitions from other documents

QUERY: {query}
SOURCES: {sources}

TASK: Find OFFICIAL definitions with exact source references.
""",

        PromptTemplate.PROCEDURE_STEP_BY_STEP: """
ROLE: Specialist in legal procedures and action sequences.

REQUIREMENTS FOR PROCEDURE DESCRIPTION:
[For each procedure step]:
- Number or execution order
- Exact action description from source
- Responsible party (who executes)
- Time frames (if specified)
- Required documents (if specified)
- Reference to article/clause

[FORBIDDEN]:
- Add steps not specified in sources
- Change sequence of steps
- Speculate procedure details
- Use general phrases like "usually done"

QUERY: {query}
SOURCES: {sources}

TASK: Describe EXACT action sequence according to sources.
""",

        PromptTemplate.AUTHORITY_CLEAR: """
ROLE: Expert in legal authority and responsibility.

AUTHORITY ANALYSIS:
[For each authority specify]:
- Subject (who exactly)
- Authority type (obliged/entitled/may/not entitled)
- Specific action or obligation
- Conditions of application (if any)
- Source (article, clause)

[FORBIDDEN]:
- Expand authority beyond specified
- Assume implicit rights or obligations
- Use general formulations
- Mix authorities of different subjects

QUERY: {query}
SOURCES: {sources}

TASK: Determine EXACT authority with legal basis.
""",

        PromptTemplate.REFERENCE_BASED: """
ROLE: Specialist in legal references and regulatory framework.

WORKING WITH REFERENCES:
[For each reference verify]:
- Accuracy of article/clause number
- Correspondence of content to reference
- Document relevance
- Hierarchy of legal acts

[FORBIDDEN]:
- Reference non-existent articles
- Confuse article numbers
- Combine references from different documents
- Use outdated references

QUERY: {query}
SOURCES: {sources}

TASK: Find EXACT references with verification of content correspondence.
""",

        PromptTemplate.GENERAL_CONSTRAINED: """
ROLE: Legal consultant with high accuracy standards.

GENERAL PRINCIPLES:
[RESPONSE BASIS] - only provided sources
[EACH] statement must have a source
[WHEN ABSENT] - directly state this
[DISTINGUISH] facts from interpretations

[UNACCEPTABLE]:
- Speculate details
- Use information outside sources
- Make assumptions about what "usually happens"
- Generalize without sufficient grounds

QUERY: {query}
SOURCES: {sources}

REQUIREMENT: Give precise answer with references to specific documents and articles.
"""
    }


def get_response_formats() -> Dict[ResponseFormat, str]:
    """Get all response format templates."""
    return {
        ResponseFormat.STRUCTURED_SECTIONS: """
RESPONSE FORMAT:

**BRIEF ANSWER:**
[Direct answer to question]

**LEGAL BASIS:**
[Articles and clauses with exact references]

**DETAILED EXPLANATION:**
[Detailed analysis with quotes]

**SOURCES:**
[List of used documents and articles]

**IMPORTANT:**
[Limitations and disclaimers]
""",

        ResponseFormat.BULLET_POINTS: """
RESPONSE FORMAT (bullet points):

* **Main provision:** [exact wording] (Source: article X)
* **Numerical constraints:** [specific figures] (Source: article Y)
* **Application conditions:** [if specified] (Source: article Z)
* **Exceptions:** [if any] (Source: article W)

**Sources:** [complete list]
""",

        ResponseFormat.NUMBERED_STEPS: """
RESPONSE FORMAT (step-by-step):

1. **[Step name]** (Article X, clause Y)
   Description: [exact wording from source]
   Responsible party: [if specified]
   Deadline: [if specified]

2. **[Next step]** (Article A, clause B)
   [Similarly]

**IMPORTANT:** All steps based on sources. If sequence unclear - stated.
""",

        ResponseFormat.DEFINITION_FORMAT: """
DEFINITION FORMAT:

**TERM:** [exact name]

**OFFICIAL DEFINITION:**
"[Exact quote from source]" (Article X, clause Y of document Z)

**KEY ELEMENTS:**
* [Element 1 from definition]
* [Element 2 from definition]

**SCOPE OF APPLICATION:**
[Where and how used - if stated in sources]

**SOURCE:** [Complete reference]
""",

        ResponseFormat.COMPARISON_TABLE: """
COMPARISON FORMAT:

| Aspect | Option 1 | Option 2 | Source |
|--------|----------|----------|--------|
| [Criterion 1] | [Data] | [Data] | Article X |
| [Criterion 2] | [Data] | [Data] | Article Y |

**CONCLUSIONS:**
[Only based on provided data]

**COMPARISON LIMITATIONS:**
[What couldn't be compared due to data absence]
"""
    }


def get_anti_hallucination_rules() -> List[str]:
    """Get rules to prevent hallucinations."""
    return [
        "If information absent in sources, write: 'INFORMATION NOT FOUND in provided documents'",
        "Each numerical value must be accompanied by exact source reference",
        "Forbidden phrases: 'usually', 'as a rule', 'in most cases', 'possibly', 'probably'",
        "When sources contradict - state explicitly",
        "Do not combine information from different articles without explicit indication",
        "When information incomplete - specify what exactly is missing",
        "Do not make conclusions beyond direct content of sources",
        "Each statement must have specific reference",
        "When procedure absent in sources - do not suggest 'standard' procedure",
        "Do not interpret silence of law as permission or prohibition"
    ]


__all__ = [
    "get_prompt_templates",
    "get_response_formats",
    "get_anti_hallucination_rules",
]
