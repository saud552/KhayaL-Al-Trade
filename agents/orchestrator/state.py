from typing import TypedDict, List, Annotated
import operator

class AgentOutput(TypedDict):
    agent: str
    symbol: str
    signal: str # STRONG BUY, BUY, NEUTRAL, SELL, STRONG SELL
    confidence: float
    reasoning: str
    timestamp: str

class AgentState(TypedDict):
    symbol: str
    current_price: float
    # Collection of outputs from all agents
    agent_outputs: Annotated[List[AgentOutput], operator.add]
    # Final Consensus
    consensus_signal: str # CALL, PUT, WAIT
    final_reasoning: str
    confidence_score: float
    # Risk Assessment
    risk_veto: bool
    risk_reason: str
    # Metadata
    mode: str # real, paper
