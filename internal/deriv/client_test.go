package deriv

import (
	"testing"
)

func TestHandleMessage(t *testing.T) {
	// Basic test to ensure it doesn't panic on empty or invalid messages
	c := &Client{}
	c.handleMessage([]byte("{}"))
}
