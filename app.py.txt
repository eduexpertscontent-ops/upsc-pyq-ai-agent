import os
import pandas as pd
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from rank_bm25 import BM25Okapi
from openai import OpenAI

# ---------------- CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CSV_PATH = "pyq.csv"

client = OpenAI(api_key=OPENAI_API_KEY)

# ---------------- LOAD DATA ----------------
df = pd.read_csv(CSV_PATH)

documents = (df["question_text"].fillna("") + " " + df["subject"].fillna("")).tolist()
tokenized_docs = [doc.lower().split() for doc in documents]
bm25 = BM25Okapi(tokenized_docs)

def search_pyqs(query, k=3):
    tokens = query.lower().split()
    scores = bm25.get_scores(tokens)
    top_ids = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return df.iloc[top_ids]

def format_pyq(row):
    return f"""
📘 *UPSC PYQ ({int(row['year'])} – {row['subject']})*

❓ {row['question_text']}

A. {row['option_a']}
B. {row['option_b']}
C. {row['option_c']}
D. {row['option_d']}

✅ *Correct Answer:* {row['answer']}
""".strip()

def generate_explanation(row):
    prompt = f"""
Explain this UPSC Prelims question using:
1. Elimination logic
2. Brief static background

Question:
{row['question_text']}

Options:
A. {row['option_a']}
B. {row['option_b']}
C. {row['option_c']}
D. {row['option_d']}

Correct Answer: {row['answer']}
"""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return resp.choices[0].message.content

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 UPSC PYQ AI Agent Ready!\n\nUse:\n/pyq <keyword>\nExample:\n/pyq fundamental rights"
    )

async def pyq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("❌ Please provide a keyword.")
        return

    results = search_pyqs(query)
    for _, row in results.iterrows():
        await update.message.reply_markdown(format_pyq(row))
        explanation = generate_explanation(row)
        await update.message.reply_text("🧠 Explanation:\n" + explanation)

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN env var")
    if not OPENAI_API_KEY:
        raise ValueError("Missing OPENAI_API_KEY env var")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pyq", pyq))
    app.run_polling()

if __name__ == "__main__":
    main()
