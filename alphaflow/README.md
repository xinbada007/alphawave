# AlphaFlow Framework

**AlphaFlow** is a modular, async-first financial research framework designed for Vibe Coding (LLM-assisted development).
It leverages **OpenBB Platform v4** for data and **QuickChart** for visualization, running perfectly inside E2B Sandboxes.

## 🚀 Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Pipeline**
   ```bash
   python main.py --symbols AAPL MSFT --tasks fetch,technicals,chart
   ```

## 📂 Structure

- `core/`: The "Kernel". Base classes and Pydantic schemas.
- `components/`: Where the magic happens.
  - `collectors/`: Data fetchers (OpenBB).
  - `processors/`: Quant logic (Pandas/AI).
  - `visualizers/`: Chart generators.
- `engine/`: The async runner.

## 🤖 For Vibe Coding (Team)

To add a new strategy or indicator:
1. Copy the content of `PROMPT.md`.
2. Paste it to your LLM (ChatGPT/Claude).
3. Ask: "Write a Processor that calculates Bollinger Bands using AlphaFlow."
4. Save the code to `components/processors/bbands.py`.
5. Import and use it in `main.py`.

## 🛡️ Data Contract

We use **Strict Typing** to ensure collaboration works.
Always use `DataFrameModel.from_df(df)` before returning data from a component.
