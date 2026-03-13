import json
from openai import AsyncOpenAI
from agents.orchestrator.state import AgentState
from loguru import logger

# Note: In a real environment, URLs would be in settings
LLM_URL = "http://khaval_ollama:11434/v1"
client = AsyncOpenAI(base_url=LLM_URL, api_key="ollama")

async def consensus_judge_node(state: AgentState):
    """
    The Qualitative LLM Judge Node.
    Analyzes the 'Reasoning' from all agents to make a final judgment.
    """
    signals = state["signals"]
    symbol = state["symbol"]

    prompt = f"""
    Asset: {symbol}
    Expert Reports:
    {json.dumps(signals, indent=2)}

    As the Chief Investment Officer, analyze these conflicting reports.
    Synthesize the information and provide:
    1. Decision (BUY, SELL, NEUTRAL)
    2. Combined Confidence Score (0.0 to 1.0)
    3. Final Consensus Reasoning

    Respond in JSON format only.
    """

    try:
        response = await client.chat.completions.create(
            model="deepseek-r1:7b",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        decision_data = json.loads(response.choices[0].message.content)

        return {
            "consensus_decision": decision_data.get("decision", "NEUTRAL"),
            "confidence_score": decision_data.get("confidence", 0.0),
            "consensus_reasoning": decision_data.get("reasoning", "No clear consensus reached.")
        }
    except Exception as e:
        logger.error(f"Judge Node Error: {e}")
        return {
            "consensus_decision": "NEUTRAL",
            "confidence_score": 0.0,
            "consensus_reasoning": "Error in consensus logic."
        }

async def risk_gatekeeper_node(state: AgentState):
    """
    The Final Gatekeeper Node.
    Checks hard constraints outside the debate.
    """
    # Mocking hard risk checks (Real implementation would query DB for daily limits)
    daily_loss = 50.0 # Mock value
    max_daily_limit = 100.0

    veto = False
    reason = "Risk checks passed."

    if daily_loss >= max_daily_limit:
        veto = True
        reason = "Daily loss limit reached. Trading halted."

    # Logic for aborting if consensus is weak
    if state["confidence_score"] < 0.6:
        veto = True
        reason = f"Low consensus confidence: {state['confidence_score']}"

    return {
        "risk_veto": veto,
        "risk_reason": reason,
        "final_action": "ABORT" if veto else "EXECUTE"
    }
