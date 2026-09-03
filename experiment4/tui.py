"""agent-chat: talk to any registered agent by name from one terminal screen.

Left, the roster with live presence read from each agent's database. Right,
the conversation. Type a line and press Enter; the agent's name is supplied
if you left it off, the turn runs through the agent's registered host in a
background thread, and the reply appears once it is persisted under the lease.
Ctrl+P cycles the host profile, F5 refreshes presence, Escape cancels a turn in
flight (the lease is released), Ctrl+Q quits.
"""
from __future__ import annotations

import argparse
import threading
from datetime import datetime, timezone
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from . import chat, presence, registry

STATE_MARK = {"awake": "●", "available": "○", "resting": "◌", "missing": "✕"}
PRESENCE_REFRESH_SECONDS = 30


def short_time(stamp: str | None) -> str:
    if not stamp:
        return "never"
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return stamp
    return moment.astimezone().strftime("%b %d %H:%M")


def presence_lines(agent: dict[str, Any], info: dict[str, Any]) -> str:
    name = agent.get("display_name") or agent["name"]
    lines = [f"{name}: {info['state']}"]
    if info["state"] == "missing":
        return "\n".join(lines + [info.get("detail", "")])
    if info.get("boundary") and info["state"] == "resting":
        lines.append(f"boundary: {info['boundary']['action']} ({info['boundary']['topic']})")
    alarm = info.get("next_alarm")
    lines.append(f"next alarm: {short_time(alarm['trigger_value']) if alarm else 'none'}")
    wake = info.get("last_wake")
    lines.append(f"last wake: {wake['status'] + ' ' + short_time(wake['created_at']) if wake else 'never'}")
    lines.append(f"last reply: {short_time(info.get('last_reply_at'))}")
    lines.append(f"open commitments: {info.get('open_commitments', 0)}")
    return "\n".join(lines)


