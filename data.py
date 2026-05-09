"""Pure-Python data layer shared between the Tkinter (`app.py`) and PySide6
(`app_qt.py`) front-ends.

Contains:
- ConversationRecord / MessageRecord dataclasses
- ChatGPT export JSON parsers (mapping & simple formats)
- Conversation loading from a folder/file
- Conversation -> prompt formatting (for DeepSeek)
- Config helpers (read/write JSON config in user app data dir)
- DEEPSEEK_TEMPLATES preset prompts

No GUI imports here.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


APP_TITLE = "Memory Extract"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _config_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "memory_extract"
    return Path.home() / ".memory_extract"


def _config_path() -> Path:
    return _config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(data: dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Activity log — JSONL history of user actions, used by the 日志 dialog.
# ---------------------------------------------------------------------------

def _history_path() -> Path:
    return _config_dir() / "history.jsonl"


def log_event(action: str, detail: str = "", **extra: Any) -> None:
    """Append a structured event line to the user activity log.

    `action` is a short stable key (e.g. "folder_load", "ds_followup");
    `detail` is the human-readable summary; `extra` keys are stashed
    under an "extra" object for later inspection.
    """
    entry: dict[str, Any] = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "detail": detail,
    }
    if extra:
        entry["extra"] = extra
    path = _history_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_history(limit: int = 1000) -> list[dict[str, Any]]:
    """Return the most recent up-to-`limit` entries (oldest -> newest).
    Pass limit <= 0 to load everything."""
    path = _history_path()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []
    if limit and limit > 0:
        lines = lines[-limit:]
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# DeepSeek prompt presets
# ---------------------------------------------------------------------------

DEEPSEEK_TEMPLATES: dict[str, str] = {
    "总结要点": "请用中文简洁地总结这次对话的核心内容、关键观点与结论，分条列出。",
    "提取代码": "请提取本次对话中出现的所有代码片段，按语言/功能分组，并用一句话说明每段的用途。",
    "未完成事项": "请找出本次对话中提到但尚未解决、未完成的事项、TODO 或悬而未决的问题，分条列出。",
    "翻译为英文": "请把本次对话的核心内容翻译成自然、准确的英文摘要。",
    "跨对话对比": (
        "我提供了多段对话。请：\n"
        "1. 先用一句话概括每段对话的核心议题；\n"
        "2. 找出它们共同涉及的主题或概念；\n"
        "3. 重点指出在这些主题上不同对话之间的立场反转、结论差异、新增信息或时间线变化；\n"
        "4. 在最后给出一个综合性的、跨对话的提炼结论。"
    ),
    "自定义": "",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MessageRecord:
    id: str
    role: str
    author_name: str
    text: str
    create_time: float | None
    recipient: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationRecord:
    id: str
    title: str
    source_path: Path
    create_time: float | None
    update_time: float | None
    messages: list[MessageRecord]
    raw: dict[str, Any]

    @property
    def search_blob(self) -> str:
        parts = [self.title]
        for message in self.messages:
            parts.append(message.role)
            parts.append(message.author_name)
            parts.append(message.text)
        return "\n".join(parts).lower()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_timestamp(timestamp: float | None) -> str:
    if timestamp is None:
        return "-"
    try:
        value = float(timestamp)
        if value > 10_000_000_000:
            value = value / 1000.0
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(timestamp)


def _display_role(role: str) -> str:
    """Uppercase the standard binary roles ("user" → "USER" so it reads
    like a chat export header) but keep any other role string as-is —
    real human names from Telegram exports etc. shouldn't be SHOUTED."""
    if role.lower() in ("user", "assistant", "system", "tool", "function"):
        return role.upper()
    return role


def _format_single_conversation(record: ConversationRecord, index: int | None = None) -> str:
    if index is None:
        header = f"# 对话标题: {record.title}"
        ref_prefix = ""  # single-conversation analysis
    else:
        header = f"# 对话 {index}：{record.title}"
        ref_prefix = f"对话{index}-"
    lines: list[str] = [header, ""]
    # Number each message so the analysis model can cite specific lines
    # via tags like [#3] or [对话2-#7].
    for i, msg in enumerate(record.messages, start=1):
        ref = f"#{i}" if not ref_prefix else f"{ref_prefix}#{i}"
        head = f"## [{ref}] {_display_role(msg.role)}"
        if msg.author_name and msg.author_name != msg.role:
            head += f" ({msg.author_name})"
        lines.append(head)
        lines.append(msg.text)
        lines.append("")
    return "\n".join(lines)


