import wikipedia

from jarvis.skills.base import BaseSkill, Tool


class WikipediaSearchSkill(BaseSkill):
    name = "wikipedia_search"
    description = "Look up encyclopedic information on Wikipedia"
    tools = [
        Tool(
            name="search",
            description="Search Wikipedia and return a short summary of the best matching article",
            parameters={
                "query": {"type": "string", "description": "Topic to look up"},
                "sentences": {"type": "integer", "description": "Number of sentences (default 3)"},
            },
            required=["query"],
        ),
    ]

    def execute(self, action: str, args: dict) -> str:
        if action == "search":
            return self._search(args["query"], int(args.get("sentences") or 3))
        raise ValueError(f"Unknown action: {action}")

    def _search(self, query: str, sentences: int = 3) -> str:
        try:
            return wikipedia.summary(query, sentences=sentences, auto_suggest=False)
        except wikipedia.exceptions.DisambiguationError as e:
            return f"'{query}' is ambiguous. Options include: {', '.join(e.options[:6])}"
        except wikipedia.exceptions.PageError:
            try:
                return wikipedia.summary(query, sentences=sentences, auto_suggest=True)
            except Exception:
                return f"No Wikipedia page found for '{query}'."
        except Exception as e:
            return f"Wikipedia search failed: {e}"
