package config

import (
	"os"
	"strings"

	"github.com/joho/godotenv"
)

type Config struct {
	DerivAPIToken string
	Symbols    []string
	RedisAddr  string
}

func Load() *Config {
	_ = godotenv.Load()

	symbolsStr := os.Getenv("SYMBOLS")
	if symbolsStr == "" {
		symbolsStr = "R_100,R_50,frxEURUSD"
	}

	return &Config{
		DerivAPIToken: os.Getenv("DERIV_API_TOKEN"),
		Symbols:    strings.Split(symbolsStr, ","),
		RedisAddr:  os.Getenv("REDIS_ADDR"),
	}
}