class AgentChatApp(App[None]):
    CSS = """
    #roster { width: 28; border: solid $secondary; }
    #presence { width: 28; height: auto; padding: 1; border: solid $secondary; }
    #transcript { border: solid $primary; }
    #status { height: 1; padding: 0 1; color: $text-muted; }
    Input { border: solid $accent; }
    """
    BINDINGS = [
        Binding("ctrl+p", "toggle_profile", "Profile", priority=True),
        Binding("f5", "refresh", "Refresh", priority=True),
        Binding("escape", "cancel_turn", "Cancel turn", priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def __init__(self, agent_names: list[str] | None = None, start_with: str | None = None) -> None:
        super().__init__()
        self.agent_names = agent_names if agent_names is not None else registry.list_agents()
        self.start_with = start_with
        self.agent: dict[str, Any] | None = None
        self.profile: str | None = None
        self.cancel_event: threading.Event | None = None
        self.busy = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical():
                yield OptionList(id="roster")
                yield Static("", id="presence")
            with Vertical():
                yield RichLog(id="transcript", wrap=True, markup=False, highlight=False)
                yield Static("", id="status")
                yield Input(placeholder="Type to the selected agent and press Enter", id="line")
        yield Footer()

    def on_mount(self) -> None:
        roster = self.query_one("#roster", OptionList)
        if not self.agent_names:
            self.set_status("No agents registered. Use: python3 -m experiment4 register-agent --input agent.json")
            return
        for name in self.agent_names:
            roster.add_option(Option(f"○ {name}", id=name))
        index = self.agent_names.index(self.start_with) if self.start_with in self.agent_names else 0
        roster.highlighted = index
        self.select_agent(self.agent_names[index])
        self.set_interval(PRESENCE_REFRESH_SECONDS, self.action_refresh)
        self.query_one("#line", Input).focus()

    def set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def select_agent(self, name: str) -> None:
        try:
            self.agent = registry.load_agent(name)
        except registry.RegistryError as error:
            self.agent = None
            self.set_status(str(error))
            return
        self.profile = None
        transcript = self.query_one("#transcript", RichLog)
        transcript.clear()
        for turn in presence.recent_transcript(self.agent):
            transcript.write(f"[{short_time(turn['at'])}] {turn['sender']}: {turn['content']}")
            if turn["answer"]:
                label = self.agent.get("display_name") or self.agent["name"]
                transcript.write(f"[{short_time(turn['answered_at'])}] {label} ({turn['model']}): {turn['answer']}")
            else:
                transcript.write("    (no reply recorded)")
            transcript.write("")
        self.action_refresh()
        self.set_status("host: default  ·  Ctrl+P to change  ·  Esc cancels a turn")

    def action_refresh(self) -> None:
        if self.agent is None:
            return
        info = presence.agent_presence(self.agent)
        self.query_one("#presence", Static).update(presence_lines(self.agent, info))
        roster = self.query_one("#roster", OptionList)
        for index, name in enumerate(self.agent_names):
            mark = STATE_MARK.get(info["state"], "○") if name == self.agent["name"] else "○"
            roster.replace_option_prompt_at_index(index, f"{mark} {name}")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.select_agent(str(event.option.id))
            self.query_one("#line", Input).focus()

    def action_toggle_profile(self) -> None:
        if self.agent is None:
            return
        profiles = [None] + list(self.agent["host"].get("profiles", {}))
        self.profile = profiles[(profiles.index(self.profile) + 1) % len(profiles)]
        self.set_status(f"host: {self.profile or 'default'}  ·  Ctrl+P to change  ·  Esc cancels a turn")

    def action_cancel_turn(self) -> None:
        if self.busy and self.cancel_event is not None:
            self.cancel_event.set()
            self.set_status("cancelling; releasing the lease")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        content = event.value.strip()
        event.input.value = ""
        if not content or self.agent is None:
            return
        if self.busy:
            self.set_status("a turn is in flight; Esc to cancel it")
            return
        self.busy = True
        self.cancel_event = threading.Event()
        self.send_turn(self.agent, content, self.profile, self.cancel_event)

    @work(thread=True, exclusive=True)
    def send_turn(self, agent: dict[str, Any], content: str, profile: str | None, cancel: threading.Event) -> None:
        transcript = self.query_one("#transcript", RichLog)
        started = datetime.now(timezone.utc)
        try:
            sent = chat.address_text(agent, content)
            self.call_from_thread(transcript.write, f"[{short_time(started.isoformat())}] you: {sent}")
            result = chat.run_turn(
                agent, content, profile,
                status=lambda text: self.call_from_thread(self.set_status, f"{text} ({profile or 'default'} host)…"),
                cancel=cancel,
            )
            if result["addressed"]:
                label = agent.get("display_name") or agent["name"]
                self.call_from_thread(
                    transcript.write,
                    f"[{short_time(datetime.now(timezone.utc).isoformat())}] {label} ({result['model_config']['model']}): {result['answer']}",
                )
                self.call_from_thread(self.set_status, f"persisted {result['addressed_response_id']}  ·  action: {result['conversation_action']}")
            else:
                self.call_from_thread(transcript.write, "    (recorded; not a direct address)")
        except chat.ChatCancelled:
            self.call_from_thread(transcript.write, "    (cancelled; lease released)")
            self.call_from_thread(self.set_status, "cancelled")
        except Exception as error:  # surfaced to the person; the lease was released in run_turn
            self.call_from_thread(transcript.write, f"    (turn failed: {type(error).__name__}: {str(error)[:200]})")
            self.call_from_thread(self.set_status, "turn failed; lease released")
        finally:
            self.call_from_thread(transcript.write, "")
            self.busy = False
            self.call_from_thread(self.action_refresh)

    async def action_quit(self) -> None:
        if self.busy and self.cancel_event is not None:
            self.cancel_event.set()
            await self.workers.wait_for_complete()
        self.exit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-chat", description=__doc__.split("\n\n")[0])
    parser.add_argument("--agent", help="agent to select first")
    args = parser.parse_args(argv)
    AgentChatApp(start_with=args.agent).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
