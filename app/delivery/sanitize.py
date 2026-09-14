import bleach

# Matches the tag vocabulary composer.py/responder.py are prompted to produce.
# Telegram's Bot API used to strip anything outside its own allowlist client-side;
# rendering directly in a browser via `| safe` has no equivalent net, so LLM output
# (which embeds unescaped external article titles/summaries) must be sanitized here.
_ALLOWED_TAGS = ["b", "i", "u", "s", "code", "pre", "a", "blockquote"]
_ALLOWED_ATTRS = {"a": ["href"]}


def sanitize_html(text: str) -> str:
    return bleach.clean(text, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)
