package models

import "time"

// MarketData represents a normalized tick or candle from any source.
type MarketData struct {
	Symbol    string    `json:"symbol"`
	Price     float64   `json:"price"`
	High      float64   `json:"high,omitempty"`
	Low       float64   `json:"low,omitempty"`
	Open      float64   `json:"open,omitempty"`
	Close     float64   `json:"close,omitempty"`
	Volume    float64   `json:"volume,omitempty"`
	Type      string    `json:"type"` // "tick" or "candle"
	Timestamp time.Time `json:"timestamp"`
	Source    string    `json:"source"` // "deriv" or "ccxt"
}
