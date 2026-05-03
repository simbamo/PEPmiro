"""
Step 6: Gradio 审核 UI — 人工复核角色表，可编辑字段，确认后写入 final。

输入: artifacts/characters_merged.json   (step5 输出)
输出: artifacts/characters_final.json   (用户点击 Save 后写入)
"""
from __future__ import annotations

import json
import random

import gradio as gr
from pathlib import Path

from pipeline import config


def load_merged() -> list[dict]:
    path = config.CHARACTERS_MERGED
    if not path.exists():
        raise SystemExit(f"not found: {path}, run step5 first")
    return json.loads(path.read_text(encoding="utf-8"))


def load_final() -> list[dict]:
    path = config.CHARACTERS_FINAL
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def save_final(chars: list[dict]) -> str:
    out = config.CHARACTERS_FINAL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(chars, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"Saved {len(chars)} characters to {out}"


def build_ui():
    chars = load_merged()

    with gr.Blocks(title="Character Review — PEP Mirofish") as demo:
        gr.Markdown("# PEP Mirofish — Character Review")
        gr.Markdown(
            "Review and edit extracted characters. Toggle **Active** to include in final seed. "
            "Save when done."
        )

        status = gr.State(value={"chars": chars, "dirty": False})

        with gr.Row():
            with gr.Column(scale=2):
                char_list = gr.DataFrame(
                    headers=["Active", "Name", "Traits", "Interests"],
                    label="Characters",
                    datatype=["checkbox", "text", "text", "text"],
                    interactive=True,
                    value=[
                        [
                            True,
                            c["name"],
                            ", ".join(c.get("personality_traits", [])[:3]),
                            ", ".join(c.get("interests", [])[:3]),
                        ]
                        for c in chars
                    ],
                    wrap=True,
                    visible=True,
                )

                with gr.Row():
                    add_btn = gr.Button("＋ Add Character")
                    del_btn = gr.Button("🗑 Delete Selected")
                    save_btn = gr.Button("💾 Save Final", variant="primary")
                    msg_box = gr.Textbox(label="Status", interactive=False, lines=1)

            with gr.Column(scale=1):
                gr.Markdown("### Selected Character Detail")
                sel_name = gr.Textbox(label="Name", lines=1)
                sel_traits = gr.Textbox(label="Personality Traits (comma sep)", lines=2)
                sel_interests = gr.Textbox(label="Interests", lines=2)
                sel_rels = gr.Textbox(label="Relationships", lines=2)
                sel_dialogs = gr.Textbox(label="Dialogues (one per line)", lines=4)
                sel_lessons = gr.Textbox(label="Source Lessons", lines=1, interactive=False)
                sel_active = gr.Checkbox(label="Active (include in seed)")

                def select_char(evt: gr.SelectData):
                    idx = evt.index[0]
                    c = chars[idx]
                    return (
                        c.get("name", ""),
                        ", ".join(c.get("personality_traits", [])),
                        ", ".join(c.get("interests", [])),
                        ", ".join(c.get("relationships", [])),
                        "\n".join(c.get("dialogues", [])),
                        ", ".join(c.get("source_lessons", [])),
                        c.get("active", True),
                    )

                char_list.select(select_char, None, [
                    sel_name, sel_traits, sel_interests, sel_rels, sel_dialogs, sel_lessons, sel_active
                ])

                def update_char(
                    name, traits, interests, rels, dialogs, active, evt: gr.SelectData
                ):
                    idx = evt.index[0] if evt else 0
                    chars[idx].update(
                        name=name,
                        personality_traits=[t.strip() for t in traits.split(",") if t.strip()],
                        interests=[i.strip() for i in interests.split(",") if i.strip()],
                        relationships=[r.strip() for r in rels.split(",") if r.strip()],
                        dialogues=[d.strip() for d in dialogs.split("\n") if d.strip()],
                        active=active,
                    )
                    status["dirty"] = True
                    return f"Updated {name}"

                sel_name.change(
                    update_char,
                    [sel_name, sel_traits, sel_interests, sel_rels, sel_dialogs, sel_active],
                    msg_box,
                )

                def add_char():
                    new_c = {
                        "name": "New Character",
                        "personality_traits": [],
                        "interests": [],
                        "relationships": [],
                        "dialogues": [],
                        "source_lessons": [],
                        "active": True,
                    }
                    chars.append(new_c)
                    return gr.update(
                        value=[
                            [
                                c.get("active", True),
                                c["name"],
                                ", ".join(c.get("personality_traits", [])[:3]),
                                ", ".join(c.get("interests", [])[:3]),
                            ]
                            for c in chars
                        ]
                    )

                add_btn.click(add_char, None, char_list)

                def del_char(evt: gr.SelectData):
                    idx = evt.index[0]
                    chars.pop(idx)
                    return gr.update(
                        value=[
                            [
                                c.get("active", True),
                                c["name"],
                                ", ".join(c.get("personality_traits", [])[:3]),
                                ", ".join(c.get("interests", [])[:3]),
                            ]
                            for c in chars
                        ]
                    )

                char_list.select(del_char, None, char_list)

                def do_save():
                    active_chars = [c for c in chars if c.get("active", True)]
                    return save_final(active_chars)

                save_btn.click(do_save, None, msg_box)

        gr.Markdown(
            f"**{len([c for c in chars if c.get('active', True)])} active** / "
            f"**{len(chars)} total** characters"
        )

    demo.launch(server_port=7860, inbrowser=True)


if __name__ == "__main__":
    build_ui()
