package main

import (
	"context"
	"flag"
	"fmt"
	"os"

	"persistent-observers/internal/lumen"
)

func main() {
	if len(os.Args) < 2 {
		fail("usage: lumen <address|record-response|release|wake> [options]")
	}
	runner := lumen.Runner{Workdir: "."}
	var args []string
	var err error
	switch os.Args[1] {
	case "address":
		flags := flag.NewFlagSet("address", flag.ExitOnError)
		database := flags.String("db", "", "Experiment 4 SQLite database")
		experiment := flags.String("experiment-id", "", "experiment ID")
		sender := flags.String("sender", "", "stable sender ID")
		issuer := flags.String(
			"assertion-issuer", "", "identity assertion issuer",
		)
		eventID := flags.String(
			"event-id", "", "external channel event ID",
		)
		verifierVersion := flags.String(
			"verifier-version", "", "authentication verifier version",
		)
		authenticated := flags.Bool(
			"sender-authenticated", false, "sender credential was authenticated",
		)
		channel := flags.String("channel", "chat", "source chat channel")
		message := flags.String("message", "", "chat message")
		lease := flags.Int("lease-seconds", 300, "activation lease duration")
		python := flags.String("python", "python3", "Python interpreter")
		_ = flags.Parse(os.Args[2:])
		runner.Python = *python
		args, err = lumen.AddressArgs(lumen.AddressOptions{
			Database:        *database,
			ExperimentID:    *experiment,
			SenderStableID:  *sender,
			AssertionIssuer: *issuer,
			ExternalEventID: *eventID,
			VerifierVersion: *verifierVersion,
			Authenticated:   *authenticated,
			Channel:         *channel,
			Content:         *message,
			LeaseSeconds:    *lease,
		})
	case "record-response":
		flags := flag.NewFlagSet("record-response", flag.ExitOnError)
		database := flags.String("db", "", "Experiment 4 SQLite database")
		experiment := flags.String("experiment-id", "", "experiment ID")
		input := flags.String("input", "", "model response JSON")
		python := flags.String("python", "python3", "Python interpreter")
		_ = flags.Parse(os.Args[2:])
		runner.Python = *python
		args, err = lumen.RecordResponseArgs(*database, *experiment, *input)
	case "release":
		flags := flag.NewFlagSet("release", flag.ExitOnError)
		database := flags.String("db", "", "Experiment 4 SQLite database")
		experiment := flags.String("experiment-id", "", "experiment ID")
		leaseID := flags.String("lease-id", "", "activation lease ID")
		reason := flags.String(
			"reason", "cancelled", "cancelled or failed",
		)
		python := flags.String("python", "python3", "Python interpreter")
		_ = flags.Parse(os.Args[2:])
		runner.Python = *python
		args, err = lumen.ReleaseArgs(
			*database, *experiment, *leaseID, *reason,
		)
	case "wake":
		flags := flag.NewFlagSet("wake", flag.ExitOnError)
		database := flags.String("db", "", "Experiment 4 SQLite database")
		experiment := flags.String("experiment-id", "", "experiment ID")
		modelCommand := flags.String(
			"model-command", "",
			"command that reads the wake prompt on stdin and prints an outcome",
		)
		python := flags.String("python", "python3", "Python interpreter")
		_ = flags.Parse(os.Args[2:])
		runner.Python = *python
		args, err = lumen.WakeArgs(*database, *experiment, *modelCommand)
	default:
		fail("unsupported command: " + os.Args[1])
	}
	if err != nil {
		fail(err.Error())
	}
	if err := runner.Run(context.Background(), args); err != nil {
		fail(err.Error())
	}
}

func fail(message string) {
	fmt.Fprintln(os.Stderr, "error:", message)
	os.Exit(2)
}
