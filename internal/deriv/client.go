package deriv

import (
	"encoding/json"
	"fmt"
	"net/url"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/user/khaval-trade/internal/models"
	"go.uber.org/zap"
)

type Client struct {
	token      string
	symbols    []string
	conn       *websocket.Conn
	mu         sync.Mutex
	dataChan   chan models.MarketData
	logger     *zap.Logger
	stopChan   chan struct{}
	reconnect  chan struct{}
}

func NewClient(token string, symbols []string, dataChan chan models.MarketData, logger *zap.Logger) *Client {
	return &Client{
		token:     token,
		symbols:   symbols,
		dataChan:  dataChan,
		logger:    logger,
		stopChan:  make(chan struct{}),
		reconnect: make(chan struct{}, 1),
	}
}

func (c *Client) Start() {
	go c.connectLoop()
}

func (c *Client) connectLoop() {
	backoff := 1 * time.Second
	maxBackoff := 60 * time.Second

	for {
		select {
		case <-c.stopChan:
			return
		default:
			err := c.connectAndListen()
			if err != nil {
				c.logger.Error("WebSocket connection error", zap.Error(err))
				time.Sleep(backoff)
				backoff *= 2
				if backoff > maxBackoff {
					backoff = maxBackoff
				}
				continue
			}
			backoff = 1 * time.Second // Reset backoff on successful connection
		}
	}
}

func (c *Client) connectAndListen() error {
	u := url.URL{Scheme: "wss", Host: "ws.binaryws.com", Path: "/websockets/v3", RawQuery: "app_id=1"} // Using app_id 1 for demo
	c.logger.Info("Connecting to Deriv WebSocket", zap.String("url", u.String()))

	conn, _, err := websocket.DefaultDialer.Dial(u.String(), nil)
	if err != nil {
		return err
	}
	defer conn.Close()

	c.mu.Lock()
	c.conn = conn
	c.mu.Unlock()

	if err := c.authenticate(); err != nil {
		return fmt.Errorf("auth failed: %w", err)
	}

	if err := c.subscribe(); err != nil {
		return fmt.Errorf("subscription failed: %w", err)
	}

	c.logger.Info("Successfully connected and subscribed to Deriv")

	for {
		_, message, err := conn.ReadMessage()
		if err != nil {
			return err
		}
		c.handleMessage(message)
	}
}

func (c *Client) authenticate() error {
	authRequest := map[string]interface{}{
		"authorize": c.token,
	}
	return c.sendJSON(authRequest)
}

func (c *Client) subscribe() error {
	for _, symbol := range c.symbols {
		subRequest := map[string]interface{}{
			"ticks": symbol,
		}
		if err := c.sendJSON(subRequest); err != nil {
			return err
		}
	}
	return nil
}

func (c *Client) sendJSON(v interface{}) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.conn == nil {
		return fmt.Errorf("connection is nil")
	}
	return c.conn.WriteJSON(v)
}

type derivTickResponse struct {
	Tick struct {
		Symbol string  `json:"symbol"`
		Quote  float64 `json:"quote"`
		Epoch  int64   `json:"epoch"`
	} `json:"tick"`
	Error struct {
		Message string `json:"message"`
	} `json:"error"`
}

func (c *Client) handleMessage(msg []byte) {
	var resp derivTickResponse
	if err := json.Unmarshal(msg, &resp); err != nil {
		c.logger.Debug("Raw message ignored or non-tick message", zap.ByteString("msg", msg))
		return
	}

	if resp.Error.Message != "" {
		c.logger.Warn("Deriv API error", zap.String("msg", resp.Error.Message))
		return
	}

	if resp.Tick.Symbol != "" {
		marketData := models.MarketData{
			Symbol:    resp.Tick.Symbol,
			Price:     resp.Tick.Quote,
			Type:      "tick",
			Timestamp: time.Unix(resp.Tick.Epoch, 0),
			Source:    "deriv",
		}
		c.dataChan <- marketData
	}
}

func (c *Client) Stop() {
	close(c.stopChan)
	c.mu.Lock()
	if c.conn != nil {
		c.conn.Close()
	}
	c.mu.Unlock()
}
