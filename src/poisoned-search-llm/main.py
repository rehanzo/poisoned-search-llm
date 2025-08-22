import argparse
import constants


async def main():
    parser = argparse.ArgumentParser(
        description="Interact with an LLM that is fed poisoned results. Model IDs are litellm IDs."
    )
    parser.add_argument(
        "--facts", required=True, help="Stated facts to poison results with"
    )
    parser.add_argument(
        "--poison_model", required=True, help="Model to poison results with"
    )
    parser.add_argument(
        "--assistant_model", required=True, help="Model to respond with"
    )

    args = parser.parse_args()

    constants.WORLD_FACTS = args.facts
    constants.POISON_MODEL = args.poison_model
    constants.ASSISTANT_MODEL = args.assistant_model

    # this is a bit of a hack but f it
    from llm import WebSearchAgent

    web_assistant = WebSearchAgent()
    await web_assistant.run()


import asyncio

asyncio.run(main())
