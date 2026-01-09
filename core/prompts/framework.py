#!/usr/bin/env python3
"""
Universal Prompt Framework - Main Framework Class (Context7 validated).
=========================================================================

Main UniversalPromptFramework class for adaptive prompt generation
with proper type hints and async patterns as per Context7 best practices.

This module contains the core prompt framework for generating anti-hallucination
prompts with strict constraints adapted to query type and source content.

Author: LegalRAG Development Team
License: MIT
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..universal_smart_search import QueryType, SmartSearchResults

from .constraints import AdaptivePromptConfig, PromptConstraints
from .templates import (
    get_anti_hallucination_rules,
    get_prompt_templates,
    get_response_formats,
)
from .types import ConstraintLevel, PromptTemplate, ResponseFormat

logger = logging.getLogger(__name__)


class UniversalPromptFramework:
    """
    Universal Prompt Framework for generating anti-hallucination prompts.

    Creates prompts with strict constraints adapted to query type and source content.
    """

    def __init__(self) -> None:
        """Initialize framework with templates and constraints."""
        self.base_constraints = self._initialize_base_constraints()
        self.prompt_templates = get_prompt_templates()
        self.response_formats = get_response_formats()
        self.anti_hallucination_rules = get_anti_hallucination_rules()
        logger.info("[UniversalPromptFramework] Initialized")

    def _initialize_base_constraints(self) -> Dict[ConstraintLevel, PromptConstraints]:
        """Initialize base constraints by level."""
        return {
            ConstraintLevel.MAXIMUM: PromptConstraints(
                require_source_attribution=True,
                require_exact_quotes=True,
                forbid_extrapolation=True,
                forbid_speculation=True,
                numerical_precision_required=True,
                verify_numerical_context=True,
                forbid_numerical_approximation=True,
                forbidden_phrases=["possibly", "probably", "can be assumed", "most likely", "usually", "as a rule", "in most cases"],
                mandatory_disclaimers=["Answer based exclusively on provided documents", "When information absent in sources stated explicitly"],
                citation_format="strict",
                uncertainty_handling="explicit"
            ),
            ConstraintLevel.HIGH: PromptConstraints(
                require_source_attribution=True,
                forbid_extrapolation=True,
                forbid_speculation=True,
                numerical_precision_required=True,
                verify_numerical_context=True,
                forbidden_phrases=["can be assumed", "most likely", "probably"],
                mandatory_disclaimers=["Information verified against official sources"],
                citation_format="detailed",
                uncertainty_handling="explicit"
            ),
            ConstraintLevel.MEDIUM: PromptConstraints(
                require_source_attribution=True,
                forbid_speculation=True,
                numerical_precision_required=True,
                forbidden_phrases=["can be assumed"],
                citation_format="standard",
                uncertainty_handling="clear"
            ),
            ConstraintLevel.MINIMAL: PromptConstraints(
                require_source_attribution=True,
                citation_format="basic",
                uncertainty_handling="mention"
            )
        }

    def generate_adaptive_prompt(
        self,
        query: str,
        search_results: Any,
        constraint_level: ConstraintLevel = ConstraintLevel.HIGH,
        response_format: Optional[ResponseFormat] = None
    ) -> str:
        """
        Generate adaptive prompt with strict anti-hallucination constraints.

        Args:
            query: User query
            search_results: Search results (SmartSearchResults)
            constraint_level: Constraint strictness level
            response_format: Desired response format

        Returns:
            Generated prompt with constraints
        """
        logger.info(f"[PromptFramework] Generating prompt for: {query[:50]}...")

        try:
            config = self._create_prompt_config(query, search_results, constraint_level, response_format)
            template = self._select_optimal_template(config)
            formatted_sources = self._format_sources_for_prompt(search_results.results)
            constraints_text = self._format_constraints(config.constraints)
            anti_hallucination_text = self._format_anti_hallucination_rules(config)
            format_instructions = self._get_format_instructions(config.response_format)

            final_prompt = self._assemble_final_prompt(
                template=template,
                query=query,
                sources=formatted_sources,
                constraints=constraints_text,
                anti_hallucination=anti_hallucination_text,
                format_instructions=format_instructions,
                config=config
            )

            logger.info("[PromptFramework] Prompt generated successfully")
            return final_prompt

        except Exception as e:
            logger.error(f"[PromptFramework] Error: {e}")
            return self._generate_fallback_prompt(query, search_results)

    def _create_prompt_config(
        self,
        query: str,
        search_results: Any,
        constraint_level: ConstraintLevel,
        response_format: Optional[ResponseFormat]
    ) -> AdaptivePromptConfig:
        """Create configuration for adaptive prompt."""
        from ..universal_smart_search import QueryType

        query_type = search_results.query_analysis.query_type
        template_type = self._map_query_to_template(query_type)

        if response_format is None:
            response_format = self._auto_select_response_format(query_type)

        base_constraints = self.base_constraints[constraint_level]
        adapted_constraints = self._adapt_constraints_to_content(base_constraints, search_results)

        complexity_level = "high" if search_results.query_analysis.complexity_score > 0.8 else "medium" if search_results.query_analysis.complexity_score > 0.5 else "low"
        technical_depth = "expert" if any(len(r.metadata.get('entity_types_present', [])) > 3 for r in search_results.results) else "intermediate"

        entity_types = list(set(t for r in search_results.results for t in r.metadata.get('entity_types_present', [])))
        has_numerical_data = any('numerical_constraints' in r.metadata for r in search_results.results)
        has_procedural_content = any('procedure_steps' in r.metadata for r in search_results.results)

        return AdaptivePromptConfig(
            query_analysis=search_results.query_analysis,
            search_results=search_results,
            template_type=template_type,
            response_format=response_format,
            constraints=adapted_constraints,
            complexity_level=complexity_level,
            technical_depth=technical_depth,
            user_expertise_assumed="intermediate",
            source_count=len(search_results.results),
            entity_types_present=entity_types,
            has_numerical_data=has_numerical_data,
            has_procedural_content=has_procedural_content
        )

    def _map_query_to_template(self, query_type: Any) -> PromptTemplate:
        """Map query type to prompt template."""
        from ..universal_smart_search import QueryType

        mapping = {
            QueryType.NUMERICAL_QUERY: PromptTemplate.NUMERICAL_VERIFICATION,
            QueryType.DEFINITION_QUERY: PromptTemplate.DEFINITION_PRECISE,
            QueryType.PROCEDURE_QUERY: PromptTemplate.PROCEDURE_STEP_BY_STEP,
            QueryType.AUTHORITY_QUERY: PromptTemplate.AUTHORITY_CLEAR,
            QueryType.REFERENCE_QUERY: PromptTemplate.REFERENCE_BASED,
            QueryType.COMPARISON_QUERY: PromptTemplate.GENERAL_CONSTRAINED,
            QueryType.GENERAL_QUERY: PromptTemplate.GENERAL_CONSTRAINED
        }
        return mapping.get(query_type, PromptTemplate.STRICT_FACTUAL)

    def _auto_select_response_format(self, query_type: Any) -> ResponseFormat:
        """Auto-select response format based on query type."""
        from ..universal_smart_search import QueryType

        format_mapping = {
            QueryType.NUMERICAL_QUERY: ResponseFormat.STRUCTURED_SECTIONS,
            QueryType.DEFINITION_QUERY: ResponseFormat.DEFINITION_FORMAT,
            QueryType.PROCEDURE_QUERY: ResponseFormat.NUMBERED_STEPS,
            QueryType.AUTHORITY_QUERY: ResponseFormat.BULLET_POINTS,
            QueryType.COMPARISON_QUERY: ResponseFormat.COMPARISON_TABLE,
            QueryType.GENERAL_QUERY: ResponseFormat.STRUCTURED_SECTIONS
        }
        return format_mapping.get(query_type, ResponseFormat.STRUCTURED_SECTIONS)

    def _adapt_constraints_to_content(
        self,
        base_constraints: PromptConstraints,
        search_results: Any
    ) -> PromptConstraints:
        """Adapt constraints to specific content."""
        from ..universal_smart_search import QueryType

        adapted = PromptConstraints(
            require_source_attribution=base_constraints.require_source_attribution,
            require_exact_quotes=base_constraints.require_exact_quotes,
            forbid_extrapolation=base_constraints.forbid_extrapolation,
            forbid_speculation=base_constraints.forbid_speculation,
            numerical_precision_required=base_constraints.numerical_precision_required,
            verify_numerical_context=base_constraints.verify_numerical_context,
            forbid_numerical_approximation=base_constraints.forbid_numerical_approximation,
            forbidden_phrases=base_constraints.forbidden_phrases.copy(),
            mandatory_disclaimers=base_constraints.mandatory_disclaimers.copy(),
            citation_format=base_constraints.citation_format,
            uncertainty_handling=base_constraints.uncertainty_handling
        )

        if search_results.query_analysis.query_type == QueryType.NUMERICAL_QUERY:
            adapted.numerical_precision_required = True
            adapted.verify_numerical_context = True
            adapted.forbid_numerical_approximation = True
            adapted.mandatory_disclaimers.append("All numerical values taken from official sources without modification")

        if search_results.query_analysis.query_type == QueryType.DEFINITION_QUERY:
            adapted.require_exact_quotes = True
            adapted.forbidden_phrases.extend(["in other words", "that is", "one could say"])

        if search_results.query_analysis.query_type == QueryType.PROCEDURE_QUERY:
            adapted.mandatory_disclaimers.append("Only action sequence explicitly stated in sources described")

        low_quality_results = [r for r in search_results.results if r.final_score < 0.7]
        if len(low_quality_results) > len(search_results.results) // 2:
            adapted.mandatory_disclaimers.append("Warning: relevance of some sources may be limited")

        return adapted

    def _select_optimal_template(self, config: AdaptivePromptConfig) -> str:
        """Select optimal prompt template."""
        base_template = self.prompt_templates[config.template_type]

        if config.has_numerical_data or config.template_type == PromptTemplate.NUMERICAL_VERIFICATION:
            if config.constraints.numerical_precision_required:
                base_template += "\n\nADDITIONAL REQUIREMENTS FOR NUMERICAL DATA:\nEACH numerical value requires: exact figure, unit, constraint context, article reference, constraint subject\nWhen exact data absent write: 'Exact numerical constraints NOT FOUND in sources'"

        return base_template

    def _format_sources_for_prompt(self, search_results: List[Any]) -> str:
        """Format sources for prompt inclusion."""
        if not search_results:
            return "SOURCES NOT PROVIDED"

        formatted_sources = []
        for i, result in enumerate(search_results, 1):
            doc_title = result.metadata.get('document_title', 'Unknown document')
            article = result.metadata.get('article_number', '')
            source_header = f"SOURCE {i}: {doc_title}" + (f", article {article}" if article else "")
            source_info = [source_header, "-" * len(source_header), f"CONTENT: {result.content.strip()}", f"RELEVANCE: {result.final_score:.2f}"]
            formatted_sources.append("\n".join(source_info))

        return "\n\n".join(formatted_sources)

    def _format_constraints(self, constraints: PromptConstraints) -> str:
        """Format constraints for prompt."""
        lines = ["STRICT CONSTRAINTS:"]
        if constraints.require_source_attribution:
            lines.append("[REQUIRED] EACH statement must have source reference")
        if constraints.require_exact_quotes:
            lines.append("[REQUIRED] Definitions and key wordings must be quoted exactly")
        if constraints.forbid_extrapolation:
            lines.append("[FORBIDDEN] Speculate information absent in sources")
        if constraints.forbid_speculation:
            lines.append("[FORBIDDEN] Use assumptions and guesses")
        if constraints.numerical_precision_required:
            lines.append("[REQUIRED] Numerical data must be exact, without rounding")
        if constraints.forbidden_phrases:
            lines.append(f'[FORBIDDEN] Phrases: "{", ".join(constraints.forbidden_phrases)}"')
        if constraints.mandatory_disclaimers:
            lines.append("[REQUIRED] Disclaimers:")
            lines.extend(f"  * {d}" for d in constraints.mandatory_disclaimers)
        return "\n".join(lines)

    def _format_anti_hallucination_rules(self, config: AdaptivePromptConfig) -> str:
        """Format anti-hallucination rules."""
        from ..universal_smart_search import QueryType

        rules_text = "ERROR PREVENTION RULES:\n"
        for i, rule in enumerate(self.anti_hallucination_rules, 1):
            rules_text += f"{i}. {rule}\n"

        if config.query_analysis.query_type == QueryType.NUMERICAL_QUERY:
            rules_text += f"{len(self.anti_hallucination_rules) + 1}. When specifying numerical constraints must specify constraint subject\n"
            rules_text += f"{len(self.anti_hallucination_rules) + 2}. Do not combine numerical data from different articles\n"
        elif config.query_analysis.query_type == QueryType.DEFINITION_QUERY:
            rules_text += f"{len(self.anti_hallucination_rules) + 1}. Give definitions in quotes with exact reference\n"
            rules_text += f"{len(self.anti_hallucination_rules) + 2}. Do not paraphrase definitions in own words\n"

        return rules_text

    def _get_format_instructions(self, response_format: ResponseFormat) -> str:
        """Get format instructions."""
        format_template = self.response_formats.get(response_format, "")
        instructions = "RESPONSE FORMAT REQUIREMENTS:\n" + format_template
        instructions += "\n\nGENERAL FORMATTING REQUIREMENTS:\n"
        instructions += "* Each statement must have source reference\n"
        instructions += "* When information absent - explicitly state this\n"
        instructions += "* Use clear structure according to template\n"
        instructions += "* Avoid unnecessary words and repetitions\n"
        return instructions

    def _assemble_final_prompt(
        self,
        template: str,
        query: str,
        sources: str,
        constraints: str,
        anti_hallucination: str,
        format_instructions: str,
        config: AdaptivePromptConfig
    ) -> str:
        """Assemble final prompt."""
        filled_template = template.format(query=query, sources=sources)
        final_prompt = filled_template + "\n\n" + constraints + "\n\n" + anti_hallucination + "\n\n" + format_instructions + "\n\n"
        final_prompt += "FINAL CHECK BEFORE ANSWERING:\n"
        final_prompt += "1. Each statement has source reference? [REQUIRED]\n"
        final_prompt += "2. No speculation of absent information? [REQUIRED]\n"
        final_prompt += "3. Numerical data exact with references? [REQUIRED]\n"
        final_prompt += "4. Correct response format used? [REQUIRED]\n"
        final_prompt += "5. Necessary disclaimers added? [REQUIRED]\n\n"
        final_prompt += "BEGIN ANSWER:"
        return final_prompt

    def _generate_fallback_prompt(self, query: str, search_results: Any) -> str:
        """Generate fallback prompt in case of error."""
        sources = self._format_sources_for_prompt(search_results.results)
        return f"You are a legal consultant. Answer based on provided sources.\n\nSTRICT REQUIREMENTS:\n- Use ONLY information from sources\n- Each statement must have reference\n- When information absent write: 'Not found in sources'\n- Forbidden to speculate or assume\n\nQUESTION: {query}\n\nSOURCES: {sources}\n\nANSWER:"

    def generate_verification_prompt(
        self,
        original_response: str,
        sources: List[Dict[str, Any]],
        verification_issues: List[str]
    ) -> str:
        """Generate prompt for response correction based on verification results."""
        formatted_sources = self._format_sources_for_prompt(sources)
        issues_text = "\n".join([f"* {issue}" for issue in verification_issues])
        return f"TASK: Correct answer based on verification results\n\nORIGINAL ANSWER:\n{original_response}\n\nISSUES FOUND:\n{issues_text}\n\nSOURCES FOR VERIFICATION:\n{formatted_sources}\n\nREQUIREMENTS FOR CORRECTED ANSWER:\n[REQUIRED] Fix ALL found issues\n[REQUIRED] Each statement must have verifiable source reference\n[REQUIRED] When information absent in sources - explicitly state\n[REQUIRED] Numerical data must exactly match sources\n[REQUIRED] Do not add information absent in sources\n\nCORRECTED ANSWER:"


_universal_prompt_framework: Optional[UniversalPromptFramework] = None

def get_universal_prompt_framework() -> UniversalPromptFramework:
    """Get global UniversalPromptFramework instance."""
    global _universal_prompt_framework
    if _universal_prompt_framework is None:
        _universal_prompt_framework = UniversalPromptFramework()
    return _universal_prompt_framework


__all__ = ["UniversalPromptFramework", "get_universal_prompt_framework"]
