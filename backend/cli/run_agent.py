"""
Diavgeia-Watch: Interactive Query Agent (CLI)

Start the text-to-SQL agent and ask questions about Greek government spending.

Usage:
    # With Ollama (default)
    python -m backend.run_agent

    # With a specific model
    python -m backend.run_agent --model mistral

    # With Groq cloud
    python -m backend.run_agent --backend groq --api-key gsk_...

    # Single question (non-interactive)
    python -m backend.run_agent --question "How much did Athens spend in 2024?"
"""

import argparse
import logging
import sys

from backend.db.manager import DatabaseManager
from backend.agent.llm_client import LLMClient
from backend.agent.sql_agent import SQLAgent
from backend.agent.cpv_lookup import CPVLookup
from backend.agent.org_resolver import OrgResolver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_agent")


def main():
    parser = argparse.ArgumentParser(
        description="Diavgeia-Watch: Interactive spending query agent"
    )
    parser.add_argument(
        "--backend", default="ollama",
        choices=["ollama", "groq", "openai"],
        help="LLM backend (default: ollama)"
    )
    parser.add_argument(
        "--model", default=None,
        help="Model name (default: llama3.1:8b for Ollama, llama-3.1-8b-instant for Groq)"
    )
    parser.add_argument(
        "--api-key", default=None,
        help="API key (required for Groq/OpenAI)"
    )
    parser.add_argument(
        "--base-url", default=None,
        help="Custom API base URL"
    )
    parser.add_argument(
        "--db-host", default="localhost",
        help="PostgreSQL host (default: localhost)"
    )
    parser.add_argument(
        "--db-port", type=int, default=5432,
        help="PostgreSQL port (default: 5432)"
    )
    parser.add_argument(
        "--question", "-q", default=None,
        help="Ask a single question (non-interactive mode)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed debug output"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # --- Initialize LLM ---
    print(f"🤖 Connecting to LLM ({args.backend})...")
    llm = LLMClient(
        backend=args.backend,
        model=args.model,
        base_url=args.base_url,
        api_key=args.api_key,
    )

    if not llm.is_available():
        print(f"\n❌ Cannot connect to {args.backend} at {llm.base_url}")
        if args.backend == "ollama":
            print("   Make sure Ollama is running: ollama serve")
            print(f"   And the model is pulled: ollama pull {llm.model}")
        else:
            print("   Check your API key and base URL.")
        sys.exit(1)

    # Show available models for Ollama
    if args.backend == "ollama":
        models = llm.list_models()
        if models:
            print(f"   Available models: {', '.join(models)}")
            if llm.model not in models:
                print(f"\n⚠️  Model '{llm.model}' not found locally.")
                print(f"   Pull it with: ollama pull {llm.model}")
                sys.exit(1)

    print(f"   Using model: {llm.model}")

    # --- Initialize Database ---
    print(f"🗄️  Connecting to PostgreSQL ({args.db_host}:{args.db_port})...")
    db_config = {
        "host": args.db_host,
        "port": args.db_port,
        "dbname": "diavgeia",
        "user": "diavgeia",
        "password": "diavgeia_dev_2024",
    }
    db = DatabaseManager(config=db_config)
    try:
        db.connect()
        stats = db.get_stats()
        print(f"   Decisions in DB: {stats['total_decisions']}")
        print(f"   Expense items:   {stats['total_expense_items']}")
        if stats['total_decisions'] == 0:
            print("\n⚠️  Database is empty! Run the ETL pipeline first:")
            print("   python -m backend.etl_pipeline --from 2024-01-01 --to 2024-01-31")
    except Exception as e:
        print(f"\n❌ Cannot connect to database: {e}")
        print("   Make sure PostgreSQL is running: docker compose up -d")
        sys.exit(1)

    # --- Initialize Agent ---
    agent = SQLAgent(
        llm=llm,
        db=db,
        cpv_lookup=CPVLookup(),
        org_resolver=OrgResolver(db_manager=db),
    )

    # --- Run ---
    if args.question:
        # Single question mode
        result = agent.ask(args.question)
        print(f"\n💭 {result.thinking}")
        if result.sql:
            print(f"\n📝 SQL:\n{result.sql}")
        print(f"\n📊 Answer:\n{result.answer}")
        if result.error:
            print(f"\n⚠️ {result.error}")
    else:
        # Interactive REPL
        agent.repl()

    db.close()


if __name__ == "__main__":
    main()