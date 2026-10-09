"""Gradio chat UI with citations shown. See SPEC.md section 2, 12 (P5)."""
from __future__ import annotations

import uuid

import gradio as gr

from app.pipeline import answer


def _respond(message: str, history: list, session_id: str):
    if not session_id:
        session_id = uuid.uuid4().hex
    result = answer(message, session_id)
    reply = result.answer
    if result.citations:
        sources = "\n".join(
            f"[{c.n}] {c.title} - {c.publisher}, p.{c.page}" for c in result.citations
        )
        reply = f"{reply}\n\nSources:\n{sources}"
    history = history + [[message, reply]]
    return history, "", session_id


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Indian Market RAG") as demo:
        gr.Markdown("## Indian Market RAG\nAsk about how the Indian stock market works.")
        session_state = gr.State(None)
        chatbot = gr.Chatbot()
        message_box = gr.Textbox(placeholder="Ask a question...", show_label=False)
        message_box.submit(
            _respond,
            inputs=[message_box, chatbot, session_state],
            outputs=[chatbot, message_box, session_state],
        )
    return demo


if __name__ == "__main__":
    build_demo().launch()
