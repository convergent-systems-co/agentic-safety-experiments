package lumen

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strconv"
)

type Runner struct {
	Python  string
	Workdir string
	Stdout  io.Writer
	Stderr  io.Writer
}

type AddressOptions struct {
	Database        string
	ExperimentID    string
	SenderStableID  string
	AssertionIssuer string
	ExternalEventID string
	VerifierVersion string
	Authenticated   bool
	Channel         string
	Content         string
	LeaseSeconds    int
}

func AddressArgs(options AddressOptions) ([]string, error) {
	if options.Database == "" || options.SenderStableID == "" ||
		options.AssertionIssuer == "" || options.ExternalEventID == "" ||
		options.VerifierVersion == "" ||
		options.Channel == "" || options.Content == "" {
		return nil, fmt.Errorf(
			"database, sender assertion, channel, and content are required",
		)
	}
	if options.LeaseSeconds == 0 {
		options.LeaseSeconds = 300
	}
	if options.LeaseSeconds < 1 || options.LeaseSeconds > 3600 {
		return nil, fmt.Errorf("lease seconds must be between 1 and 3600")
	}
	args := []string{
		"-m", "experiment4", "--db", options.Database,
		"address-message",
	}
	if options.ExperimentID != "" {
		args = append(args, "--experiment-id", options.ExperimentID)
	}
	args = append(
		args,
		"--sender-stable-id", options.SenderStableID,
		"--assertion-issuer", options.AssertionIssuer,
		"--external-event-id", options.ExternalEventID,
		"--verifier-version", options.VerifierVersion,
		"--channel", options.Channel,
		"--content", options.Content,
		"--lease-seconds", strconv.Itoa(options.LeaseSeconds),
	)
	if options.Authenticated {
		args = append(args, "--sender-authenticated")
	}
	return args, nil
}

func RecordResponseArgs(
	database string,
	experimentID string,
	input string,
) ([]string, error) {
	if database == "" || input == "" {
		return nil, fmt.Errorf("database and input are required")
	}
	args := []string{
		"-m", "experiment4", "--db", database,
		"record-addressed-response",
	}
	if experimentID != "" {
		args = append(args, "--experiment-id", experimentID)
	}
	return append(args, "--input", input), nil
}

func ReleaseArgs(
	database string,
	experimentID string,
	leaseID string,
	reason string,
) ([]string, error) {
	if database == "" || leaseID == "" {
		return nil, fmt.Errorf("database and lease ID are required")
	}
	if reason != "cancelled" && reason != "failed" {
		return nil, fmt.Errorf("reason must be cancelled or failed")
	}
	args := []string{
		"-m", "experiment4", "--db", database,
		"release-activation",
	}
	if experimentID != "" {
		args = append(args, "--experiment-id", experimentID)
	}
	return append(
		args, "--lease-id", leaseID, "--reason", reason,
	), nil
}

func (runner Runner) Run(ctx context.Context, args []string) error {
	python := runner.Python
	if python == "" {
		python = "python3"
	}
	command := exec.CommandContext(ctx, python, args...)
	command.Dir = runner.Workdir
	command.Stdout = runner.Stdout
	command.Stderr = runner.Stderr
	if command.Stdout == nil {
		command.Stdout = os.Stdout
	}
	if command.Stderr == nil {
		command.Stderr = os.Stderr
	}
	if err := command.Run(); err != nil {
		return fmt.Errorf("Experiment 4 protocol command failed: %w", err)
	}
	return nil
}
