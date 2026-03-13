package redis

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/redis/go-redis/v9"
	"github.com/user/khaval-trade/internal/models"
	"go.uber.org/zap"
)

type Producer struct {
	client *redis.Client
	logger *zap.Logger
}

func NewProducer(addr string, logger *zap.Logger) *Producer {
	rdb := redis.NewClient(&redis.Options{
		Addr: addr,
	})
	return &Producer{
		client: rdb,
		logger: logger,
	}
}

func (p *Producer) Start(ctx context.Context, dataChan <-chan models.MarketData) {
	// Worker pool could be implemented here if needed, but for now a single goroutine
	// consuming from the channel is enough since Redis is very fast.
	go func() {
		for {
			select {
			case <-ctx.Done():
				return
			case data := <-dataChan:
				if err := p.publish(ctx, data); err != nil {
					p.logger.Error("Failed to publish to Redis Stream", zap.Error(err))
				}
			}
		}
	}()
}

func (p *Producer) publish(ctx context.Context, data models.MarketData) error {
	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("marshal error: %w", err)
	}

	err = p.client.XAdd(ctx, &redis.XAddArgs{
		Stream: "market:data:stream",
		Values: map[string]interface{}{
			"payload": string(jsonData),
		},
	}).Err()

	if err != nil {
		return fmt.Errorf("xadd error: %w", err)
	}

	return nil
}

func (p *Producer) Close() error {
	return p.client.Close()
}
