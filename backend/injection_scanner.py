"""Deterministic screening: any rule match requires review, not proof of an attack.

NFKC/format-character normalization catches basic obfuscation. Bounded patterns
avoid matching ordinary imperative instructions. Academic quotations may still
match, and semantic/encoded attacks may be missed. Rules were chosen over an LLM classifier for reproducibility, explainability
and no provider cost. No model or network calls.
"""

import re
import unicodedata
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Finding:
    rule_id: str
    message: str
    severity: str
    line: int
    excerpt: str


_RULES = [
    ('instruction_override', 'Possible override of assistant instructions', 'high',
     r'\b(?:ignore|disregard|forget|override)\s+(?:(?:all|any|the|your|my|our|previous|prior|above|earlier|system|developer)\s+){0,6}(?:instructions?|rules?|prompts?|policies)\b'),
    ('role_impersonation', 'Possible system/developer role impersonation', 'high',
     r'^\s*(?:#{1,6}\s*)?(?:system|developer|assistant)\s*(?:message\s*)?:|\byou\s+are\s+now\s+(?:the\s+)?(?:system|developer)\b'),
    ('secret_extraction', 'Possible request for secrets or private instructions', 'high',
     r'\b(?:reveal|print|show|dump|expose|return|provide|extract)\b[\s\S]{0,100}?\b(?:api[\s_-]*keys?|secrets?|passwords?|private\s+(?:data|information)|(?:hidden\s+)?system\s+prompt|environment\s+variables?)\b'),
    ('external_exfiltration', 'Possible instruction to transmit document data', 'high',
     r'\b(?:send|upload|post|transmit|forward|exfiltrate)\b(?=[\s\S]{0,240}\b(?:data|contents?|documents?|secrets?|tokens?|keys?|conversation|prompts?)\b)(?=[\s\S]{0,240}https?://)[\s\S]{0,240}'),
    ('assistant_redirect', 'Possible instruction aimed at an AI assistant', 'medium',
     r'\b(?:AI\s+assistant|language\s+model|chatgpt|LLM)\b[\s\S]{0,100}?\b(?:must|should|shall|ignore|instead|always|never)\b|\b(?:when|if)\s+you\s+(?:answer|respond|generate)\b[\s\S]{0,100}?\b(?:always|instead|ignore|include|say|output|omit|refuse)\b'),
    ('context_escape', 'Possible prompt delimiter or document-context escape', 'high',
     r'\[/?INST\]|<\|(?:im_start|im_end|system|start_header_id|end_header_id)\|>|</(?:document|context|retrieved[_-]text)\s*>'),
    ('policy_reset', 'Possible replacement of system/developer instructions', 'high',
     r'\b(?:new|updated|highest[- ]priority)\s+(?:system|developer)\s+(?:instructions?|prompt)\b'),
]
RULES = [(rule_id, message, severity, re.compile(pattern, re.I | re.M))
         for rule_id, message, severity, pattern in _RULES]
MAX_FINDINGS = 100


def _excerpt(text):
    # Review text is bounded and never included in traces. Mask common secrets/PII.
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[EMAIL]', text)
    text = re.sub(r'https?://\S+', '[URL]', text)
    text = re.sub(r'(?i)\b((?:api[ _-]?key|password|secret|token)\s*[:=]\s*)\S+', r'\1[REDACTED]', text)
    text = ''.join(c if c.isprintable() else ' ' for c in text)
    return text[:160]


def scan_document(content: str) -> list[dict]:
    if not isinstance(content, str):
        raise ValueError('Document content must be text')
    text = unicodedata.normalize('NFKC', content.replace('\r\n', '\n').replace('\r', '\n'))
    text = ''.join(c for c in text if unicodedata.category(c) != 'Cf')
    findings = []
    seen = set()
    for rule_id, message, severity, pattern in RULES:
        for match in pattern.finditer(text):
            line = text.count('\n', 0, match.start()) + 1
            key = (rule_id, line)
            if key in seen:
                continue
            seen.add(key)
            findings.append(asdict(Finding(rule_id, message, severity, line, _excerpt(match.group()))))
            if len(findings) >= MAX_FINDINGS:
                break
        if len(findings) >= MAX_FINDINGS:
            break
    return sorted(findings, key=lambda f: (f['line'], f['rule_id']))
