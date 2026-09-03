# ADR 0005: agent-chat Terminal UI and Cancel-Safe Turns

- Status: Accepted
- Date: 2026-09-03
- Scope: all persistent agents

## Context

With the model host and registry in place (ADR 0004), talking to an agent
still meant typing a Python command per turn, and an interrupted command left
the agent's exclusive lease open until it expired: a killed process cannot
release anything. Thomas asked for a terminal UI that lets him chat with any
registered agent by name and see whether it is awake.

## Decision

1. `experiment4/chat.py` owns a turn. The host runs as a child process this
   process can kill; from lease acquisition until a reply is persisted, every
   exit path releases the lease as failed, including cancellation and
   interrupt. When the registry records the agent's chosen name as
   `display_name`, a line that omits it is prefixed so it counts as a direct
   address; what was actually sent is shown.
2. `experiment4/presence.py` reads, in SQLite read-only mode, what a roster
   needs: awake (live lease), resting (a boundary), available; next alarm; last
   wake outcome; last reply; open commitments; and the recent transcript across
   channels.
3. `experiment4/tui.py` is `agent-chat`, built with Textual: roster with
   presence marks, transcript, one input line; turns run in a worker thread
   with a thinking indicator; Ctrl+P cycles host profiles; F5 refreshes; Escape
   cancels the turn in flight; quitting cancels and waits for the release.
4. `deploy/install-agent-chat.sh` creates the repo-local environment from the
   lockfile, installs the package, and links `agent-chat` into `~/.local/bin`,
   so one command opens the roster.

## Alternatives considered

### A Go TUI over the existing adapter

Rejected for now. The protocol, host, registry, and presence logic are
Python; a Go screen would shell out per turn and duplicate the presence
queries. Revisit if the Go adapter grows.

### Standard-library curses

Rejected. A scrolling transcript, an input line, and a worker-thread status
line are exactly what Textual provides well; hand-rolling them in curses would
cost more maintenance than the one dependency it saves.

## Consequences

An agent is reachable from one screen by name, with its state visible, and an
interrupted turn can no longer strand its lease. Textual (MIT, actively
maintained) is a pinned optional dependency in `requirements-tui.lock`; the
protocol, executor, and local host still need only the standard library. The
screen test runs only where Textual is installed and is skipped elsewhere.
The registry-supplied sender assertion is asserted by the tool itself: anyone
with a shell as this user speaks as the registered sender. That is the trust
boundary of a local single-user tool and is recorded here plainly.

Review findings folded in: host diagnostics are shown in the transcript, never
written to the raw terminal under the screen; the status line shows today's
spend from the agent's ledger; the roster reads presence for every agent, not
only the selected one; the name prefix uses the same word-boundary rule the
harness uses to decide a direct address; SIGHUP and SIGTERM cancel the turn in
flight and wait up to five seconds for the release. Two residuals are
accepted: a process killed outright still strands the lease until it expires,
at most fifteen minutes, and every line typed in the screen is a direct
address, so an incidental mention that should not wake the agent must come
through another channel. Registry entries may set `display_name` (the chosen
name) and `repo_root` (an existing, trusted checkout used as the host's
working directory); prefer absolute script paths in host commands regardless.
