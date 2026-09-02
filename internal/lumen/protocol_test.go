package lumen

import (
	"reflect"
	"testing"
)

func TestAddressArgsPreserveProcessContract(t *testing.T) {
	args, err := AddressArgs(AddressOptions{
		Database:        "state.db",
		ExperimentID:    "experiment-4",
		SenderStableID:  "founder",
		AssertionIssuer: "test-chat",
		ExternalEventID: "event-1",
		VerifierVersion: "test-verifier-v1",
		Authenticated:   true,
		Channel:         "chat",
		Content:         "Lumen, are you there?",
		LeaseSeconds:    90,
	})
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		"-m", "experiment4", "--db", "state.db",
		"address-message", "--experiment-id", "experiment-4",
		"--sender-stable-id", "founder",
		"--assertion-issuer", "test-chat",
		"--external-event-id", "event-1",
		"--verifier-version", "test-verifier-v1",
		"--channel", "chat",
		"--content", "Lumen, are you there?",
		"--lease-seconds", "90",
		"--sender-authenticated",
	}
	if !reflect.DeepEqual(args, want) {
		t.Fatalf("args = %#v, want %#v", args, want)
	}
}

func TestAddressArgsRejectInvalidLease(t *testing.T) {
	_, err := AddressArgs(AddressOptions{
		Database:        "state.db",
		SenderStableID:  "founder",
		AssertionIssuer: "test-chat",
		ExternalEventID: "event-2",
		VerifierVersion: "test-verifier-v1",
		Channel:         "chat",
		Content:         "Lumen?",
		LeaseSeconds:    3601,
	})
	if err == nil {
		t.Fatal("expected invalid lease to fail")
	}
}

func TestReleaseArgsRequireAuditableReason(t *testing.T) {
	args, err := ReleaseArgs(
		"state.db", "experiment-4", "activation-lease-1", "failed",
	)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		"-m", "experiment4", "--db", "state.db",
		"release-activation", "--experiment-id", "experiment-4",
		"--lease-id", "activation-lease-1", "--reason", "failed",
	}
	if !reflect.DeepEqual(args, want) {
		t.Fatalf("args = %#v, want %#v", args, want)
	}
	if _, err := ReleaseArgs(
		"state.db", "", "activation-lease-1", "completed",
	); err == nil {
		t.Fatal("expected completed manual release to fail")
	}
}
