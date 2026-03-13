from typing import TypedDict, List, Annotated
import operator

class AgentSignal(TypedDict):
    agent: str
    symbol: str
    signal: str # BUY, SELL, NEUTRAL, etc.
    confidence: float
    reasoning: str
    timestamp: str

class AgentState(TypedDict):
    symbol: str
    # Signals are collected during the aggregation window
    signals: Annotated[List[AgentSignal], operator.add]
    # The outcome of the LLM Judge
    consensus_decision: str
    consensus_reasoning: str
    confidence_score: float
    # Risk Gatekeeper status
    risk_veto: bool
    risk_reason: str
    # Final instruction
    final_action: str # EXECUTE, ABORT, WAIT_FOR_APPROVAL
    mode: str # real, paper
