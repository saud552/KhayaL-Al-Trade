from langgraph.graph import StateGraph, END
from agents.orchestrator.state import AgentState
from agents.orchestrator.nodes import aggregator_node, debate_node, risk_guard_node

def build_orchestrator_graph():
    workflow = StateGraph(AgentState)

    # 1. Define Nodes
    workflow.add_node("aggregator", aggregator_node)
    workflow.add_node("debate", debate_node)
    workflow.add_node("risk_guard", risk_guard_node)

    # 2. Define Sequential Flow
    # Aggregation -> Analysis (Debate) -> Risk Check -> Final Output
    workflow.set_entry_point("aggregator")
    workflow.add_edge("aggregator", "debate")
    workflow.add_edge("debate", "risk_guard")
    workflow.add_edge("risk_guard", END)

    return workflow.compile()

# Global graph instance for the service to invoke
orchestrator_graph = build_orchestrator_graph()
