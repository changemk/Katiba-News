"""Explainable topic hints, not legal conclusions or automatic publication decisions."""
import re
from html import unescape
from html.parser import HTMLParser

# Match meaningful constitutional phrases, not generic terms like "court" or
# "government". The terms can be extended after reviewing missed/irrelevant leads.
TOPICS = {
    'constitution': ('constitution', 'constitutional', 'constitutionalism', 'unconstitutional', 'katiba'),
    'rights': ('human rights', 'bill of rights', 'fundamental rights', 'fundamental freedoms',
               'civil liberties', 'freedom of expression', 'freedom of assembly', 'haki za binadamu'),
    'participation': ('public participation', 'civic education', 'ushiriki wa umma'),
    'devolution': ('devolution', 'devolved governance', 'ugatuzi'),
    'accountability': ('rule of law', 'separation of powers', 'judicial independence',
                       'court orders', 'public accountability', 'leadership and integrity'),
    'information': ('access to information', 'data protection', 'right to privacy'),
    'equality': ('gender equality', 'two-thirds', 'two thirds', 'non-discrimination'),
    'justice': ('access to justice', 'fair trial', 'fair administrative action'),
}


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value):
    """Extract text for matching only; this is not an HTML rendering sanitizer."""
    parser = PlainText()
    parser.feed(value or '')
    return ' '.join(unescape(' '.join(parser.parts)).split())


def topic_matches(**fields):
    """Return explainable topic/term/field hints using word-bounded phrases.

    A match suggests relevance, not verified constitutional significance.
    Different matching fields may produce multiple hints for the same topic.
    """
    matches = []
    for field, value in fields.items():
        text = plain_text(value).casefold().replace('–', '-').replace('‑', '-')
        for topic, terms in TOPICS.items():
            for term in terms:
                if re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text):
                    matches.append({'topic': topic, 'term': term, 'field': field})
    return matches
