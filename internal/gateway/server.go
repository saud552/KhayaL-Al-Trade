package gateway

import (
	"context"
	"encoding/json"
	"net/http"
	"sync"

	"github.com/gorilla/websocket"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type Gateway struct {
	redisClient *redis.Client
	logger      *zap.Logger
	clients     map[*websocket.Conn]bool
	mu          sync.Mutex
}

func NewGateway(redisAddr string, logger *zap.Logger) *Gateway {
	rdb := redis.NewClient(&redis.Options{
		Addr: redisAddr,
	})
	return &Gateway{
		redisClient: rdb,
		logger:      logger,
		clients:     make(map[*websocket.Conn]bool),
	}
}

func (g *Gateway) HandleConnections(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		g.logger.Error("Failed to upgrade to WebSocket", zap.Error(err))
		return
	}
	defer conn.Close()

	g.mu.Lock()
	g.clients[conn] = true
	g.mu.Unlock()

	g.logger.Info("New client connected")

	defer func() {
		g.mu.Lock()
		delete(g.clients, conn)
		g.mu.Unlock()
		g.logger.Info("Client disconnected")
	}()

	// Keep connection alive
	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			break
		}
	}
}

func (g *Gateway) StartStreaming(ctx context.Context) {
	streams := []string{"market:data:stream", "agent:signals:stream", "execution:signal:stream"}

	for _, stream := range streams {
		go g.consumeStream(ctx, stream)
	}
}

func (g *Gateway) consumeStream(ctx context.Context, stream string) {
	lastID := "$"
	for {
		select {
		case <-ctx.Done():
			return
		default:
			entries, err := g.redisClient.XRead(ctx, &redis.XReadArgs{
				Streams: []string{stream, lastID},
				Count:   10,
				Block:   0,
			}).Result()

			if err != nil {
				g.logger.Error("Redis XRead error", zap.String("stream", stream), zap.Error(err))
				continue
			}

			for _, entry := range entries {
				for _, msg := range entry.Messages {
					lastID = msg.ID
					g.broadcast(stream, msg.Values)
				}
			}
		}
	}
}

func (g *Gateway) broadcast(stream string, data map[string]interface{}) {
	payload, _ := json.Marshal(map[string]interface{}{
		"stream": stream,
		"data":   data,
	})

	g.mu.Lock()
	defer g.mu.Unlock()

	for client := range g.clients {
		if err := client.WriteMessage(websocket.TextMessage, payload); err != nil {
			g.logger.Warn("Failed to send message to client", zap.Error(err))
			client.Close()
			delete(g.clients, client)
		}
	}
}
