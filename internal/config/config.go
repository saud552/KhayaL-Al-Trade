package config

import (
	"os"
	"strings"

	"github.com/joho/godotenv"
)

type Config struct {
	DerivToken string
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
		DerivToken: os.Getenv("DERIV_TOKEN"),
		Symbols:    strings.Split(symbolsStr, ","),
		RedisAddr:  os.Getenv("REDIS_ADDR"),
	}
}
