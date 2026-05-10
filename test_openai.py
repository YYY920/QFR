import os

from dotenv import load_dotenv
from openai import OpenAI


def main() -> None:
    load_dotenv()

    api_key_qfr = os.getenv("OPENAI_API_KEY_QFR", "").strip()
    api_key = api_key_qfr or os.getenv("OPENAI_API_KEY", "").strip()
    source = "OPENAI_API_KEY_QFR" if api_key_qfr else "OPENAI_API_KEY"

    if not api_key:
        raise SystemExit("OPENAI_API_KEY_QFR or OPENAI_API_KEY is not set.")

    print(f"Using {source} (length: {len(api_key)})")

    client = OpenAI(api_key=api_key)

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say hello in one short sentence."}],
        )
        print("✅ OpenAI response OK:")
        print(resp.choices[0].message.content)
    except Exception as exc:  # noqa: BLE001
        print("❌ OpenAI test FAILED with exception:")
        print(repr(exc))


if __name__ == "__main__":
    main()
