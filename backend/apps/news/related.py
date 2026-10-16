"""Conservative related-coverage suggestions; editors must confirm every grouping."""
import re
from .models import Lead

STOP_WORDS = set('the a an of in on and or to for by with from at v vs court high kenya declares says calls'.split())
CITATION = re.compile(r'\[\s*(\d{4})\s*\]\s*(KE[A-Z-]+)\s*(\d+)', re.I)


def suggested_coverage(lead):
    citations = set(CITATION.findall(lead.title.upper()))
    tokens = set(re.findall(r'\b\w{4,}\b', lead.title.casefold())) - STOP_WORDS
    suggestions = []
    # Bound work for a review screen. This is discovery, not an exhaustive case index.
    for other in Lead.objects.select_related('source').exclude(source=lead.source).order_by('-discovered_at')[:500]:
        if lead.story_group_id and lead.story_group_id == other.story_group_id:
            continue
        shared_citation = citations & set(CITATION.findall(other.title.upper()))
        other_tokens = set(re.findall(r'\b\w{4,}\b', other.title.casefold())) - STOP_WORDS
        shared = tokens & other_tokens
        score = len(shared) / max(1, len(tokens | other_tokens))
        if shared_citation or (len(shared) >= 3 and score >= 0.45):
            suggestions.append({'lead': other, 'reason': 'Same case citation' if shared_citation
                                else 'Shared title terms: ' + ', '.join(sorted(shared)),
                                'score': 1 if shared_citation else score})
    return sorted(suggestions, key=lambda item: (-item['score'], -item['lead'].pk))[:10]
