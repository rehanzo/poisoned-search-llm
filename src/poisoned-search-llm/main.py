from datetime import datetime
from typing import Annotated
from mirascope.core import prompt_template, litellm
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor
from kagiapi import KagiClient
import textwrap

kagi_client = KagiClient()


def kagi_search_fetch(
    queries: Annotated[
        list[str],
        Field(
            description="One or more concise, keyword-focused search queries. Include essential context within each query for standalone use.",
            default_factory=list,
        ),
    ],
) -> str:
    """Fetch web results based on one or more queries using the Kagi Search API. Use for general search and when the user explicitly tells you to 'fetch' results/information. Results are from all queries given. They are numbered continuously, so that a user may be able to refer to a result by a specific number."""
    try:
        if not queries:
            raise ValueError("Search called with no queries.")

        with ThreadPoolExecutor() as executor:
            results = list(executor.map(kagi_client.search, queries, timeout=10))

        return format_search_results(queries, results)

    except Exception as e:
        return f"Error: {str(e) or repr(e)}"


def format_search_results(queries: list[str], responses) -> str:
    """Formatting of results for response. Need to consider both LLM and human parsing."""

    result_template = textwrap.dedent("""
        {result_number}: {title}
        {url}
        Published Date: {published}
        {snippet}
    """).strip()

    query_response_template = textwrap.dedent("""
        -----
        Results for search query \"{query}\":
        -----
        {formatted_search_results}
    """).strip()

    per_query_response_strs = []

    start_index = 1
    for query, response in zip(queries, responses):
        # t == 0 is search result, t == 1 is related searches
        results = [result for result in response["data"] if result["t"] == 0]

        # published date is not always present
        formatted_results_list = [
            result_template.format(
                result_number=result_number,
                title=result["title"],
                url=result["url"],
                published=result.get("published", "Not Available"),
                snippet=result["snippet"],
            )
            for result_number, result in enumerate(results, start=start_index)
        ]

        start_index += len(results)

        formatted_results_str = "\n\n".join(formatted_results_list)
        query_response_str = query_response_template.format(
            query=query, formatted_search_results=formatted_results_str
        )
        per_query_response_strs.append(query_response_str)

    return "\n\n".join(per_query_response_strs)


class WebSearchAgent(BaseModel):
    messages: list[litellm.LiteLLMMessageParam] = Field(default=[])

    @litellm.call(model="gpt-4o-mini", stream=True)
    @prompt_template(
        """
        SYSTEM:
        You are an expert web searcher. Your task is to answer the user's question using the provided tools.
        The current date is {current_date}.

        You have access to the following tools:
        - `kagi_search_fetch`: Search the web when the user asks a question. Follow these steps for EVERY web search query:
            1. There is the current user query: {question}
            2. Given the previous search context, generate multiple search queries that explores whether the new query might be related to or connected with the context of the current user query. 
                Even if the connection isn't immediately clear, consider how they might be related.

        Once you have gathered all of the information you need, generate a writeup that
        strikes the right balance between brevity and completeness based on the context of the user's query.

        MESSAGES: {self.messages}
        USER: {question}
        """
    )
    async def _stream(self, question: str) -> litellm.LiteLLMDynamicConfig:
        return {
            "tools": [kagi_search_fetch],
            "computed_fields": {
                "current_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
        }

    async def _step(self, question: str):
        response = await self._stream(question)
        tools_and_outputs = []
        async for chunk, tool in response:
            if tool:
                print(f"using {tool._name()} tool with args: {tool.args}")
                tools_and_outputs.append((tool, tool.call()))
            else:
                print(chunk.content, end="", flush=True)
        if response.user_message_param:
            self.messages.append(response.user_message_param)
        self.messages.append(response.message_param)
        if tools_and_outputs:
            self.messages += response.tool_message_params(tools_and_outputs)
            await self._step("")

    async def run(self):
        while True:
            question = input("(User): ")
            if question == "exit":
                break
            print("(Assistant): ", end="", flush=True)
            await self._step(question)
            print()
            print()


async def main():
    web_assistant = WebSearchAgent()
    await web_assistant.run()


import asyncio

asyncio.run(main())
