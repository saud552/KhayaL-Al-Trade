import json
from openai import AsyncOpenAI
from agents.orchestrator.state import AgentState
from agents.orchestrator.prompts import JUDGE_PROMPT_TEMPLATE
from loguru import logger

# Note: In production, these would be loaded from a config service
LLM_URL = "http://khaval_ollama:11434/v1"
client = AsyncOpenAI(base_url=LLM_URL, api_key="ollama")

async def aggregator_node(state: AgentState):
    """
    Aggregation is handled by the service layer, this node
    primarily ensures the state is valid for analysis.
    """
    logger.info(f"Aggregating reports for {state['symbol']} at {state['current_price']}")
    return state

async def debate_node(state: AgentState):
    """
    The Judge Node: Uses LLM to weigh agent reports.
    """
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        symbol=state["symbol"],
        current_price=state["current_price"],
        agent_outputs=json.dumps(state["agent_outputs"], indent=2)
    )

    try:
        response = await client.chat.completions.create(
            model="deepseek-r1:7b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)

        return {
            "consensus_signal": data.get("decision", "WAIT"),
            "confidence_score": data.get("confidence", 0.0),
            "final_reasoning": data.get("reasoning", "No consensus reached.")
        }
    except Exception as e:
        logger.error(f"Debate Node LLM Error: {e}")
        return {
            "consensus_signal": "WAIT",
            "confidence_score": 0.0,
            "final_reasoning": "System error in debate node."
        }

async def risk_guard_node(state: AgentState):
    """
    Final Risk Veto Logic.
    """
    signal = state["consensus_signal"]
    confidence = state["confidence_score"]

    veto = False
    reason = "Risk checks passed."

    # 1. Hard confidence threshold
    if signal != "WAIT" and confidence < 0.75:
        veto = True
        reason = f"Confidence {confidence} below threshold 0.75."
        signal = "WAIT"

    # 2. Simulated volatility check (In prod, this would use live volatility indicators)
    # if volatility > threshold: veto = True

    return {
        "risk_veto": veto,
        "risk_reason": reason,
        "consensus_signal": signal # Potential override to WAIT
    }
