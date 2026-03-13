from langgraph.graph import StateGraph, END
from agents.orchestrator.state import AgentState
from agents.orchestrator.nodes import consensus_judge_node, risk_gatekeeper_node

def build_orchestrator_graph():
    workflow = StateGraph(AgentState)

    # Define Nodes
    workflow.add_node("judge", consensus_judge_node)
    workflow.add_node("gatekeeper", risk_gatekeeper_node)

    # Define Flow
    workflow.set_entry_point("judge")
    workflow.add_edge("judge", "gatekeeper")
    workflow.add_edge("gatekeeper", END)

    return workflow.compile()

# Global graph instance
orchestrator_graph = build_orchestrator_graph()
