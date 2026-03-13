package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"github.com/user/khaval-trade/internal/config"
	"github.com/user/khaval-trade/internal/deriv"
	"github.com/user/khaval-trade/internal/models"
	"github.com/user/khaval-trade/internal/redis"
	"go.uber.org/zap"
)

func main() {
	// Initialize logger
	logger, _ := zap.NewProduction()
	defer logger.Sync()

	cfg := config.Load()
	if cfg.DerivToken == "" {
		logger.Fatal("DERIV_TOKEN is required")
	}
	if cfg.RedisAddr == "" {
		cfg.RedisAddr = "localhost:6379"
	}

	logger.Info("Starting Ingestor Service", zap.Strings("symbols", cfg.Symbols))

	// Data channel with buffer to handle bursts
	dataChan := make(chan models.MarketData, 1000)

	// Initialize components
	redisProducer := redis.NewProducer(cfg.RedisAddr, logger)
	derivClient := deriv.NewClient(cfg.DerivToken, cfg.Symbols, dataChan, logger)

	// Start components
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	redisProducer.Start(ctx, dataChan)
	derivClient.Start()

	// Wait for termination signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	logger.Info("Shutting down Ingestor Service...")
	cancel()
	derivClient.Stop()
	redisProducer.Close()
	logger.Info("Shutdown complete")
}