def conversation_to_prompt(record: ConversationRecord, max_chars: int = 80_000) -> tuple[str, bool]:
    full = _format_single_conversation(record)
    if len(full) <= max_chars:
        return full, False
    head = full[: max_chars // 2]
    tail = full[-max_chars // 2 :]
    return head + "\n\n... [中间内容已省略以适应长度限制] ...\n\n" + tail, True


def conversations_to_prompt(records: list[ConversationRecord], max_chars: int = 80_000) -> tuple[str, bool]:
    if len(records) == 1:
        return conversation_to_prompt(records[0], max_chars=max_chars)
    sections = [_format_single_conversation(rec, index=i) for i, rec in enumerate(records, start=1)]
    separator = "\n\n=========================================\n\n"
    full = separator.join(sections)
    if len(full) <= max_chars:
        return full, False
    per_budget = max(2000, max_chars // len(records))
    truncated_sections: list[str] = []
    for section in sections:
        if len(section) <= per_budget:
            truncated_sections.append(section)
        else:
            head_len = per_budget // 2
            tail_len = per_budget - head_len
            truncated_sections.append(
                section[:head_len] + "\n\n... [此段中间内容已省略] ...\n\n" + section[-tail_len:]
            )
    return separator.join(truncated_sections), True


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [normalize_text(item) for item in value]
        return "\n".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        content_type = value.get("content_type")
        if "parts" in value:
            return normalize_text(value.get("parts"))
        if "text" in value:
            return normalize_text(value.get("text"))
        if content_type == "code" and "text" in value:
            return normalize_text(value.get("text"))
        if content_type == "multimodal_text":
            return normalize_text(value.get("parts"))
        if "result" in value:
            return normalize_text(value.get("result"))
        if "name" in value:
            return str(value.get("name")).strip()
        return json.dumps(value, ensure_ascii=False, indent=2).strip()
    return str(value).strip()


def extract_message_text(message: dict[str, Any]) -> str:
    text_candidates = [
        message.get("content"),
        message.get("text"),
        message.get("result"),
    ]
    for candidate in text_candidates:
        text = normalize_text(candidate)
        if text:
            return text

    metadata = message.get("metadata")
    if isinstance(metadata, dict):
        for key in ("aggregate_result", "model_slug", "command"):
            text = normalize_text(metadata.get(key))
            if text:
                return text
    return ""


def extract_role(message: dict[str, Any]) -> tuple[str, str]:
    author = message.get("author")
    if isinstance(author, dict):
        role = str(author.get("role") or "unknown")
        name = str(author.get("name") or role)
        return role, name
    role = str(message.get("role") or "unknown")
    return role, role


def parse_mapping_conversation(item: dict[str, Any], source_path: Path) -> ConversationRecord:
    mapping = item.get("mapping") or {}
    nodes: dict[str, dict[str, Any]] = {}
    for node_id, node in mapping.items():
        if isinstance(node, dict):
            nodes[str(node_id)] = node

    child_ids: set[str] = set()
    for node in nodes.values():
        for child in node.get("children") or []:
            child_ids.add(str(child))

    current_node = item.get("current_node")
    ordered_ids: list[str] = []

    if current_node and str(current_node) in nodes:
        chain: list[str] = []
        seen_chain: set[str] = set()
        cursor = str(current_node)
        while cursor and cursor not in seen_chain and cursor in nodes:
            seen_chain.add(cursor)
            chain.append(cursor)
            parent = nodes[cursor].get("parent")
            cursor = str(parent) if parent is not None else ""
        ordered_ids = list(reversed(chain))
    else:
        root_ids = [node_id for node_id in nodes if node_id not in child_ids]
        if not root_ids and nodes:
            root_ids = list(nodes.keys())

        visited: set[str] = set()

        def walk(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            ordered_ids.append(node_id)
            node = nodes.get(node_id) or {}
            for child in node.get("children") or []:
                child_str = str(child)
                if child_str in nodes:
                    walk(child_str)

        for root_id in root_ids:
            walk(root_id)

    messages: list[MessageRecord] = []
    for node_id in ordered_ids:
        node = nodes.get(node_id) or {}
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        role, author_name = extract_role(message)
        text = extract_message_text(message)
        if not text and role in {"system", "unknown"}:
            continue
        messages.append(
            MessageRecord(
                id=str(message.get("id") or node_id),
                role=role,
                author_name=author_name,
                text=text or "[empty message]",
                create_time=message.get("create_time"),
                recipient=message.get("recipient"),
                status=message.get("status"),
                metadata=message.get("metadata") if isinstance(message.get("metadata"), dict) else {},
            )
        )

    return ConversationRecord(
        id=str(item.get("conversation_id") or item.get("id") or source_path.stem),
        title=str(item.get("title") or "Untitled conversation"),
        source_path=source_path,
        create_time=item.get("create_time"),
        update_time=item.get("update_time"),
        messages=messages,
        raw=item,
    )


def _iso_to_unix(value: Any) -> float | None:
    """Best-effort timestamp normaliser. Accepts:
       - int/float → returned as float
       - ISO-8601 strings (Anthropic exports use these)
       - Numeric strings (Telegram exports use these in `date_unixtime`)
    Returns None for unparseable inputs."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # Numeric-string fast path — covers Telegram's date_unixtime.
        try:
            return float(s)
        except ValueError:
            pass
        # ISO 8601 (3.11+ also handles trailing 'Z'; replace defensively).
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None
    return None


def _flatten_anthropic_content(content: Any) -> str:
    """Anthropic messages can have a `content` field that is either a plain
    string or a list of typed blocks (text / tool_use / tool_result /
    image / thinking …). Render them as readable text."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        btype = block.get("type", "")
        if btype == "text":
            t = block.get("text") or ""
            if t:
                parts.append(t)
        elif btype == "thinking":
            t = block.get("thinking") or block.get("text") or ""
            if t:
                parts.append(f"[thinking]\n{t}")
        elif btype == "tool_use":
            name = block.get("name", "tool")
            args = block.get("input")
            args_str = json.dumps(args, ensure_ascii=False) if args else ""
            parts.append(f"[tool_use: {name}] {args_str}".strip())
        elif btype == "tool_result":
            inner = block.get("content")
            inner_text = _flatten_anthropic_content(inner) if inner is not None else ""
            parts.append(f"[tool_result]\n{inner_text}".rstrip())
        elif btype == "image":
            src = block.get("source", {})
            if isinstance(src, dict):
                media = src.get("media_type", "image")
                parts.append(f"[image: {media}]")
            else:
                parts.append("[image]")
        else:
            # Fall back to a JSON dump for unknown block types so nothing
            # silently disappears.
            parts.append(json.dumps(block, ensure_ascii=False))
    return "\n\n".join(p for p in parts if p).strip()


def parse_anthropic_conversation(item: dict[str, Any], source_path: Path) -> ConversationRecord | None:
    """Parse a Claude.ai conversation export.

    Recognised shape::

        { "uuid": ..., "name": "Conversation title",
          "created_at": "2024-...", "updated_at": "2024-...",
          "chat_messages": [
              { "uuid": ..., "sender": "human"|"assistant",
                "text": "...",  # legacy
                "content": [ {"type": "text", "text": "..."}, ... ],
                "created_at": "2024-..." },
              ...
          ] }
    """
    chat_messages = item.get("chat_messages")
    if not isinstance(chat_messages, list):
        return None

    messages: list[MessageRecord] = []
    for index, msg in enumerate(chat_messages):
        if not isinstance(msg, dict):
            continue
        sender = msg.get("sender") or msg.get("role") or "unknown"
        # Normalise to the same vocabulary the rest of the app uses.
        if sender == "human":
            role = "user"
        elif sender in ("assistant", "claude"):
            role = "assistant"
        else:
            role = str(sender)
        author_name = role

        text = _flatten_anthropic_content(msg.get("content"))
        if not text:
            text = normalize_text(msg.get("text"))

        messages.append(
            MessageRecord(
                id=str(msg.get("uuid") or msg.get("id") or f"{source_path.stem}-{index}"),
                role=role,
                author_name=author_name,
                text=text or "[empty message]",
                create_time=_iso_to_unix(msg.get("created_at") or msg.get("timestamp")),
                recipient=None,
                status=None,
                metadata={},
            )
        )

    if not messages:
        return None

    return ConversationRecord(
        id=str(item.get("uuid") or item.get("conversation_id") or item.get("id") or source_path.stem),
        title=str(item.get("name") or item.get("title") or "Untitled conversation"),
        source_path=source_path,
        create_time=_iso_to_unix(item.get("created_at")),
        update_time=_iso_to_unix(item.get("updated_at") or item.get("created_at")),
        messages=messages,
        raw=item,
    )


def _flatten_telegram_text(value: Any) -> str:
    """Telegram exports can give `text` as either a plain string or a list
    that mixes raw strings with entity dicts (`{"type": "bold", "text": ...}`,
    links, mentions, code spans, etc.). Flatten both shapes to plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("text") or ""
                if t:
                    parts.append(str(t))
        return "".join(parts).strip()
    return str(value).strip()


_TELEGRAM_CHAT_TYPES = {
    "personal_chat", "private_supergroup", "private_group",
    "bot_chat", "saved_messages", "private_channel",
    "public_supergroup", "public_channel",
}


def _looks_like_telegram(item: dict[str, Any]) -> bool:
    """Heuristic detection: Telegram exports also have a `messages` list,
    so we need stronger signals to avoid stealing generic message-list
    files from `parse_simple_conversation`."""
    if str(item.get("type", "")) in _TELEGRAM_CHAT_TYPES:
        return True
    msgs = item.get("messages") or []
    if not isinstance(msgs, list):
        return False
    for m in msgs[:8]:
        if not isinstance(m, dict):
            continue
        if "from_id" in m or "date_unixtime" in m or m.get("type") == "service":
            return True
    return False


def parse_telegram_conversation(item: dict[str, Any], source_path: Path) -> ConversationRecord | None:
    """Parse Telegram Desktop's "Export chat history → JSON" format.

    Sample shape::

        { "name": "Chat Title", "type": "personal_chat", "id": 12345,
          "messages": [
            { "id": ..., "type": "message", "date": "2026-04-05T20:41:33",
              "date_unixtime": "1775389293", "from": "Alice",
              "from_id": "user1234567",
              "text": "..."  // string or list of entities
              "text_entities": [...]
            },
            // service messages too: type=="service", action="phone_call" etc.
          ] }

    Telegram has no user/assistant role concept — it's people talking to
    people. Rather than synthesise a fake binary (which makes analysis
    confusing for group chats and 1-on-1 chats alike), we use the actual
    sender's display name as the role. So the rendered timeline reads
    `[1] Alice` / `[2] Bob` and the analysis model can naturally reason
    about each named voice instead of "USER vs ASSISTANT".
    """
    if not _looks_like_telegram(item):
        return None

    raw_messages = item.get("messages") or []
    if not isinstance(raw_messages, list):
        return None

    messages: list[MessageRecord] = []
    times: list[float] = []

    for index, msg in enumerate(raw_messages):
        if not isinstance(msg, dict):
            continue
        msg_type = msg.get("type", "message")
        ts = _iso_to_unix(msg.get("date_unixtime") or msg.get("date"))

        if msg_type == "service":
            # Calls, joins, pinned, etc. — render compactly so timeline
            # context is preserved without drowning the actual text.
            actor = msg.get("actor") or msg.get("from") or "system"
            action = msg.get("action") or "service"
            text = f"[{action}] {actor}".strip()
            messages.append(
                MessageRecord(
                    id=str(msg.get("id") or f"{source_path.stem}-svc-{index}"),
                    role="system",
                    author_name=str(actor),
                    text=text,
                    create_time=ts,
                    metadata={"telegram_service": True},
                )
            )
            if ts is not None:
                times.append(ts)
            continue

        sender_name = str(msg.get("from") or msg.get("from_id") or "unknown")
        role = sender_name  # name-as-role: keeps each speaker distinct

        text = _flatten_telegram_text(msg.get("text"))
        if not text:
            # Media-only messages — preserve a hint so the timeline isn't
            # full of blanks.
            for key in ("photo", "file", "sticker_emoji", "media_type",
                        "voice_message", "video_message", "animation"):
                marker = msg.get(key)
                if marker:
                    text = f"[{key}: {marker}]" if isinstance(marker, str) else f"[{key}]"
                    break
        if not text:
            continue

        messages.append(
            MessageRecord(
                id=str(msg.get("id") or f"{source_path.stem}-{index}"),
                role=role,
                author_name=sender_name,
                text=text,
                create_time=ts,
                metadata={},
            )
        )
        if ts is not None:
            times.append(ts)

    if not messages:
        return None

    create_time = min(times) if times else None
    update_time = max(times) if times else None

    return ConversationRecord(
        id=str(item.get("id") or source_path.stem),
        title=str(item.get("name") or "Telegram chat"),
        source_path=source_path,
        create_time=create_time,
        update_time=update_time,
        messages=messages,
        raw=item,
    )


def parse_simple_conversation(item: dict[str, Any], source_path: Path) -> ConversationRecord | None:
    message_list = item.get("messages")
    if not isinstance(message_list, list):
        return None

    messages: list[MessageRecord] = []
    for index, message in enumerate(message_list):
        if not isinstance(message, dict):
            continue
        role, author_name = extract_role(message)
        text = extract_message_text(message) or normalize_text(message)
        messages.append(
            MessageRecord(
                id=str(message.get("id") or f"{source_path.stem}-{index}"),
                role=role,
                author_name=author_name,
                text=text or "[empty message]",
                create_time=message.get("create_time") or message.get("timestamp"),
                recipient=message.get("recipient"),
                status=message.get("status"),
                metadata=message.get("metadata") if isinstance(message.get("metadata"), dict) else {},
            )
        )

    return ConversationRecord(
        id=str(item.get("conversation_id") or item.get("id") or source_path.stem),
        title=str(item.get("title") or "Untitled conversation"),
        source_path=source_path,
        create_time=item.get("create_time"),
        update_time=item.get("update_time") or item.get("timestamp"),
        messages=messages,
        raw=item,
    )


def parse_conversation(item: Any, source_path: Path) -> ConversationRecord | None:
    if not isinstance(item, dict):
        return None
    # Format-detection cascade in order of specificity:
    # ChatGPT mapping → Claude.ai → Telegram → generic simple list.
    if isinstance(item.get("mapping"), dict):
        return parse_mapping_conversation(item, source_path)
    if isinstance(item.get("chat_messages"), list):
        return parse_anthropic_conversation(item, source_path)
    tg = parse_telegram_conversation(item, source_path)
    if tg is not None:
        return tg
    return parse_simple_conversation(item, source_path)


def extract_conversation_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("conversations"), list):
            return [item for item in payload["conversations"] if isinstance(item, dict)]
        if isinstance(payload.get("items"), list):
            return [item for item in payload["items"] if isinstance(item, dict)]
        # Single conversation in any of the supported shapes (Telegram
        # also uses the "messages" key, so it's covered too).
        if "mapping" in payload or "messages" in payload or "chat_messages" in payload:
            return [payload]
    return []


def load_conversations_from_path(path: Path) -> list[ConversationRecord]:
    records: list[ConversationRecord] = []
    files: list[Path]
    if path.is_dir():
        files = sorted(
            candidate
            for candidate in path.rglob("*.json")
            if candidate.is_file()
        )
    else:
        files = [path]

    for file_path in files:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            payload = json.loads(file_path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue

        for item in extract_conversation_items(payload):
            record = parse_conversation(item, file_path)
            if record:
                records.append(record)

    deduped: dict[str, ConversationRecord] = {}
    for record in records:
        key = record.id
        current = deduped.get(key)
        if current is None or len(record.messages) > len(current.messages):
            deduped[key] = record

    return sorted(
        deduped.values(),
        key=lambda record: (record.update_time or record.create_time or 0, record.title.lower()),
        reverse=True,
    )
