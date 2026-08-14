package agent

import (
	"context"

	"github.com/cloudwego/eino-ext/components/model/openai"
	"github.com/cloudwego/eino/components/model"
)

type LLMConfig struct {
	APIKey  string
	BaseURL string
	Model   string
}

// NewChatModel 装配 OpenAI 兼容接口的 ChatModel；APIKey 为空时返回 nil，
// 由调用方回退到 scriptedModel（离线 demo 与确定性测试不依赖真模型）。
func NewChatModel(ctx context.Context, cfg LLMConfig) (model.ToolCallingChatModel, error) {
	if cfg.APIKey == "" {
		return nil, nil
	}
	return openai.NewChatModel(ctx, &openai.ChatModelConfig{
		APIKey:  cfg.APIKey,
		BaseURL: cfg.BaseURL,
		Model:   cfg.Model,
	})
}

// defaultScriptedModel 是未配置 API key 时的离线兜底：固定一句答复，不调用工具。
func defaultScriptedModel() model.ToolCallingChatModel {
	return NewScriptedModel(Script{Steps: []ScriptStep{
		{Chunks: []string{"（离线 scriptedModel）未配置 LLM API Key，无法执行真实推理。"}},
	}})
}
